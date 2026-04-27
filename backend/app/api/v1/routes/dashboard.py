from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, func, select

from app.db import get_session, init_db
from app.models.alert import STATUS_OPEN, STATUS_RESOLVED, Alert
from app.models.alert_event import AlertEvent
from app.models.property_change_event import PropertyChangeEvent
from app.models.property_snapshot import PropertySnapshot
from app.models.workflow_change_event import WorkflowChangeEvent
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.hubspot_ticket_visibility import load_ticket_visibility
from app.services.portal_entitlements import get_portal_entitlement, portal_is_entitled
from app.services.portal_settings import (
    SEVERITY_ORDER,
    load_portal_settings,
    normalize_severity,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ACTION_REQUIRED_SEVERITIES = ("critical", "high")
WATCHING_SEVERITY = "medium"


def _resolved_level(row: AlertEvent, threshold: str) -> str:
    override = str(row.severity_override or "").strip().lower()
    if override in ("", "use_settings"):
        return threshold
    return normalize_severity(override, threshold)


def _visible(level: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(level, 0) >= SEVERITY_ORDER.get(threshold, 0)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _alert_title(alert: Alert) -> str:
    rewritten = str(alert.plain_english_explanation or "").strip()
    if rewritten:
        return rewritten
    return str(alert.title or "").strip()


def _alert_payload(alert: Alert) -> dict:
    return {
        "id": str(alert.id),
        "severity": str(alert.severity or "").lower(),
        "title": _alert_title(alert),
        "sourceEventType": alert.source_event_type,
        "impactedWorkflowId": alert.impacted_workflow_id,
        "impactedWorkflowName": alert.impacted_workflow_name,
        "sourceDependencyId": alert.source_dependency_id,
        "sourceObjectTypeId": alert.source_object_type_id,
        "createdAtUtc": _isoformat(alert.created_at),
    }


def _portal_filtered(stmt, model, portal_id: str):
    if portal_id:
        return stmt.where(model.portal_id == portal_id)
    return stmt


def _count_alerts(session, portal_id: str, *filters) -> int:
    stmt = select(func.count()).select_from(Alert)
    stmt = _portal_filtered(stmt, Alert, portal_id)
    for clause in filters:
        stmt = stmt.where(clause)
    return int(session.scalar(stmt) or 0)


def _alert_rows(session, portal_id: str, *filters, limit: int = 5) -> list[Alert]:
    stmt = select(Alert)
    stmt = _portal_filtered(stmt, Alert, portal_id)
    for clause in filters:
        stmt = stmt.where(clause)
    stmt = stmt.order_by(desc(Alert.created_at)).limit(limit)
    return list(session.execute(stmt).scalars().all())


def _latest_timestamp(session, portal_id: str, model, column):
    stmt = select(func.max(column))
    stmt = _portal_filtered(stmt, model, portal_id)
    return session.scalar(stmt)


def _max_timestamp(*values):
    cleaned = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                continue
        if getattr(value, "tzinfo", None) is None:
            value = value.replace(tzinfo=timezone.utc)
        cleaned.append(value.astimezone(timezone.utc))
    if not cleaned:
        return None
    return max(cleaned)


def _action_summary(session, portal_id: str, settings: dict) -> dict:
    action_filter = func.lower(Alert.severity).in_(ACTION_REQUIRED_SEVERITIES)
    watching_filter = func.lower(Alert.severity) == WATCHING_SEVERITY

    action_rows = _alert_rows(
        session,
        portal_id,
        Alert.status == STATUS_OPEN,
        action_filter,
        limit=5,
    )
    watching_rows = _alert_rows(
        session,
        portal_id,
        Alert.status == STATUS_OPEN,
        watching_filter,
        limit=5,
    )

    resolved_cutoff = _utc_now() - timedelta(days=7)
    resolved_this_week_count = _count_alerts(
        session,
        portal_id,
        Alert.resolved_at.is_not(None),
        Alert.resolved_at >= resolved_cutoff,
    )

    last_poll = _max_timestamp(
        _latest_timestamp(session, portal_id, WorkflowSnapshot, WorkflowSnapshot.last_seen_at),
        _latest_timestamp(session, portal_id, PropertySnapshot, PropertySnapshot.last_seen_at),
        _latest_timestamp(session, portal_id, WorkflowChangeEvent, WorkflowChangeEvent.detected_at),
        _latest_timestamp(session, portal_id, PropertyChangeEvent, PropertyChangeEvent.detected_at),
    )

    return {
        "actionRequired": [_alert_payload(alert) for alert in action_rows],
        "watching": [_alert_payload(alert) for alert in watching_rows],
        "resolvedThisWeekCount": resolved_this_week_count,
        "actionRequiredCount": _count_alerts(
            session,
            portal_id,
            Alert.status == STATUS_OPEN,
            action_filter,
        ),
        "watchingCount": _count_alerts(
            session,
            portal_id,
            Alert.status == STATUS_OPEN,
            watching_filter,
        ),
        "lastPollUtc": _isoformat(last_poll),
        "slackConnected": bool(str(settings.get("slackWebhookUrl") or "").strip()),
    }


def _empty_action_summary(settings: dict | None = None) -> dict:
    settings = settings or {}
    return {
        "actionRequired": [],
        "watching": [],
        "resolvedThisWeekCount": 0,
        "actionRequiredCount": 0,
        "watchingCount": 0,
        "lastPollUtc": None,
        "slackConnected": bool(str(settings.get("slackWebhookUrl") or "").strip()),
    }


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
                **_empty_action_summary(settings),
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
                **_action_summary(session, portal_id, settings),
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


@router.post("/alerts/{alert_id}/resolve")
def resolve_dashboard_alert(alert_id: str, request: Request):
    query = request.query_params
    portal_id = str(query.get("portalId", "")).strip()

    try:
        cleaned_alert_id = int(str(alert_id).strip())
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Alert not found.") from exc

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None or not portal_id:
        raise HTTPException(status_code=404, detail="Alert not found.")

    try:
        stmt = (
            select(Alert)
            .where(Alert.id == cleaned_alert_id)
            .where(Alert.portal_id == portal_id)
        )
        alert = session.execute(stmt).scalar_one_or_none()
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found.")

        if alert.resolved_at is None:
            alert.resolved_at = _utc_now()
        alert.status = STATUS_RESOLVED
        session.commit()
        session.refresh(alert)

        return {
            "status": "ok",
            "alertId": str(alert.id),
            "resolvedAtUtc": _isoformat(alert.resolved_at),
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
