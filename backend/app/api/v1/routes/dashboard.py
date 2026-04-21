from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent
from app.services.hubspot_ticket_visibility import load_ticket_visibility
from app.services.portal_entitlements import get_portal_entitlement, portal_is_entitled
from app.services.portal_settings import (
    SEVERITY_ORDER,
    load_portal_settings,
    normalize_severity,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _resolved_level(row: AlertEvent, threshold: str) -> str:
    override = str(row.severity_override or "").strip().lower()
    if override in ("", "use_settings"):
        return threshold
    return normalize_severity(override, threshold)


def _visible(level: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(level, 0) >= SEVERITY_ORDER.get(threshold, 0)


@router.get("/overview")
def dashboard_overview(request: Request):
    query = request.query_params

    portal_id = str(query.get("portalId", "")).strip()
    user_id = str(query.get("userId", "")).strip()
    user_email = str(query.get("userEmail", "")).strip()
    app_id = str(query.get("appId", "")).strip()

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        settings = load_portal_settings(None, portal_id)
        entitlement = get_portal_entitlement(None, portal_id)
        return {
            "status": "ok",
            "app": "OpsLens AI",
            "connectedBackend": True,
            "settings": settings,
            "entitlement": entitlement,
            "summary": {
                "openIncidents": 0,
                "criticalIssues": 0,
                "monitoredWorkflows": 0,
                "lastCheckedUtc": None,
                "activeIncidents": [],
            },
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
        entitlement = get_portal_entitlement(session, portal_id)
        threshold = normalize_severity(settings.get("alertThreshold"), "high")

        stmt = select(AlertEvent).where(AlertEvent.result == "accepted")
        if portal_id:
            stmt = stmt.where(AlertEvent.portal_id == portal_id)

        stmt = stmt.order_by(desc(AlertEvent.received_at_utc))
        rows = session.execute(stmt).scalars().all()

        monitored_workflows = len(
            {str(row.workflow_id) for row in rows if str(row.workflow_id or "").strip()}
        )

        visible_rows = []
        for row in rows:
            level = _resolved_level(row, threshold)
            if _visible(level, threshold):
                visible_rows.append((row, level))

        critical_issues = sum(1 for _, level in visible_rows if level == "critical")

        active_incidents = []
        for row, level in visible_rows[:5]:
            workflow_id_text = str(row.workflow_id).strip() if row.workflow_id is not None else "unknown"
            object_label = str(row.object_type or "record").strip()
            object_id = str(row.object_id or "").strip()

            active_incidents.append(
                {
                    "id": row.callback_id or f"alert-{row.id}",
                    "severity": level,
                    "title": f"Workflow {workflow_id_text} alert",
                    "affectedRecords": 1,
                    "recommendation": row.analyst_note or f"Review the latest saved alert for {object_label} {object_id}.",
                }
            )

        last_checked = rows[0].received_at_utc.isoformat() if rows and rows[0].received_at_utc else None

        return {
            "status": "ok",
            "app": "OpsLens AI",
            "connectedBackend": True,
            "settings": settings,
            "entitlement": entitlement,
            "summary": {
                "openIncidents": len(visible_rows),
                "criticalIssues": critical_issues,
                "monitoredWorkflows": monitored_workflows,
                "lastCheckedUtc": last_checked,
                "activeIncidents": active_incidents,
            },
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": True,
                "savedAlertRows": len(rows),
                "visibleRowsAtThreshold": len(visible_rows),
                "settingsStorage": settings.get("storage", "unknown"),
            },
        }
    finally:
        session.close()


@router.get("/ticket-automation")
def dashboard_ticket_automation(request: Request):
    query = request.query_params

    portal_id = str(query.get("portalId", "")).strip()
    raw_limit = str(query.get("limit", "4")).strip()

    try:
        limit = int(raw_limit or "4")
    except Exception:
        limit = 4

    if not portal_id:
        return {
            "status": "error",
            "message": "portalId is required.",
            "entitlement": get_portal_entitlement(None, portal_id),
            "provisioned": False,
            "total": 0,
            "results": [],
        }

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        return {
            "status": "ok",
            "portalId": portal_id,
            "entitlement": get_portal_entitlement(None, portal_id),
            "provisioned": False,
            "reason": "Database is not configured.",
            "total": 0,
            "results": [],
        }

    try:
        entitlement = get_portal_entitlement(session, portal_id)
    finally:
        session.close()

    if not portal_is_entitled(entitlement):
        return {
            "status": "ok",
            "portalId": portal_id,
            "entitlement": entitlement,
            "provisioned": False,
            "reason": "Portal activation is blocked until the subscription is active or trial-approved.",
            "total": 0,
            "results": [],
        }

    try:
        payload = load_ticket_visibility(
            portal_id=portal_id,
            limit=max(1, min(limit, 20)),
        )
        payload["entitlement"] = entitlement
        return payload
    except Exception as exc:
        return {
            "status": "ok",
            "portalId": portal_id,
            "entitlement": entitlement,
            "provisioned": False,
            "reason": str(exc),
            "total": 0,
            "results": [],
        }
