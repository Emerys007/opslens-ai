import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.hubapi.com"
OBJECT_TYPE = "tickets"
GROUP_NAME = "opslens_ai_tickets"
GROUP_LABEL = "OpsLens AI Tickets"

PROPERTIES = [
    {
        "name": "opslens_ticket_callback_id",
        "label": "OpsLens Ticket Callback ID",
        "type": "string",
        "fieldType": "text",
        "description": "OpsLens callback ID used to dedupe ticket creation.",
    },
    {
        "name": "opslens_ticket_workflow_id",
        "label": "OpsLens Ticket Workflow ID",
        "type": "string",
        "fieldType": "text",
        "description": "HubSpot workflow ID tied to this OpsLens alert.",
    },
    {
        "name": "opslens_ticket_severity",
        "label": "OpsLens Ticket Severity",
        "type": "enumeration",
        "fieldType": "select",
        "description": "Severity of the OpsLens alert that created this ticket.",
        "options": [
            {"label": "Critical", "value": "critical", "displayOrder": 0},
            {"label": "High", "value": "high", "displayOrder": 1},
            {"label": "Medium", "value": "medium", "displayOrder": 2},
            {"label": "Low", "value": "low", "displayOrder": 3},
        ],
    },
    {
        "name": "opslens_ticket_delivery_status",
        "label": "OpsLens Ticket Delivery Status",
        "type": "enumeration",
        "fieldType": "select",
        "description": "Slack delivery outcome for the OpsLens alert.",
        "options": [
            {"label": "Slack Sent", "value": "SLACK_SENT", "displayOrder": 0},
            {
                "label": "Slack Skipped - Threshold",
                "value": "SLACK_SKIPPED_THRESHOLD",
                "displayOrder": 1,
            },
            {
                "label": "Slack Skipped - No Webhook",
                "value": "SLACK_SKIPPED_NO_WEBHOOK",
                "displayOrder": 2,
            },
            {"label": "Slack Failed", "value": "SLACK_FAILED", "displayOrder": 3},
        ],
    },
    {
        "name": "opslens_ticket_contact_id",
        "label": "OpsLens Ticket Contact ID",
        "type": "string",
        "fieldType": "text",
        "description": "HubSpot contact ID associated with the OpsLens alert.",
    },
    {
        "name": "opslens_ticket_reason",
        "label": "OpsLens Ticket Reason",
        "type": "string",
        "fieldType": "textarea",
        "description": "Reason or delivery message captured by OpsLens.",
    },
]

def get_token() -> str:
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise SystemExit("HUBSPOT_PRIVATE_APP_TOKEN is not set in this PowerShell session.")
    return token

def hubspot_request(method: str, path: str, body=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.getcode(), (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw": raw}
        return exc.code, payload

def ensure_group():
    body = {
        "name": GROUP_NAME,
        "label": GROUP_LABEL,
        "displayOrder": -1,
    }
    status, payload = hubspot_request(
        "POST",
        f"/crm/v3/properties/{OBJECT_TYPE}/groups",
        body,
    )

    if status in (200, 201):
        print(f"CREATED group {GROUP_NAME}  status={status}")
        return

    if status == 409:
        print(f"EXISTS  group {GROUP_NAME}  status={status}")
        return

    raise SystemExit(f"Failed to create property group:\nstatus={status}\n{json.dumps(payload, indent=2)}")

def ensure_property(defn: dict):
    body = {
        "groupName": GROUP_NAME,
        "name": defn["name"],
        "label": defn["label"],
        "type": defn["type"],
        "fieldType": defn["fieldType"],
        "description": defn["description"],
        "formField": False,
        "hidden": False,
    }

    if "options" in defn:
        body["options"] = defn["options"]

    status, payload = hubspot_request(
        "POST",
        f"/crm/v3/properties/{OBJECT_TYPE}",
        body,
    )

    if status in (200, 201):
        print(f"CREATED  {defn['name']}  status={status}")
        return

    if status == 409:
        print(f"EXISTS   {defn['name']}  status={status}")
        return

    raise SystemExit(
        f"Failed to create property {defn['name']}:\nstatus={status}\n{json.dumps(payload, indent=2)}"
    )

def main():
    ensure_group()
    for prop in PROPERTIES:
        ensure_property(prop)

    print("\nStep 27 ticket properties completed successfully.")
    print("OpsLens native ticket properties are now available in HubSpot.")

if __name__ == "__main__":
    main()