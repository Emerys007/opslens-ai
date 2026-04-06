from fastapi import APIRouter, Request

from app.db import get_session, init_db
from app.services.portal_settings import load_portal_settings, save_portal_settings

router = APIRouter(prefix="/settings-store", tags=["settings-store"])


@router.get("")
def get_settings(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        return {
            "status": "ok",
            "portalId": portal_id or "not-provided",
            "settings": load_portal_settings(None, portal_id),
            "dbConfigured": False,
        }

    try:
        return {
            "status": "ok",
            "portalId": portal_id or "not-provided",
            "settings": load_portal_settings(session, portal_id),
            "dbConfigured": True,
        }
    finally:
        session.close()


@router.post("")
async def save_settings(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    payload = await request.json()

    if not portal_id:
        return {
            "status": "error",
            "message": "portalId is required.",
        }

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        return {
            "status": "error",
            "message": "Database is not configured.",
        }

    try:
        settings = save_portal_settings(session, portal_id, payload)
        return {
            "status": "ok",
            "portalId": portal_id,
            "settings": settings,
            "dbConfigured": True,
        }
    finally:
        session.close()
