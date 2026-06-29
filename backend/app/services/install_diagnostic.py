from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.alert import (
    SEVERITY_HIGH,
    SOURCE_EVENT_LIST_ARCHIVED,
    SOURCE_EVENT_LIST_DELETED,
    SOURCE_EVENT_OWNER_DEACTIVATED,
    SOURCE_EVENT_OWNER_DELETED,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_EVENT_PROPERTY_DELETED,
    SOURCE_EVENT_TEMPLATE_ARCHIVED,
    SOURCE_EVENT_TEMPLATE_DELETED,
    SOURCE_KIND_INSTALL_DIAGNOSTIC,
    STATUS_OPEN,
    Alert,
)
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.models.list_snapshot import ListSnapshot
from app.models.owner_snapshot import OwnerSnapshot
from app.models.portal_setting import PortalSetting
from app.models.property_snapshot import PropertySnapshot
from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_EMAIL_TEMPLATE,
    DEPENDENCY_TYPE_LIST,
    DEPENDENCY_TYPE_OWNER,
    DEPENDENCY_TYPE_PROPERTY,
    WorkflowDependency,
)
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.alert_rewriter import rewrite_alert
from app.services.dependency_mapping import rebuild_workflow_dependencies
from app.services.email_template_polling import poll_portal_email_templates
from app.services.list_polling import poll_portal_lists
from app.services.owner_polling import poll_portal_owners
from app.services.plan_capabilities import plan_allows_category
from app.services.property_polling import poll_portal_properties
from app.services.workflow_polling import poll_portal_workflows

logger = logging.getLogger(__name__)

DIAGNOSTIC_KIND = "install_diagnostic_broken_dependency"
DIAGNOSTIC_STATUS_COMPLETED = "completed"
DIAGNOSTIC_STATUS_NOT_RUN = "not_run"

CHECKED_DEPENDENCY_TYPES = {
    DEPENDENCY_TYPE_PROPERTY,
    DEPENDENCY_TYPE_LIST,
    DEPENDENCY_TYPE_EMAIL_TEMPLATE,
    DEPENDENCY_TYPE_OWNER,
}

DEPENDENCY_LABELS = {
    DEPENDENCY_TYPE_PROPERTY: "property",
    DEPENDENCY_TYPE_LIST: "list",
    DEPENDENCY_TYPE_EMAIL_TEMPLATE: "email template",
    DEPENDENCY_TYPE_OWNER: "owner",
}

SOURCE_EVENT_BY_ISSUE = {
    (DEPENDENCY_TYPE_PROPERTY, "missing"): SOURCE_EVENT_PROPERTY_DELETED,
    (DEPENDENCY_TYPE_PROPERTY, "deleted"): SOURCE_EVENT_PROPERTY_DELETED,
    (DEPENDENCY_TYPE_PROPERTY, "archived"): SOURCE_EVENT_PROPERTY_ARCHIVED,
    (DEPENDENCY_TYPE_LIST, "missing"): SOURCE_EVENT_LIST_DELETED,
    (DEPENDENCY_TYPE_LIST, "deleted"): SOURCE_EVENT_LIST_DELETED,
    (DEPENDENCY_TYPE_LIST, "archived"): SOURCE_EVENT_LIST_ARCHIVED,
    (DEPENDENCY_TYPE_EMAIL_TEMPLATE, "missing"): SOURCE_EVENT_TEMPLATE_DELETED,
    (DEPENDENCY_TYPE_EMAIL_TEMPLATE, "deleted"): SOURCE_EVENT_TEMPLATE_DELETED,
    (DEPENDENCY_TYPE_EMAIL_TEMPLATE, "archived"): SOURCE_EVENT_TEMPLATE_ARCHIVED,
    (DEPENDENCY_TYPE_OWNER, "missing"): SOURCE_EVENT_OWNER_DELETED,
    (DEPENDENCY_TYPE_OWNER, "deleted"): SOURCE_EVENT_OWNER_DELETED,
    (DEPENDENCY_TYPE_OWNER, "inactive"): SOURCE_EVENT_OWNER_DEACTIVATED,
}


@dataclass(frozen=True)
class DependencyGroup:
    dependency_type: str
    dependency_id: str
    object_type_id: str
    workflow_id: str
    workflow_name: str
    locations: tuple[str, ...]


