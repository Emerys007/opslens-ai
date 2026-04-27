"""Per-portal HubSpot owner poller.

Owners API rows represent the users assigned by workflow actions. We fetch
both active and archived owners so a user deactivation is visible in one cycle.
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

from app.models.owner_change_event import (
    OWNER_EVENT_DEACTIVATED,
    OWNER_EVENT_DELETED,
    OWNER_EVENT_REACTIVATED,
    OwnerChangeEvent,
)
from app.models.owner_snapshot import OwnerSnapshot
from app.services.hubspot_oauth import get_portal_access_token

logger = logging.getLogger(__name__)


HUBSPOT_OWNERS_URL = "https://api.hubapi.com/crm/v3/owners/"
DEFAULT_PAGE_LIMIT = 100
MAX_PAGES = 200


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _http_get_json(url: str, access_token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response_body = response.read().decode("utf-8", errors="replace")
        return json.loads(response_body) if response_body.strip() else {}


def _fetch_page(access_token: str, params: dict[str, Any], http_client=None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{HUBSPOT_OWNERS_URL}?{query}"
    if http_client is None:
        return _http_get_json(url, access_token)
    if hasattr(http_client, "get_json"):
        return http_client.get_json(url, access_token)
    return http_client(url, access_token)


def _owner_pages(
    access_token: str,
    *,
    archived: bool,
    http_client=None,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    after: str | None = None

    for _ in range(MAX_PAGES):
        params: dict[str, Any] = {
            "limit": str(DEFAULT_PAGE_LIMIT),
            "archived": "true" if archived else "false",
        }
        if after:
            params["after"] = after

        payload = _fetch_page(access_token, params, http_client)
        results = payload.get("results") or []
        if isinstance(results, list):
            collected.extend(item for item in results if isinstance(item, dict))

        paging = payload.get("paging") or {}
        next_block = paging.get("next") if isinstance(paging, dict) else {}
        next_after = str((next_block or {}).get("after") or "").strip()
        if not next_after or next_after == after:
            break
        after = next_after
    else:
        logger.warning(
            "owner_polling.list hit MAX_PAGES; truncating",
            extra={"max_pages": MAX_PAGES, "archived": archived},
        )

    return collected


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_owner_id(item: dict[str, Any]) -> str:
    return _clean(item.get("id") or item.get("ownerId") or item.get("owner_id"))


def _normalize_email(item: dict[str, Any]) -> str:
    return _clean(item.get("email"))


def _normalize_archived(item: dict[str, Any], *, fallback: bool = False) -> bool:
    raw = item.get("archived")
    if raw is None:
        raw = item.get("isArchived")
    if raw is None:
        return fallback
    return bool(raw)


def _event_payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _record_event(
    session: Session,
    *,
    portal_id: str,
    owner_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> OwnerChangeEvent:
    event = OwnerChangeEvent(
        portal_id=portal_id,
        owner_id=owner_id,
        event_type=event_type,
        payload_json=_event_payload_json(payload),
    )
    session.add(event)
    return event


def _classify_http_error(http_err: urllib.error.HTTPError) -> tuple[str, str]:
    status = int(getattr(http_err, "code", 0) or 0)
    if status == 401:
        return "skipped", "hubspot_unauthorized"
    if status == 429:
        return "error", "hubspot_rate_limited"
    if 500 <= status < 600:
        return "error", f"hubspot_server_error_{status}"
    return "error", f"hubspot_http_error_{status}"


def _fetch_owners(access_token: str, http_client=None) -> list[dict[str, Any]]:
    active = _owner_pages(access_token, archived=False, http_client=http_client)
    archived = _owner_pages(access_token, archived=True, http_client=http_client)
    merged: dict[str, dict[str, Any]] = {}
    for item in active:
        owner_id = _normalize_owner_id(item)
        if owner_id:
            merged[owner_id] = {**item, "archived": _normalize_archived(item)}
    for item in archived:
        owner_id = _normalize_owner_id(item)
        if owner_id:
            merged[owner_id] = {**item, "archived": _normalize_archived(item, fallback=True)}
    return list(merged.values())


def poll_portal_owners(
    session: Session,
    portal_id: str,
    http_client=None,
) -> dict[str, Any]:
    """Poll HubSpot owners for one portal and emit owner lifecycle events."""

    portal_key = _clean(portal_id)
    if not portal_key:
        raise ValueError("portal_id is required.")

    summary: dict[str, Any] = {
        "portalId": portal_key,
        "status": "ok",
        "polled": 0,
        "events_emitted": 0,
        "deactivatedEvents": 0,
        "reactivatedEvents": 0,
        "deletedEvents": 0,
        "errors": [],
    }

    try:
        access_token = get_portal_access_token(session, portal_key)
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "skipped"
        summary["reason"] = f"no_access_token: {exc}"
        return summary

    try:
        owners = _fetch_owners(access_token, http_client)
    except urllib.error.HTTPError as http_err:
        status, reason = _classify_http_error(http_err)
        summary["status"] = status
        summary["reason"] = reason
        summary["errors"].append({"status": status, "reason": reason})
        return summary
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "error"
        summary["reason"] = f"transport_error: {exc}"
        summary["errors"].append({"status": "error", "reason": summary["reason"]})
        return summary

    summary["polled"] = len(owners)
    now = _utc_now()
    seen_owner_ids: set[str] = set()

    for item in owners:
        owner_id = _normalize_owner_id(item)
        if not owner_id:
            continue
        seen_owner_ids.add(owner_id)

        email = _normalize_email(item) or None
        is_active = not _normalize_archived(item)

        snapshot = (
            session.query(OwnerSnapshot)
            .filter(
                OwnerSnapshot.portal_id == portal_key,
                OwnerSnapshot.owner_id == owner_id,
            )
            .one_or_none()
        )

        if snapshot is None:
            session.add(
                OwnerSnapshot(
                    portal_id=portal_key,
                    owner_id=owner_id,
                    email=email,
                    is_active=is_active,
                    last_seen_at=now,
                )
            )
            continue

        previous_active = bool(snapshot.is_active)
        previously_deleted = snapshot.deleted_at is not None
        if previously_deleted:
            snapshot.deleted_at = None

        if previous_active and not is_active:
            _record_event(
                session,
                portal_id=portal_key,
                owner_id=owner_id,
                event_type=OWNER_EVENT_DEACTIVATED,
                payload={
                    "owner_id": owner_id,
                    "email": email,
                    "previous_active": True,
                    "new_active": False,
                },
            )
            summary["deactivatedEvents"] += 1
        elif is_active and not previous_active:
            _record_event(
                session,
                portal_id=portal_key,
                owner_id=owner_id,
                event_type=OWNER_EVENT_REACTIVATED,
                payload={
                    "owner_id": owner_id,
                    "email": email,
                    "previous_active": False,
                    "new_active": True,
                },
            )
            summary["reactivatedEvents"] += 1

        snapshot.email = email
        snapshot.is_active = is_active
        snapshot.last_seen_at = now
        snapshot.updated_at = now

    query = session.query(OwnerSnapshot).filter(
        OwnerSnapshot.portal_id == portal_key,
        OwnerSnapshot.deleted_at.is_(None),
    )
    if seen_owner_ids:
        query = query.filter(~OwnerSnapshot.owner_id.in_(seen_owner_ids))
    existing_missing = query.all()

    for missing in existing_missing:
        _record_event(
            session,
            portal_id=portal_key,
            owner_id=missing.owner_id,
            event_type=OWNER_EVENT_DELETED,
            payload={
                "owner_id": missing.owner_id,
                "email": missing.email,
                "previous_active": bool(missing.is_active),
            },
        )
        missing.deleted_at = now
        missing.updated_at = now
        summary["deletedEvents"] += 1

    summary["events_emitted"] = (
        int(summary["deactivatedEvents"])
        + int(summary["reactivatedEvents"])
        + int(summary["deletedEvents"])
    )
    session.commit()
    return summary
