"""Per-portal property schema poller.

Walks the four CRM core object types we care about
(``contacts`` / ``companies`` / ``deals`` / ``tickets``), persists the
last-known schema state of every property, and emits change events
when archives flip, types change, labels rename, or properties go
away. The alert correlation engine consumes these events alongside
``WorkflowChangeEvent`` to surface workflow-impacting schema changes.

Network shape mirrors ``app.services.workflow_polling``: same
``urllib`` boundary, same auth helper, same mockable
``_http_get_json`` seam. HTTP error semantics also match —
401 → portal skipped, 429 / 5xx → portal aborted, per-object-type
errors do not abort the rest of the portal cycle.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.property_change_event import (
    PROPERTY_EVENT_ARCHIVED,
    PROPERTY_EVENT_CREATED,
    PROPERTY_EVENT_DELETED,
    PROPERTY_EVENT_RENAMED,
    PROPERTY_EVENT_TYPE_CHANGED,
    PROPERTY_EVENT_UNARCHIVED,
    PropertyChangeEvent,
)
from app.models.property_snapshot import PropertySnapshot
from app.services.hubspot_oauth import get_portal_access_token

logger = logging.getLogger(__name__)


# CRM Properties API base. The Properties API ignores `archived=true`
# on some legacy paths; we always pass it explicitly because we need
# archived rows in the response to detect archive flips.
HUBSPOT_PROPERTIES_URL = "https://api.hubapi.com/crm/v3/properties/{object_type}"

# The four core object types OpsLens v2 monitors. Each entry is
# (path_segment, object_type_id). The path segment is what HubSpot's
# v3 properties endpoint accepts; the id is what dependency rows use
# to refer to the same thing.
DEFAULT_OBJECT_TYPES: tuple[tuple[str, str], ...] = (
    ("contacts", "0-1"),
    ("companies", "0-2"),
    ("deals", "0-3"),
    ("tickets", "0-5"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_hubspot_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _http_get_json(url: str, access_token: str) -> dict[str, Any]:
    """GET a JSON resource with the portal access token. Raises on
    HTTP-level errors so callers can branch on status code."""
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body) if body.strip() else {}


def fetch_object_type_properties(
    session: Session,
    portal_id: str,
    object_type: str,
) -> list[dict[str, Any]]:
    """Fetch every property (including archived) for one CRM object
    type from HubSpot. Returns the parsed `results` list.

    ``object_type`` is the path segment HubSpot expects
    (``contacts``, ``companies``, ``deals``, ``tickets``, or a custom
    object id like ``2-12345``).
    """
    portal_key = str(portal_id or "").strip()
    object_type_path = str(object_type or "").strip()
    if not portal_key:
        raise ValueError("portal_id is required.")
    if not object_type_path:
        raise ValueError("object_type is required.")

    access_token = get_portal_access_token(session, portal_key)
    url = HUBSPOT_PROPERTIES_URL.format(
        object_type=urllib.parse.quote(object_type_path, safe=""),
    )
    # `archived=true` includes archived rows alongside live ones, which
    # is the only way to detect an archive flip via this endpoint.
    url = f"{url}?{urllib.parse.urlencode({'archived': 'true'})}"

    payload = _http_get_json(url, access_token)
    results = payload.get("results") or []
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, dict)]


def _record_event(
    session: Session,
    *,
    portal_id: str,
    object_type_id: str,
    property_name: str,
    event_type: str,
    previous_archived: bool | None = None,
    new_archived: bool | None = None,
    previous_type: str | None = None,
    new_type: str | None = None,
    previous_label: str | None = None,
    new_label: str | None = None,
) -> PropertyChangeEvent:
    event = PropertyChangeEvent(
        portal_id=portal_id,
        object_type_id=object_type_id,
        property_name=property_name,
        event_type=event_type,
        previous_archived=previous_archived,
        new_archived=new_archived,
        previous_type=previous_type,
        new_type=new_type,
        previous_label=previous_label,
        new_label=new_label,
    )
    session.add(event)
    return event


def _normalise(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _classify_object_type_error(http_err: urllib.error.HTTPError) -> tuple[str, str]:
    """Return (status, reason) for a HubSpot HTTP error during a
    single object-type fetch. Mirrors the workflow-polling rule set:
    401 → skipped, 429 → rate_limited, 5xx → server_error, other → http_error.
    """
    status = int(getattr(http_err, "code", 0) or 0)
    if status == 401:
        return "skipped", "hubspot_unauthorized"
    if status == 429:
        return "error", "hubspot_rate_limited"
    if 500 <= status < 600:
        return "error", f"hubspot_server_error_{status}"
    return "error", f"hubspot_http_error_{status}"


def poll_portal_properties(
    session: Session,
    portal_id: str,
    *,
    object_types: tuple[tuple[str, str], ...] | None = None,
) -> dict[str, Any]:
    """Poll one portal's CRM property schema across every object type
    we monitor, persist snapshots, emit change events.

    Returns a summary suitable for logging or admin response::

        {
            "portalId": "12345",
            "status": "ok" | "skipped" | "error",
            "polled": 42,                  # total properties seen
            "createdEvents": 0,
            "archivedEvents": 0,
            "unarchivedEvents": 0,
            "typeChangedEvents": 0,
            "renamedEvents": 0,
            "deletedEvents": 0,
            "errors": [{"objectType": "...", "reason": "..."}],
            "perObjectType": [{"objectType": "...", "objectTypeId": "...", "polled": N}],
        }

    Per-object-type errors are recorded in ``errors`` and the cycle
    continues to the next object type. A 429 response on any object
    type aborts the whole portal poll because rate-limiting one
    endpoint usually means the next one will fail too — we record the
    error and let the scheduler retry on the next cycle.
    """
    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise ValueError("portal_id is required.")

    types_to_poll: tuple[tuple[str, str], ...] = (
        object_types if object_types is not None else DEFAULT_OBJECT_TYPES
    )

    summary: dict[str, Any] = {
        "portalId": portal_key,
        "status": "ok",
        "polled": 0,
        "createdEvents": 0,
        "archivedEvents": 0,
        "unarchivedEvents": 0,
        "typeChangedEvents": 0,
        "renamedEvents": 0,
        "deletedEvents": 0,
        "errors": [],
        "perObjectType": [],
    }

    try:
        access_token = get_portal_access_token(session, portal_key)
    except Exception as exc:  # noqa: BLE001 — propagate as skipped
        summary["status"] = "skipped"
        summary["reason"] = f"no_access_token: {exc}"
        return summary

    now = _utc_now()
    seen_keys: set[tuple[str, str]] = set()
    aborted = False

    for object_type_path, object_type_id in types_to_poll:
        url = HUBSPOT_PROPERTIES_URL.format(
            object_type=urllib.parse.quote(object_type_path, safe=""),
        )
        url = f"{url}?{urllib.parse.urlencode({'archived': 'true'})}"

        try:
            payload = _http_get_json(url, access_token)
        except urllib.error.HTTPError as http_err:
            status, reason = _classify_object_type_error(http_err)
            summary["errors"].append(
                {
                    "objectType": object_type_path,
                    "objectTypeId": object_type_id,
                    "status": status,
                    "reason": reason,
                }
            )
            # 429 means this portal is being rate-limited; subsequent
            # object types are likely to fail too. Abort the portal
            # cycle and let the scheduler retry next interval.
            if reason == "hubspot_rate_limited":
                summary["status"] = "error"
                summary["reason"] = "hubspot_rate_limited"
                aborted = True
                break
            # Otherwise (401 on this object type, 5xx, generic HTTP),
            # log it and move to the next object type.
            continue
        except Exception as exc:  # noqa: BLE001 — defensive
            summary["errors"].append(
                {
                    "objectType": object_type_path,
                    "objectTypeId": object_type_id,
                    "status": "error",
                    "reason": f"transport_error: {exc}",
                }
            )
            continue

        results = payload.get("results") or []
        if not isinstance(results, list):
            results = []

        polled_for_type = 0
        for item in results:
            if not isinstance(item, dict):
                continue
            property_name = _normalise(item.get("name"))
            if not property_name:
                continue
            polled_for_type += 1
            seen_keys.add((object_type_id, property_name))

            new_label = _normalise(item.get("label")) or None
            new_type = _normalise(item.get("type")) or None
            new_field_type = _normalise(item.get("fieldType")) or None
            new_description_raw = item.get("description")
            new_description = (
                str(new_description_raw)
                if new_description_raw is not None
                else None
            )
            new_archived = bool(item.get("archived"))
            new_calculated = bool(item.get("calculated"))
            new_display_order = _coerce_int(item.get("displayOrder"))
            new_group_name = _normalise(item.get("groupName")) or None
            hubspot_created_at = _parse_hubspot_timestamp(item.get("createdAt"))
            hubspot_updated_at = _parse_hubspot_timestamp(item.get("updatedAt"))

            snapshot = (
                session.query(PropertySnapshot)
                .filter(
                    PropertySnapshot.portal_id == portal_key,
                    PropertySnapshot.object_type_id == object_type_id,
                    PropertySnapshot.property_name == property_name,
                )
                .one_or_none()
            )

            if snapshot is None:
                snapshot = PropertySnapshot(
                    portal_id=portal_key,
                    object_type_id=object_type_id,
                    property_name=property_name,
                    label=new_label,
                    type=new_type,
                    field_type=new_field_type,
                    description=new_description,
                    archived=new_archived,
                    calculated=new_calculated,
                    display_order=new_display_order,
                    group_name=new_group_name,
                    hubspot_created_at=hubspot_created_at,
                    hubspot_updated_at=hubspot_updated_at,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(snapshot)
                _record_event(
                    session,
                    portal_id=portal_key,
                    object_type_id=object_type_id,
                    property_name=property_name,
                    event_type=PROPERTY_EVENT_CREATED,
                    new_archived=new_archived,
                    new_type=new_type,
                    new_label=new_label,
                )
                summary["createdEvents"] += 1
                continue

            previous_archived = bool(snapshot.archived)
            previous_type = snapshot.type
            previous_label = snapshot.label
            previously_deleted = snapshot.deleted_at is not None

            # A property that had been observed deleted but reappeared
            # is treated as a fresh "created" event.
            if previously_deleted:
                _record_event(
                    session,
                    portal_id=portal_key,
                    object_type_id=object_type_id,
                    property_name=property_name,
                    event_type=PROPERTY_EVENT_CREATED,
                    new_archived=new_archived,
                    new_type=new_type,
                    new_label=new_label,
                )
                summary["createdEvents"] += 1
                snapshot.deleted_at = None

            # Archive flips.
            if previous_archived and not new_archived:
                _record_event(
                    session,
                    portal_id=portal_key,
                    object_type_id=object_type_id,
                    property_name=property_name,
                    event_type=PROPERTY_EVENT_UNARCHIVED,
                    previous_archived=True,
                    new_archived=False,
                )
                summary["unarchivedEvents"] += 1
            elif new_archived and not previous_archived:
                _record_event(
                    session,
                    portal_id=portal_key,
                    object_type_id=object_type_id,
                    property_name=property_name,
                    event_type=PROPERTY_EVENT_ARCHIVED,
                    previous_archived=False,
                    new_archived=True,
                )
                summary["archivedEvents"] += 1

            # Type change.
            if new_type and previous_type and new_type != previous_type:
                _record_event(
                    session,
                    portal_id=portal_key,
                    object_type_id=object_type_id,
                    property_name=property_name,
                    event_type=PROPERTY_EVENT_TYPE_CHANGED,
                    previous_type=previous_type,
                    new_type=new_type,
                )
                summary["typeChangedEvents"] += 1

            # Label rename — same internal name, different label.
            if new_label and previous_label and new_label != previous_label:
                _record_event(
                    session,
                    portal_id=portal_key,
                    object_type_id=object_type_id,
                    property_name=property_name,
                    event_type=PROPERTY_EVENT_RENAMED,
                    previous_label=previous_label,
                    new_label=new_label,
                )
                summary["renamedEvents"] += 1

            snapshot.label = new_label
            snapshot.type = new_type
            snapshot.field_type = new_field_type
            snapshot.description = new_description
            snapshot.archived = new_archived
            snapshot.calculated = new_calculated
            snapshot.display_order = new_display_order
            snapshot.group_name = new_group_name
            snapshot.hubspot_created_at = (
                hubspot_created_at or snapshot.hubspot_created_at
            )
            snapshot.hubspot_updated_at = (
                hubspot_updated_at or snapshot.hubspot_updated_at
            )
            snapshot.last_seen_at = now

        summary["polled"] += polled_for_type
        summary["perObjectType"].append(
            {
                "objectType": object_type_path,
                "objectTypeId": object_type_id,
                "polled": polled_for_type,
            }
        )

    if not aborted:
        # Hard-delete sweep: any non-archived snapshot for this portal
        # that did not reappear in any object type's response gets
        # marked deleted. We exclude archived rows because an
        # archived-then-unhydrated property is still a known dead
        # property — we don't want to double-emit.
        seen_object_types = {object_type_id for object_type_id, _ in seen_keys}
        if seen_object_types:
            existing = (
                session.query(PropertySnapshot)
                .filter(
                    PropertySnapshot.portal_id == portal_key,
                    PropertySnapshot.deleted_at.is_(None),
                    PropertySnapshot.archived.is_(False),
                    PropertySnapshot.object_type_id.in_(list(seen_object_types)),
                )
                .all()
            )
        else:
            existing = []

        for snapshot in existing:
            key = (snapshot.object_type_id, snapshot.property_name)
            if key in seen_keys:
                continue
            _record_event(
                session,
                portal_id=portal_key,
                object_type_id=snapshot.object_type_id,
                property_name=snapshot.property_name,
                event_type=PROPERTY_EVENT_DELETED,
                previous_archived=bool(snapshot.archived),
                previous_type=snapshot.type,
                previous_label=snapshot.label,
            )
            snapshot.deleted_at = now
            summary["deletedEvents"] += 1

    if summary["errors"] and summary["status"] == "ok":
        # We saw partial failure — at least one object type errored
        # but others succeeded. Flag it so the scheduler logs it
        # appropriately.
        summary["status"] = "partial"

    session.commit()
    return summary
