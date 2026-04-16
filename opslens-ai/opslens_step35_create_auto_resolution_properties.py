import json
import os
import urllib.error
import urllib.request

BASE_URL = "https://api.hubapi.com"


def token() -> str:
    value = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not value:
        raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN is not set.")
    return value


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token()}",
        "Content-Type": "application/json",
    }


def request_json(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers(), method=method)

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


def ensure_property_group(object_type: str, group_name: str, label: str, display_order: int) -> None:
    status, _ = request_json(
        "POST",
        f"/crm/v3/properties/{object_type}/groups",
        {
            "name": group_name,
            "label": label,
            "displayOrder": display_order,
        },
    )
    if status in (200, 201):
        print(f"CREATED group {group_name}  status={status}")
    elif status == 409:
        print(f"Group already exists: {group_name}")
    else:
        raise RuntimeError(f"Failed to ensure group {group_name} on {object_type}")


def ensure_property(object_type: str, payload: dict) -> None:
    name = payload["name"]

    status, _ = request_json(
        "POST",
        f"/crm/v3/properties/{object_type}",
        payload,
    )
    if status in (200, 201):
        print(f"CREATED  {name}  status={status}")
        return

    if status == 409:
        patch_payload = {
            "label": payload["label"],
            "description": payload.get("description", ""),
            "groupName": payload["groupName"],
            "fieldType": payload["fieldType"],
            "type": payload["type"],
            "displayOrder": payload.get("displayOrder", -1),
        }
        patch_status, _ = request_json(
            "PATCH",
            f"/crm/v3/properties/{object_type}/{name}",
            patch_payload,
        )
        if patch_status == 200:
            print(f"UPDATED  {name}  status={patch_status}")
            return

    raise RuntimeError(f"Failed to ensure property {name} on {object_type}")


def main() -> None:
    ensure_property_group("contacts", "opslens_ai", "OpsLens AI", 9)
    ensure_property_group("tickets", "opslens_ai_tickets", "OpsLens AI Tickets", 10)

    ensure_property(
        "contacts",
        {
            "groupName": "opslens_ai",
            "name": "opslens_healthy_signal_at",
            "label": "OpsLens Healthy Signal At",
            "description": "Timestamp of the most recent healthy follow-up signal for OpsLens auto-resolution.",
            "type": "datetime",
            "fieldType": "date",
            "displayOrder": 20,
            "formField": False,
            "hidden": False,
        },
    )

    ensure_property(
        "tickets",
        {
            "groupName": "opslens_ai_tickets",
            "name": "opslens_ticket_resolved_at",
            "label": "OpsLens Ticket Resolved At",
            "description": "Timestamp when OpsLens auto-resolved this ticket.",
            "type": "datetime",
            "fieldType": "date",
            "displayOrder": 20,
            "formField": False,
            "hidden": False,
        },
    )

    ensure_property(
        "tickets",
        {
            "groupName": "opslens_ai_tickets",
            "name": "opslens_ticket_resolution_reason",
            "label": "OpsLens Ticket Resolution Reason",
            "description": "Reason why OpsLens auto-resolved this ticket.",
            "type": "string",
            "fieldType": "textarea",
            "displayOrder": 21,
            "formField": False,
            "hidden": False,
        },
    )

    print("\nStep 35 completed successfully.")
    print("OpsLens auto-resolution properties are now ready in HubSpot.")


if __name__ == "__main__":
    main()