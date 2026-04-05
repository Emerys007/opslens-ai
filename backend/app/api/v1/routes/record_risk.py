from pathlib import Path
import json

from fastapi import APIRouter, Request

router = APIRouter(prefix="/records", tags=["records"])

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


@router.get("/contact-risk")
async def contact_risk(request: Request):
    query = dict(request.query_params)

    record_id = query.get("recordId", "unknown")
    object_type = query.get("objectTypeId", "0-1")
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

    if str(record_id).endswith("2"):
        risk_level = "critical"
        incident_title = "Quote Sync workflow failures"
        affected_workflows = 3
        recommendation = "Review latest workflow revision and test this contact through the sync path."
    elif str(record_id).endswith("5"):
        risk_level = "high"
        incident_title = "Owner routing mismatch after property update"
        affected_workflows = 2
        recommendation = "Validate owner mapping and confirm fallback routing logic."
    else:
        risk_level = "medium"
        incident_title = "Duplicate contacts spike after import"
        affected_workflows = 1
        recommendation = "Review duplicate cleanup queue and confirm this record's merge status."

    visible = SEVERITY_ORDER.get(risk_level, 0) >= threshold_rank

    return {
        "status": "ok",
        "record": {
            "recordId": record_id,
            "objectTypeId": object_type,
        },
        "appliedSettings": portal_settings,
        "risk": {
            "level": risk_level,
            "incidentTitle": incident_title if visible else "Below current alert threshold",
            "affectedWorkflows": affected_workflows if visible else 0,
            "recommendation": recommendation if visible else "No action required at the current alert threshold.",
            "visibleAtCurrentThreshold": visible,
        },
        "debug": {
            "portalId": portal_id,
            "userId": query.get("userId", "not-provided"),
            "userEmail": query.get("userEmail", "not-provided"),
            "appId": query.get("appId", "not-provided"),
        },
    }
