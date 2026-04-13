from pathlib import Path

ROOT = Path(r"C:\OpsLens AI")
BACKEND = ROOT / "backend"
WORKFLOW_PATH = BACKEND / "app" / "api" / "v1" / "routes" / "workflow_actions.py"
SERVICE_PATH = BACKEND / "app" / "services" / "hubspot_native_contact_sync.py"

SERVICE_CONTENT = r'''from __future__ import annotations

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
'''

CREATE_PROPERTIES_SCRIPT = r'''import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\OpsLens AI")
API_BASE = "https://api.hubapi.com"

token = str(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "") or "").strip()
if not token:
    raise SystemExit("HUBSPOT_PRIVATE_APP_TOKEN is not configured in this PowerShell session.")

properties = [
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_at",
        "label": "OpsLens Last Alert At",
        "type": "datetime",
        "fieldType": "date",
        "description": "Last time OpsLens wrote a successful alert back to this contact.",
        "formField": False,
    },
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_severity",
        "label": "OpsLens Last Alert Severity",
        "type": "string",
        "fieldType": "text",
        "description": "Latest OpsLens alert severity for this contact.",
        "formField": False,
    },
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_result",
        "label": "OpsLens Last Alert Result",
        "type": "string",
        "fieldType": "text",
        "description": "Latest OpsLens alert result for this contact.",
        "formField": False,
    },
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_callback_id",
        "label": "OpsLens Last Alert Callback ID",
        "type": "string",
        "fieldType": "text",
        "description": "Latest OpsLens workflow callback ID for this contact.",
        "formField": False,
    },
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_workflow_id",
        "label": "OpsLens Last Alert Workflow ID",
        "type": "string",
        "fieldType": "text",
        "description": "Latest OpsLens workflow ID for this contact.",
        "formField": False,
    },
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_reason",
        "label": "OpsLens Last Alert Reason",
        "type": "string",
        "fieldType": "textarea",
        "description": "Latest OpsLens delivery or handling reason for this contact.",
        "formField": False,
    },
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_analyst_note",
        "label": "OpsLens Last Alert Analyst Note",
        "type": "string",
        "fieldType": "textarea",
        "description": "Latest OpsLens analyst note for this contact.",
        "formField": False,
    },
    {
        "groupName": "contactinformation",
        "name": "opslens_last_alert_delivery_status",
        "label": "OpsLens Last Alert Delivery Status",
        "type": "string",
        "fieldType": "text",
        "description": "Latest OpsLens delivery status for this contact.",
        "formField": False,
    },
]

def create_property(defn: dict) -> None:
    body = json.dumps(defn).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/crm/v3/properties/contacts",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            print(f"CREATED  {defn['name']}  status={getattr(response, 'status', 200)}")
    except urllib.error.HTTPError as exc:
        try:
            error_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_text = str(exc)

        if exc.code == 409 or "PROPERTY_ALREADY_EXISTS" in error_text:
            print(f"EXISTS   {defn['name']}")
        else:
            print(f"FAILED   {defn['name']}  status={exc.code}")
            print(error_text)
            raise

for item in properties:
    create_property(item)
'''

SYNC_BLOCK = r'''
    # STEP23_NATIVE_CONTACT_SYNC_START
    native_contact_sync_attempted = False
    native_contact_sync_ok = False
    native_contact_sync_error = ""
    native_contact_properties_written = []

    try:
        target_object_type = str(details.get("objectType") or "").strip().upper()
        target_contact_id = str(details.get("objectId") or "").strip()

        if target_object_type == "CONTACT" and target_contact_id:
            native_contact_sync_attempted = True

            severity_used = str(
                details.get("severityOverride")
                or details.get("severity")
                or "high"
            ).strip().lower()

            if severity_used in ("", "use_settings"):
                severity_used = str(slack_threshold or "high").strip().lower()

            if slack_sent:
                delivery_status = "SLACK_SENT"
                delivery_reason = "Slack alert delivered successfully."
            elif slack_attempted:
                delivery_status = "SLACK_FAILED"
                delivery_reason = str(slack_error or "Slack delivery attempt failed.").strip()
            elif slack_webhook_configured:
                delivery_status = "SLACK_SKIPPED_THRESHOLD"
                delivery_reason = f"Saved Slack threshold is {slack_threshold}; this alert did not meet that threshold."
            else:
                delivery_status = "SLACK_SKIPPED_NO_WEBHOOK"
                delivery_reason = "No Slack webhook URL is configured for this portal."

            native_contact_sync_ok, native_contact_sync_error, native_contact_properties_written = sync_latest_alert_to_hubspot_contact(
                contact_id=target_contact_id,
                received_at_utc=received_at,
                workflow_id=str(details.get("workflowId") or ""),
                callback_id=str(details.get("callbackId") or ""),
                severity=severity_used,
                result="accepted",
                reason=delivery_reason,
                analyst_note=str(details.get("analystNote") or ""),
                delivery_status=delivery_status,
            )
    except Exception as exc:
        native_contact_sync_error = str(exc)
    # STEP23_NATIVE_CONTACT_SYNC_END
'''

RESPONSE_INSERT_AFTER = '''        "slackWebhookConfigured": slack_webhook_configured,
'''

RESPONSE_BLOCK = '''        "nativeContactSyncAttempted": native_contact_sync_attempted,
        "nativeContactSyncOk": native_contact_sync_ok,
        "nativeContactSyncError": native_contact_sync_error,
        "nativeContactPropertiesWritten": native_contact_properties_written,
'''

def main() -> None:
    SERVICE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SERVICE_PATH.write_text(SERVICE_CONTENT, encoding="utf-8")

    helper_script_path = ROOT / "opslens-ai" / "opslens_step23_create_hubspot_contact_properties.py"
    helper_script_path.write_text(CREATE_PROPERTIES_SCRIPT, encoding="utf-8")

    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    import_line = "from app.services.hubspot_native_contact_sync import sync_latest_alert_to_hubspot_contact\n"
    if import_line not in text:
        anchor = "from app.models.alert_event import AlertEvent\n"
        if anchor in text:
            text = text.replace(anchor, anchor + import_line)
        else:
            raise SystemExit("Could not find AlertEvent import anchor in workflow_actions.py")

    if "# STEP23_NATIVE_CONTACT_SYNC_START" not in text:
        marker = "# STEP18_SLACK_RUNTIME_END"
        if marker not in text:
            raise SystemExit("Could not find STEP18 slack marker in workflow_actions.py")
        text = text.replace(marker, marker + SYNC_BLOCK, 1)

    if '"nativeContactSyncAttempted": native_contact_sync_attempted,' not in text:
        if RESPONSE_INSERT_AFTER not in text:
            raise SystemExit("Could not find slackWebhookConfigured response line in workflow_actions.py")
        text = text.replace(RESPONSE_INSERT_AFTER, RESPONSE_INSERT_AFTER + RESPONSE_BLOCK, 1)

    WORKFLOW_PATH.write_text(text, encoding="utf-8")

    print(f"Updated workflow route: {WORKFLOW_PATH}")
    print(f"Created sync service: {SERVICE_PATH}")
    print(f"Created property bootstrap script: {helper_script_path}")

if __name__ == "__main__":
    main()