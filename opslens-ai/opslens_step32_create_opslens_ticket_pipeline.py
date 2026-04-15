import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.hubapi.com"
API_VERSION = "2026-03"
OBJECT_TYPE = "tickets"

PIPELINE_ID = "opslens_alerts"
PIPELINE_LABEL = "OpsLens Alerts"

STAGES = [
    {
        "stageId": "opslens_new_alert",
        "label": "New Alert",
        "displayOrder": 0,
        "metadata": {"ticketState": "OPEN"},
    },
    {
        "stageId": "opslens_in_progress",
        "label": "Investigating",
        "displayOrder": 1,
        "metadata": {"ticketState": "OPEN"},
    },
    {
        "stageId": "opslens_waiting",
        "label": "Waiting / Monitoring",
        "displayOrder": 2,
        "metadata": {"ticketState": "OPEN"},
    },
    {
        "stageId": "opslens_resolved",
        "label": "Resolved",
        "displayOrder": 3,
        "metadata": {"ticketState": "CLOSED"},
    },
    {
        "stageId": "opslens_duplicate_closed",
        "label": "Closed as Duplicate",
        "displayOrder": 4,
        "metadata": {"ticketState": "CLOSED"},
    },
]

def hubspot_request(method: str, path: str, token: str, body=None):
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return e.code, parsed

def main():
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise SystemExit("Missing HUBSPOT_PRIVATE_APP_TOKEN in environment.")

    list_path = f"/crm/pipelines/{API_VERSION}/{OBJECT_TYPE}"
    status, payload = hubspot_request("GET", list_path, token)

    if status != 200:
        raise SystemExit(
            f"Failed to list ticket pipelines. status={status}\n{json.dumps(payload, indent=2)}"
        )

    results = payload.get("results") or payload.get("pipelines") or []
    for pipeline in results:
        existing_id = str(pipeline.get("id") or pipeline.get("pipelineId") or "").strip()
        existing_label = str(pipeline.get("label") or "").strip()

        if existing_id == PIPELINE_ID or existing_label == PIPELINE_LABEL:
            print("OpsLens ticket pipeline already exists.")
            print(json.dumps(pipeline, indent=2))
            return

    create_body = {
        "pipelineId": PIPELINE_ID,
        "label": PIPELINE_LABEL,
        "displayOrder": 99,
        "stages": STAGES,
    }

    create_path = f"/crm/pipelines/{API_VERSION}/{OBJECT_TYPE}"
    status, payload = hubspot_request("POST", create_path, token, create_body)

    if status not in (200, 201):
        raise SystemExit(
            f"Failed to create OpsLens ticket pipeline. status={status}\n{json.dumps(payload, indent=2)}"
        )

    print("Created OpsLens ticket pipeline successfully.")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()