import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.hubapi.com"
TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("HUBSPOT_PRIVATE_APP_TOKEN is not set in this PowerShell session.")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

GROUP_NAME = "opslens_ai_tickets"
GROUP_LABEL = "OpsLens AI Tickets"

PROPERTIES = [
    {
        "name": "opslens_ticket_first_alert_at",
        "label": "OpsLens Ticket First Alert At",
        "type": "datetime",
        "fieldType": "date",
        "groupName": GROUP_NAME,
        "description": "UTC datetime when this OpsLens ticket was first created from an alert.",
        "displayOrder": 7,
        "formField": False,
        "hidden": False,
    },
    {
        "name": "opslens_ticket_last_alert_at",
        "label": "OpsLens Ticket Last Alert At",
        "type": "datetime",
        "fieldType": "date",
        "groupName": GROUP_NAME,
        "description": "UTC datetime of the most recent OpsLens alert that touched this ticket.",
        "displayOrder": 8,
        "formField": False,
        "hidden": False,
    },
    {
        "name": "opslens_ticket_repeat_count",
        "label": "OpsLens Ticket Repeat Count",
        "type": "number",
        "fieldType": "number",
        "groupName": GROUP_NAME,
        "description": "How many OpsLens alerts have been merged into this same open ticket.",
        "displayOrder": 9,
        "formField": False,
        "hidden": False,
    },
]


def request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace").strip()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed


def ensure_group() -> None:
    url = f"{BASE_URL}/crm/v3/properties/tickets/groups/{GROUP_NAME}"
    status, _ = request_json("GET", url)
    if status == 200:
        print(f"Group already exists: {GROUP_NAME}")
        return

    create_url = f"{BASE_URL}/crm/v3/properties/tickets/groups"
    status, body = request_json(
        "POST",
        create_url,
        {
            "name": GROUP_NAME,
            "label": GROUP_LABEL,
            "displayOrder": 9,
        },
    )
    if status not in (200, 201):
        raise SystemExit(f"Failed to create group {GROUP_NAME}: {status} {body}")
    print(f"CREATED group {GROUP_NAME}  status={status}")


def upsert_property(prop: dict) -> None:
    get_url = f"{BASE_URL}/crm/v3/properties/tickets/{prop['name']}"
    status, _ = request_json("GET", get_url)

    if status == 200:
        patch_url = get_url
        status, body = request_json("PATCH", patch_url, prop)
        if status != 200:
            raise SystemExit(f"Failed to update property {prop['name']}: {status} {body}")
        print(f"UPDATED property {prop['name']}  status={status}")
        return

    create_url = f"{BASE_URL}/crm/v3/properties/tickets"
    status, body = request_json("POST", create_url, prop)
    if status not in (200, 201):
        raise SystemExit(f"Failed to create property {prop['name']}: {status} {body}")
    print(f"CREATED  {prop['name']}  status={status}")


def main() -> None:
    ensure_group()
    for prop in PROPERTIES:
        upsert_property(prop)

    print("\nStep 33 completed successfully.")
    print("OpsLens ticket progression properties are now ready in HubSpot.")


if __name__ == "__main__":
    main()