@dataclass(frozen=True)
class DependencyIssue:
    dependency_type: str
    dependency_id: str
    object_type_id: str
    workflow_id: str
    workflow_name: str
    locations: tuple[str, ...]
    issue_kind: str
    display_name: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def install_diagnostic_not_run_summary(portal_id: str) -> dict[str, Any]:
    return {
        "status": DIAGNOSTIC_STATUS_NOT_RUN,
        "portalId": str(portal_id or "").strip(),
        "ranAtUtc": None,
        "issuesFound": 0,
        "alertsCreated": 0,
        "alertsExisting": 0,
        "dependenciesChecked": 0,
        "issues": [],
    }


def _ensure_settings_row(session: Session, portal_id: str) -> PortalSetting:
    row = session.get(PortalSetting, portal_id)
    if row is None:
        row = PortalSetting(portal_id=portal_id)
        session.add(row)
        session.flush()
    return row


def _run_poll_step(
    session: Session,
    portal_id: str,
    name: str,
    poller: Callable[[Session, str], dict[str, Any]],
) -> dict[str, Any]:
    try:
        summary = poller(session, portal_id)
        if isinstance(summary, dict):
            return summary
        return {"status": "ok", "result": summary}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "install_diagnostic.poll_step_failed",
            extra={"portal_id": portal_id, "step": name, "error": repr(exc)},
        )
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {"status": "error", "reason": repr(exc)}


def _refresh_portal_inventory(session: Session, portal_id: str) -> dict[str, Any]:
    pollers: tuple[tuple[str, Callable[[Session, str], dict[str, Any]]], ...] = (
        ("workflows", poll_portal_workflows),
        ("properties", poll_portal_properties),
        ("lists", poll_portal_lists),
        ("emailTemplates", poll_portal_email_templates),
        ("owners", poll_portal_owners),
    )
    return {
        name: _run_poll_step(session, portal_id, name, poller)
        for name, poller in pollers
    }


def _ensure_cached_workflow_dependencies(
    session: Session,
    portal_id: str,
    *,
    force: bool,
) -> dict[str, Any]:
    existing_workflow_ids = {
        str(row[0] or "")
        for row in session.query(WorkflowDependency.workflow_id)
        .filter(WorkflowDependency.portal_id == portal_id)
        .distinct()
        .all()
    }
    snapshots = (
        session.query(WorkflowSnapshot)
        .filter(
            WorkflowSnapshot.portal_id == portal_id,
            WorkflowSnapshot.deleted_at.is_(None),
        )
        .order_by(WorkflowSnapshot.workflow_id.asc())
        .all()
    )

    rebuilt = 0
    extracted = 0
    failed = 0
    for snapshot in snapshots:
        workflow_id = str(snapshot.workflow_id or "").strip()
        if not workflow_id:
            continue
        if not str(snapshot.definition_json or "").strip():
            continue
        if not force and workflow_id in existing_workflow_ids:
            continue
        try:
            result = rebuild_workflow_dependencies(session, portal_id, workflow_id)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.warning(
                "install_diagnostic.rebuild_dependencies_failed",
                extra={
                    "portal_id": portal_id,
                    "workflow_id": workflow_id,
                    "error": repr(exc),
                },
            )
            continue
        rebuilt += 1
        extracted += int(result.get("dependencies_extracted") or 0)

    if rebuilt:
        session.flush()

    return {
        "workflowsConsidered": len(snapshots),
        "workflowsRebuilt": rebuilt,
        "dependenciesExtracted": extracted,
        "failures": failed,
    }


