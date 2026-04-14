import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.hubapi.com"


PROPERTIES = [
    {
        "name": "opslens_last_alert_at",
        "label": "OpsLens Last Alert At",
        "description": "UTC timestamp of the most recent OpsLens alert written by the hosted workflow backend.",
        "displayOrder": 1,
    },
    {
        "name": "opslens_last_alert_severity",
        "label": "OpsLens Last Alert Severity",
        "description": "Severity of the most recent OpsLens alert.",
        "displayOrder": 2,
    },
    {
        "name": "opslens_last_alert_result",
        "label": "OpsLens Last Alert Result",
        "description": "Final result returned by the most recent OpsLens alert workflow action.",
        "displayOrder": 3,
    },
    {
        "name": "opslens_last_alert_callback_id",
        "label": "OpsLens Last Alert Callback ID",
        "description": "HubSpot callback ID returned by the most recent OpsLens alert workflow execution.",
        "displayOrder": 4,
    },
    {
        "name": "opslens_last_alert_workflow_id",
        "label": "OpsLens Last Alert Workflow ID",
        "description": "HubSpot workflow ID that produced the most recent OpsLens alert.",
        "displayOrder": 5,
    },
    {
        "name": "opslens_last_alert_reason",
        "label": "OpsLens Last Alert Reason",
        "description": "Reason or delivery summary returned by the most recent OpsLens alert.",
        "displayOrder": 6,
    },
    {
        "name": "opslens_last_alert_analyst_note",
        "label": "OpsLens Last Alert Analyst Note",
        "description": "Analyst note saved from the most recent OpsLens alert.",
        "displayOrder": 7,
    },
    {
        "name": "opslens_last_alert_delivery_status",
        "label": "OpsLens Last Alert Delivery Status",
        "description": "Delivery outcome for the most recent OpsLens alert, such as SLACK_SENT.",
        "displayOrder": 8,
    },
]

GROUP_NAME = "opslens_ai"
GROUP_LABEL = "OpsLens AI"


def get_token() -> str:
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "HUBSPOT_PRIVATE_APP_TOKEN is not set in this terminal session."
        )
    return token


def hs_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    token = get_token()
    url = f"{BASE_URL}{path}"

    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.getcode()
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return status_code, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw": raw}
        return exc.code, payload


def ensure_group() -> None:
    read_status, _ = hs_request(
        "GET",
        f"/crm/v3/properties/contacts/groups/{GROUP_NAME}",
    )

    if read_status == 200:
        patch_status, patch_payload = hs_request(
            "PATCH",
            f"/crm/v3/properties/contacts/groups/{GROUP_NAME}",
            {
                "label": GROUP_LABEL,
                "displayOrder": -1,
            },
        )
        if patch_status != 200:
            raise SystemExit(
                f"Failed to update group {GROUP_NAME}: {patch_status} {patch_payload}"
            )
        print(f"UPDATED group {GROUP_NAME}  status={patch_status}")
        return

    if read_status == 404:
        create_status, create_payload = hs_request(
            "POST",
            "/crm/v3/properties/contacts/groups",
            {
                "name": GROUP_NAME,
                "label": GROUP_LABEL,
                "displayOrder": -1,
            },
        )
        if create_status not in (200, 201):
            raise SystemExit(
                f"Failed to create group {GROUP_NAME}: {create_status} {create_payload}"
            )
        print(f"CREATED group {GROUP_NAME}  status={create_status}")
        return

    raise SystemExit(
        f"Unexpected response while reading group {GROUP_NAME}: {read_status}"
    )


def update_property(prop: dict) -> None:
    prop_name = prop["name"]

    read_status, read_payload = hs_request(
        "GET",
        f"/crm/v3/properties/contacts/{prop_name}",
    )

    if read_status != 200:
        raise SystemExit(
            f"Property {prop_name} not found or unreadable: {read_status} {read_payload}"
        )

    patch_body = {
        "groupName": GROUP_NAME,
        "label": prop["label"],
        "description": prop["description"],
        "displayOrder": prop["displayOrder"],
        "hidden": False,
    }

    patch_status, patch_payload = hs_request(
        "PATCH",
        f"/crm/v3/properties/contacts/{prop_name}",
        patch_body,
    )

    if patch_status != 200:
        raise SystemExit(
            f"Failed to update property {prop_name}: {patch_status} {patch_payload}"
        )

    updated_group = patch_payload.get("groupName", "")
    print(f"UPDATED property {prop_name}  group={updated_group}  status={patch_status}")


def main() -> None:
    ensure_group()

    for prop in PROPERTIES:
        update_property(prop)

    print()
    print("Step 24 completed successfully.")
    print("OpsLens native contact properties are now grouped under 'OpsLens AI'.")


if __name__ == "__main__":
    main()