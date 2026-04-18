import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_session, init_db
from app.services.hubspot_oauth import get_portal_access_token

BASE_URL = "https://api.hubapi.com"

OPSLENS_PIPELINE_ID = os.getenv("HUBSPOT_OPSLENS_PIPELINE_ID", "890820374").strip()
OPSLENS_STAGE_NEW_ALERT = os.getenv("HUBSPOT_OPSLENS_STAGE_NEW_ALERT", "1341759033").strip()
OPSLENS_STAGE_INVESTIGATING = os.getenv("HUBSPOT_OPSLENS_STAGE_INVESTIGATING", "1341759034").strip()
OPSLENS_STAGE_WAITING = os.getenv("HUBSPOT_OPSLENS_STAGE_WAITING", "1341759035").strip()
OPSLENS_STAGE_RESOLVED = os.getenv("HUBSPOT_OPSLENS_STAGE_RESOLVED", "1341759036").strip()
OPSLENS_STAGE_DUPLICATE = os.getenv("HUBSPOT_OPSLENS_STAGE_DUPLICATE", "1341759037").strip()

OPSLENS_REOPEN_WINDOW_HOURS = int(
    os.getenv("HUBSPOT_OPSLENS_REOPEN_WINDOW_HOURS", "168").strip() or "168"
)

OPEN_STAGE_IDS = {
    OPSLENS_STAGE_NEW_ALERT,
    OPSLENS_STAGE_INVESTIGATING,
    OPSLENS_STAGE_WAITING,
}

CLOSED_STAGE_IDS = {
    OPSLENS_STAGE_RESOLVED,
    OPSLENS_STAGE_DUPLICATE,
}

TICKET_TO_CONTACT_ASSOCIATION_TYPE_ID = 16
TICKET_TO_COMPANY_ASSOCIATION_TYPE_ID = 339

NOTE_TO_CONTACT_ASSOCIATION_TYPE_ID = 202
NOTE_TO_COMPANY_ASSOCIATION_TYPE_ID = 190
NOTE_TO_TICKET_ASSOCIATION_TYPE_ID = 228


def _resolve_token_for_portal(portal_id: str) -> str:
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id:
        raise RuntimeError("portal_id is required to resolve a HubSpot OAuth token.")

    if not init_db():
        raise RuntimeError("Database is not available, so the OAuth installation token could not be resolved.")

    session = get_session()
    if session is None:
        raise RuntimeError("Database session could not be created, so the OAuth installation token could not be resolved.")

    try:
        return get_portal_access_token(session, cleaned_portal_id)
    finally:
        session.close()


def _headers(token: str) -> dict[str, str]:
    auth_token = str(token or "").strip()
    if not auth_token:
        raise RuntimeError("A HubSpot access token is required.")
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