def _dependency_groups(session: Session, portal_id: str) -> list[DependencyGroup]:
    snapshots = (
        session.query(WorkflowSnapshot)
        .filter(WorkflowSnapshot.portal_id == portal_id)
        .all()
    )
    snapshot_by_id = {
        str(snapshot.workflow_id or ""): snapshot
        for snapshot in snapshots
        if str(snapshot.workflow_id or "").strip()
    }

    rows = (
        session.query(WorkflowDependency)
        .filter(WorkflowDependency.portal_id == portal_id)
        .order_by(WorkflowDependency.workflow_id.asc(), WorkflowDependency.id.asc())
        .all()
    )

    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        dependency_type = str(row.dependency_type or "").strip()
        if dependency_type not in CHECKED_DEPENDENCY_TYPES:
            continue

        workflow_id = str(row.workflow_id or "").strip()
        snapshot = snapshot_by_id.get(workflow_id)
        if snapshot is None or snapshot.deleted_at is not None:
            continue

        dependency_id = str(row.dependency_id or "").strip()
        if not dependency_id:
            continue

        object_type_id = str(
            row.dependency_object_type or snapshot.object_type_id or ""
        ).strip()
        key = (workflow_id, dependency_type, dependency_id, object_type_id)
        bucket = grouped.setdefault(
            key,
            {
                "dependency_type": dependency_type,
                "dependency_id": dependency_id,
                "object_type_id": object_type_id,
                "workflow_id": workflow_id,
                "workflow_name": str(snapshot.name or "").strip(),
                "locations": [],
            },
        )
        location = str(row.location or "").strip()
        if location and location not in bucket["locations"]:
            bucket["locations"].append(location)

    return [
        DependencyGroup(
            dependency_type=str(item["dependency_type"]),
            dependency_id=str(item["dependency_id"]),
            object_type_id=str(item["object_type_id"]),
            workflow_id=str(item["workflow_id"]),
            workflow_name=str(item["workflow_name"]),
            locations=tuple(item["locations"]),
        )
        for item in grouped.values()
    ]


def _display_name(value: str | None, fallback: str) -> str:
    cleaned = str(value or "").strip()
    return cleaned or fallback


def _property_status(
    property_map: dict[tuple[str, str], PropertySnapshot],
    properties_by_name: dict[str, list[PropertySnapshot]],
    group: DependencyGroup,
) -> tuple[str, str] | None:
    snapshot = None
    if group.object_type_id:
        snapshot = property_map.get((group.object_type_id, group.dependency_id))
    else:
        candidates = properties_by_name.get(group.dependency_id, [])
        active = [
            row
            for row in candidates
            if row.deleted_at is None and not bool(row.archived)
        ]
        snapshot = active[0] if active else (candidates[0] if candidates else None)

    if snapshot is None:
        return "missing", group.dependency_id
    if snapshot.deleted_at is not None:
        return "deleted", _display_name(snapshot.label, group.dependency_id)
    if bool(snapshot.archived):
        return "archived", _display_name(snapshot.label, group.dependency_id)
    return None


def _list_status(
    list_map: dict[str, ListSnapshot],
    group: DependencyGroup,
) -> tuple[str, str] | None:
    snapshot = list_map.get(group.dependency_id)
    if snapshot is None:
        return "missing", group.dependency_id
    if snapshot.deleted_at is not None:
        return "deleted", _display_name(snapshot.list_name, group.dependency_id)
    if bool(snapshot.is_archived):
        return "archived", _display_name(snapshot.list_name, group.dependency_id)
    return None


def _template_status(
    template_map: dict[str, EmailTemplateSnapshot],
    group: DependencyGroup,
) -> tuple[str, str] | None:
    snapshot = template_map.get(group.dependency_id)
    if snapshot is None:
        return "missing", group.dependency_id
    display_name = _display_name(snapshot.template_name or snapshot.subject, group.dependency_id)
    if snapshot.deleted_at is not None:
        return "deleted", display_name
    if bool(snapshot.is_archived):
        return "archived", display_name
    return None


def _owner_status(
    owner_map: dict[str, OwnerSnapshot],
    group: DependencyGroup,
) -> tuple[str, str] | None:
    snapshot = owner_map.get(group.dependency_id)
    if snapshot is None:
        return "missing", group.dependency_id
    display_name = _display_name(snapshot.email, group.dependency_id)
    if snapshot.deleted_at is not None:
        return "deleted", display_name
    if not bool(snapshot.is_active):
        return "inactive", display_name
    return None


