"""Per-portal HubSpot list poller.

Persists last-known list state and emits change events for archived,
unarchived, deleted, and criteria-changed lists. Freshly observed lists
establish the baseline and do not emit alertable change events.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.orm import Session

from app.models.list_change_event import (
    LIST_EVENT_ARCHIVED,
    LIST_EVENT_CRITERIA_CHANGED,
    LIST_EVENT_DELETED,
    LIST_EVENT_UNARCHIVED,
    ListChangeEvent,
)
from app.models.list_snapshot import ListSnapshot
from app.services.hubspot_oauth import get_portal_access_token

logger = logging.getLogger(__name__)


HUBSPOT_LISTS_SEARCH_URL = "https://api.hubapi.com/crm/v3/lists/search"
DEFAULT_PAGE_LIMIT = 100
MAX_PAGES = 200


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _http_post_json(url: str, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response_body = response.read().decode("utf-8", errors="replace")
        return json.loads(response_body) if response_body.strip() else {}


def _fetch_page(
    access_token: str,
    body: dict[str, Any],
    http_client=None,
) -> dict[str, Any]:
    if http_client is None:
        return _http_post_json(HUBSPOT_LISTS_SEARCH_URL, access_token, body)
    if hasattr(http_client, "post_json"):
        return http_client.post_json(HUBSPOT_LISTS_SEARCH_URL, body, access_token)
    return http_client(HUBSPOT_LISTS_SEARCH_URL, access_token, body)


def _list_pages(access_token: str, http_client=None) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    after: str | None = None

    for _ in range(MAX_PAGES):
        body: dict[str, Any] = {"count": DEFAULT_PAGE_LIMIT}
        if after:
            body["offset"] = after

        payload = _fetch_page(access_token, body, http_client)
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
            "list_polling.search hit MAX_PAGES; truncating",
            extra={"max_pages": MAX_PAGES},
        )

    return collected


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list_id(item: dict[str, Any]) -> str:
    return _clean(item.get("listId") or item.get("id") or item.get("list_id"))


def _normalize_list_name(item: dict[str, Any]) -> str:
    return _clean(item.get("name") or item.get("listName") or item.get("list_name"))


def _normalize_list_type(item: dict[str, Any]) -> str:
    return _clean(item.get("listType") or item.get("list_type"))


def _normalize_processing_type(item: dict[str, Any]) -> str:
    return _clean(item.get("processingType") or item.get("processing_type"))


def _normalize_archived(item: dict[str, Any]) -> bool:
    raw = item.get("archived")
    if raw is None:
        raw = item.get("isArchived")
    return bool(raw)


def _definition_payload(item: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "filterBranch",
        "filterBranches",
        "filters",
        "definition",
        "criteria",
        "listCriteria",
    ):
        value = item.get(key)
        if value is not None:
            return {key: value}
    return {}


def _definition_json_and_hash(item: dict[str, Any]) -> tuple[str, str]:
    definition_json = json.dumps(
        _definition_payload(item),
        separators=(",", ":"),
        sort_keys=True,
    )
    return definition_json, sha256(definition_json.encode("utf-8")).hexdigest()


def _event_payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _record_event(
    session: Session,
    *,
    portal_id: str,
    list_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> ListChangeEvent:
    event = ListChangeEvent(
        portal_id=portal_id,
        list_id=list_id,
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


def poll_portal_lists(session: Session, portal_id: str, http_client=None) -> dict[str, Any]:
    """Poll HubSpot CRM lists for one portal and emit list change events."""

    portal_key = _clean(portal_id)
    if not portal_key:
        raise ValueError("portal_id is required.")

    summary: dict[str, Any] = {
        "portalId": portal_key,
        "status": "ok",
        "polled": 0,
        "events_emitted": 0,
        "archivedEvents": 0,
        "unarchivedEvents": 0,
        "criteriaChangedEvents": 0,
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
        lists = _list_pages(access_token, http_client)
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

    summary["polled"] = len(lists)
    now = _utc_now()
    seen_list_ids: set[str] = set()

    for item in lists:
        list_id = _normalize_list_id(item)
        if not list_id:
            continue
        seen_list_ids.add(list_id)

        list_name = _normalize_list_name(item) or None
        list_type = _normalize_list_type(item) or None
        processing_type = _normalize_processing_type(item) or None
        is_archived = _normalize_archived(item)
        definition_json, definition_hash = _definition_json_and_hash(item)

        snapshot = (
            session.query(ListSnapshot)
            .filter(
                ListSnapshot.portal_id == portal_key,
                ListSnapshot.list_id == list_id,
            )
            .one_or_none()
        )

        if snapshot is None:
            snapshot = ListSnapshot(
                portal_id=portal_key,
                list_id=list_id,
                list_name=list_name,
                list_type=list_type,
                processing_type=processing_type,
                is_archived=is_archived,
                definition_json=definition_json,
                definition_hash=definition_hash,
                last_seen_at=now,
            )
            session.add(snapshot)
            continue

        previous_archived = bool(snapshot.is_archived)
        previous_definition_hash = str(snapshot.definition_hash or "")
        previously_deleted = snapshot.deleted_at is not None
        if previously_deleted:
            snapshot.deleted_at = None

        if previous_archived and not is_archived:
            _record_event(
                session,
                portal_id=portal_key,
                list_id=list_id,
                event_type=LIST_EVENT_UNARCHIVED,
                payload={
                    "list_id": list_id,
                    "list_name": list_name,
                    "previous_archived": True,
                    "new_archived": False,
                },
            )
            summary["unarchivedEvents"] += 1
        elif is_archived and not previous_archived:
            _record_event(
                session,
                portal_id=portal_key,
                list_id=list_id,
                event_type=LIST_EVENT_ARCHIVED,
                payload={
                    "list_id": list_id,
                    "list_name": list_name,
                    "previous_archived": False,
                    "new_archived": True,
                },
            )
            summary["archivedEvents"] += 1

        if (
            previous_definition_hash
            and definition_hash != previous_definition_hash
            and not previously_deleted
        ):
            _record_event(
                session,
                portal_id=portal_key,
                list_id=list_id,
                event_type=LIST_EVENT_CRITERIA_CHANGED,
                payload={
                    "list_id": list_id,
                    "list_name": list_name,
                    "previous_definition_hash": previous_definition_hash,
                    "new_definition_hash": definition_hash,
                },
            )
            summary["criteriaChangedEvents"] += 1

        snapshot.list_name = list_name
        snapshot.list_type = list_type
        snapshot.processing_type = processing_type
        snapshot.is_archived = is_archived
        snapshot.definition_json = definition_json
        snapshot.definition_hash = definition_hash
        snapshot.last_seen_at = now
        snapshot.updated_at = now

    query = session.query(ListSnapshot).filter(
        ListSnapshot.portal_id == portal_key,
        ListSnapshot.deleted_at.is_(None),
    )
    if seen_list_ids:
        query = query.filter(~ListSnapshot.list_id.in_(seen_list_ids))
    existing_missing = query.all()

    for missing in existing_missing:
        _record_event(
            session,
            portal_id=portal_key,
            list_id=missing.list_id,
            event_type=LIST_EVENT_DELETED,
            payload={
                "list_id": missing.list_id,
                "list_name": missing.list_name,
                "previous_archived": bool(missing.is_archived),
                "definition_hash": missing.definition_hash,
            },
        )
        missing.deleted_at = now
        missing.updated_at = now
        summary["deletedEvents"] += 1

    summary["events_emitted"] = (
        int(summary["archivedEvents"])
        + int(summary["unarchivedEvents"])
        + int(summary["criteriaChangedEvents"])
        + int(summary["deletedEvents"])
    )
    session.commit()
    return summary