def _request_json(token: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers=_headers(token),
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace").strip()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed


def _now_utc_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_severity(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in {"critical", "high", "medium", "low"}:
        return text
    return "high"


def _normalize_delivery_status(value: str | None) -> str:
    text = str(value or "").strip().upper().replace(" ", "_")
    allowed = {
        "SLACK_SENT",
        "SLACK_SKIPPED_THRESHOLD",
        "SLACK_SKIPPED_NO_WEBHOOK",
        "SLACK_FAILED",
    }
    return text if text in allowed else "SLACK_FAILED"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _parse_repeat_count(value: Any) -> int:
    parsed = _safe_int(value, 1)
    return max(1, parsed)


def _get_next_repeated_alert_stage(current_stage_id: str) -> str:
    current = str(current_stage_id or "").strip()

    if current == OPSLENS_STAGE_NEW_ALERT:
        return OPSLENS_STAGE_INVESTIGATING

    if current == OPSLENS_STAGE_INVESTIGATING:
        return OPSLENS_STAGE_WAITING

    if current == OPSLENS_STAGE_WAITING:
        return OPSLENS_STAGE_WAITING

    return OPSLENS_STAGE_INVESTIGATING


def _stage_label(stage_id: str) -> str:
    mapping = {
        OPSLENS_STAGE_NEW_ALERT: "New Alert",
        OPSLENS_STAGE_INVESTIGATING: "Investigating",
        OPSLENS_STAGE_WAITING: "Waiting / Monitoring",
        OPSLENS_STAGE_RESOLVED: "Resolved",
        OPSLENS_STAGE_DUPLICATE: "Closed as Duplicate",
    }
    return mapping.get(str(stage_id or "").strip(), str(stage_id or "").strip() or "Unknown")


def _subject_for_alert(workflow_id: str, contact_id: str) -> str:
    return f"OpsLens critical alert | Workflow {workflow_id} | Contact {contact_id}"


def _description_for_alert(
    *,
    portal_id: str,
    contact_id: str,
    workflow_id: str,
    callback_id: str,
    analyst_note: str,
    delivery_reason: str,
) -> str:
    lines = [
        "OpsLens created this ticket automatically.",
        f"Portal ID: {portal_id}",
        f"Contact ID: {contact_id}",
        f"Workflow ID: {workflow_id}",
        f"Callback ID: {callback_id}",
        f"Delivery reason: {delivery_reason}",
    ]
    note = str(analyst_note or "").strip()
    if note:
        lines.append(f"Analyst note: {note}")
    return "\n".join(lines)


def _timeline_note_body(
    *,
    event_label: str,
    portal_id: str,
    contact_id: str,
    workflow_id: str,
    callback_id: str,
    ticket_id: str,
    stage_id: str,
    repeat_count: int,
    severity: str,
    delivery_status: str,
    delivery_reason: str,
    analyst_note: str,
) -> str:
    lines = [
        f"OpsLens ticket event: {event_label}",
        f"Ticket ID: {ticket_id}",
        f"Ticket stage: {_stage_label(stage_id)}",
        f"Repeat count: {max(1, repeat_count)}",
        f"Severity: {severity}",
        f"Delivery status: {delivery_status}",
        f"Delivery reason: {delivery_reason}",
        f"Portal ID: {portal_id}",
        f"Contact ID: {contact_id}",
        f"Workflow ID: {workflow_id}",
        f"Callback ID: {callback_id}",
    ]

    note = str(analyst_note or "").strip()
    if note:
        lines.append(f"Analyst note: {note}")

    return "\n".join(lines)


def _create_ticket_timeline_note(
    *,
    token: str,
    ticket_id: str,
    contact_id: str,
    company_id: str,
    portal_id: str,
    workflow_id: str,
    callback_id: str,
    stage_id: str,
    repeat_count: int,
    severity: str,
    delivery_status: str,
    delivery_reason: str,
    analyst_note: str,
    event_label: str,
    timestamp_utc: str,
) -> tuple[bool, str, str]:
    associations: list[dict[str, Any]] = [
        {
            "to": {"id": ticket_id},
            "types": [
                {
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": NOTE_TO_TICKET_ASSOCIATION_TYPE_ID,
                }
            ],
        },
        {
            "to": {"id": contact_id},
            "types": [
                {
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": NOTE_TO_CONTACT_ASSOCIATION_TYPE_ID,
                }
            ],
        },
    ]

    if company_id:
        associations.append(
            {
                "to": {"id": company_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": NOTE_TO_COMPANY_ASSOCIATION_TYPE_ID,
                    }
                ],
            }
        )

    payload = {
        "properties": {
            "hs_timestamp": str(timestamp_utc or "").strip() or _now_utc_iso(),
            "hs_note_body": _timeline_note_body(
                event_label=event_label,
                portal_id=portal_id,
                contact_id=contact_id,
                workflow_id=workflow_id,
                callback_id=callback_id,
                ticket_id=ticket_id,
                stage_id=stage_id,
                repeat_count=repeat_count,
                severity=severity,
                delivery_status=delivery_status,
                delivery_reason=delivery_reason,
                analyst_note=analyst_note,
            ),
        },
        "associations": associations,
    }

    status, body = _request_json(token, "POST", "/crm/v3/objects/notes", payload)
    if status not in (200, 201):
        return False, "", json.dumps(body)

    note_id = str(body.get("id") or "").strip()
    return True, note_id, ""


def _pin_note_on_ticket(token: str, ticket_id: str, note_id: str) -> tuple[bool, str]:
    if not ticket_id or not note_id:
        return False, "Missing ticket ID or note ID."

    status, body = _request_json(
        token,
        "PATCH",
        f"/crm/v3/objects/tickets/{urllib.parse.quote(ticket_id)}",
        {
            "properties": {
                "hs_pinned_engagement_id": str(note_id),
            }
        },
    )
    if status != 200:
        return False, json.dumps(body)

    return True, ""


def _get_contact_company_id(token: str, contact_id: str) -> str:
    path = f"/crm/v3/objects/contacts/{urllib.parse.quote(contact_id)}?associations=companies"
    status, body = _request_json(token, "GET", path)
    if status != 200:
        return ""

    companies = (
        body.get("associations", {})
        .get("companies", {})
        .get("results", [])
    )
    if not companies:
        return ""

    return str(companies[0].get("id") or "").strip()


def _ensure_ticket_contact_association(token: str, ticket_id: str, contact_id: str) -> bool:
    if not ticket_id or not contact_id:
        return False

    path = (
        f"/crm/v3/objects/tickets/{urllib.parse.quote(ticket_id)}"
        f"/associations/contacts/{urllib.parse.quote(contact_id)}"
        f"/{TICKET_TO_CONTACT_ASSOCIATION_TYPE_ID}"
    )
    status, _ = _request_json(token, "PUT", path)
    return status in (200, 201, 204)


def _ensure_ticket_company_association(token: str, ticket_id: str, company_id: str) -> bool:
    if not ticket_id or not company_id:
        return False

    path = (
        f"/crm/v3/objects/tickets/{urllib.parse.quote(ticket_id)}"
        f"/associations/companies/{urllib.parse.quote(company_id)}"
        f"/{TICKET_TO_COMPANY_ASSOCIATION_TYPE_ID}"
    )
    status, _ = _request_json(token, "PUT", path)
    return status in (200, 201, 204)


def _search_matching_tickets(token: str, contact_id: str, workflow_id: str, limit: int = 20) -> list[dict]:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "hs_pipeline",
                        "operator": "EQ",
                        "value": OPSLENS_PIPELINE_ID,
                    },
                    {
                        "propertyName": "opslens_ticket_contact_id",
                        "operator": "EQ",
                        "value": str(contact_id),
                    },
                    {
                        "propertyName": "opslens_ticket_workflow_id",
                        "operator": "EQ",
                        "value": str(workflow_id),
                    },
                ]
            }
        ],
        "properties": [
            "subject",
            "hs_pipeline",
            "hs_pipeline_stage",
            "hs_lastmodifieddate",
            "opslens_ticket_callback_id",
            "opslens_ticket_workflow_id",
            "opslens_ticket_contact_id",
            "opslens_ticket_severity",
            "opslens_ticket_delivery_status",
            "opslens_ticket_reason",
            "opslens_ticket_first_alert_at",
            "opslens_ticket_last_alert_at",
            "opslens_ticket_repeat_count",
            "opslens_ticket_resolved_at",
            "opslens_ticket_resolution_reason",
        ],
        "sorts": ["-hs_lastmodifieddate"],
        "limit": limit,
    }

    status, body = _request_json(token, "POST", "/crm/v3/objects/tickets/search", payload)
    if status != 200:
        return []

    return body.get("results", []) or []


