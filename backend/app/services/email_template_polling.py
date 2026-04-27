"""Per-portal HubSpot workflow email-template poller.

Polls automated marketing emails because workflow Send Email actions refer
to marketing email content IDs. Freshly observed templates establish the
baseline and do not emit alertable change events.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_template_change_event import (
    TEMPLATE_EVENT_ARCHIVED,
    TEMPLATE_EVENT_DELETED,
    TEMPLATE_EVENT_EDITED,
    TEMPLATE_EVENT_UNARCHIVED,
    EmailTemplateChangeEvent,
)
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.services.hubspot_oauth import get_portal_access_token

logger = logging.getLogger(__name__)


HUBSPOT_MARKETING_EMAILS_URL = "https://api.hubapi.com/marketing/v3/emails"
AUTOMATED_EMAIL_TYPES = ("AUTOMATED_EMAIL", "AUTOMATED_AB_EMAIL")
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
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{HUBSPOT_MARKETING_EMAILS_URL}?{query}"
    if http_client is None:
        return _http_get_json(url, access_token)
    if hasattr(http_client, "get_json"):
        return http_client.get_json(url, access_token)
    return http_client(url, access_token)


def _email_pages(
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
            "type": list(AUTOMATED_EMAIL_TYPES),
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
            "email_template_polling.list hit MAX_PAGES; truncating",
            extra={"max_pages": MAX_PAGES, "archived": archived},
        )

    return collected


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize_template_id(item: dict[str, Any]) -> str:
    return _clean(item.get("id") or item.get("emailId") or item.get("contentId"))


def _normalize_name(item: dict[str, Any]) -> str:
    return _clean(item.get("name") or item.get("templateName"))


def _normalize_type(item: dict[str, Any]) -> str:
    return _clean(item.get("type") or item.get("emailType"))


def _normalize_subject(item: dict[str, Any]) -> str:
    return _clean(item.get("subject") or item.get("emailSubject"))


def _normalize_archived(item: dict[str, Any], *, fallback: bool = False) -> bool:
    raw = item.get("archived")
    if raw is None:
        raw = item.get("isArchived")
    if raw is None:
        return fallback
    return bool(raw)


def _definition_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item.get("name"),
        "subject": item.get("subject"),
        "type": item.get("type"),
        "content": item.get("content"),
        "templatePath": item.get("templatePath"),
        "from": item.get("from"),
        "replyTo": item.get("replyTo"),
        "subscriptionDetails": item.get("subscriptionDetails"),
        "language": item.get("language"),
        "webversion": item.get("webversion"),
    }


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
    template_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> EmailTemplateChangeEvent:
    event = EmailTemplateChangeEvent(
        portal_id=portal_id,
        template_id=template_id,
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


def _fetch_templates(access_token: str, http_client=None) -> list[dict[str, Any]]:
    active = _email_pages(access_token, archived=False, http_client=http_client)
    archived = _email_pages(access_token, archived=True, http_client=http_client)
    merged: dict[str, dict[str, Any]] = {}
    for item in active:
        template_id = _normalize_template_id(item)
        if template_id:
            merged[template_id] = {**item, "archived": _normalize_archived(item)}
    for item in archived:
        template_id = _normalize_template_id(item)
        if template_id:
            merged[template_id] = {**item, "archived": _normalize_archived(item, fallback=True)}
    return list(merged.values())


def poll_portal_email_templates(
    session: Session,
    portal_id: str,
    http_client=None,
) -> dict[str, Any]:
    """Poll HubSpot automated marketing emails and emit template change events."""

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
        "editedEvents": 0,
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
        templates = _fetch_templates(access_token, http_client)
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

    summary["polled"] = len(templates)
    now = _utc_now()
    seen_template_ids: set[str] = set()

    for item in templates:
        template_id = _normalize_template_id(item)
        if not template_id:
            continue
        seen_template_ids.add(template_id)

        template_name = _normalize_name(item) or None
        template_type = _normalize_type(item) or None
        subject = _normalize_subject(item) or None
        is_archived = _normalize_archived(item)
        definition_json, definition_hash = _definition_json_and_hash(item)

        snapshot = (
            session.query(EmailTemplateSnapshot)
            .filter(
                EmailTemplateSnapshot.portal_id == portal_key,
                EmailTemplateSnapshot.template_id == template_id,
            )
            .one_or_none()
        )

        if snapshot is None:
            snapshot = EmailTemplateSnapshot(
                portal_id=portal_key,
                template_id=template_id,
                template_name=template_name,
                template_type=template_type,
                subject=subject,
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
                template_id=template_id,
                event_type=TEMPLATE_EVENT_UNARCHIVED,
                payload={
                    "template_id": template_id,
                    "template_name": template_name,
                    "previous_archived": True,
                    "new_archived": False,
                },
            )
            summary["unarchivedEvents"] += 1
        elif is_archived and not previous_archived:
            _record_event(
                session,
                portal_id=portal_key,
                template_id=template_id,
                event_type=TEMPLATE_EVENT_ARCHIVED,
                payload={
                    "template_id": template_id,
                    "template_name": template_name,
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
                template_id=template_id,
                event_type=TEMPLATE_EVENT_EDITED,
                payload={
                    "template_id": template_id,
                    "template_name": template_name,
                    "previous_definition_hash": previous_definition_hash,
                    "new_definition_hash": definition_hash,
                },
            )
            summary["editedEvents"] += 1

        snapshot.template_name = template_name
        snapshot.template_type = template_type
        snapshot.subject = subject
        snapshot.is_archived = is_archived
        snapshot.definition_json = definition_json
        snapshot.definition_hash = definition_hash
        snapshot.last_seen_at = now
        snapshot.updated_at = now

    query = session.query(EmailTemplateSnapshot).filter(
        EmailTemplateSnapshot.portal_id == portal_key,
        EmailTemplateSnapshot.deleted_at.is_(None),
    )
    if seen_template_ids:
        query = query.filter(~EmailTemplateSnapshot.template_id.in_(seen_template_ids))
    existing_missing = query.all()

    for missing in existing_missing:
        _record_event(
            session,
            portal_id=portal_key,
            template_id=missing.template_id,
            event_type=TEMPLATE_EVENT_DELETED,
            payload={
                "template_id": missing.template_id,
                "template_name": missing.template_name,
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
        + int(summary["editedEvents"])
        + int(summary["deletedEvents"])
    )
    session.commit()
    return summary
