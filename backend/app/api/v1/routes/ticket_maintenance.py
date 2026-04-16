import os

from fastapi import APIRouter, Header, HTTPException, Query

from app.services.hubspot_ticket_auto_resolve import auto_resolve_waiting_tickets

router = APIRouter()


def _expected_key() -> str:
    return os.getenv("OPSLENS_MAINTENANCE_KEY", "").strip()


@router.post("/auto-resolve")
def run_auto_resolve(
    quiet_hours: int = Query(default=24, ge=1, le=720),
    max_records: int = Query(default=100, ge=1, le=200),
    x_opslens_maintenance_key: str | None = Header(default=None),
):
    expected = _expected_key()
    if expected:
        supplied = str(x_opslens_maintenance_key or "").strip()
        if supplied != expected:
            raise HTTPException(status_code=401, detail="Invalid maintenance key.")

    return auto_resolve_waiting_tickets(
        quiet_hours=quiet_hours,
        max_records=max_records,
    )