def _find_existing_open_ticket(token: str, contact_id: str, workflow_id: str) -> dict | None:
    for row in _search_matching_tickets(token, contact_id, workflow_id, limit=20):
        props = row.get("properties", {}) or {}
        stage_id = str(props.get("hs_pipeline_stage") or "").strip()
        if stage_id in OPEN_STAGE_IDS:
            return row
    return None


def _is_recently_resolved_ticket(props: dict[str, Any]) -> bool:
    stage_id = str(props.get("hs_pipeline_stage") or "").strip()
    if stage_id not in CLOSED_STAGE_IDS:
        return False

    resolved_at = _parse_iso_datetime(props.get("opslens_ticket_resolved_at"))
    if resolved_at is None:
        resolved_at = _parse_iso_datetime(props.get("hs_lastmodifieddate"))

    if resolved_at is None:
        return False

    age = datetime.now(timezone.utc) - resolved_at
    return age <= timedelta(hours=OPSLENS_REOPEN_WINDOW_HOURS)


def _find_recently_resolved_matching_ticket(token: str, contact_id: str, workflow_id: str) -> dict | None:
    for row in _search_matching_tickets(token, contact_id, workflow_id, limit=20):
        props = row.get("properties", {}) or {}
        if _is_recently_resolved_ticket(props):
            return row
    return None


