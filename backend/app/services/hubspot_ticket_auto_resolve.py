import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db import get_session, init_db
from app.models.hubspot_installation import HubSpotInstallation
from app.services.hubspot_ticket_pipeline import (
    PortalProvisioningRequiredError,
    TicketPipelineConfig,
    load_portal_ticket_pipeline_config,
)
from app.services.hubspot_oauth import get_portal_access_token

BASE_URL = "https://api.hubapi.com"

DEFAULT_QUIET_HOURS = int(os.getenv("OPSLENS_AUTO_RESOLVE_QUIET_HOURS", "24").strip() or "24")

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


def _installed_portal_ids() -> list[str]:
    if not init_db():
        return []

    session = get_session()
    if session is None:
        return []

    try:
        rows = session.execute(
            select(HubSpotInstallation.portal_id).where(HubSpotInstallation.is_active.is_(True))
        ).scalars().all()
        values = []
        seen = set()
        for row in rows:
            portal_id = str(row or "").strip()
            if portal_id and portal_id not in seen:
                seen.add(portal_id)
                values.append(portal_id)
        return values
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


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    try:
        if text.isdigit():
            raw = int(text)
            timestamp = raw / 1000 if raw > 10_000_000_000 else raw
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return default


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_utc_iso() -> str:
    return _now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_contact_healthy_signal_at(token: str, contact_id: str) -> datetime | None:
    if not contact_id:
        return None

    path = (
        f"/crm/v3/objects/contacts/{urllib.parse.quote(contact_id)}"
        "?properties=opslens_healthy_signal_at"
    )
    status, body = _request_json(token, "GET", path)
    if status != 200:
        return None

    props = body.get("properties", {}) or {}
    return _parse_dt(props.get("opslens_healthy_signal_at"))


def _get_contact_company_id(token: str, contact_id: str) -> str:
    if not contact_id:
        return ""

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


def _search_waiting_tickets(
    token: str,
    pipeline_config: TicketPipelineConfig,
    limit: int = 100,
) -> list[dict]:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "hs_pipeline",
                        "operator": "EQ",
                        "value": pipeline_config.pipeline_id,
                    },
                    {
                        "propertyName": "hs_pipeline_stage",
                        "operator": "EQ",
                        "value": pipeline_config.stage_waiting,
                    },
                ]
            }
        ],
        "properties": [
            "subject",
            "hs_pipeline",
            "hs_pipeline_stage",
            "opslens_ticket_contact_id",
            "opslens_ticket_workflow_id",
            "opslens_ticket_callback_id",
            "opslens_ticket_severity",
            "opslens_ticket_delivery_status",
            "opslens_ticket_reason",
            "opslens_ticket_first_alert_at",
            "opslens_ticket_last_alert_at",
            "opslens_ticket_repeat_count",
            "opslens_ticket_resolved_at",
            "opslens_ticket_resolution_reason",
        ],
        "sorts": [
            {
                "propertyName": "hs_lastmodifieddate",
                "direction": "DESCENDING",
            }
        ],
        "limit": max(1, min(limit, 200)),
    }

    status, body = _request_json(token, "POST", "/crm/v3/objects/tickets/search", payload)
    if status != 200:
        raise RuntimeError(f"Ticket search failed: {body}")

    return body.get("results", []) or []


def _resolve_ticket(
    token: str,
    pipeline_config: TicketPipelineConfig,
    ticket_id: str,
    reason: str,
    resolved_at_utc: str,
) -> tuple[bool, str]:
    payload = {
        "properties": {
            "hs_pipeline": pipeline_config.pipeline_id,
            "hs_pipeline_stage": pipeline_config.stage_resolved,
            "opslens_ticket_resolved_at": resolved_at_utc,
            "opslens_ticket_resolution_reason": reason,
        }
    }

    status, body = _request_json(
        token,
        "PATCH",
        f"/crm/v3/objects/tickets/{urllib.parse.quote(ticket_id)}",
        payload,
    )
    if status != 200:
        return False, json.dumps(body)

    return True, ""


def _resolution_mode_label(mode: str) -> str:
    if mode == "healthy_signal":
        return "Healthy follow-up signal"
    return "Quiet period"