def _find_dependency_issues(
    session: Session,
    portal_id: str,
    groups: list[DependencyGroup],
) -> list[DependencyIssue]:
    property_rows = (
        session.query(PropertySnapshot)
        .filter(PropertySnapshot.portal_id == portal_id)
        .all()
    )
    property_map = {
        (str(row.object_type_id or ""), str(row.property_name or "")): row
        for row in property_rows
    }
    properties_by_name: dict[str, list[PropertySnapshot]] = defaultdict(list)
    for row in property_rows:
        properties_by_name[str(row.property_name or "")].append(row)

    list_map = {
        str(row.list_id or ""): row
        for row in session.query(ListSnapshot)
        .filter(ListSnapshot.portal_id == portal_id)
        .all()
    }
    template_map = {
        str(row.template_id or ""): row
        for row in session.query(EmailTemplateSnapshot)
        .filter(EmailTemplateSnapshot.portal_id == portal_id)
        .all()
    }
    owner_map = {
        str(row.owner_id or ""): row
        for row in session.query(OwnerSnapshot)
        .filter(OwnerSnapshot.portal_id == portal_id)
        .all()
    }

    issues: list[DependencyIssue] = []
    for group in groups:
        result: tuple[str, str] | None
        if group.dependency_type == DEPENDENCY_TYPE_PROPERTY:
            result = _property_status(property_map, properties_by_name, group)
        elif group.dependency_type == DEPENDENCY_TYPE_LIST:
            result = _list_status(list_map, group)
        elif group.dependency_type == DEPENDENCY_TYPE_EMAIL_TEMPLATE:
            result = _template_status(template_map, group)
        elif group.dependency_type == DEPENDENCY_TYPE_OWNER:
            result = _owner_status(owner_map, group)
        else:
            result = None

        if result is None:
            continue

        issue_kind, display_name = result
        issues.append(
            DependencyIssue(
                dependency_type=group.dependency_type,
                dependency_id=group.dependency_id,
                object_type_id=group.object_type_id,
                workflow_id=group.workflow_id,
                workflow_name=group.workflow_name,
                locations=group.locations,
                issue_kind=issue_kind,
                display_name=display_name,
            )
        )

    issues.sort(
        key=lambda issue: (
            issue.workflow_id,
            issue.dependency_type,
            issue.dependency_id,
            issue.issue_kind,
        )
    )
    return issues


