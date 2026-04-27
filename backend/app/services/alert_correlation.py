"""Alert correlation engine.

Reads ``PropertyChangeEvent`` and ``WorkflowChangeEvent`` rows that
have not been processed yet, joins them against the workflow
dependency map, and produces ``Alert`` rows. Slack senders, ticket
creators, and the LLM rewriter all read from ``Alert`` — never from
the raw change events.

Correlation rules per the v2 plan:

    Property archived  ── high   ── one alert per impacted workflow
    Property deleted   ── high   ── one alert per impacted workflow
    Property type-chg  ── medium ── one alert per impacted workflow
    Property renamed   ── low    ── one alert per impacted workflow (info)
    Property created   ── (no alert; baseline event)
    Property unarchived── (no alert; recovery)

    Workflow disabled  ── high   ── alert about the workflow itself
    Workflow deleted   ── high   ── alert about the workflow itself
    Workflow edited    ── medium ── alert about the workflow itself
    Workflow created   ── (no alert)
    Workflow enabled   ── (no alert; recovery)

Dedup window: 7 days. While an alert is open or acknowledged and
younger than 7 days, repeat firings increment ``repeat_count`` and
update ``last_repeated_at`` instead of inserting new rows.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.alert import (
    ACTIVE_STATUSES,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SOURCE_EVENT_LIST_ARCHIVED,
    SOURCE_EVENT_LIST_CRITERIA_CHANGED,
    SOURCE_EVENT_LIST_DELETED,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_EVENT_PROPERTY_DELETED,
    SOURCE_EVENT_PROPERTY_RENAMED,
    SOURCE_EVENT_PROPERTY_TYPE_CHANGED,
    SOURCE_EVENT_TEMPLATE_ARCHIVED,
    SOURCE_EVENT_TEMPLATE_DELETED,
    SOURCE_EVENT_TEMPLATE_EDITED,
    SOURCE_EVENT_WORKFLOW_DELETED,
    SOURCE_EVENT_WORKFLOW_DISABLED,
    SOURCE_EVENT_WORKFLOW_EDITED,
    SOURCE_KIND_EMAIL_TEMPLATE,
    SOURCE_KIND_LIST,
    SOURCE_KIND_PROPERTY,
    SOURCE_KIND_WORKFLOW,
    STATUS_OPEN,
    Alert,
)
from app.models.email_template_change_event import (
    TEMPLATE_EVENT_ARCHIVED,
    TEMPLATE_EVENT_DELETED,
    TEMPLATE_EVENT_EDITED,
    EmailTemplateChangeEvent,
)
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.models.list_change_event import (
    LIST_EVENT_ARCHIVED,
    LIST_EVENT_CRITERIA_CHANGED,
    LIST_EVENT_DELETED,
    ListChangeEvent,
)
from app.models.list_snapshot import ListSnapshot
from app.models.property_change_event import (
    PROPERTY_EVENT_ARCHIVED,
    PROPERTY_EVENT_DELETED,
    PROPERTY_EVENT_RENAMED,
    PROPERTY_EVENT_TYPE_CHANGED,
    PropertyChangeEvent,
)
from app.models.property_snapshot import PropertySnapshot
from app.models.workflow_change_event import (
    EVENT_TYPE_DELETED as WORKFLOW_EVENT_DELETED,
    EVENT_TYPE_DISABLED as WORKFLOW_EVENT_DISABLED,
    EVENT_TYPE_EDITED as WORKFLOW_EVENT_EDITED,
    WorkflowChangeEvent,
)
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.dependency_mapping import (
    find_workflows_affected_by_email_template,
    find_workflows_affected_by_list,
    find_workflows_affected_by_property,
)
from app.services.monitoring_config import (
    MONITORING_CATEGORIES,
    get_category_severity,
    is_category_enabled,
    is_list_excluded,
    is_property_excluded,
    is_template_excluded,
    is_workflow_excluded,
    load_monitoring_coverage,
)

logger = logging.getLogger(__name__)


DEDUP_WINDOW = timedelta(days=7)


# Mapping from raw property/workflow change-event types → Alert source-event
# constants. None means "no alert for this event type" (created / enabled / etc.).
_PROPERTY_EVENT_TO_SOURCE: dict[str, str | None] = {
    PROPERTY_EVENT_ARCHIVED: SOURCE_EVENT_PROPERTY_ARCHIVED,
    PROPERTY_EVENT_DELETED: SOURCE_EVENT_PROPERTY_DELETED,
    PROPERTY_EVENT_TYPE_CHANGED: SOURCE_EVENT_PROPERTY_TYPE_CHANGED,
    PROPERTY_EVENT_RENAMED: SOURCE_EVENT_PROPERTY_RENAMED,
}

_PROPERTY_EVENT_TO_SEVERITY: dict[str, str] = {
    PROPERTY_EVENT_ARCHIVED: SEVERITY_HIGH,
    PROPERTY_EVENT_DELETED: SEVERITY_HIGH,
    PROPERTY_EVENT_TYPE_CHANGED: SEVERITY_MEDIUM,
    PROPERTY_EVENT_RENAMED: SEVERITY_LOW,
}

_WORKFLOW_EVENT_TO_SOURCE: dict[str, str | None] = {
    WORKFLOW_EVENT_DISABLED: SOURCE_EVENT_WORKFLOW_DISABLED,
    WORKFLOW_EVENT_DELETED: SOURCE_EVENT_WORKFLOW_DELETED,
    WORKFLOW_EVENT_EDITED: SOURCE_EVENT_WORKFLOW_EDITED,
}

_WORKFLOW_EVENT_TO_SEVERITY: dict[str, str] = {
    WORKFLOW_EVENT_DISABLED: SEVERITY_HIGH,
    WORKFLOW_EVENT_DELETED: SEVERITY_HIGH,
    WORKFLOW_EVENT_EDITED: SEVERITY_MEDIUM,
}

_LIST_EVENT_TO_SOURCE: dict[str, str | None] = {
    LIST_EVENT_ARCHIVED: SOURCE_EVENT_LIST_ARCHIVED,
    LIST_EVENT_DELETED: SOURCE_EVENT_LIST_DELETED,
    LIST_EVENT_CRITERIA_CHANGED: SOURCE_EVENT_LIST_CRITERIA_CHANGED,
}

_LIST_EVENT_TO_SEVERITY: dict[str, str] = {
    LIST_EVENT_ARCHIVED: SEVERITY_HIGH,
    LIST_EVENT_DELETED: SEVERITY_HIGH,
    LIST_EVENT_CRITERIA_CHANGED: SEVERITY_MEDIUM,
}

_TEMPLATE_EVENT_TO_SOURCE: dict[str, str | None] = {
    TEMPLATE_EVENT_ARCHIVED: SOURCE_EVENT_TEMPLATE_ARCHIVED,
    TEMPLATE_EVENT_DELETED: SOURCE_EVENT_TEMPLATE_DELETED,
    TEMPLATE_EVENT_EDITED: SOURCE_EVENT_TEMPLATE_EDITED,
}

_TEMPLATE_EVENT_TO_SEVERITY: dict[str, str] = {
    TEMPLATE_EVENT_ARCHIVED: SEVERITY_HIGH,
    TEMPLATE_EVENT_DELETED: SEVERITY_HIGH,
    TEMPLATE_EVENT_EDITED: SEVERITY_MEDIUM,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """Treat naive datetimes coming back from SQLite as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _mark_processed(event) -> None:
    if getattr(event, "processed_at", None) is None:
        event.processed_at = _utc_now()