def _build_ticket_properties(
    *,
    portal_id: str,
    contact_id: str,
    workflow_id: str,
    callback_id: str,
    severity: str,
    delivery_status: str,
    delivery_reason: str,
    analyst_note: str,
    received_at_utc: str,
    stage_id: str,
    repeat_count: int,
    first_alert_at_utc: str,
) -> dict[str, str]:
    timestamp_value = str(received_at_utc or "").strip() or _now_utc_iso()
    first_alert_value = str(first_alert_at_utc or "").strip() or timestamp_value

    return {
        "subject": _subject_for_alert(workflow_id, contact_id),
        "content": _description_for_alert(
            portal_id=portal_id,
            contact_id=contact_id,
            workflow_id=workflow_id,
            callback_id=callback_id,
            analyst_note=analyst_note,
            delivery_reason=delivery_reason,
        ),
        "hs_pipeline": OPSLENS_PIPELINE_ID,
        "hs_pipeline_stage": stage_id,
        "hs_ticket_priority": "HIGH" if severity == "critical" else "MEDIUM",
        "opslens_ticket_callback_id": callback_id,
        "opslens_ticket_workflow_id": workflow_id,
        "opslens_ticket_severity": severity,
        "opslens_ticket_delivery_status": delivery_status,
        "opslens_ticket_contact_id": contact_id,
        "opslens_ticket_reason": delivery_reason,
        "opslens_ticket_first_alert_at": first_alert_value,
        "opslens_ticket_last_alert_at": timestamp_value,
        "opslens_ticket_repeat_count": str(max(1, repeat_count)),
    }


def _reopen_resolved_ticket(
    *,
    token: str,
    existing_ticket: dict,
    portal_id: str,
    contact_id: str,
    workflow_id: str,
    callback_id: str,
    severity: str,
    delivery_status: str,
    delivery_reason: str,
    analyst_note: str,
    received_at_utc: str,
) -> dict:
    ticket_id = str(existing_ticket.get("id") or "").strip()
    props = existing_ticket.get("properties", {}) or {}

    previous_repeat_count = _parse_repeat_count(props.get("opslens_ticket_repeat_count"))
    next_repeat_count = previous_repeat_count + 1
    first_alert_at_utc = str(
        props.get("opslens_ticket_first_alert_at") or received_at_utc
    ).strip()

    update_properties = _build_ticket_properties(
        portal_id=portal_id,
        contact_id=contact_id,
        workflow_id=workflow_id,
        callback_id=callback_id,
        severity=severity,
        delivery_status=delivery_status,
        delivery_reason=delivery_reason,
        analyst_note=analyst_note,
        received_at_utc=received_at_utc,
        stage_id=OPSLENS_STAGE_NEW_ALERT,
        repeat_count=next_repeat_count,
        first_alert_at_utc=first_alert_at_utc,
    )

    update_properties["opslens_ticket_resolved_at"] = ""
    update_properties["opslens_ticket_resolution_reason"] = ""

    status, body = _request_json(
        token,
        "PATCH",
        f"/crm/v3/objects/tickets/{urllib.parse.quote(ticket_id)}",
        {"properties": update_properties},
    )

    if status != 200:
        return {
            "ok": False,
            "ticketId": ticket_id,
            "error": body,
            "repeatCount": next_repeat_count,
            "stageUsed": OPSLENS_STAGE_NEW_ALERT,
        }

    return {
        "ok": True,
        "ticketId": ticket_id,
        "error": {},
        "repeatCount": next_repeat_count,
        "stageUsed": OPSLENS_STAGE_NEW_ALERT,
    }


