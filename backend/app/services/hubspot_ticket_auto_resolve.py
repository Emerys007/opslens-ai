import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

BASE_URL = "https://api.hubapi.com"

OPSLENS_PIPELINE_ID = os.getenv("HUBSPOT_OPSLENS_PIPELINE_ID", "890820374").strip()
OPSLENS_STAGE_WAITING = os.getenv("HUBSPOT_OPSLENS_STAGE_WAITING", "1341759035").strip()
OPSLENS_STAGE_RESOLVED = os.getenv("HUBSPOT_OPSLENS_STAGE_RESOLVED", "1341759036").strip()

DEFAULT_QUIET_HOURS = int(os.getenv("OPSLENS_AUTO_RESOLVE_QUIET_HOURS", "24").strip() or "24")


def _token() -> str:
    return os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()


def _headers() -> dict[str, str]:
    token = _token()
    if not token:
        raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN is not configured.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _request_json(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers=_headers(),
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
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except Exception:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_utc_iso() -> str:
    return _now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_contact_healthy_signal_at(contact_id: str) -> datetime | None:
    if not contact_id:
        return None

    path = (
        f"/crm/v3/objects/contacts/{urllib.parse.quote(contact_id)}"
        "?properties=opslens_healthy_signal_at"
    )
    status, body = _request_json("GET", path)
    if status != 200:
        return None

    props = body.get("properties", {}) or {}
    return _parse_dt(props.get("opslens_healthy_signal_at"))


def _search_waiting_tickets(limit: int = 100) -> list[dict]:
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
                        "propertyName": "hs_pipeline_stage",
                        "operator": "EQ",
                        "value": OPSLENS_STAGE_WAITING,
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

    status, body = _request_json("POST", "/crm/v3/objects/tickets/search", payload)
    if status != 200:
        raise RuntimeError(f"Ticket search failed: {body}")

    return body.get("results", []) or []


def _resolve_ticket(ticket_id: str, reason: str) -> tuple[bool, str]:
    payload = {
        "properties": {
            "hs_pipeline": OPSLENS_PIPELINE_ID,
            "hs_pipeline_stage": OPSLENS_STAGE_RESOLVED,
            "opslens_ticket_resolved_at": _now_utc_iso(),
            "opslens_ticket_resolution_reason": reason,
        }
    }

    status, body = _request_json(
        "PATCH",
        f"/crm/v3/objects/tickets/{urllib.parse.quote(ticket_id)}",
        payload,
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
        "skipped": 0,
        "errors": [],
        "resolvedTicketIds": [],
    }

    tickets = _search_waiting_tickets(limit=max_records)
    summary["searched"] = len(tickets)

    for row in tickets:
        ticket_id = str(row.get("id") or "").strip()
        props = row.get("properties", {}) or {}

        contact_id = str(props.get("opslens_ticket_contact_id") or "").strip()
        last_alert_at = _parse_dt(props.get("opslens_ticket_last_alert_at"))
        healthy_signal_at = _get_contact_healthy_signal_at(contact_id)

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

        ok, err = _resolve_ticket(ticket_id, reason)
        if not ok:
            summary["errors"].append(
                {
                    "ticketId": ticket_id,
                    "error": err,
                }
            )
            continue

        summary["resolvedTicketIds"].append(ticket_id)
        if resolution_mode == "healthy_signal":
            summary["resolvedHealthySignal"] += 1
        else:
            summary["resolvedQuietPeriod"] += 1

    return summary