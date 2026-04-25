from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow_change_event import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_DISABLED,
    EVENT_TYPE_EDITED,
    EVENT_TYPE_ENABLED,
    WorkflowChangeEvent,
)
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.hubspot_oauth import get_portal_access_token

logger = logging.getLogger(__name__)

# Endpoints — Automation v4 (BETA). See
# docs/v2/workflow-failure-detection-research.md and -followup.md.
HUBSPOT_FLOWS_LIST_URL = "https://api.hubapi.com/automation/v4/flows"
HUBSPOT_FLOW_DETAIL_URL = "https://api.hubapi.com/automation/v4/flows/{flow_id}"

# Page size for list endpoint. HubSpot v4 default is 10; we ask for more
# to keep page count down for large portals while staying well under the
# 100-per-page documented ceiling.
DEFAULT_PAGE_LIMIT = 100

# Hard ceiling on pagination loops to defend against malformed paging
# responses that never advance.
MAX_PAGES = 200


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_hubspot_timestamp(value: Any) -> datetime | None:
    """Parse a HubSpot ISO 8601 timestamp into a UTC-aware datetime."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # HubSpot uses trailing "Z"; Python's fromisoformat doesn't accept
    # that prior to 3.11, and we want broad compat.
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
    """GET a JSON resource with the portal access token.

    Raises urllib.error.HTTPError on HTTP-level errors so callers can
    branch on status code (401 / 429 / 5xx).
    """
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


def fetch_workflow_definition(
    session: Session,
    portal_id: str,
    workflow_id: str,
) -> dict[str, Any]:
    """Fetch the full workflow definition for a single workflow.

    Returns the parsed JSON dict. Raises on transport errors. Callers
    are expected to catch and decide whether to swallow.
    """
    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key:
        raise ValueError("portal_id is required.")
    if not workflow_key:
        raise ValueError("workflow_id is required.")

    access_token = get_portal_access_token(session, portal_key)
    url = HUBSPOT_FLOW_DETAIL_URL.format(
        flow_id=urllib.parse.quote(workflow_key, safe=""),
    )
    return _http_get_json(url, access_token)


def _list_flows_pages(
    access_token: str,
    *,
    page_limit: int = DEFAULT_PAGE_LIMIT,
) -> list[dict[str, Any]]:
    """Walk the paginated /automation/v4/flows endpoint.

    Yields parsed `results` rows across all pages.
    """
    collected: list[dict[str, Any]] = []
    after: str | None = None

    for _ in range(MAX_PAGES):
        params: dict[str, str] = {"limit": str(page_limit)}
        if after:
            params["after"] = after
        url = f"{HUBSPOT_FLOWS_LIST_URL}?{urllib.parse.urlencode(params)}"

        payload = _http_get_json(url, access_token)
        results = payload.get("results") or []
        if isinstance(results, list):
            collected.extend(item for item in results if isinstance(item, dict))

        paging = payload.get("paging") or {}
        next_block = (paging or {}).get("next") or {}
        next_after = str(next_block.get("after") or "").strip()
        if not next_after or next_after == after:
            break
        after = next_after
    else:
        logger.warning(
            "workflow_polling.list_flows hit MAX_PAGES; truncating",
            extra={"max_pages": MAX_PAGES},
        )

    return collected


def _normalize_workflow_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("flowId") or "").strip()


def _normalize_revision_id(item: dict[str, Any]) -> str:
    return str(item.get("revisionId") or item.get("revision_id") or "").strip()


def _normalize_object_type_id(item: dict[str, Any]) -> str:
    return str(item.get("objectTypeId") or item.get("object_type_id") or "").strip()


def _normalize_flow_type(item: dict[str, Any]) -> str:
    return str(item.get("flowType") or item.get("flow_type") or "").strip()


def _normalize_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or "").strip()


def _normalize_is_enabled(item: dict[str, Any]) -> bool:
    raw = item.get("isEnabled")
    if raw is None:
        raw = item.get("is_enabled")
    return bool(raw)


def _record_event(
    session: Session,
    *,
    portal_id: str,
    workflow_id: str,
    event_type: str,
    previous_revision_id: str | None = None,
    new_revision_id: str | None = None,
    previous_is_enabled: bool | None = None,
    new_is_enabled: bool | None = None,
) -> WorkflowChangeEvent:
    event = WorkflowChangeEvent(
        portal_id=portal_id,
        workflow_id=workflow_id,
        event_type=event_type,
        previous_revision_id=previous_revision_id,
        new_revision_id=new_revision_id,
        previous_is_enabled=previous_is_enabled,
        new_is_enabled=new_is_enabled,
    )
    session.add(event)
    return event


def _refresh_definition(
    session: Session,
    portal_id: str,
    workflow_id: str,
    snapshot: WorkflowSnapshot,
) -> None:
    """Fetch the full definition for a single workflow and write it onto
    the snapshot row. Errors are swallowed and logged; the rest of the
    polling cycle continues.
    """
    try:
        definition = fetch_workflow_definition(session, portal_id, workflow_id)
    except Exception as exc:  # noqa: BLE001 — we log and continue
        logger.warning(
            "workflow_polling.fetch_definition_failed",
            extra={
                "portal_id": portal_id,
                "workflow_id": workflow_id,
                "error": repr(exc),
            },
        )
        return
    snapshot.definition_json = json.dumps(definition, separators=(",", ":"), sort_keys=True)
    snapshot.definition_fetched_at = _utc_now()


def poll_portal_workflows(session: Session, portal_id: str) -> dict[str, Any]:
    """Poll one portal's workflow list, persist snapshots, emit change events.

    Returns a small dict summary suitable for logging or admin response:
        {
            "portalId": "12345",
            "status": "ok" | "skipped" | "error",
            "reason": "...",
            "polled": 17,
            "createdEvents": 0,
            "deletedEvents": 0,
            "editedEvents": 1,
            "enabledEvents": 0,
            "disabledEvents": 0,
        }

    HTTP error handling:
      * 401 — token rejected; mark `skipped`, do not raise. Caller decides
        whether to disable the install.
      * 429 / 5xx — abort this portal's poll; record `error` with reason.
      * Per-workflow detail-fetch errors are swallowed (logged) so a
        single bad workflow does not stop the whole portal cycle.
    """
    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise ValueError("portal_id is required.")

    summary: dict[str, Any] = {
        "portalId": portal_key,
        "status": "ok",
        "polled": 0,
        "createdEvents": 0,
        "deletedEvents": 0,
        "editedEvents": 0,
        "enabledEvents": 0,
        "disabledEvents": 0,
    }

    try:
        access_token = get_portal_access_token(session, portal_key)
    except Exception as exc:  # noqa: BLE001 — propagate as skipped
        summary["status"] = "skipped"
        summary["reason"] = f"no_access_token: {exc}"
        return summary

    try:
        flows = _list_flows_pages(access_token)
    except urllib.error.HTTPError as http_err:
        status = int(getattr(http_err, "code", 0) or 0)
        if status == 401:
            summary["status"] = "skipped"
            summary["reason"] = "hubspot_unauthorized"
            return summary
        if status == 429:
            summary["status"] = "error"
            summary["reason"] = "hubspot_rate_limited"
            return summary
        if 500 <= status < 600:
            summary["status"] = "error"
            summary["reason"] = f"hubspot_server_error_{status}"
            return summary
        summary["status"] = "error"
        summary["reason"] = f"hubspot_http_error_{status}"
        return summary
    except Exception as exc:  # noqa: BLE001 — defensive
        summary["status"] = "error"
        summary["reason"] = f"transport_error: {exc}"
        return summary

    summary["polled"] = len(flows)
    now = _utc_now()
    seen_workflow_ids: set[str] = set()

    for item in flows:
        workflow_id = _normalize_workflow_id(item)
        if not workflow_id:
            continue
        seen_workflow_ids.add(workflow_id)

        new_revision_id = _normalize_revision_id(item)
        new_is_enabled = _normalize_is_enabled(item)
        new_name = _normalize_name(item)
        new_flow_type = _normalize_flow_type(item)
        new_object_type_id = _normalize_object_type_id(item)
        hubspot_created_at = _parse_hubspot_timestamp(item.get("createdAt"))
        hubspot_updated_at = _parse_hubspot_timestamp(item.get("updatedAt"))

        snapshot = (
            session.query(WorkflowSnapshot)
            .filter(
                WorkflowSnapshot.portal_id == portal_key,
                WorkflowSnapshot.workflow_id == workflow_id,
            )
            .one_or_none()
        )

        if snapshot is None:
            snapshot = WorkflowSnapshot(
                portal_id=portal_key,
                workflow_id=workflow_id,
                name=new_name,
                flow_type=new_flow_type,
                object_type_id=new_object_type_id,
                is_enabled=new_is_enabled,
                revision_id=new_revision_id,
                hubspot_created_at=hubspot_created_at,
                hubspot_updated_at=hubspot_updated_at,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(snapshot)
            _record_event(
                session,
                portal_id=portal_key,
                workflow_id=workflow_id,
                event_type=EVENT_TYPE_CREATED,
                new_revision_id=new_revision_id or None,
                new_is_enabled=new_is_enabled,
            )
            summary["createdEvents"] += 1
            _refresh_definition(session, portal_key, workflow_id, snapshot)
            continue

        previous_revision_id = str(snapshot.revision_id or "")
        previous_is_enabled = bool(snapshot.is_enabled)
        previously_deleted = snapshot.deleted_at is not None

        # If the workflow had been observed deleted but reappeared, treat
        # that as a "created" event again.
        if previously_deleted:
            _record_event(
                session,
                portal_id=portal_key,
                workflow_id=workflow_id,
                event_type=EVENT_TYPE_CREATED,
                new_revision_id=new_revision_id or None,
                new_is_enabled=new_is_enabled,
            )
            summary["createdEvents"] += 1
            snapshot.deleted_at = None

        revision_changed = bool(new_revision_id) and new_revision_id != previous_revision_id
        enabled_changed = new_is_enabled != previous_is_enabled

        if revision_changed:
            _record_event(
                session,
                portal_id=portal_key,
                workflow_id=workflow_id,
                event_type=EVENT_TYPE_EDITED,
                previous_revision_id=previous_revision_id or None,
                new_revision_id=new_revision_id or None,
            )
            summary["editedEvents"] += 1

        if enabled_changed:
            event_type = EVENT_TYPE_ENABLED if new_is_enabled else EVENT_TYPE_DISABLED
            _record_event(
                session,
                portal_id=portal_key,
                workflow_id=workflow_id,
                event_type=event_type,
                previous_is_enabled=previous_is_enabled,
                new_is_enabled=new_is_enabled,
            )
            if new_is_enabled:
                summary["enabledEvents"] += 1
            else:
                summary["disabledEvents"] += 1

        # Refresh the cached definition only when the revision actually
        # changed (or we've never fetched one).
        needs_definition_refresh = revision_changed or not snapshot.definition_json

        snapshot.name = new_name
        snapshot.flow_type = new_flow_type
        snapshot.object_type_id = new_object_type_id
        snapshot.is_enabled = new_is_enabled
        snapshot.revision_id = new_revision_id
        snapshot.hubspot_created_at = hubspot_created_at or snapshot.hubspot_created_at
        snapshot.hubspot_updated_at = hubspot_updated_at or snapshot.hubspot_updated_at
        snapshot.last_seen_at = now

        if needs_definition_refresh:
            _refresh_definition(session, portal_key, workflow_id, snapshot)

    # Anything we used to know about that didn't show up this cycle is
    # treated as deleted. (deleted_at is set, but the row is kept so we
    # can detect re-appearance and so the change-event log keeps a
    # foreign key to a real snapshot row.)
    if seen_workflow_ids:
        existing_iter = (
            session.query(WorkflowSnapshot)
            .filter(
                WorkflowSnapshot.portal_id == portal_key,
                ~WorkflowSnapshot.workflow_id.in_(seen_workflow_ids),
                WorkflowSnapshot.deleted_at.is_(None),
            )
            .all()
        )
    else:
        existing_iter = (
            session.query(WorkflowSnapshot)
            .filter(
                WorkflowSnapshot.portal_id == portal_key,
                WorkflowSnapshot.deleted_at.is_(None),
            )
            .all()
        )

    for missing in existing_iter:
        _record_event(
            session,
            portal_id=portal_key,
            workflow_id=missing.workflow_id,
            event_type=EVENT_TYPE_DELETED,
            previous_revision_id=missing.revision_id or None,
            previous_is_enabled=bool(missing.is_enabled),
        )
        missing.deleted_at = now
        summary["deletedEvents"] += 1

    session.commit()
    return summary
