from pathlib import Path
import textwrap

PROJECT_ROOT = Path.cwd()
WORKSPACE_ROOT = PROJECT_ROOT.parent

route_file = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "workflow_actions.py"
router_file = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "router.py"

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

print("OpsLens step 9 fix applied successfully.")
print(f"Project root: {PROJECT_ROOT}")
print(f"Workspace root: {WORKSPACE_ROOT}")
print()
print("Updated files:")
print(f" - {route_file}")
print(f" - {router_file}")
