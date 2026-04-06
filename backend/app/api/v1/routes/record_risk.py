from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent
from app.services.portal_settings import (
    SEVERITY_ORDER,
    load_portal_settings,
    normalize_severity,
)

router = APIRouter(prefix="/records", tags=["records"])


def _severity_visible_at_threshold(level: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(level, 0) >= SEVERITY_ORDER.get(threshold, 0)


def _object_type_candidates(object_type_id: str) -> list[str]:
    value = str(object_type_id or "").strip()
    if value == "0-1":
        return ["CONTACT", "0-1"]
    return [value] if value else ["CONTACT", "0-1"]


@router.get("/contact-risk")
def contact_risk(request: Request):
    query = request.query_params

    record_id = str(query.get("recordId", "")).strip()
    object_type_id = str(query.get("objectTypeId", "0-1")).strip() or "0-1"
    portal_id = str(query.get("portalId", "")).strip()
    user_id = str(query.get("userId", "")).strip()
    user_email = str(query.get("userEmail", "")).strip()
    app_id = str(query.get("appId", "")).strip()

    if not record_id:
        return {
            "status": "error",
            "message": "recordId is required.",
        }

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        settings = load_portal_settings(None, portal_id)
        threshold = normalize_severity(settings.get("alertThreshold"), "high")

        return {
            "status": "ok",
            "record": {
                "recordId": record_id,
                "objectTypeId": object_type_id,
            },
            "settings": settings,
            "risk": {
                "level": "unknown",
                "incidentTitle": "Database unavailable",
                "recommendation": "Check DATABASE_URL and database connectivity.",
            },
            "visibility": {
                "threshold": threshold,
                "visible": False,
            },
            "latestAlert": None,
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": False,
            },
        }

    try:
        settings = load_portal_settings(session, portal_id)
        threshold = normalize_severity(settings.get("alertThreshold"), "high")

        stmt = (
            select(AlertEvent)
            .where(AlertEvent.object_id == record_id)
            .where(AlertEvent.object_type.in_(_object_type_candidates(object_type_id)))
            .where(AlertEvent.result == "accepted")
        )

        if portal_id:
            stmt = stmt.where(AlertEvent.portal_id == portal_id)

        stmt = stmt.order_by(desc(AlertEvent.received_at_utc)).limit(1)
        row = session.execute(stmt).scalars().first()

        if row is None:
            return {
                "status": "ok",
                "record": {
                    "recordId": record_id,
                    "objectTypeId": object_type_id,
                },
                "settings": settings,
                "risk": {
                    "level": "none",
                    "incidentTitle": "No saved OpsLens alert for this record",
                    "recommendation": "Run the workflow action for this contact, then refresh the card.",
                },
                "visibility": {
                    "threshold": threshold,
                    "visible": False,
                },
                "latestAlert": None,
                "debug": {
                    "portalId": portal_id or "not-provided",
                    "userId": user_id or "not-provided",
                    "userEmail": user_email or "not-provided",
                    "appId": app_id or "not-provided",
                    "dbConfigured": True,
                    "settingsStorage": settings.get("storage", "unknown"),
                },
            }

        override = str(row.severity_override or "").strip().lower()
        resolved_level = threshold if override in ("", "use_settings") else normalize_severity(override, threshold)
        visible = _severity_visible_at_threshold(resolved_level, threshold)

        latest_alert = {
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

        return {
            "status": "ok",
            "record": {
                "recordId": record_id,
                "objectTypeId": object_type_id,
            },
            "settings": settings,
            "risk": {
                "level": resolved_level,
                "incidentTitle": "Latest saved OpsLens alert",
                "recommendation": row.analyst_note or "Review the latest workflow execution details.",
            },
            "visibility": {
                "threshold": threshold,
                "visible": visible,
            },
            "latestAlert": latest_alert,
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": True,
                "settingsStorage": settings.get("storage", "unknown"),
            },
        }
    finally:
        session.close()
