import json
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
