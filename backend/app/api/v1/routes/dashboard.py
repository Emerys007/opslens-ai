import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import case, desc, func, select

from app.core.security import require_hubspot_portal_request
from app.db import get_session, init_db
from app.models.alert import (
    SOURCE_EVENT_WORKFLOW_DISABLED,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Alert,
)
from app.models.alert_event import AlertEvent
from app.models.email_template_change_event import EmailTemplateChangeEvent
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.models.list_change_event import ListChangeEvent
from app.models.list_snapshot import ListSnapshot
from app.models.monitoring_exclusion import (
    EXCLUSION_TYPE_LIST,
    EXCLUSION_TYPE_PROPERTY,
    EXCLUSION_TYPE_TEMPLATE,
    EXCLUSION_TYPE_WORKFLOW,
    MonitoringExclusion,
)
from app.models.owner_change_event import OwnerChangeEvent
from app.models.owner_snapshot import OwnerSnapshot
from app.models.hubspot_installation import HubSpotInstallation
from app.models.marketplace_install_session import MarketplaceInstallSession
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
from app.services.alert_correlation import correlate_unprocessed_events
from app.services.dependency_mapping import (
    find_workflows_affected_by_email_template,
    find_workflows_affected_by_list,
    find_workflows_affected_by_owner,
    find_workflows_affected_by_property,
)
from app.services.email_template_polling import poll_portal_email_templates
from app.services.list_polling import poll_portal_lists
from app.services.owner_polling import poll_portal_owners
from app.services.property_polling import poll_portal_properties
from app.services.portal_entitlements import get_portal_entitlement, portal_is_entitled
from app.services.portal_settings import (
    SEVERITY_ORDER,
    load_portal_settings,
    normalize_severity,
)
from app.services.hubspot_oauth import get_portal_access_token
from app.services.install_diagnostic import (
    install_diagnostic_not_run_summary,
    run_install_diagnostic,
)
from app.services.remediation_guidance import fix_guidance_for
from app.services.slack_delivery import send_test_slack_message
from app.services.slack_oauth import SlackOAuthError, build_slack_authorize_url
from app.services.workflow_remediation import (
    WorkflowRemediationError,
    reenable_workflow,
)
from app.services.workflow_polling import poll_portal_workflows

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_hubspot_portal_request)],
)

ACTION_REQUIRED_SEVERITIES = ("critical", "high")
WATCHING_SEVERITY = "medium"
VALID_EXCLUSION_TYPES = (
    EXCLUSION_TYPE_WORKFLOW,
    EXCLUSION_TYPE_PROPERTY,
    EXCLUSION_TYPE_LIST,
    EXCLUSION_TYPE_TEMPLATE,
)
VALID_ACTION_PAGE_SIZES = (3, 5, 10, 25, 50)
HUBSPOT_PROPERTIES_URL = "https://api.hubapi.com/crm/v3/properties/{object_type}"
POLL_NOW_RATE_LIMIT_SECONDS = 30
_LAST_POLL_AT: dict[str, datetime] = {}
OBJECT_TYPE_ID_TO_PROPERTIES_PATH = {
    "0-1": "contacts",
    "0-2": "companies",
    "0-3": "deals",
    "0-5": "tickets",
}


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


def _dependency_locations(alert: Alert) -> list[str]:
    """Pull the 'where is the changed asset used' strings the correlator
    persisted on the alert summary (e.g. 'Enrollment trigger', 'If/then
    branch'). These power the blast-radius display. Returns [] when the
    summary is missing or malformed — never raises.
    """
    raw = getattr(alert, "summary", None)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    impact = payload.get("impact") if isinstance(payload, dict) else None
    if not isinstance(impact, dict):
        return []
    locations = impact.get("dependency_locations")
    if not isinstance(locations, list):
        return []
    return [str(loc) for loc in locations if str(loc).strip()]


