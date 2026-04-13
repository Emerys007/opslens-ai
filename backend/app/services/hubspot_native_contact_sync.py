from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import urllib.error
import urllib.request


HUBSPOT_API_BASE = "https://api.hubapi.com"


def _to_epoch_ms(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return str(int(dt.timestamp() * 1000))


def sync_latest_alert_to_hubspot_contact(
    *,
    contact_id: str,
    received_at_utc: str,
    workflow_id: str,
    callback_id: str,
    severity: str,
    result: str,
    reason: str,
    analyst_note: str,
    delivery_status: str,
) -> tuple[bool, str, list[str]]:
    token = str(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "") or "").strip()
    if not token:
        return False, "HUBSPOT_PRIVATE_APP_TOKEN is not configured.", []

    contact_id = str(contact_id or "").strip()
    if not contact_id:
        return False, "No contact_id was provided.", []

    properties = {
        "opslens_last_alert_at": _to_epoch_ms(received_at_utc),
        "opslens_last_alert_severity": str(severity or "").strip(),
        "opslens_last_alert_result": str(result or "").strip(),
        "opslens_last_alert_callback_id": str(callback_id or "").strip(),
        "opslens_last_alert_workflow_id": str(workflow_id or "").strip(),
        "opslens_last_alert_reason": str(reason or "").strip(),
        "opslens_last_alert_analyst_note": str(analyst_note or "").strip(),
        "opslens_last_alert_delivery_status": str(delivery_status or "").strip(),
    }

    body = json.dumps({"properties": properties}).encode("utf-8")

    request = urllib.request.Request(
        f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts/{contact_id}",
        data=body,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                return True, "", sorted(properties.keys())

            response_body = response.read().decode("utf-8", errors="replace")
            return False, response_body or f"Unexpected status {status_code}", []
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = str(exc)
        return False, body_text or str(exc), []
    except Exception as exc:
        return False, str(exc), []
