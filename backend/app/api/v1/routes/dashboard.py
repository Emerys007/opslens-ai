from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import case, desc, func, select

from app.db import get_session, init_db
from app.models.alert import STATUS_OPEN, STATUS_RESOLVED, Alert
from app.models.alert_event import AlertEvent
from app.models.monitoring_exclusion import (
    EXCLUSION_TYPE_PROPERTY,
    EXCLUSION_TYPE_WORKFLOW,
    MonitoringExclusion,
)
from app.models.portal_setting import PortalSetting
from app.models.property_change_event import PropertyChangeEvent
from app.models.property_snapshot import PropertySnapshot
from app.models.workflow_change_event import WorkflowChangeEvent
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.hubspot_ticket_visibility import load_ticket_visibility
from app.services.monitoring_config import (
    MONITORING_CATEGORIES,
    VALID_SEVERITY_OVERRIDES,
    category_metadata,
    load_monitoring_coverage,
    merge_monitoring_coverage_update,
)
from app.services.portal_entitlements import get_portal_entitlement, portal_is_entitled
from app.services.portal_settings import (
    SEVERITY_ORDER,
    load_portal_settings,
    normalize_severity,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ACTION_REQUIRED_SEVERITIES = ("critical", "high")
WATCHING_SEVERITY = "medium"
VALID_EXCLUSION_TYPES = (EXCLUSION_TYPE_WORKFLOW, EXCLUSION_TYPE_PROPERTY)
VALID_ACTION_PAGE_SIZES = (3, 5, 10, 25, 50)


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


def _alert_rows(
    session,
    portal_id: str,
    *filters,
    limit: int = 5,
    offset: int = 0,
    order_by=None,
) -> list[Alert]:
    stmt = select(Alert)
    stmt = _portal_filtered(stmt, Alert, portal_id)
    for clause in filters:
        stmt = stmt.where(clause)
    for ordering in (order_by or (desc(Alert.created_at),)):
        stmt = stmt.order_by(ordering)
    if offset:
        stmt = stmt.offset(offset)
    stmt = stmt.limit(limit)
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


def _parse_int_param(value, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _action_page_size(value) -> int:
    parsed = _parse_int_param(value, 10)
    return parsed if parsed in VALID_ACTION_PAGE_SIZES else 10


def _action_page(value) -> int:
    parsed = _parse_int_param(value, 1)
    return parsed if parsed >= 1 else 1


def _action_required_ordering():
    severity_rank = case(
        (func.lower(Alert.severity) == "critical", 0),
        (func.lower(Alert.severity) == "high", 1),
        else_=2,
    )
    return (severity_rank, desc(Alert.created_at))


def _action_summary(
    session,
    portal_id: str,
    settings: dict,
    *,
    action_page_size: int = 10,
    action_page: int = 1,
) -> dict:
    action_filter = func.lower(Alert.severity).in_(ACTION_REQUIRED_SEVERITIES)
    watching_filter = func.lower(Alert.severity) == WATCHING_SEVERITY
    action_offset = (action_page - 1) * action_page_size

    action_rows = _alert_rows(
        session,
        portal_id,
        Alert.status == STATUS_OPEN,
        action_filter,
        limit=action_page_size,
        offset=action_offset,
        order_by=_action_required_ordering(),
    )
    watching_rows = _alert_rows(
        session,
        portal_id,
        Alert.status == STATUS_OPEN,
        watching_filter,
        limit=10,
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


def _coverage_response(portal_id: str, coverage: dict) -> dict:
    return {
        "status": "ok",
        "portalId": portal_id,
        "coverage": coverage,
        "categories": category_metadata(coverage),
    }


def _validate_monitoring_coverage_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be an object.")

    sanitized = {}
    for category, config in payload.items():
        if category not in MONITORING_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail=f"{category} must be an object.")

        allowed_keys = {"enabled", "severityOverride"}
        unknown_keys = set(config.keys()) - allowed_keys
        if unknown_keys:
            joined = ", ".join(sorted(str(key) for key in unknown_keys))
            raise HTTPException(status_code=400, detail=f"Unknown field(s): {joined}")

        next_config = {}
        if "enabled" in config:
            if not isinstance(config["enabled"], bool):
                raise HTTPException(
                    status_code=400,
                    detail=f"{category}.enabled must be a boolean.",
                )
            next_config["enabled"] = config["enabled"]

        if "severityOverride" in config:
            override = config["severityOverride"]
            if override is None:
                next_config["severityOverride"] = None
            else:
                normalized = str(override).strip().lower()
                if normalized not in VALID_SEVERITY_OVERRIDES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid severityOverride for {category}.",
                    )
                next_config["severityOverride"] = normalized

        sanitized[category] = next_config
    return sanitized


def _exclusion_payload(row: MonitoringExclusion) -> dict:
    return {
        "id": row.id,
        "portalId": row.portal_id,
        "type": row.exclusion_type,
        "exclusionId": row.exclusion_id,
        "objectTypeId": row.object_type_id,
        "reason": row.reason,
        "createdAtUtc": _isoformat(row.created_at),
        "createdByUserId": row.created_by_user_id,
    }


def _exclusion_exists(
    session,
    *,
    portal_id: str,
    exclusion_type: str,
    exclusion_id: str,
    object_type_id: str | None,
) -> bool:
    stmt = select(MonitoringExclusion).where(
        MonitoringExclusion.portal_id == portal_id,
        MonitoringExclusion.exclusion_type == exclusion_type,
        MonitoringExclusion.exclusion_id == exclusion_id,
    )
    if object_type_id is None:
        stmt = stmt.where(MonitoringExclusion.object_type_id.is_(None))
    else:
        stmt = stmt.where(MonitoringExclusion.object_type_id == object_type_id)
    return session.execute(stmt).scalar_one_or_none() is not None


@router.get("/overview")
def dashboard_overview(request: Request):
    query = request.query_params

    portal_id = str(query.get("portalId", "")).strip()
    user_id = str(query.get("userId", "")).strip()
    user_email = str(query.get("userEmail", "")).strip()
    app_id = str(query.get("appId", "")).strip()
    action_page_size = _action_page_size(query.get("actionPageSize", "10"))
    action_page = _action_page(query.get("actionPage", "1"))

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
                **_action_summary(
                    session,
                    portal_id,
                    settings,
                    action_page_size=action_page_size,
                    action_page=action_page,
                ),
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


@router.get("/monitoring-coverage")
def get_monitoring_coverage(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return _coverage_response(portal_id, load_monitoring_coverage(None, portal_id))

    try:
        return _coverage_response(portal_id, load_monitoring_coverage(session, portal_id))
    finally:
        session.close()


@router.put("/monitoring-coverage")
def put_monitoring_coverage(payload: dict, request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")
    sanitized = _validate_monitoring_coverage_payload(payload)

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")

    try:
        row = session.get(PortalSetting, portal_id)
        if row is None:
            row = PortalSetting(portal_id=portal_id)
            session.add(row)
        row.monitoring_coverage = merge_monitoring_coverage_update(
            getattr(row, "monitoring_coverage", None),
            sanitized,
        )
        session.commit()
        session.refresh(row)
        coverage = load_monitoring_coverage(session, portal_id)
        return _coverage_response(portal_id, coverage)
    finally:
        session.close()


@router.get("/exclusions")
def list_monitoring_exclusions(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    exclusion_type = str(request.query_params.get("type", "")).strip().lower()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")
    if exclusion_type and exclusion_type not in VALID_EXCLUSION_TYPES:
        raise HTTPException(status_code=400, detail="type must be workflow or property.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return []

    try:
        stmt = (
            select(MonitoringExclusion)
            .where(MonitoringExclusion.portal_id == portal_id)
            .order_by(desc(MonitoringExclusion.created_at), desc(MonitoringExclusion.id))
        )
        if exclusion_type:
            stmt = stmt.where(MonitoringExclusion.exclusion_type == exclusion_type)
        return [_exclusion_payload(row) for row in session.execute(stmt).scalars().all()]
    finally:
        session.close()


@router.post("/exclusions")
def create_monitoring_exclusion(payload: dict, request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    user_id = str(request.query_params.get("userId", "")).strip() or None
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be an object.")

    exclusion_type = str(payload.get("type", "")).strip().lower()
    exclusion_id = str(payload.get("id", "")).strip()
    object_type_id = str(payload.get("objectTypeId", "")).strip() or None
    reason = str(payload.get("reason", "")).strip() or None

    if exclusion_type not in VALID_EXCLUSION_TYPES:
        raise HTTPException(status_code=400, detail="type must be workflow or property.")
    if not exclusion_id:
        raise HTTPException(status_code=400, detail="id is required.")
    if exclusion_type == EXCLUSION_TYPE_PROPERTY and not object_type_id:
        raise HTTPException(
            status_code=400,
            detail="objectTypeId is required for property exclusions.",
        )
    if exclusion_type == EXCLUSION_TYPE_WORKFLOW:
        object_type_id = None

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")

    try:
        if _exclusion_exists(
            session,
            portal_id=portal_id,
            exclusion_type=exclusion_type,
            exclusion_id=exclusion_id,
            object_type_id=object_type_id,
        ):
            raise HTTPException(status_code=409, detail="Exclusion already exists.")

        row = MonitoringExclusion(
            portal_id=portal_id,
            exclusion_type=exclusion_type,
            exclusion_id=exclusion_id,
            object_type_id=object_type_id,
            reason=reason,
            created_by_user_id=user_id,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _exclusion_payload(row)
    finally:
        session.close()


@router.delete("/exclusions/{exclusion_id}")
def delete_monitoring_exclusion(exclusion_id: int, request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        raise HTTPException(status_code=404, detail="Exclusion not found.")

    try:
        row = (
            session.execute(
                select(MonitoringExclusion)
                .where(MonitoringExclusion.id == exclusion_id)
                .where(MonitoringExclusion.portal_id == portal_id)
            )
            .scalar_one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Exclusion not found.")
        session.delete(row)
        session.commit()
        return {"status": "ok", "exclusionId": exclusion_id}
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