def _alert_signature(portal_id: str, issue: DependencyIssue) -> str:
    raw = "\x1f".join(
        [
            DIAGNOSTIC_KIND,
            portal_id,
            issue.workflow_id,
            issue.dependency_type,
            issue.dependency_id,
            issue.object_type_id,
            issue.issue_kind,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _truncate_title(value: str, *, max_length: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _alert_title(issue: DependencyIssue) -> str:
    dependency_label = DEPENDENCY_LABELS.get(issue.dependency_type, issue.dependency_type)
    workflow_label = issue.workflow_name or issue.workflow_id
    return _truncate_title(
        f"Workflow '{workflow_label}' references {issue.issue_kind} "
        f"{dependency_label} '{issue.display_name}'"
    )


def _summary_payload(
    portal_id: str,
    issue: DependencyIssue,
    *,
    ran_at: datetime,
) -> dict[str, Any]:
    return {
        "kind": DIAGNOSTIC_KIND,
        "portal_id": portal_id,
        "diagnostic": {
            "ran_at_utc": _iso_utc(ran_at),
        },
        "change": {
            "issue": issue.issue_kind,
            "dependency_type": issue.dependency_type,
            "dependency_id": issue.dependency_id,
            "dependency_object_type": issue.object_type_id or None,
            "display_name": issue.display_name,
        },
        "impact": {
            "workflow_id": issue.workflow_id,
            "workflow_name": issue.workflow_name,
            "dependency_locations": list(issue.locations),
        },
    }


def _issue_response(issue: DependencyIssue, *, alert_id: int | None) -> dict[str, Any]:
    return {
        "dependencyType": issue.dependency_type,
        "dependencyId": issue.dependency_id,
        "dependencyObjectType": issue.object_type_id or None,
        "displayName": issue.display_name,
        "issue": issue.issue_kind,
        "workflowId": issue.workflow_id,
        "workflowName": issue.workflow_name,
        "locations": list(issue.locations),
        "alertId": alert_id,
    }


def _create_or_reuse_alert(
    session: Session,
    portal_id: str,
    issue: DependencyIssue,
    *,
    ran_at: datetime,
    force: bool,
) -> tuple[Alert, bool]:
    signature = _alert_signature(portal_id, issue)
    existing = (
        session.query(Alert)
        .filter(Alert.portal_id == portal_id, Alert.alert_signature == signature)
        .order_by(Alert.created_at.desc())
        .first()
    )
    summary_payload = _summary_payload(portal_id, issue, ran_at=ran_at)
    source_event_type = SOURCE_EVENT_BY_ISSUE.get(
        (issue.dependency_type, issue.issue_kind),
        DIAGNOSTIC_KIND,
    )

    if existing is not None:
        if force:
            existing.title = _alert_title(issue)
            existing.summary = json.dumps(
                summary_payload,
                separators=(",", ":"),
                sort_keys=True,
            )
            if not str(existing.plain_english_explanation or "").strip():
                try:
                    rewrite_alert(session, existing)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "install_diagnostic.rewrite_existing_alert_failed",
                        extra={"portal_id": portal_id, "alert_id": existing.id},
                    )
        return existing, False

    alert = Alert(
        portal_id=portal_id,
        alert_signature=signature,
        severity=SEVERITY_HIGH,
        status=STATUS_OPEN,
        source_event_type=source_event_type,
        source_event_id=None,
        source_event_kind=SOURCE_KIND_INSTALL_DIAGNOSTIC,
        source_dependency_type=issue.dependency_type,
        source_dependency_id=issue.dependency_id,
        source_object_type_id=issue.object_type_id or None,
        impacted_workflow_id=issue.workflow_id or None,
        impacted_workflow_name=issue.workflow_name or None,
        title=_alert_title(issue),
        summary=json.dumps(summary_payload, separators=(",", ":"), sort_keys=True),
        repeat_count=1,
        created_at=ran_at,
    )
    session.add(alert)
    session.flush()
    try:
        rewrite_alert(session, alert)
    except Exception:  # noqa: BLE001
        logger.exception(
            "install_diagnostic.rewrite_alert_failed",
            extra={"portal_id": portal_id, "alert_id": alert.id},
        )
    return alert, True


def run_install_diagnostic(
    portal_id: str,
    session: Session,
    *,
    force: bool = False,
) -> dict[str, Any]:
    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise ValueError("portal_id is required.")

    settings = _ensure_settings_row(session, portal_key)
    existing_summary = settings.install_diagnostic_summary
    if (
        isinstance(existing_summary, dict)
        and existing_summary.get("status") == DIAGNOSTIC_STATUS_COMPLETED
        and not force
    ):
        return dict(existing_summary)

    inventory_summary = _refresh_portal_inventory(session, portal_key)
    dependency_summary = _ensure_cached_workflow_dependencies(
        session,
        portal_key,
        force=force,
    )
    groups = _dependency_groups(session, portal_key)
    issues = _find_dependency_issues(session, portal_key, groups)

    # Plan-tier gating: the diagnostic must not create or surface alerts for
    # detection categories the portal's plan excludes (list/template need
    # Professional+, owner needs Agency) — same policy the correlation engine
    # enforces. Unknown/empty plans fail OPEN (full coverage).
    # Local import avoids a portal_entitlements <-> install_diagnostic cycle.
    from app.services.portal_entitlements import get_portal_entitlement

    plan = str(get_portal_entitlement(session, portal_key).get("plan") or "")
    issues = [
        issue
        for issue in issues
        if plan_allows_category(
            plan,
            SOURCE_EVENT_BY_ISSUE.get(
                (issue.dependency_type, issue.issue_kind), DIAGNOSTIC_KIND
            ),
        )
    ]

    ran_at = _utc_now()
    issue_rows: list[dict[str, Any]] = []
    alerts_created = 0
    alerts_existing = 0
    for issue in issues:
        alert, created = _create_or_reuse_alert(
            session,
            portal_key,
            issue,
            ran_at=ran_at,
            force=force,
        )
        if created:
            alerts_created += 1
        else:
            alerts_existing += 1
        issue_rows.append(_issue_response(issue, alert_id=alert.id))

    summary = {
        "status": DIAGNOSTIC_STATUS_COMPLETED,
        "portalId": portal_key,
        "ranAtUtc": _iso_utc(ran_at),
        "forced": bool(force),
        "issuesFound": len(issues),
        "alertsCreated": alerts_created,
        "alertsExisting": alerts_existing,
        "dependenciesChecked": len(groups),
        "dependencyExtraction": dependency_summary,
        "inventoryRefresh": inventory_summary,
        "issues": issue_rows[:50],
    }
    settings = _ensure_settings_row(session, portal_key)
    settings.install_diagnostic_summary = summary
    session.commit()
    return summary