def _alert_payload(alert: Alert) -> dict:
    return {
        "id": str(alert.id),
        "severity": str(alert.severity or "").lower(),
        "title": _alert_title(alert),
        "sourceEventType": alert.source_event_type,
        "impactedWorkflowId": alert.impacted_workflow_id,
        "impactedWorkflowName": alert.impacted_workflow_name,
        "recommendedAction": (str(alert.recommended_action).strip() or None)
        if alert.recommended_action
        else None,
        "fixGuidance": fix_guidance_for(alert.source_event_type),
        "dependencyLocations": _dependency_locations(alert),
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


def _event_count_from_poll_summary(summary: dict) -> int:
    return sum(
        int(summary.get(key) or 0)
        for key in (
            "createdEvents",
            "deletedEvents",
            "editedEvents",
            "enabledEvents",
            "disabledEvents",
            "archivedEvents",
            "unarchivedEvents",
            "typeChangedEvents",
            "renamedEvents",
            "criteriaChangedEvents",
            "deactivatedEvents",
            "reactivatedEvents",
        )
    )


def _hubspot_get_json(url: str, access_token: str) -> dict:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body) if body.strip() else {}


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
        _latest_timestamp(session, portal_id, ListSnapshot, ListSnapshot.last_seen_at),
        _latest_timestamp(
            session,
            portal_id,
            EmailTemplateSnapshot,
            EmailTemplateSnapshot.last_seen_at,
        ),
        _latest_timestamp(session, portal_id, OwnerSnapshot, OwnerSnapshot.last_seen_at),
        _latest_timestamp(session, portal_id, WorkflowChangeEvent, WorkflowChangeEvent.detected_at),
        _latest_timestamp(session, portal_id, PropertyChangeEvent, PropertyChangeEvent.detected_at),
        _latest_timestamp(session, portal_id, ListChangeEvent, ListChangeEvent.detected_at),
        _latest_timestamp(
            session,
            portal_id,
            EmailTemplateChangeEvent,
            EmailTemplateChangeEvent.detected_at,
        ),
        _latest_timestamp(session, portal_id, OwnerChangeEvent, OwnerChangeEvent.detected_at),
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


def _workflow_picker_payload(row: WorkflowSnapshot) -> dict:
    workflow_id = str(row.workflow_id or "").strip()
    return {
        "id": workflow_id,
        "name": str(row.name or "").strip() or workflow_id,
        "isEnabled": bool(row.is_enabled),
    }


def _list_picker_payload(row: ListSnapshot) -> dict:
    list_id = str(row.list_id or "").strip()
    return {
        "id": list_id,
        "name": str(row.list_name or "").strip() or list_id,
        "isArchived": bool(row.is_archived),
    }


def _template_picker_payload(row: EmailTemplateSnapshot) -> dict:
    template_id = str(row.template_id or "").strip()
    return {
        "id": template_id,
        "name": str(row.template_name or "").strip() or template_id,
        "subject": str(row.subject or "").strip(),
        "isArchived": bool(row.is_archived),
    }


def _property_picker_payload(row: dict) -> dict | None:
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    return {
        "name": name,
        "label": str(row.get("label") or "").strip() or name,
        "type": str(row.get("type") or "").strip(),
    }


def _properties_path_for_object_type(object_type_id: str) -> str:
    cleaned = str(object_type_id or "").strip()
    return OBJECT_TYPE_ID_TO_PROPERTIES_PATH.get(cleaned, cleaned)


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
        action = _action_summary(
            session,
            portal_id,
            settings,
            action_page_size=action_page_size,
            action_page=action_page,
        )

        # Top-line counts are sourced from the v2 Alert table (these fields
        # previously read the dead v1 AlertEvent table and read zero for a
        # pure v2 install). activeIncidents is superseded by `actionRequired`.
        open_filter = Alert.status == STATUS_OPEN
        open_incidents = _count_alerts(session, portal_id, open_filter)
        critical_issues = _count_alerts(
            session, portal_id, open_filter, func.lower(Alert.severity) == "critical"
        )
        monitored_workflows = int(
            session.execute(
                _portal_filtered(
                    select(func.count()).select_from(WorkflowSnapshot),
                    WorkflowSnapshot,
                    portal_id,
                )
            ).scalar()
            or 0
        )

        return {
            "status": "ok",
            "app": "OpsLens AI",
            "connectedBackend": True,
            "settings": settings,
            "entitlement": entitlement,
            "summary": {
                "openIncidents": open_incidents,
                "criticalIssues": critical_issues,
                "monitoredWorkflows": monitored_workflows,
                "lastCheckedUtc": action.get("lastPollUtc"),
                "activeIncidents": [],
                **action,
            },
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": True,
                "openAlerts": open_incidents,
                "settingsStorage": settings.get("storage", "unknown"),
            },
        }
    finally:
        session.close()


