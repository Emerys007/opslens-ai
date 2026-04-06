from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/recent")
def recent_alerts(request: Request, limit: int = 10):
    safe_limit = max(1, min(limit, 25))
    portal_id = request.query_params.get("portalId")

    if not init_db():
        return {
            "status": "ok",
            "dbConfigured": False,
            "alerts": [],
        }

    session = get_session()
    if session is None:
        return {
            "status": "ok",
            "dbConfigured": False,
            "alerts": [],
        }

    try:
        stmt = select(AlertEvent)

        if portal_id:
            stmt = stmt.where(AlertEvent.portal_id == str(portal_id))

        stmt = stmt.order_by(desc(AlertEvent.received_at_utc)).limit(safe_limit)
        rows = session.execute(stmt).scalars().all()

        alerts = []
        for row in rows:
            alerts.append(
                {
                    "id": row.id,
                    "receivedAtUtc": row.received_at_utc.isoformat() if row.received_at_utc else None,
                    "callbackId": row.callback_id,
                    "portalId": row.portal_id,
                    "workflowId": row.workflow_id,
                    "objectType": row.object_type,
                    "objectId": row.object_id,
                    "severityOverride": row.severity_override,
                    "analystNote": row.analyst_note,
                    "result": row.result,
                    "reason": row.reason,
                }
            )

        return {
            "status": "ok",
            "dbConfigured": True,
            "count": len(alerts),
            "alerts": alerts,
        }
    finally:
        session.close()