def _build_auto_resolve_note_body(
    *,
    ticket_id: str,
    contact_id: str,
    workflow_id: str,
    callback_id: str,
    severity: str,
    delivery_status: str,
    delivery_reason: str,
    repeat_count: int,
    resolution_mode: str,
    resolution_reason: str,
    latest_alert_at_utc: str,
    healthy_signal_at_utc: str,
) -> str:
    lines = [
        f"OpsLens ticket auto-resolution event: {_resolution_mode_label(resolution_mode)}",
        f"Ticket ID: {ticket_id}",
        "Ticket stage: Resolved",
        f"Contact ID: {contact_id}",
        f"Workflow ID: {workflow_id}",
        f"Callback ID: {callback_id}",
        f"Severity: {severity}",
        f"Delivery status: {delivery_status}",
        f"Delivery reason: {delivery_reason}",
        f"Repeat count: {max(1, repeat_count)}",
        f"Resolution reason: {resolution_reason}",
        f"Latest alert at: {latest_alert_at_utc or '-'}",
    ]

    if healthy_signal_at_utc:
        lines.append(f"Healthy signal at: {healthy_signal_at_utc}")

    return "\n".join(lines)


def _create_auto_resolve_note(
    *,
    token: str,
    ticket_id: str,
    contact_id: str,
    company_id: str,
    workflow_id: str,
    callback_id: str,
    severity: str,
    delivery_status: str,
    delivery_reason: str,
    repeat_count: int,
    resolution_mode: str,
    resolution_reason: str,
    latest_alert_at_utc: str,
    healthy_signal_at_utc: str,
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
        }
    ]

    if contact_id:
        associations.append(
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": NOTE_TO_CONTACT_ASSOCIATION_TYPE_ID,
                    }
                ],
            }
        )

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
            "hs_note_body": _build_auto_resolve_note_body(
                ticket_id=ticket_id,
                contact_id=contact_id,
                workflow_id=workflow_id,
                callback_id=callback_id,
                severity=severity,
                delivery_status=delivery_status,
                delivery_reason=delivery_reason,
                repeat_count=repeat_count,
                resolution_mode=resolution_mode,
                resolution_reason=resolution_reason,
                latest_alert_at_utc=latest_alert_at_utc,
                healthy_signal_at_utc=healthy_signal_at_utc,
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


def auto_resolve_waiting_tickets(
    *,
    quiet_hours: int | None = None,
    max_records: int = 100,
) -> dict:
    quiet_hours = quiet_hours if quiet_hours is not None else DEFAULT_QUIET_HOURS
    now_utc = _now_utc()

    summary = {
        "status": "ok",
        "quietHours": quiet_hours,
        "searched": 0,
        "resolvedQuietPeriod": 0,
        "resolvedHealthySignal": 0,
        "notesCreated": 0,
        "notesPinned": 0,
        "skipped": 0,
        "skippedPortals": [],
        "errors": [],
        "noteErrors": [],
        "pinErrors": [],
        "resolvedTicketIds": [],
        "resolvedDetails": [],
    }

    portal_ids = _installed_portal_ids()
    portal_tokens: list[tuple[str, str, TicketPipelineConfig]] = []

    for portal_id in portal_ids:
        try:
            token = _resolve_token_for_portal(portal_id)
            pipeline_config = load_portal_ticket_pipeline_config(
                token=token,
                portal_id=portal_id,
            )
            portal_tokens.append((portal_id, token, pipeline_config))
        except PortalProvisioningRequiredError as exc:
            summary["skippedPortals"].append(
                {
                    "portalId": portal_id,
                    "reason": str(exc),
                }
            )
        except Exception as exc:
            summary["errors"].append(
                {
                    "portalId": portal_id,
                    "error": str(exc),
                }
            )

    if not portal_ids:
        summary["errors"].append(
            {
                "portalId": "",
                "error": "No active HubSpot OAuth installations were found.",
            }
        )
        return summary

    if not portal_tokens:
        return summary

    for portal_id, token, pipeline_config in portal_tokens:
        try:
            tickets = _search_waiting_tickets(token, pipeline_config, limit=max_records)
        except Exception as exc:
            summary["errors"].append(
                {
                    "portalId": portal_id,
                    "error": str(exc),
                }
            )
            continue

        summary["searched"] += len(tickets)

        for row in tickets:
            ticket_id = str(row.get("id") or "").strip()
            props = row.get("properties", {}) or {}

            contact_id = str(props.get("opslens_ticket_contact_id") or "").strip()
            workflow_id = str(props.get("opslens_ticket_workflow_id") or "").strip()
            callback_id = str(props.get("opslens_ticket_callback_id") or "").strip()
            severity = str(props.get("opslens_ticket_severity") or "").strip().lower() or "critical"
            delivery_status = str(props.get("opslens_ticket_delivery_status") or "").strip().upper() or "SLACK_SENT"
            delivery_reason = str(props.get("opslens_ticket_reason") or "").strip()
            repeat_count = max(1, _safe_int(props.get("opslens_ticket_repeat_count"), 1))

            latest_alert_text = str(props.get("opslens_ticket_last_alert_at") or "").strip()
            last_alert_at = _parse_dt(latest_alert_text)

            healthy_signal_at = _get_contact_healthy_signal_at(token, contact_id)
            healthy_signal_text = (
                healthy_signal_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
                if healthy_signal_at
                else ""
            )

            reason = ""
            resolution_mode = ""

            if healthy_signal_at and last_alert_at and healthy_signal_at > last_alert_at:
                reason = "Healthy follow-up signal received after the latest alert."
                resolution_mode = "healthy_signal"
            elif last_alert_at and now_utc >= (last_alert_at + timedelta(hours=quiet_hours)):
                reason = f"No repeat alert received for {quiet_hours} hours while ticket was in Waiting / Monitoring."
                resolution_mode = "quiet_period"
            else:
                summary["skipped"] += 1
                continue

            resolved_at_utc = _now_utc_iso()
            ok, err = _resolve_ticket(
                token,
                pipeline_config,
                ticket_id,
                reason,
                resolved_at_utc,
            )
            if not ok:
                summary["errors"].append(
                    {
                        "portalId": portal_id,
                        "ticketId": ticket_id,
                        "error": err,
                    }
                )
                continue

            company_id = _get_contact_company_id(token, contact_id)

            note_ok, note_id, note_error = _create_auto_resolve_note(
                token=token,
                ticket_id=ticket_id,
                contact_id=contact_id,
                company_id=company_id,
                workflow_id=workflow_id,
                callback_id=callback_id,
                severity=severity,
                delivery_status=delivery_status,
                delivery_reason=delivery_reason,
                repeat_count=repeat_count,
                resolution_mode=resolution_mode,
                resolution_reason=reason,
                latest_alert_at_utc=latest_alert_text,
                healthy_signal_at_utc=healthy_signal_text,
                timestamp_utc=resolved_at_utc,
            )

            pin_ok = False
            pin_error = ""
            if note_ok and note_id:
                pin_ok, pin_error = _pin_note_on_ticket(token, ticket_id, note_id)

            summary["resolvedTicketIds"].append(ticket_id)

            if resolution_mode == "healthy_signal":
                summary["resolvedHealthySignal"] += 1
            else:
                summary["resolvedQuietPeriod"] += 1

            if note_ok:
                summary["notesCreated"] += 1
            else:
                summary["noteErrors"].append(
                    {
                        "portalId": portal_id,
                        "ticketId": ticket_id,
                        "error": note_error,
                    }
                )

            if pin_ok:
                summary["notesPinned"] += 1
            elif note_ok:
                summary["pinErrors"].append(
                    {
                        "portalId": portal_id,
                        "ticketId": ticket_id,
                        "noteId": note_id,
                        "error": pin_error,
                    }
                )

            summary["resolvedDetails"].append(
                {
                    "portalId": portal_id,
                    "ticketId": ticket_id,
                    "resolutionMode": resolution_mode,
                    "resolutionReason": reason,
                    "resolvedAt": resolved_at_utc,
                    "noteCreated": note_ok,
                    "noteId": note_id,
                    "noteError": note_error,
                    "notePinned": pin_ok,
                    "pinError": pin_error,
                }
            )

    return summary