# Agency-tier multi-portal rollup --------------------------------------------

_AGENCY_PLANS = {"agency", "business", "enterprise"}
_PORTFOLIO_PORTAL_CAP = 50


def _partner_emails_for_portal(session, portal_id: str) -> set[str]:
    """The owner email identity(ies) of the SIGNED portal, derived server-side
    — never from a caller-supplied param. This is what scopes the agency
    rollup, so a caller can only ever see portals tied to the portal they're
    actually authenticated in."""
    emails: set[str] = set()
    install = session.get(HubSpotInstallation, portal_id)
    if install is not None:
        email = str(getattr(install, "installing_user_email", "") or "").strip().lower()
        if email:
            emails.add(email)
    for (email,) in session.execute(
        select(MarketplaceInstallSession.partner_user_email).where(
            MarketplaceInstallSession.hubspot_portal_id == portal_id
        )
    ).all():
        cleaned = str(email or "").strip().lower()
        if cleaned:
            emails.add(cleaned)
    return emails


def _find_portals_for_emails(session, emails: set[str]) -> list[str]:
    """Every portal owned by any of these (server-derived) partner emails."""
    if not emails:
        return []
    portal_ids: set[str] = set()
    for (pid,) in session.execute(
        select(HubSpotInstallation.portal_id).where(
            func.lower(HubSpotInstallation.installing_user_email).in_(emails),
            HubSpotInstallation.is_active.is_(True),
        )
    ).all():
        if pid:
            portal_ids.add(str(pid))
    for (pid,) in session.execute(
        select(MarketplaceInstallSession.hubspot_portal_id).where(
            func.lower(MarketplaceInstallSession.partner_user_email).in_(emails)
        )
    ).all():
        if pid:
            portal_ids.add(str(pid))
    return sorted(portal_ids)


def _portfolio_portal_summary(session, portal_id: str) -> dict:
    settings = load_portal_settings(session, portal_id)
    entitlement = get_portal_entitlement(session, portal_id)
    install = session.get(HubSpotInstallation, portal_id)
    action_filter = func.lower(Alert.severity).in_(ACTION_REQUIRED_SEVERITIES)
    watching_filter = func.lower(Alert.severity) == WATCHING_SEVERITY
    last_poll = _max_timestamp(
        _latest_timestamp(session, portal_id, WorkflowSnapshot, WorkflowSnapshot.last_seen_at),
        _latest_timestamp(session, portal_id, PropertySnapshot, PropertySnapshot.last_seen_at),
        _latest_timestamp(session, portal_id, ListSnapshot, ListSnapshot.last_seen_at),
        _latest_timestamp(
            session, portal_id, EmailTemplateSnapshot, EmailTemplateSnapshot.last_seen_at
        ),
        _latest_timestamp(session, portal_id, OwnerSnapshot, OwnerSnapshot.last_seen_at),
    )
    return {
        "portalId": portal_id,
        "hubDomain": str(getattr(install, "hub_domain", "") or ""),
        "plan": str(entitlement.get("plan") or ""),
        "active": bool(entitlement.get("active")),
        "actionRequiredCount": _count_alerts(
            session, portal_id, Alert.status == STATUS_OPEN, action_filter
        ),
        "watchingCount": _count_alerts(
            session, portal_id, Alert.status == STATUS_OPEN, watching_filter
        ),
        "lastPollUtc": _isoformat(last_poll),
        "slackConnected": bool(str(settings.get("slackWebhookUrl") or "").strip()),
    }