def sync_hubspot_ticket_for_alert(payload: dict) -> dict:
    result = {
        "ticketSyncAttempted": False,
        "ticketSyncOk": False,
        "ticketId": "",
        "ticketCreated": False,
        "ticketUpdated": False,
        "ticketAssociationOk": False,
        "ticketReason": "",
        "ticketSyncError": "",
        "ticketStageUsed": "",
        "ticketRepeatCount": "",
        "timelineNoteCreated": False,
        "timelineNoteId": "",
        "timelineNoteAssociationOk": False,
        "timelineNoteError": "",
        "timelineNotePinned": False,
        "timelineNotePinError": "",
    }

    try:
        contact_id = str(payload.get("objectId") or "").strip()
        workflow_id = str(payload.get("workflowId") or "").strip()
        callback_id = str(payload.get("callbackId") or "").strip()
        portal_id = str(payload.get("portalId") or payload.get("portalIdUsed") or "").strip()
        received_at_utc = str(payload.get("receivedAtUtc") or "").strip() or _now_utc_iso()
        analyst_note = str(payload.get("analystNote") or "").strip()

        severity = _normalize_severity(
            payload.get("severityUsed") or payload.get("severity")
        )
        delivery_status = _normalize_delivery_status(payload.get("deliveryStatus"))
        delivery_reason = str(
            payload.get("deliveryReason")
            or payload.get("reason")
            or ""
        ).strip()

        if not contact_id or not workflow_id or not callback_id:
            result["ticketReason"] = "HubSpot ticket sync skipped because required alert fields were missing."
            return result

        token = _resolve_token_for_portal(portal_id)
        result["ticketSyncAttempted"] = True

        company_id = _get_contact_company_id(token, contact_id)

        existing = _find_existing_open_ticket(token, contact_id, workflow_id)
        if existing:
            ticket_id = str(existing.get("id") or "").strip()
            props = existing.get("properties", {}) or {}

            current_stage = str(props.get("hs_pipeline_stage") or "").strip()
            current_repeat_count = _parse_repeat_count(
                props.get("opslens_ticket_repeat_count")
            )
            next_repeat_count = current_repeat_count + 1
            next_stage = _get_next_repeated_alert_stage(current_stage)

            if next_stage == OPSLENS_STAGE_INVESTIGATING:
                ticket_reason = "Existing open OpsLens ticket found and moved to Investigating."
            elif next_stage == OPSLENS_STAGE_WAITING:
                ticket_reason = "Existing open OpsLens ticket found and moved to Waiting / Monitoring."
            else:
                ticket_reason = "Existing open OpsLens ticket found and updated successfully."

            first_alert_at_utc = str(
                props.get("opslens_ticket_first_alert_at") or received_at_utc
            ).strip()

            update_properties = _build_ticket_properties(
                portal_id=portal_id,
                contact_id=contact_id,
                workflow_id=workflow_id,
                callback_id=callback_id,
                severity=severity,
                delivery_status=delivery_status,
                delivery_reason=delivery_reason,
                analyst_note=analyst_note,
                received_at_utc=received_at_utc,
                stage_id=next_stage,
                repeat_count=next_repeat_count,
                first_alert_at_utc=first_alert_at_utc,
            )

            status, body = _request_json(
                token,
                "PATCH",
                f"/crm/v3/objects/tickets/{urllib.parse.quote(ticket_id)}",
                {"properties": update_properties},
            )
            if status != 200:
                result["ticketSyncError"] = json.dumps(body)
                result["ticketReason"] = f"HubSpot ticket update failed: {body}"
                return result

            assoc_contact_ok = _ensure_ticket_contact_association(token, ticket_id, contact_id)
            assoc_company_ok = True
            if company_id:
                assoc_company_ok = _ensure_ticket_company_association(token, ticket_id, company_id)

            note_ok, note_id, note_error = _create_ticket_timeline_note(
                token=token,
                ticket_id=ticket_id,
                contact_id=contact_id,
                company_id=company_id,
                portal_id=portal_id,
                workflow_id=workflow_id,
                callback_id=callback_id,
                stage_id=next_stage,
                repeat_count=next_repeat_count,
                severity=severity,
                delivery_status=delivery_status,
                delivery_reason=delivery_reason,
                analyst_note=analyst_note,
                event_label=ticket_reason,
                timestamp_utc=received_at_utc,
            )

            pin_ok = False
            pin_error = ""
            if note_ok and note_id:
                pin_ok, pin_error = _pin_note_on_ticket(token, ticket_id, note_id)

            result.update(
                {
                    "ticketSyncOk": True,
                    "ticketId": ticket_id,
                    "ticketCreated": False,
                    "ticketUpdated": True,
                    "ticketAssociationOk": bool(assoc_contact_ok and assoc_company_ok),
                    "ticketReason": ticket_reason,
                    "ticketSyncError": "",
                    "ticketStageUsed": next_stage,
                    "ticketRepeatCount": str(next_repeat_count),
                    "timelineNoteCreated": note_ok,
                    "timelineNoteId": note_id,
                    "timelineNoteAssociationOk": note_ok,
                    "timelineNoteError": note_error,
                    "timelineNotePinned": pin_ok,
                    "timelineNotePinError": pin_error,
                }
            )
            return result

        resolved_ticket = _find_recently_resolved_matching_ticket(token, contact_id, workflow_id)
        if resolved_ticket:
            reopened = _reopen_resolved_ticket(
                token=token,
                existing_ticket=resolved_ticket,
                portal_id=portal_id,
                contact_id=contact_id,
                workflow_id=workflow_id,
                callback_id=callback_id,
                severity=severity,
                delivery_status=delivery_status,
                delivery_reason=delivery_reason,
                analyst_note=analyst_note,
                received_at_utc=received_at_utc,
            )

            if not reopened.get("ok"):
                body = reopened.get("error") or {}
                result["ticketSyncError"] = json.dumps(body)
                result["ticketReason"] = f"HubSpot ticket reopen failed: {body}"
                return result

            ticket_id = str(reopened.get("ticketId") or "").strip()
            stage_used = str(reopened.get("stageUsed") or OPSLENS_STAGE_NEW_ALERT)
            repeat_count = _safe_int(reopened.get("repeatCount"), 1)

            assoc_contact_ok = _ensure_ticket_contact_association(token, ticket_id, contact_id)
            assoc_company_ok = True
            if company_id:
                assoc_company_ok = _ensure_ticket_company_association(token, ticket_id, company_id)

            ticket_reason = "Recently resolved OpsLens ticket reopened and moved back to New Alert."

            note_ok, note_id, note_error = _create_ticket_timeline_note(
                token=token,
                ticket_id=ticket_id,
                contact_id=contact_id,
                company_id=company_id,
                portal_id=portal_id,
                workflow_id=workflow_id,
                callback_id=callback_id,
                stage_id=stage_used,
                repeat_count=repeat_count,
                severity=severity,
                delivery_status=delivery_status,
                delivery_reason=delivery_reason,
                analyst_note=analyst_note,
                event_label=ticket_reason,
                timestamp_utc=received_at_utc,
            )

            pin_ok = False
            pin_error = ""
            if note_ok and note_id:
                pin_ok, pin_error = _pin_note_on_ticket(token, ticket_id, note_id)

            result.update(
                {
                    "ticketSyncOk": True,
                    "ticketId": ticket_id,
                    "ticketCreated": False,
                    "ticketUpdated": True,
                    "ticketAssociationOk": bool(assoc_contact_ok and assoc_company_ok),
                    "ticketReason": ticket_reason,
                    "ticketSyncError": "",
                    "ticketStageUsed": stage_used,
                    "ticketRepeatCount": str(repeat_count),
                    "timelineNoteCreated": note_ok,
                    "timelineNoteId": note_id,
                    "timelineNoteAssociationOk": note_ok,
                    "timelineNoteError": note_error,
                    "timelineNotePinned": pin_ok,
                    "timelineNotePinError": pin_error,
                }
            )
            return result

        create_properties = _build_ticket_properties(
            portal_id=portal_id,
            contact_id=contact_id,
            workflow_id=workflow_id,
            callback_id=callback_id,
            severity=severity,
            delivery_status=delivery_status,
            delivery_reason=delivery_reason,
            analyst_note=analyst_note,
            received_at_utc=received_at_utc,
            stage_id=OPSLENS_STAGE_NEW_ALERT,
            repeat_count=1,
            first_alert_at_utc=received_at_utc,
        )

        status, body = _request_json(
            token,
            "POST",
            "/crm/v3/objects/tickets",
            {"properties": create_properties},
        )
        if status not in (200, 201):
            result["ticketSyncError"] = json.dumps(body)
            result["ticketReason"] = f"HubSpot ticket create failed: {body}"
            return result

        ticket_id = str(body.get("id") or "").strip()

        assoc_contact_ok = _ensure_ticket_contact_association(token, ticket_id, contact_id)
        assoc_company_ok = True
        if company_id:
            assoc_company_ok = _ensure_ticket_company_association(token, ticket_id, company_id)

        note_ok, note_id, note_error = _create_ticket_timeline_note(
            token=token,
            ticket_id=ticket_id,
            contact_id=contact_id,
            company_id=company_id,
            portal_id=portal_id,
            workflow_id=workflow_id,
            callback_id=callback_id,
            stage_id=OPSLENS_STAGE_NEW_ALERT,
            repeat_count=1,
            severity=severity,
            delivery_status=delivery_status,
            delivery_reason=delivery_reason,
            analyst_note=analyst_note,
            event_label="HubSpot ticket created successfully.",
            timestamp_utc=received_at_utc,
        )

        pin_ok = False
        pin_error = ""
        if note_ok and note_id:
            pin_ok, pin_error = _pin_note_on_ticket(token, ticket_id, note_id)

        result.update(
            {
                "ticketSyncOk": True,
                "ticketId": ticket_id,
                "ticketCreated": True,
                "ticketUpdated": False,
                "ticketAssociationOk": bool(assoc_contact_ok and assoc_company_ok),
                "ticketReason": "HubSpot ticket created successfully.",
                "ticketSyncError": "",
                "ticketStageUsed": OPSLENS_STAGE_NEW_ALERT,
                "ticketRepeatCount": "1",
                "timelineNoteCreated": note_ok,
                "timelineNoteId": note_id,
                "timelineNoteAssociationOk": note_ok,
                "timelineNoteError": note_error,
                "timelineNotePinned": pin_ok,
                "timelineNotePinError": pin_error,
            }
        )
        return result

    except Exception as exc:
        result["ticketSyncError"] = str(exc)
        result["ticketReason"] = f"HubSpot ticket sync failed: {exc}"
        return result