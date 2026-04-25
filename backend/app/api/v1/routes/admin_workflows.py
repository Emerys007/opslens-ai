from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path

from app.config import settings
from app.db import get_session
from app.services.workflow_polling import poll_portal_workflows
from app.services.workflow_polling_scheduler import run_polling_cycle

router = APIRouter()


def _require_admin_key(supplied: str | None) -> None:
    expected = str(settings.maintenance_api_key or "").strip()
    if not expected:
        # Fail closed: if no key is configured the endpoint is effectively
        # disabled. This matches the pattern in ticket_maintenance.py
        # where an unset key blocks access in production. Operators must
        # explicitly set MAINTENANCE_API_KEY to enable manual triggers.
        raise HTTPException(status_code=503, detail="Admin API key is not configured.")
    if str(supplied or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid admin key.")


@router.post("/admin/workflows/poll/{portal_id}")
def trigger_workflow_poll(
    portal_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Manually trigger a workflow poll for a single portal.

    Authenticated via the `X-OpsLens-Admin-Key` request header against
    `settings.maintenance_api_key`.
    """
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise HTTPException(status_code=400, detail="portal_id is required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        try:
            return poll_portal_workflows(session, portal_key)
        except Exception:  # noqa: BLE001
            session.rollback()
            raise
    finally:
        session.close()


@router.post("/admin/workflows/poll")
async def trigger_workflow_poll_all(
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Manually trigger a polling cycle across every active portal.

    Same auth as the per-portal endpoint. Uses the same code path as the
    background scheduler so the manual trigger and automatic loop never
    diverge.
    """
    _require_admin_key(x_opslens_admin_key)
    return await run_polling_cycle(get_session)
