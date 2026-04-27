"""Database-aware persistence layer for the workflow dependency map.

This module wraps `dependency_extraction.extract_dependencies` with
SQLAlchemy I/O. It rebuilds dependencies for a workflow on every
revision change (called from the polling cycle) and exposes reverse-
index queries that future tasks (alerting, dependency reasoning) will
consume.

No HTTP calls live here. Dependencies are rebuilt purely from the
cached `definition_json` on `WorkflowSnapshot` — the polling layer is
responsible for keeping that JSON fresh.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_EMAIL_TEMPLATE,
    DEPENDENCY_TYPE_LIST,
    DEPENDENCY_TYPE_OWNER,
    DEPENDENCY_TYPE_PROPERTY,
    WorkflowDependency,
)
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.dependency_extraction import extract_dependencies

logger = logging.getLogger(__name__)


def _delete_workflow_dependencies(
    session: Session,
    portal_id: str,
    workflow_id: str,
) -> int:
    deleted = (
        session.query(WorkflowDependency)
        .filter(
            WorkflowDependency.portal_id == portal_id,
            WorkflowDependency.workflow_id == workflow_id,
        )
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)


def delete_workflow_dependencies(
    session: Session,
    portal_id: str,
    workflow_id: str,
) -> int:
    """Public helper used by the polling layer when a workflow is marked
    deleted. Returns the number of rows removed.

    Flushes (but does not commit) so direct callers can immediately
    requery the same session without seeing stale rows. Composable
    inside a larger transaction — the surrounding code is still
    responsible for the final commit.
    """
    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key or not workflow_key:
        return 0
    deleted = _delete_workflow_dependencies(session, portal_key, workflow_key)
    session.flush()
    return deleted


def rebuild_workflow_dependencies(
    session: Session,
    portal_id: str,
    workflow_id: str,
) -> dict[str, Any]:
    """Re-extract dependencies for one workflow from its cached
    `definition_json` and persist them.

    Deletes every existing `WorkflowDependency` row for
    (portal_id, workflow_id), then re-inserts based on the snapshot's
    current definition. Returns a small summary dict.

    The function flushes (but does not commit) at the end, so direct
    callers can immediately query for the persisted rows on the same
    session. The polling cycle still drives the final ``session.commit()``
    after walking every workflow, and other future callers can compose
    this function inside a larger transaction.
    """
    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key or not workflow_key:
        raise ValueError("portal_id and workflow_id are required.")

    summary: dict[str, Any] = {
        "portal_id": portal_key,
        "workflow_id": workflow_key,
        "dependencies_extracted": 0,
        "by_type": {},
        "status": "ok",
    }

    snapshot = (
        session.query(WorkflowSnapshot)
        .filter(
            WorkflowSnapshot.portal_id == portal_key,
            WorkflowSnapshot.workflow_id == workflow_key,
        )
        .one_or_none()
    )
    if snapshot is None:
        # No snapshot to extract from — drop any stale rows and exit.
        _delete_workflow_dependencies(session, portal_key, workflow_key)
        session.flush()
        summary["status"] = "no_snapshot"
        return summary

    raw_definition = snapshot.definition_json or ""
    if not raw_definition.strip():
        _delete_workflow_dependencies(session, portal_key, workflow_key)
        session.flush()
        summary["status"] = "no_definition"
        return summary

    try:
        definition = json.loads(raw_definition)
    except Exception as exc:  # noqa: BLE001 — bad JSON is non-fatal
        logger.warning(
            "dependency_mapping.bad_definition_json",
            extra={
                "portal_id": portal_key,
                "workflow_id": workflow_key,
                "error": repr(exc),
            },
        )
        _delete_workflow_dependencies(session, portal_key, workflow_key)
        session.flush()
        summary["status"] = "invalid_definition_json"
        return summary

    default_object_type = str(snapshot.object_type_id or "").strip()
    extracted = extract_dependencies(
        definition,
        default_object_type_id=default_object_type,
    )

    # Delete existing rows and re-insert in one transaction.
    _delete_workflow_dependencies(session, portal_key, workflow_key)

    by_type: dict[str, int] = defaultdict(int)
    revision_id = str(snapshot.revision_id or "") or None

    for descriptor in extracted:
        dep = WorkflowDependency(
            portal_id=portal_key,
            workflow_id=workflow_key,
            dependency_type=str(descriptor.get("dependency_type") or "unknown"),
            dependency_id=str(descriptor.get("dependency_id") or ""),
            dependency_object_type=descriptor.get("dependency_object_type"),
            location=str(descriptor.get("location") or ""),
            revision_id=revision_id,
        )
        if not dep.dependency_id:
            continue
        session.add(dep)
        by_type[dep.dependency_type] += 1

    # Flush so the just-added rows are queryable on the same session.
    # The surrounding transaction (e.g. the polling cycle) commits
    # later; standalone callers are guaranteed durable visibility
    # within their own session without needing to know that.
    session.flush()

    summary["dependencies_extracted"] = sum(by_type.values())
    summary["by_type"] = dict(by_type)
    return summary


def _serialise_workflow_match(
    workflow_id: str,
    workflow_name: str,
    rows: list[WorkflowDependency],
) -> dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "locations": [
            {
                "location": row.location,
                "dependency_type": row.dependency_type,
                "dependency_id": row.dependency_id,
                "dependency_object_type": row.dependency_object_type,
            }
            for row in rows
        ],
    }


def _group_matches(
    session: Session,
    portal_id: str,
    rows: list[WorkflowDependency],
) -> list[dict[str, Any]]:
    """Group a flat list of dependency rows by workflow_id and join
    against `WorkflowSnapshot` to fetch the workflow name. Excludes
    workflows that have been marked deleted on the snapshot.
    """
    if not rows:
        return []
    grouped: dict[str, list[WorkflowDependency]] = defaultdict(list)
    for row in rows:
        grouped[row.workflow_id].append(row)

    snapshots = (
        session.query(WorkflowSnapshot)
        .filter(
            WorkflowSnapshot.portal_id == portal_id,
            WorkflowSnapshot.workflow_id.in_(list(grouped.keys())),
        )
        .all()
    )
    snap_by_id = {snap.workflow_id: snap for snap in snapshots}

    results: list[dict[str, Any]] = []
    for workflow_id, dep_rows in grouped.items():
        snap = snap_by_id.get(workflow_id)
        if snap is None or snap.deleted_at is not None:
            # Stale dependency — the workflow no longer exists or has
            # been deleted. Don't surface it in reverse queries.
            continue
        results.append(
            _serialise_workflow_match(workflow_id, snap.name or "", dep_rows)
        )
    # Stable ordering by workflow_id so downstream consumers and tests
    # get deterministic output.
    results.sort(key=lambda item: item["workflow_id"])
    return results


def find_workflows_affected_by_property(
    session: Session,
    portal_id: str,
    property_name: str,
    object_type_id: str = "",
) -> list[dict[str, Any]]:
    """Reverse query: which workflows in this portal depend on the
    named property?
    """
    portal_key = str(portal_id or "").strip()
    prop_key = str(property_name or "").strip()
    if not portal_key or not prop_key:
        return []

    query = session.query(WorkflowDependency).filter(
        WorkflowDependency.portal_id == portal_key,
        WorkflowDependency.dependency_type == DEPENDENCY_TYPE_PROPERTY,
        WorkflowDependency.dependency_id == prop_key,
    )
    object_type = str(object_type_id or "").strip()
    if object_type:
        query = query.filter(
            WorkflowDependency.dependency_object_type == object_type,
        )

    rows = query.all()
    return _group_matches(session, portal_key, rows)


def find_workflows_affected_by_list(
    session: Session,
    portal_id: str,
    list_id: str,
) -> list[dict[str, Any]]:
    """Reverse query for list dependencies."""
    portal_key = str(portal_id or "").strip()
    lid = str(list_id or "").strip()
    if not portal_key or not lid:
        return []
    rows = (
        session.query(WorkflowDependency)
        .filter(
            WorkflowDependency.portal_id == portal_key,
            WorkflowDependency.dependency_type == DEPENDENCY_TYPE_LIST,
            WorkflowDependency.dependency_id == lid,
        )
        .all()
    )
    return _group_matches(session, portal_key, rows)


def find_workflows_affected_by_email_template(
    session: Session,
    portal_id: str,
    template_id: str,
) -> list[dict[str, Any]]:
    """Reverse query for email-template dependencies."""
    portal_key = str(portal_id or "").strip()
    tid = str(template_id or "").strip()
    if not portal_key or not tid:
        return []
    rows = (
        session.query(WorkflowDependency)
        .filter(
            WorkflowDependency.portal_id == portal_key,
            WorkflowDependency.dependency_type == DEPENDENCY_TYPE_EMAIL_TEMPLATE,
            WorkflowDependency.dependency_id == tid,
        )
        .all()
    )
    return _group_matches(session, portal_key, rows)


def find_workflows_affected_by_owner(
    session: Session,
    portal_id: str,
    owner_id: str,
) -> list[dict[str, Any]]:
    """Reverse query for owner/user dependencies."""
    portal_key = str(portal_id or "").strip()
    oid = str(owner_id or "").strip()
    if not portal_key or not oid:
        return []
    rows = (
        session.query(WorkflowDependency)
        .filter(
            WorkflowDependency.portal_id == portal_key,
            WorkflowDependency.dependency_type == DEPENDENCY_TYPE_OWNER,
            WorkflowDependency.dependency_id == oid,
        )
        .all()
    )
    return _group_matches(session, portal_key, rows)


def list_workflow_dependencies(
    session: Session,
    portal_id: str,
    workflow_id: str,
) -> list[dict[str, Any]]:
    """Forward query: list every dependency for a single workflow."""
    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key or not workflow_key:
        return []
    rows = (
        session.query(WorkflowDependency)
        .filter(
            WorkflowDependency.portal_id == portal_key,
            WorkflowDependency.workflow_id == workflow_key,
        )
        .order_by(WorkflowDependency.id.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "dependency_type": row.dependency_type,
            "dependency_id": row.dependency_id,
            "dependency_object_type": row.dependency_object_type,
            "location": row.location,
            "revision_id": row.revision_id,
            "extracted_at": row.extracted_at.isoformat() if row.extracted_at else None,
        }
        for row in rows
    ]
