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
