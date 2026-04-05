from datetime import datetime, timezone
from pathlib import Path
import json

from fastapi import APIRouter, Request

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "portal_settings.json"

SEVERITY_ORDER = {
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def _read_all_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


@router.get("/overview")
async def dashboard_overview(request: Request):
    query = dict(request.query_params)
    portal_id = query.get("portalId", "not-provided")

    all_settings = _read_all_settings()
    portal_settings = all_settings.get(
        portal_id,
        {
            "slackWebhookUrl": "",
            "alertThreshold": "high",
            "criticalWorkflows": "",
        },
    )

    threshold = str(portal_settings.get("alertThreshold", "high")).lower()
    threshold_rank = SEVERITY_ORDER.get(threshold, 2)

    all_incidents = [
        {
            "id": "INC-1001",
            "severity": "critical",
            "title": "Quote Sync workflow failures",
            "recommendation": "Review latest workflow revision and test 3 sample records.",
            "affectedRecords": 42,
        },
        {
            "id": "INC-1002",
            "severity": "high",
            "title": "Owner routing mismatch after property update",
            "recommendation": "Validate owner mapping and confirm fallback logic.",
            "affectedRecords": 17,
        },
        {
            "id": "INC-1003",
            "severity": "medium",
            "title": "Duplicate contacts spike after import",
            "recommendation": "Review import source and run duplicate cleanup queue.",
            "affectedRecords": 9,
        },
    ]

    filtered_incidents = [
        incident
        for incident in all_incidents
        if SEVERITY_ORDER.get(incident["severity"], 0) >= threshold_rank
    ]

    critical_count = len(
        [incident for incident in filtered_incidents if incident["severity"] == "critical"]
    )

    return {
        "status": "ok",
        "app": "OpsLens AI",
        "connectedBackend": True,
        "appliedSettings": portal_settings,
        "summary": {
            "openIncidents": len(filtered_incidents),
            "criticalIssues": critical_count,
            "monitoredWorkflows": 12,
            "lastCheckedUtc": datetime.now(timezone.utc).isoformat(),
        },
        "activeIncidents": filtered_incidents,
        "debug": {
            "portalId": portal_id,
            "userId": query.get("userId", "not-provided"),
            "userEmail": query.get("userEmail", "not-provided"),
            "appId": query.get("appId", "not-provided"),
        },
    }
