from pathlib import Path
import json
import textwrap

PROJECT_ROOT = Path.cwd()
WORKSPACE_ROOT = PROJECT_ROOT.parent

workflow_hsmeta = PROJECT_ROOT / "src" / "app" / "workflow-actions" / "workflow-actions-hsmeta.json"
router_file = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "router.py"
route_file = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "workflow_actions.py"

if not workflow_hsmeta.exists():
    raise SystemExit(f"Could not find: {workflow_hsmeta}")

data = json.loads(workflow_hsmeta.read_text(encoding="utf-8"))
data["uid"] = "opslens_workflow_action"
data["type"] = "workflow-action"
data["config"] = {
    "actionUrl": "https://REPLACE_WITH_PUBLIC_HTTPS_URL/api/v1/workflow-actions/notify",
    "isPublished": True,
    "supportedClients": [
        {
            "client": "WORKFLOWS"
        }
    ],
    "objectTypes": ["CONTACT"],
    "inputFields": [
        {
            "typeDefinition": {
                "name": "severityOverride",
                "type": "enumeration",
                "fieldType": "select",
                "options": [
                    {"value": "use_settings", "label": "Use app settings"},
                    {"value": "critical", "label": "Critical"},
                    {"value": "high", "label": "High"},
                    {"value": "medium", "label": "Medium"}
                ]
            },
            "supportedValueTypes": ["STATIC_VALUE"],
            "isRequired": True
        },
        {
            "typeDefinition": {
                "name": "analystNote",
                "type": "string",
                "fieldType": "textarea"
            },
            "supportedValueTypes": ["STATIC_VALUE"],
            "isRequired": False
        }
    ],
    "labels": {
        "en": {
            "appDisplayName": "OpsLens AI",
            "actionName": "Send OpsLens alert",
            "actionDescription": "Send an OpsLens alert event to the external service.",
            "actionCardContent": "Send OpsLens alert with {{severityOverride}} threshold",
            "inputFieldLabels": {
                "severityOverride": "Severity override",
                "analystNote": "Analyst note"
            },
            "inputFieldDescriptions": {
                "severityOverride": "Choose whether to use the saved app threshold or force a severity.",
                "analystNote": "Optional note to include in the alert event."
            }
        }
    }
}
workflow_hsmeta.write_text(json.dumps(data, indent=2), encoding="utf-8")

route_file.parent.mkdir(parents=True, exist_ok=True)
route_file.write_text(textwrap.dedent("""
from datetime import datetime, timezone
from pathlib import Path
import json

from fastapi import APIRouter, Request

router = APIRouter(prefix="/workflow-actions", tags=["workflow-actions"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "workflow_action_events.jsonl"


@router.post("/notify")
async def notify(request: Request):
    payload = await request.json()

    event = {
        "receivedAtUtc": datetime.now(timezone.utc).isoformat(),
        "source": "hubspot-workflow-action",
        "payload": payload,
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    return {
        "status": "ok",
        "message": "Workflow action event captured by OpsLens AI.",
        "loggedTo": str(LOG_FILE),
        "receivedAtUtc": event["receivedAtUtc"],
    }
""").lstrip("\n"), encoding="utf-8")

router_file.write_text(textwrap.dedent("""
from fastapi import APIRouter

from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.record_risk import router as record_risk_router
from app.api.v1.routes.settings_store import router as settings_store_router
from app.api.v1.routes.webhooks import router as webhook_router
from app.api.v1.routes.workflow_actions import router as workflow_actions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhook_router)
api_router.include_router(dashboard_router)
api_router.include_router(settings_store_router)
api_router.include_router(record_risk_router)
api_router.include_router(workflow_actions_router)
""").lstrip("\n"), encoding="utf-8")

print("OpsLens step 9 scaffold created successfully.")
print(f"Project root: {PROJECT_ROOT}")
print(f"Workspace root: {WORKSPACE_ROOT}")
print()
print("Updated / created files:")
print(f" - {workflow_hsmeta}")
print(f" - {route_file}")
print(f" - {router_file}")
