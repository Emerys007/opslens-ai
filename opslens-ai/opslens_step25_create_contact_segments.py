import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

BASE_URL = "https://api.hubapi.com"
API_PREFIX = "/crm/lists/2026-03"
OBJECT_TYPE_ID = "0-1"  # contacts


def get_token() -> str:
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise SystemExit("HUBSPOT_PRIVATE_APP_TOKEN is not set in this PowerShell session.")
    return token


def hs_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/json",
    }

    data = None
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


def root_and_branch(filters: list[dict]) -> dict:
    return {
        "filterBranchType": "OR",
        "filterBranchOperator": "OR",
        "filters": [],
        "filterBranches": [
            {
                "filterBranchType": "AND",
                "filterBranchOperator": "AND",
                "filters": filters,
                "filterBranches": [],
            }
        ],
    }


def filter_is_known(property_name: str) -> dict:
    return {
        "filterType": "PROPERTY",
        "property": property_name,
        "operation": {
            "operationType": "ALL_PROPERTY",
            "operator": "IS_KNOWN",
            "includeObjectsWithNoValueSet": False,
        },
    }


def filter_string_equals(property_name: str, value: str) -> dict:
    return {
        "filterType": "PROPERTY",
        "property": property_name,
        "operation": {
            "operationType": "MULTISTRING",
            "operator": "IS_EQUAL_TO",
            "values": [value],
            "includeObjectsWithNoValueSet": False,
        },
    }


LIST_DEFINITIONS = [
    {
        "name": "OpsLens - Any Alerted Contacts",
        "filterBranch": root_and_branch([
            filter_is_known("opslens_last_alert_at"),
        ]),
    },
    {
        "name": "OpsLens - Critical Alerts",
        "filterBranch": root_and_branch([
            filter_is_known("opslens_last_alert_at"),
            filter_string_equals("opslens_last_alert_severity", "critical"),
        ]),
    },
    {
        "name": "OpsLens - Slack Sent Alerts",
        "filterBranch": root_and_branch([
            filter_is_known("opslens_last_alert_at"),
            filter_string_equals("opslens_last_alert_delivery_status", "SLACK_SENT"),
        ]),
    },
    {
        "name": "OpsLens - Critical + Slack Sent",
        "filterBranch": root_and_branch([
            filter_is_known("opslens_last_alert_at"),
            filter_string_equals("opslens_last_alert_severity", "critical"),
            filter_string_equals("opslens_last_alert_delivery_status", "SLACK_SENT"),
        ]),
    },
]


def get_list_by_name(list_name: str) -> tuple[int, dict]:
    encoded_name = urllib.parse.quote(list_name, safe="")
    return hs_request(
        "GET",
        f"{API_PREFIX}/object-type-id/{OBJECT_TYPE_ID}/name/{encoded_name}?includeFilters=true",
    )


def create_list(list_name: str, filter_branch: dict) -> tuple[int, dict]:
    body = {
        "name": list_name,
        "objectTypeId": OBJECT_TYPE_ID,
        "processingType": "DYNAMIC",
        "filterBranch": filter_branch,
    }
    return hs_request("POST", API_PREFIX, body)


def update_list_filters(list_id: str, filter_branch: dict) -> tuple[int, dict]:
    body = {"filterBranch": filter_branch}
    return hs_request("PUT", f"{API_PREFIX}/{list_id}/update-list-filters?includeFilters=true", body)


def ensure_list(defn: dict) -> None:
    list_name = defn["name"]
    filter_branch = defn["filterBranch"]

    status, payload = get_list_by_name(list_name)

    if status == 404:
        create_status, create_payload = create_list(list_name, filter_branch)
        if create_status not in (200, 201):
            raise SystemExit(
                f"Failed to create list '{list_name}': {create_status} {json.dumps(create_payload, indent=2)}"
            )

        created_list = create_payload.get("list", create_payload.get("updatedList", {}))
        print(
            f"CREATED  {list_name}  "
            f"listId={created_list.get('listId', 'unknown')}  "
            f"processingType={created_list.get('processingType', 'unknown')}  "
            f"status={create_status}"
        )
        return

    if status != 200:
        raise SystemExit(
            f"Failed to retrieve list '{list_name}': {status} {json.dumps(payload, indent=2)}"
        )

    existing = payload.get("list", payload.get("updatedList", {}))
    list_id = existing.get("listId")
    if not list_id:
        raise SystemExit(f"List '{list_name}' was found, but no listId was returned.")

    update_status, update_payload = update_list_filters(list_id, filter_branch)
    if update_status != 200:
        raise SystemExit(
            f"Failed to update filters for '{list_name}': {update_status} {json.dumps(update_payload, indent=2)}"
        )

    updated = update_payload.get("updatedList", update_payload.get("list", {}))
    print(
        f"UPDATED  {list_name}  "
        f"listId={updated.get('listId', list_id)}  "
        f"processingType={updated.get('processingType', 'unknown')}  "
        f"status={update_status}"
    )


def main() -> None:
    for definition in LIST_DEFINITIONS:
        ensure_list(definition)

    print()
    print("Step 25 completed successfully.")
    print("OpsLens dynamic contact segments are now created or updated in HubSpot.")


if __name__ == "__main__":
    main()