@router.get("/portfolio")
def dashboard_portfolio(request: Request):
    """Agency multi-portal rollup: aggregate alert counts across every portal
    the requesting partner manages. Cross-portal data is returned ONLY when the
    current portal is on an Agency-tier plan (the gated feature); otherwise just
    the current portal is returned with agencyEnabled=false."""
    query = request.query_params
    portal_id = str(query.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    empty = {
        "status": "ok",
        "agencyEnabled": False,
        "portals": [],
        "totals": {"portalCount": 0, "actionRequiredTotal": 0, "watchingTotal": 0},
    }
    if not init_db():
        return empty
    session = get_session()
    if session is None:
        return empty
    try:
        current_plan = str(
            get_portal_entitlement(session, portal_id).get("plan") or ""
        ).strip().lower()
        agency_enabled = current_plan in _AGENCY_PLANS

        if agency_enabled:
            # Scope strictly to the SIGNED portal's owner identity, derived
            # server-side — never trust a caller-supplied userEmail.
            emails = _partner_emails_for_portal(session, portal_id)
            portal_ids = _find_portals_for_emails(session, emails)
            if portal_id not in portal_ids:
                portal_ids.append(portal_id)
            portal_ids = sorted(set(portal_ids))[:_PORTFOLIO_PORTAL_CAP]
        else:
            portal_ids = [portal_id]

        summaries = [_portfolio_portal_summary(session, pid) for pid in portal_ids]
        return {
            "status": "ok",
            "agencyEnabled": agency_enabled,
            "portals": summaries,
            "totals": {
                "portalCount": len(summaries),
                "actionRequiredTotal": sum(s["actionRequiredCount"] for s in summaries),
                "watchingTotal": sum(s["watchingCount"] for s in summaries),
            },
        }
    finally:
        session.close()


@router.get("/slack/install-url")
def dashboard_slack_install_url(request: Request):
    """Return the Slack OAuth URL (incoming-webhook). State is signed for the
    authenticated portal, so the Slack callback can only attach the connection
    to this portal — no cross-tenant redirection."""
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")
    try:
        return {"status": "ok", "authorizationUrl": build_slack_authorize_url(portal_id)}
    except SlackOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/slack/status")
def dashboard_slack_status(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return {"status": "ok", "connected": False, "channel": "", "team": ""}
    try:
        row = session.get(PortalSetting, portal_id)
        webhook = str(getattr(row, "slack_webhook_url", "") or "").strip() if row else ""
        return {
            "status": "ok",
            "connected": bool(webhook),
            "channel": (str(getattr(row, "slack_channel_name", "") or "") if row else ""),
            "team": (str(getattr(row, "slack_team_name", "") or "") if row else ""),
        }
    finally:
        session.close()


@router.post("/slack/disconnect")
def dashboard_slack_disconnect(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        row = session.get(PortalSetting, portal_id)
        if row is not None:
            row.slack_webhook_url = ""
            row.slack_channel_name = ""
            row.slack_team_name = ""
            session.commit()
        return {"status": "ok", "connected": False}
    finally:
        session.close()


@router.post("/slack/test")
def dashboard_slack_test(request: Request):
    """Send a test message to the portal's connected Slack channel."""
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        ok, message = send_test_slack_message(session, portal_id)
        if not ok:
            raise HTTPException(status_code=400, detail=message)
        return {"status": "ok", "message": message}
    finally:
        session.close()


@router.get("/install-diagnostic")
def dashboard_install_diagnostic(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return {
            "status": "ok",
            "portalId": portal_id,
            "summary": install_diagnostic_not_run_summary(portal_id),
        }

    try:
        row = session.get(PortalSetting, portal_id)
        summary = (
            getattr(row, "install_diagnostic_summary", None)
            if row is not None
            else None
        )
        if not isinstance(summary, dict):
            summary = install_diagnostic_not_run_summary(portal_id)
        return {
            "status": "ok",
            "portalId": portal_id,
            "summary": summary,
        }
    finally:
        session.close()


@router.post("/install-diagnostic/run")
def dashboard_run_install_diagnostic(request: Request):
    """Re-run the on-install dependency scan on demand (force=True) and
    return the fresh summary. Synchronous — it polls HubSpot and rebuilds
    the dependency map, so it can take a little while.
    """
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")

    try:
        try:
            summary = run_install_diagnostic(portal_id, session, force=True)
        except Exception as exc:  # noqa: BLE001
            try:
                session.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(
                status_code=502,
                detail="The scan could not be completed. Please try again.",
            ) from exc
        return {
            "status": "ok",
            "portalId": portal_id,
            "summary": summary
            if isinstance(summary, dict)
            else install_diagnostic_not_run_summary(portal_id),
        }
    finally:
        session.close()


@router.post("/poll-now")
def dashboard_poll_now(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    now = _utc_now()
    previous = _LAST_POLL_AT.get(portal_id)
    if previous is not None:
        if getattr(previous, "tzinfo", None) is None:
            previous = previous.replace(tzinfo=timezone.utc)
        elapsed = (now - previous.astimezone(timezone.utc)).total_seconds()
        if elapsed < POLL_NOW_RATE_LIMIT_SECONDS:
            raise HTTPException(
                status_code=429,
                detail="Poll already requested recently.",
            )

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")

    _LAST_POLL_AT[portal_id] = now
    try:
        workflow_summary = poll_portal_workflows(session, portal_id)
        property_summary = poll_portal_properties(session, portal_id)
        list_summary = poll_portal_lists(session, portal_id)
        template_summary = poll_portal_email_templates(session, portal_id)
        owner_summary = poll_portal_owners(session, portal_id)
        correlation_summary = correlate_unprocessed_events(session)
        return {
            "status": "ok",
            "eventsDetected": _event_count_from_poll_summary(workflow_summary)
            + _event_count_from_poll_summary(property_summary)
            + _event_count_from_poll_summary(list_summary)
            + _event_count_from_poll_summary(template_summary)
            + _event_count_from_poll_summary(owner_summary),
            "alertsCreated": int(correlation_summary.get("alerts_created") or 0),
        }
    except Exception:
        _LAST_POLL_AT.pop(portal_id, None)
        try:
            session.rollback()
        except Exception:
            pass
        raise
    finally:
        session.close()


@router.get("/workflows")
def dashboard_workflows(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return []

    try:
        stmt = (
            select(WorkflowSnapshot)
            .where(WorkflowSnapshot.portal_id == portal_id)
            .order_by(func.lower(WorkflowSnapshot.name), WorkflowSnapshot.workflow_id)
            .limit(200)
        )
        return [_workflow_picker_payload(row) for row in session.execute(stmt).scalars().all()]
    finally:
        session.close()


@router.get("/lists")
def dashboard_lists(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return []

    try:
        stmt = (
            select(ListSnapshot)
            .where(ListSnapshot.portal_id == portal_id)
            .order_by(func.lower(ListSnapshot.list_name), ListSnapshot.list_id)
            .limit(200)
        )
        return [_list_picker_payload(row) for row in session.execute(stmt).scalars().all()]
    finally:
        session.close()


@router.get("/templates")
def dashboard_templates(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return []

    try:
        stmt = (
            select(EmailTemplateSnapshot)
            .where(EmailTemplateSnapshot.portal_id == portal_id)
            .order_by(
                func.lower(EmailTemplateSnapshot.template_name),
                EmailTemplateSnapshot.template_id,
            )
            .limit(200)
        )
        return [_template_picker_payload(row) for row in session.execute(stmt).scalars().all()]
    finally:
        session.close()


@router.get("/properties")
def dashboard_properties(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    object_type_id = str(request.query_params.get("objectTypeId", "")).strip()
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")
    if not object_type_id:
        raise HTTPException(status_code=400, detail="objectTypeId is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return []

    try:
        try:
            access_token = get_portal_access_token(session, portal_id)
        except Exception:
            return []

        object_type_path = _properties_path_for_object_type(object_type_id)
        url = HUBSPOT_PROPERTIES_URL.format(
            object_type=urllib.parse.quote(object_type_path, safe=""),
        )
        try:
            payload = _hubspot_get_json(url, access_token)
        except Exception:
            return []
        if not isinstance(payload, dict):
            return []
        rows = [
            normalized
            for item in payload.get("results", [])
            if isinstance(item, dict)
            for normalized in [_property_picker_payload(item)]
            if normalized is not None
        ]
        rows.sort(key=lambda item: (item["label"].lower(), item["name"].lower()))
        return rows[:500]
    finally:
        session.close()


_DEPENDENT_TYPES = {"property", "list", "template", "owner"}


def _dependents_response(portal_id, dep_type, dep_id, dependents, db_configured):
    return {
        "status": "ok",
        "portalId": portal_id,
        "type": dep_type,
        "dependencyId": dep_id,
        "dependents": dependents,
        "dependentCount": len(dependents),
        "dbConfigured": db_configured,
    }


@router.get("/dependents")
def dashboard_dependents(request: Request):
    """Read-only 'what depends on this?' lookup.

    HubSpot blocks deleting/archiving an asset that's still in use but
    won't show you *where* it's used — admins hunt through workflows by
    hand. This surfaces every workflow (and the location within it, e.g.
    'Enrollment trigger') that references the given property / list /
    email template / owner, straight from the cached dependency map. No
    HubSpot API call — purely the reverse index OpsLens already stores.
    """
    portal_id = str(request.query_params.get("portalId", "")).strip()
    dep_type = str(request.query_params.get("type", "")).strip().lower()
    dep_id = str(request.query_params.get("id", "")).strip()
    object_type_id = str(request.query_params.get("objectTypeId", "")).strip()

    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required.")
    if dep_type not in _DEPENDENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="type must be one of: property, list, template, owner.",
        )
    if not dep_id:
        raise HTTPException(status_code=400, detail="id is required.")

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None:
        return _dependents_response(portal_id, dep_type, dep_id, [], False)

    try:
        if dep_type == "property":
            matches = find_workflows_affected_by_property(
                session, portal_id, dep_id, object_type_id=object_type_id,
            )
        elif dep_type == "list":
            matches = find_workflows_affected_by_list(session, portal_id, dep_id)
        elif dep_type == "template":
            matches = find_workflows_affected_by_email_template(
                session, portal_id, dep_id,
            )
        else:  # owner
            matches = find_workflows_affected_by_owner(session, portal_id, dep_id)

        dependents = [
            {
                "workflowId": match.get("workflow_id"),
                "workflowName": match.get("workflow_name"),
                "locations": [
                    str(loc.get("location") or "")
                    for loc in (match.get("locations") or [])
                    if str(loc.get("location") or "").strip()
                ],
            }
            for match in matches
        ]
        return _dependents_response(portal_id, dep_type, dep_id, dependents, True)
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
        raise HTTPException(
            status_code=400,
            detail="type must be workflow, property, or list.",
        )

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
        raise HTTPException(
            status_code=400,
            detail="type must be workflow, property, or list.",
        )
    if not exclusion_id:
        raise HTTPException(status_code=400, detail="id is required.")
    if exclusion_type == EXCLUSION_TYPE_PROPERTY and not object_type_id:
        raise HTTPException(
            status_code=400,
            detail="objectTypeId is required for property exclusions.",
        )
    if exclusion_type == EXCLUSION_TYPE_WORKFLOW:
        object_type_id = None
    if exclusion_type in (EXCLUSION_TYPE_LIST, EXCLUSION_TYPE_TEMPLATE):
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


@router.post("/alerts/{alert_id}/reenable-workflow")
def dashboard_reenable_workflow(alert_id: str, request: Request):
    """One-click fix for a 'workflow disabled' alert: re-enable the workflow
    in HubSpot, then resolve the alert. This WRITES to the portal via the v4
    Automation API. Scoped to the signed portal; only valid for
    workflow_disabled alerts that carry an impacted workflow id.
    """
    portal_id = str(request.query_params.get("portalId", "")).strip()

    try:
        cleaned_alert_id = int(str(alert_id).strip())
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Alert not found.") from exc

    db_ready = init_db()
    session = get_session()
    if not db_ready or session is None or not portal_id:
        raise HTTPException(status_code=404, detail="Alert not found.")

    try:
        alert = session.execute(
            select(Alert)
            .where(Alert.id == cleaned_alert_id)
            .where(Alert.portal_id == portal_id)
        ).scalar_one_or_none()
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found.")

        if alert.source_event_type != SOURCE_EVENT_WORKFLOW_DISABLED:
            raise HTTPException(
                status_code=400,
                detail="Re-enable is only available for disabled-workflow alerts.",
            )
        workflow_id = str(alert.impacted_workflow_id or "").strip()
        if not workflow_id:
            raise HTTPException(
                status_code=400,
                detail="This alert has no workflow to re-enable.",
            )

        try:
            result = reenable_workflow(session, portal_id, workflow_id)
        except WorkflowRemediationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # The fix succeeded -> clear the alert.
        if alert.resolved_at is None:
            alert.resolved_at = _utc_now()
        alert.status = STATUS_RESOLVED
        session.commit()
        session.refresh(alert)

        return {
            "status": "ok",
            "alertId": str(alert.id),
            "workflowId": result.get("workflowId"),
            "isEnabled": result.get("isEnabled", True),
            "alreadyEnabled": result.get("alreadyEnabled", False),
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