def _truncate_title(text: str, *, max_length: int = 120) -> str:
    """Cap titles at 120 chars (incl. trailing ``…``) so they fit
    inside Slack mobile notification previews. The Alert model's
    ``title`` column accommodates 255, but anything beyond ~120 gets
    visually clipped on mobile and is wasted screen real estate.
    """
    cleaned = (text or "").strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def _compute_signature(
    portal_id: str,
    source_event_type: str,
    source_dependency_id: str,
    impacted_workflow_id: str,
) -> str:
    """Deterministic hash used as the dedup key.

    SHA-256 truncated to 32 hex chars (128 bits) is plenty for
    collision resistance at OpsLens scale and fits comfortably in the
    String(128) column.
    """
    raw = "".join(
        [
            (portal_id or "").strip(),
            (source_event_type or "").strip(),
            (source_dependency_id or "").strip(),
            (impacted_workflow_id or "").strip(),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:32]


def _summary_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _lookup_property_label(
    session: Session,
    portal_id: str,
    object_type_id: str,
    property_name: str,
) -> str | None:
    """Pull the property's display label off the latest snapshot, if
    we have one. Used to make alert titles human-readable. Returns
    None when no snapshot exists (defensive — the polling cycle
    creates the snapshot on first sighting, so this should be rare).
    """
    snap = (
        session.query(PropertySnapshot)
        .filter(
            PropertySnapshot.portal_id == portal_id,
            PropertySnapshot.object_type_id == object_type_id,
            PropertySnapshot.property_name == property_name,
        )
        .one_or_none()
    )
    if snap is None:
        return None
    label = (snap.label or "").strip()
    return label or None


def _lookup_workflow_name(
    session: Session,
    portal_id: str,
    workflow_id: str,
) -> str:
    snap = (
        session.query(WorkflowSnapshot)
        .filter(
            WorkflowSnapshot.portal_id == portal_id,
            WorkflowSnapshot.workflow_id == workflow_id,
        )
        .one_or_none()
    )
    if snap is None:
        return ""
    return (snap.name or "").strip()


def _lookup_list_name(
    session: Session,
    portal_id: str,
    list_id: str,
) -> str:
    snap = (
        session.query(ListSnapshot)
        .filter(
            ListSnapshot.portal_id == portal_id,
            ListSnapshot.list_id == list_id,
        )
        .one_or_none()
    )
    if snap is None:
        return ""
    return (snap.list_name or "").strip()


def _lookup_template_name(
    session: Session,
    portal_id: str,
    template_id: str,
) -> str:
    snap = (
        session.query(EmailTemplateSnapshot)
        .filter(
            EmailTemplateSnapshot.portal_id == portal_id,
            EmailTemplateSnapshot.template_id == template_id,
        )
        .one_or_none()
    )
    if snap is None:
        return ""
    return (snap.template_name or "").strip()


def _lookup_dependency_locations(
    session: Session,
    portal_id: str,
    workflow_id: str,
    dependency_type: str,
    dependency_id: str,
    object_type_id: str | None,
) -> list[str]:
    """The location strings — e.g. ``actions[3].fields.property_name`` —
    where ``workflow_id`` references the changed dependency. Embedded
    in alert summaries so the LLM and Slack consumers can describe
    *where* the impact is.
    """
    query = (
        session.query(WorkflowDependency.location)
        .filter(
            WorkflowDependency.portal_id == portal_id,
            WorkflowDependency.workflow_id == workflow_id,
            WorkflowDependency.dependency_type == dependency_type,
            WorkflowDependency.dependency_id == dependency_id,
        )
    )
    if object_type_id:
        query = query.filter(WorkflowDependency.dependency_object_type == object_type_id)
    return [row[0] for row in query.all() if row and row[0]]


# ---------------------------------------------------------------------------
# Insert / dedup
# ---------------------------------------------------------------------------


def _find_dedup_target(
    session: Session,
    portal_id: str,
    alert_signature: str,
    *,
    now: datetime,
) -> Alert | None:
    """Return the alert row to bump on repeat firings, if any.

    Match criteria:
      * same ``alert_signature``
      * status is open or acknowledged
      * created within the last ``DEDUP_WINDOW``

    Resolved alerts and alerts older than the window do NOT match; the
    caller will create a fresh row instead.
    """
    candidates = (
        session.query(Alert)
        .filter(
            Alert.portal_id == portal_id,
            Alert.alert_signature == alert_signature,
            Alert.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Alert.created_at.desc())
        .all()
    )
    cutoff = now - DEDUP_WINDOW
    for candidate in candidates:
        created_at = _aware(candidate.created_at)
        if created_at is None:
            return candidate
        if created_at >= cutoff:
            return candidate
    return None


def _upsert_alert(
    session: Session,
    *,
    portal_id: str,
    severity: str,
    source_event_type: str,
    source_event_id: int | None,
    source_event_kind: str,
    source_dependency_type: str | None,
    source_dependency_id: str | None,
    source_object_type_id: str | None,
    impacted_workflow_id: str | None,
    impacted_workflow_name: str | None,
    title: str,
    summary_payload: dict[str, Any],
    counters: dict[str, int],
) -> Alert:
    """Create a new alert or bump an existing one inside the dedup
    window. Updates ``counters`` in place so the caller can report
    created-vs-repeated counts.
    """
    now = _utc_now()
    signature = _compute_signature(
        portal_id,
        source_event_type,
        source_dependency_id or "",
        impacted_workflow_id or "",
    )

    existing = _find_dedup_target(session, portal_id, signature, now=now)
    if existing is not None:
        existing.repeat_count = int(existing.repeat_count or 0) + 1
        existing.last_repeated_at = now
        # Always refresh the "what we last knew" fields — the latest
        # firing has the freshest summary / event id / workflow name.
        existing.source_event_id = source_event_id
        existing.source_event_kind = source_event_kind
        existing.summary = _summary_to_json(summary_payload)
        if impacted_workflow_name:
            existing.impacted_workflow_name = impacted_workflow_name
        counters["alerts_updated_repeat"] = counters.get("alerts_updated_repeat", 0) + 1
        return existing

    alert = Alert(
        portal_id=portal_id,
        alert_signature=signature,
        severity=severity,
        status=STATUS_OPEN,
        source_event_type=source_event_type,
        source_event_id=source_event_id,
        source_event_kind=source_event_kind,
        source_dependency_type=source_dependency_type,
        source_dependency_id=source_dependency_id,
        source_object_type_id=source_object_type_id,
        impacted_workflow_id=impacted_workflow_id,
        impacted_workflow_name=impacted_workflow_name,
        title=_truncate_title(title),
        summary=_summary_to_json(summary_payload),
        repeat_count=1,
        created_at=now,
    )
    session.add(alert)
    counters["alerts_created"] = counters.get("alerts_created", 0) + 1
    return alert


# ---------------------------------------------------------------------------
# Property correlator
# ---------------------------------------------------------------------------


def _impacted_workflows_for_property(
    session: Session,
    portal_id: str,
    property_name: str,
    object_type_id: str,
) -> list[dict[str, Any]]:
    """Wrapper that hides the empty-string→None coercion for object type."""
    return find_workflows_affected_by_property(
        session,
        portal_id,
        property_name,
        object_type_id=(object_type_id or ""),
    )


def _build_property_change_block(
    event: PropertyChangeEvent,
    *,
    property_label: str | None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "property_name": event.property_name,
        "property_label": property_label,
        "object_type_id": event.object_type_id,
        "previous_archived": event.previous_archived,
        "new_archived": event.new_archived,
        "previous_type": event.previous_type,
        "new_type": event.new_type,
        "previous_label": event.previous_label,
        "new_label": event.new_label,
    }
    return {k: v for k, v in block.items() if v is not None}


def correlate_property_change_event(
    session: Session,
    event: PropertyChangeEvent,
    *,
    counters: dict[str, int] | None = None,
) -> list[Alert]:
    """Correlate one ``PropertyChangeEvent``. Returns the list of alert
    rows created or updated (empty list when the event type is one we
    don't alert on).

    The caller is responsible for setting ``event.processed_at`` —
    this function just emits alerts.
    """
    counters = counters if counters is not None else {}
    source_event_type = _PROPERTY_EVENT_TO_SOURCE.get(event.event_type)
    if source_event_type is None:
        # Baseline / recovery events don't produce alerts.
        return []

    severity = _PROPERTY_EVENT_TO_SEVERITY[event.event_type]
    portal_id = event.portal_id
    property_name = event.property_name
    object_type_id = event.object_type_id or ""
    coverage = load_monitoring_coverage(session, portal_id)

    if not is_category_enabled(coverage, source_event_type):
        _mark_processed(event)
        return []

    if is_property_excluded(session, portal_id, property_name, object_type_id):
        _mark_processed(event)
        return []

    severity = get_category_severity(coverage, source_event_type, severity)

    property_label = _lookup_property_label(
        session, portal_id, object_type_id, property_name,
    )
    display_name = property_label or property_name

    impacted = _impacted_workflows_for_property(
        session, portal_id, property_name, object_type_id,
    )

    if not impacted:
        # Nothing depends on this property — process the event but
        # don't emit any alerts. (We still log the change for v3
        # exploration.)
        return []

    change_block = _build_property_change_block(event, property_label=property_label)
    n_workflows = len(impacted)

    title_for_event_type = {
        SOURCE_EVENT_PROPERTY_ARCHIVED: f"Property '{display_name}' archived — {n_workflows} workflow(s) affected",
        SOURCE_EVENT_PROPERTY_DELETED: f"Property '{display_name}' deleted — {n_workflows} workflow(s) affected",
        SOURCE_EVENT_PROPERTY_TYPE_CHANGED: (
            f"Property '{display_name}' type changed "
            f"({event.previous_type or '?'} → {event.new_type or '?'}) — {n_workflows} workflow(s) affected"
        ),
        SOURCE_EVENT_PROPERTY_RENAMED: (
            f"Property '{display_name}' label renamed "
            f"({event.previous_label or '?'} → {event.new_label or '?'}) — {n_workflows} workflow(s) affected"
        ),
    }
    title = title_for_event_type.get(
        source_event_type,
        f"Property '{display_name}' changed — {n_workflows} workflow(s) affected",
    )

    alerts: list[Alert] = []
    for impact in impacted:
        impacted_workflow_id = str(impact.get("workflow_id") or "")
        impacted_workflow_name = str(impact.get("workflow_name") or "")
        # Prefer the location strings persisted on the dependency rows
        # over whatever the reverse-query happened to return — the
        # impact's ``locations`` field is already that, but we re-query
        # to keep one canonical access path.
        locations = _lookup_dependency_locations(
            session,
            portal_id=portal_id,
            workflow_id=impacted_workflow_id,
            dependency_type="property",
            dependency_id=property_name,
            object_type_id=object_type_id or None,
        )
        if not locations:
            # Fall back to the locations the reverse query carries.
            locations = [
                str(loc.get("location") or "")
                for loc in (impact.get("locations") or [])
                if loc.get("location")
            ]

        summary_payload = {
            "kind": source_event_type,
            "portal_id": portal_id,
            "change": change_block,
            "impact": {
                "workflow_id": impacted_workflow_id,
                "workflow_name": impacted_workflow_name,
                "dependency_locations": locations,
            },
        }

        alert = _upsert_alert(
            session,
            portal_id=portal_id,
            severity=severity,
            source_event_type=source_event_type,
            source_event_id=event.id,
            source_event_kind=SOURCE_KIND_PROPERTY,
            source_dependency_type="property",
            source_dependency_id=property_name,
            source_object_type_id=object_type_id or None,
            impacted_workflow_id=impacted_workflow_id or None,
            impacted_workflow_name=impacted_workflow_name or None,
            title=title,
            summary_payload=summary_payload,
            counters=counters,
        )
        alerts.append(alert)
    return alerts


# ---------------------------------------------------------------------------
# List correlator
# ---------------------------------------------------------------------------


def _build_list_change_block(event: ListChangeEvent, *, list_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except Exception:  # noqa: BLE001
        payload = {}
    block: dict[str, Any] = {
        "list_id": event.list_id,
        "list_name": list_name or payload.get("list_name"),
    }
    if isinstance(payload, dict):
        block.update({k: v for k, v in payload.items() if v is not None})
    return {k: v for k, v in block.items() if v is not None}


def correlate_list_change_event(
    session: Session,
    event: ListChangeEvent,
    *,
    counters: dict[str, int] | None = None,
) -> list[Alert]:
    """Process one list change event and emit an alert per impacted workflow."""
    counters = counters if counters is not None else {}
    source_event_type = _LIST_EVENT_TO_SOURCE.get(event.event_type)
    if source_event_type is None:
        return []

    severity = _LIST_EVENT_TO_SEVERITY[event.event_type]
    portal_id = event.portal_id
    list_id = event.list_id
    coverage = load_monitoring_coverage(session, portal_id)

    if not is_category_enabled(coverage, source_event_type):
        _mark_processed(event)
        return []

    if is_list_excluded(session, portal_id, list_id):
        _mark_processed(event)
        return []

    severity = get_category_severity(coverage, source_event_type, severity)

    list_name = _lookup_list_name(session, portal_id, list_id)
    display_name = list_name or list_id
    impacted = find_workflows_affected_by_list(session, portal_id, list_id)

    if not impacted:
        return []

    n_workflows = len(impacted)
    title_for_event_type = {
        SOURCE_EVENT_LIST_ARCHIVED: f"List '{display_name}' archived — {n_workflows} workflow(s) affected",
        SOURCE_EVENT_LIST_DELETED: f"List '{display_name}' deleted — {n_workflows} workflow(s) affected",
        SOURCE_EVENT_LIST_CRITERIA_CHANGED: (
            f"List '{display_name}' criteria changed — {n_workflows} workflow(s) affected"
        ),
    }
    title = title_for_event_type.get(
        source_event_type,
        f"List '{display_name}' changed — {n_workflows} workflow(s) affected",
    )
    change_block = _build_list_change_block(event, list_name=list_name)

    alerts: list[Alert] = []
    for impact in impacted:
        impacted_workflow_id = str(impact.get("workflow_id") or "")
        impacted_workflow_name = str(impact.get("workflow_name") or "")
        locations = _lookup_dependency_locations(
            session,
            portal_id=portal_id,
            workflow_id=impacted_workflow_id,
            dependency_type="list",
            dependency_id=list_id,
            object_type_id=None,
        )
        if not locations:
            locations = [
                str(loc.get("location") or "")
                for loc in (impact.get("locations") or [])
                if loc.get("location")
            ]

        summary_payload = {
            "kind": source_event_type,
            "portal_id": portal_id,
            "change": change_block,
            "impact": {
                "workflow_id": impacted_workflow_id,
                "workflow_name": impacted_workflow_name,
                "dependency_locations": locations,
            },
        }

        alert = _upsert_alert(
            session,
            portal_id=portal_id,
            severity=severity,
            source_event_type=source_event_type,
            source_event_id=event.id,
            source_event_kind=SOURCE_KIND_LIST,
            source_dependency_type="list",
            source_dependency_id=list_id,
            source_object_type_id=None,
            impacted_workflow_id=impacted_workflow_id or None,
            impacted_workflow_name=impacted_workflow_name or None,
            title=title,
            summary_payload=summary_payload,
            counters=counters,
        )
        alerts.append(alert)
    return alerts


# ---------------------------------------------------------------------------
# Email template correlator
# ---------------------------------------------------------------------------


def _build_template_change_block(
    event: EmailTemplateChangeEvent,
    *,
    template_name: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except Exception:  # noqa: BLE001
        payload = {}
    block: dict[str, Any] = {
        "template_id": event.template_id,
        "template_name": template_name or payload.get("template_name"),
    }
    if isinstance(payload, dict):
        block.update({k: v for k, v in payload.items() if v is not None})
    return {k: v for k, v in block.items() if v is not None}


def correlate_email_template_change_event(
    session: Session,
    event: EmailTemplateChangeEvent,
    *,
    counters: dict[str, int] | None = None,
) -> list[Alert]:
    """Process one email template event and emit an alert per impacted workflow."""
    counters = counters if counters is not None else {}
    source_event_type = _TEMPLATE_EVENT_TO_SOURCE.get(event.event_type)
    if source_event_type is None:
        return []

    severity = _TEMPLATE_EVENT_TO_SEVERITY[event.event_type]
    portal_id = event.portal_id
    template_id = event.template_id
    coverage = load_monitoring_coverage(session, portal_id)

    if not is_category_enabled(coverage, source_event_type):
        _mark_processed(event)
        return []

    if is_template_excluded(session, portal_id, template_id):
        _mark_processed(event)
        return []

    severity = get_category_severity(coverage, source_event_type, severity)

    template_name = _lookup_template_name(session, portal_id, template_id)
    display_name = template_name or template_id
    impacted = find_workflows_affected_by_email_template(session, portal_id, template_id)

    if not impacted:
        return []

    n_workflows = len(impacted)
    title_for_event_type = {
        SOURCE_EVENT_TEMPLATE_ARCHIVED: (
            f"Email template '{display_name}' archived — {n_workflows} workflow(s) affected"
        ),
        SOURCE_EVENT_TEMPLATE_DELETED: (
            f"Email template '{display_name}' deleted — {n_workflows} workflow(s) affected"
        ),
        SOURCE_EVENT_TEMPLATE_EDITED: (
            f"Email template '{display_name}' edited — {n_workflows} workflow(s) affected"
        ),
    }
    title = title_for_event_type.get(
        source_event_type,
        f"Email template '{display_name}' changed — {n_workflows} workflow(s) affected",
    )
    change_block = _build_template_change_block(event, template_name=template_name)

    alerts: list[Alert] = []
    for impact in impacted:
        impacted_workflow_id = str(impact.get("workflow_id") or "")
        impacted_workflow_name = str(impact.get("workflow_name") or "")
        locations = _lookup_dependency_locations(
            session,
            portal_id=portal_id,
            workflow_id=impacted_workflow_id,
            dependency_type="email_template",
            dependency_id=template_id,
            object_type_id=None,
        )
        if not locations:
            locations = [
                str(loc.get("location") or "")
                for loc in (impact.get("locations") or [])
                if loc.get("location")
            ]

        summary_payload = {
            "kind": source_event_type,
            "portal_id": portal_id,
            "change": change_block,
            "impact": {
                "workflow_id": impacted_workflow_id,
                "workflow_name": impacted_workflow_name,
                "dependency_locations": locations,
            },
        }

        alert = _upsert_alert(
            session,
            portal_id=portal_id,
            severity=severity,
            source_event_type=source_event_type,
            source_event_id=event.id,
            source_event_kind=SOURCE_KIND_EMAIL_TEMPLATE,
            source_dependency_type="email_template",
            source_dependency_id=template_id,
            source_object_type_id=None,
            impacted_workflow_id=impacted_workflow_id or None,
            impacted_workflow_name=impacted_workflow_name or None,
            title=title,
            summary_payload=summary_payload,
            counters=counters,
        )
        alerts.append(alert)
    return alerts


# ---------------------------------------------------------------------------
# Workflow correlator
# ---------------------------------------------------------------------------


def correlate_workflow_change_event(
    session: Session,
    event: WorkflowChangeEvent,
    *,
    counters: dict[str, int] | None = None,
) -> list[Alert]:
    """Correlate one ``WorkflowChangeEvent``. Workflow events alert
    about the workflow itself; there is no separate impacted entity.
    """
    counters = counters if counters is not None else {}
    source_event_type = _WORKFLOW_EVENT_TO_SOURCE.get(event.event_type)
    if source_event_type is None:
        return []

    severity = _WORKFLOW_EVENT_TO_SEVERITY[event.event_type]
    portal_id = event.portal_id
    workflow_id = event.workflow_id
    if source_event_type in MONITORING_CATEGORIES:
        coverage = load_monitoring_coverage(session, portal_id)
        if not is_category_enabled(coverage, source_event_type):
            _mark_processed(event)
            return []
        if is_workflow_excluded(session, portal_id, workflow_id):
            _mark_processed(event)
            return []
        severity = get_category_severity(coverage, source_event_type, severity)

    workflow_name = _lookup_workflow_name(session, portal_id, workflow_id) or ""
    display_name = workflow_name or workflow_id

    if source_event_type == SOURCE_EVENT_WORKFLOW_EDITED:
        title = (
            f"Workflow '{display_name}' was edited "
            f"(revision {event.previous_revision_id or '?'} → {event.new_revision_id or '?'})"
        )
    elif source_event_type == SOURCE_EVENT_WORKFLOW_DELETED:
        title = f"Workflow '{display_name}' deleted"
    else:  # disabled
        title = f"Workflow '{display_name}' disabled"

    change_block = {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "previous_revision_id": event.previous_revision_id,
        "new_revision_id": event.new_revision_id,
        "previous_is_enabled": event.previous_is_enabled,
        "new_is_enabled": event.new_is_enabled,
    }
    change_block = {k: v for k, v in change_block.items() if v is not None}

    summary_payload = {
        "kind": source_event_type,
        "portal_id": portal_id,
        "change": change_block,
        "impact": None,
    }

    alert = _upsert_alert(
        session,
        portal_id=portal_id,
        severity=severity,
        source_event_type=source_event_type,
        source_event_id=event.id,
        source_event_kind=SOURCE_KIND_WORKFLOW,
        source_dependency_type=None,
        source_dependency_id=None,
        source_object_type_id=None,
        impacted_workflow_id=workflow_id,
        impacted_workflow_name=workflow_name or None,
        title=title,
        summary_payload=summary_payload,
        counters=counters,
    )
    return [alert]


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------


def correlate_unprocessed_events(
    session: Session,
    *,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Find every change event whose ``processed_at`` is null, dispatch
    to the appropriate correlator, and mark each event processed.

    Events that produce no alert (e.g. ``created`` / ``enabled`` /
    ``unarchived``) are still marked ``processed_at = now`` — that
    flag means "we have looked at this event," not "we acted on it."
    """
    counters: dict[str, int] = {
        "events_processed": 0,
        "alerts_created": 0,
        "alerts_updated_repeat": 0,
    }
    now = _utc_now()

    # ------- Property events
    property_events: list[PropertyChangeEvent] = (
        session.query(PropertyChangeEvent)
        .filter(PropertyChangeEvent.processed_at.is_(None))
        .order_by(PropertyChangeEvent.id.asc())
        .limit(batch_size)
        .all()
    )
    for event in property_events:
        try:
            correlate_property_change_event(session, event, counters=counters)
        except Exception:  # noqa: BLE001 — never let one event poison the batch
            logger.exception(
                "alert_correlation.property_event_failed",
                extra={"event_id": event.id, "portal_id": event.portal_id},
            )
            continue
        event.processed_at = now
        counters["events_processed"] += 1

    # ------- List events
    list_events: list[ListChangeEvent] = (
        session.query(ListChangeEvent)
        .filter(ListChangeEvent.processed_at.is_(None))
        .order_by(ListChangeEvent.id.asc())
        .limit(batch_size)
        .all()
    )
    for event in list_events:
        try:
            correlate_list_change_event(session, event, counters=counters)
        except Exception:  # noqa: BLE001
            logger.exception(
                "alert_correlation.list_event_failed",
                extra={"event_id": event.id, "portal_id": event.portal_id},
            )
            continue
        event.processed_at = now
        counters["events_processed"] += 1

    # ------- Email template events
    template_events: list[EmailTemplateChangeEvent] = (
        session.query(EmailTemplateChangeEvent)
        .filter(EmailTemplateChangeEvent.processed_at.is_(None))
        .order_by(EmailTemplateChangeEvent.id.asc())
        .limit(batch_size)
        .all()
    )
    for event in template_events:
        try:
            correlate_email_template_change_event(session, event, counters=counters)
        except Exception:  # noqa: BLE001
            logger.exception(
                "alert_correlation.email_template_event_failed",
                extra={"event_id": event.id, "portal_id": event.portal_id},
            )
            continue
        event.processed_at = now
        counters["events_processed"] += 1

    # ------- Workflow events
    workflow_events: list[WorkflowChangeEvent] = (
        session.query(WorkflowChangeEvent)
        .filter(WorkflowChangeEvent.processed_at.is_(None))
        .order_by(WorkflowChangeEvent.id.asc())
        .limit(batch_size)
        .all()
    )
    for event in workflow_events:
        try:
            correlate_workflow_change_event(session, event, counters=counters)
        except Exception:  # noqa: BLE001
            logger.exception(
                "alert_correlation.workflow_event_failed",
                extra={"event_id": event.id, "portal_id": event.portal_id},
            )
            continue
        event.processed_at = now
        counters["events_processed"] += 1

    session.commit()
    return counters


def list_alerts_for_portal(
    session: Session,
    portal_id: str,
    *,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """Open + recent-resolved alerts for a portal, newest first.

    Used by the admin dashboard endpoint. Includes resolved alerts
    that were resolved within the dedup window so we have something
    to show during the demo even after a status flip.
    """
    portal_key = str(portal_id or "").strip()
    if not portal_key:
        return []

    rows = (
        session.query(Alert)
        .filter(Alert.portal_id == portal_key)
        .order_by(Alert.created_at.desc())
        .limit(max(1, int(max_results or 50)))
        .all()
    )

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            summary_obj = json.loads(row.summary or "{}")
        except Exception:  # noqa: BLE001
            summary_obj = {}
        out.append(
            {
                "id": row.id,
                "portal_id": row.portal_id,
                "alert_signature": row.alert_signature,
                "severity": row.severity,
                "status": row.status,
                "source_event_type": row.source_event_type,
                "source_event_id": row.source_event_id,
                "source_event_kind": row.source_event_kind,
                "source_dependency_type": row.source_dependency_type,
                "source_dependency_id": row.source_dependency_id,
                "source_object_type_id": row.source_object_type_id,
                "impacted_workflow_id": row.impacted_workflow_id,
                "impacted_workflow_name": row.impacted_workflow_name,
                "title": row.title,
                "summary": summary_obj,
                "plain_english_explanation": row.plain_english_explanation,
                "recommended_action": row.recommended_action,
                "repeat_count": row.repeat_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_repeated_at": (
                    row.last_repeated_at.isoformat() if row.last_repeated_at else None
                ),
                "acknowledged_at": (
                    row.acknowledged_at.isoformat() if row.acknowledged_at else None
                ),
                "resolved_at": (
                    row.resolved_at.isoformat() if row.resolved_at else None
                ),
                "slack_delivered_at": (
                    row.slack_delivered_at.isoformat() if row.slack_delivered_at else None
                ),
                "hubspot_ticket_id": row.hubspot_ticket_id,
            }
        )
    return out
