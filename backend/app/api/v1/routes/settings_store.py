
from pathlib import Path
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/settings-store", tags=["settings-store"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "portal_settings.json"

DEFAULT_SETTINGS = {
    "slackWebhookUrl": "",
    "alertThreshold": "high",
    "criticalWorkflows": "",
}


def _read_all_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


def _write_all_settings(data: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@router.get("")
async def get_settings(request: Request):
    query = dict(request.query_params)
    portal_id = query.get("portalId")
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required")

    all_settings = _read_all_settings()
    current = all_settings.get(portal_id, DEFAULT_SETTINGS.copy())

    return {
        "status": "ok",
        "portalId": portal_id,
        "settings": current,
        "loadedAtUtc": datetime.now(timezone.utc).isoformat(),
    }


@router.post("")
async def save_settings(request: Request):
    query = dict(request.query_params)
    portal_id = query.get("portalId")
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required")

    body = await request.json()

    settings = {
        "slackWebhookUrl": str(body.get("slackWebhookUrl", "")).strip(),
        "alertThreshold": str(body.get("alertThreshold", "high")).strip() or "high",
        "criticalWorkflows": str(body.get("criticalWorkflows", "")).strip(),
    }

    all_settings = _read_all_settings()
    all_settings[portal_id] = settings
    _write_all_settings(all_settings)

    return {
        "status": "ok",
        "portalId": portal_id,
        "settings": settings,
        "savedAtUtc": datetime.now(timezone.utc).isoformat(),
    }
