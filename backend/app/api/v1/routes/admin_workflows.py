from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path, Query

from app.config import settings
from app.db import get_session
from app.models.property_snapshot import PropertySnapshot
from app.services.alert_correlation import (
    correlate_unprocessed_events,
    list_alerts_for_portal,
)
from app.services.alert_rewriter import rewrite_pending_alerts
from app.services.slack_delivery import deliver_pending_alerts
from app.services.ticket_delivery import deliver_pending_tickets
from app.services.dependency_mapping import (
    find_workflows_affected_by_email_template,
    find_workflows_affected_by_list,
    find_workflows_affected_by_property,
    list_workflow_dependencies,
)
from app.services.property_polling import poll_portal_properties
from app.services.workflow_polling import poll_portal_workflows
from app.services.workflow_polling_scheduler import run_polling_cycle

router = APIRouter()


def _require_admin_key(supplied: str | None) -> None:
    expected = str(settings.maintenance_api_key or "").strip()
    if not expected:
        # Fail closed: if no key is configured the endpoint is effectively
        # disabled. This matches the pattern in ticket_maintenance.py
        # where an unset key blocks access in production. Operators must
        # explicitly set MAINTENANCE_API_KEY to enable manual triggers.
        raise HTTPException(status_code=503, detail="Admin API key is not configured.")
    if str(supplied or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid admin key.")


@router.post("/admin/workflows/poll/{portal_id}")
def trigger_workflow_poll(
    portal_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Manually trigger a workflow poll for a single portal.

    Authenticated via the `X-OpsLens-Admin-Key` request header against
    `settings.maintenance_api_key`.
    """
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise HTTPException(status_code=400, detail="portal_id is required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        try:
            return poll_portal_workflows(session, portal_key)
        except Exception:  # noqa: BLE001
            session.rollback()
            raise
    finally:
        session.close()


@router.post("/admin/workflows/poll")
async def trigger_workflow_poll_all(
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Manually trigger a polling cycle across every active portal.

    Same auth as the per-portal endpoint. Uses the same code path as the
    background scheduler so the manual trigger and automatic loop never
    diverge.
    """
    _require_admin_key(x_opslens_admin_key)
    return await run_polling_cycle(get_session)


@router.get("/admin/workflows/{portal_id}/{workflow_id}/dependencies")
def list_dependencies_for_workflow(
    portal_id: str = Path(..., min_length=1),
    workflow_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Forward query: every dependency persisted for one workflow."""
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key or not workflow_key:
        raise HTTPException(status_code=400, detail="portal_id and workflow_id are required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        dependencies = list_workflow_dependencies(session, portal_key, workflow_key)
    finally:
        session.close()

    return {
        "portalId": portal_key,
        "workflowId": workflow_key,
        "count": len(dependencies),
        "dependencies": dependencies,
    }


@router.get("/admin/workflows/{portal_id}/dependencies/property/{property_name}")
def list_workflows_for_property(
    portal_id: str = Path(..., min_length=1),
    property_name: str = Path(..., min_length=1),
    object_type_id: str = Query(default="", alias="objectTypeId"),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Reverse query: which workflows depend on the named property?

    Optional ``?objectTypeId=`` query param scopes the lookup to
    properties on a specific HubSpot object type (e.g. ``0-1`` for
    contact, ``0-2`` for company).
    """
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    prop_key = str(property_name or "").strip()
    if not portal_key or not prop_key:
        raise HTTPException(status_code=400, detail="portal_id and property_name are required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        workflows = find_workflows_affected_by_property(
            session, portal_key, prop_key, object_type_id=object_type_id,
        )
    finally:
        session.close()

    return {
        "portalId": portal_key,
        "propertyName": prop_key,
        "objectTypeId": str(object_type_id or "").strip() or None,
        "count": len(workflows),
        "workflows": workflows,
    }


@router.get("/admin/workflows/{portal_id}/dependencies/list/{list_id}")
def list_workflows_for_list(
    portal_id: str = Path(..., min_length=1),
    list_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Reverse query for list dependencies."""
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    lid = str(list_id or "").strip()
    if not portal_key or not lid:
        raise HTTPException(status_code=400, detail="portal_id and list_id are required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        workflows = find_workflows_affected_by_list(session, portal_key, lid)
    finally:
        session.close()

    return {
        "portalId": portal_key,
        "listId": lid,
        "count": len(workflows),
        "workflows": workflows,
    }


@router.get("/admin/workflows/{portal_id}/dependencies/email-template/{template_id}")
def list_workflows_for_email_template(
    portal_id: str = Path(..., min_length=1),
    template_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Reverse query for email-template dependencies."""
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    tid = str(template_id or "").strip()
    if not portal_key or not tid:
        raise HTTPException(status_code=400, detail="portal_id and template_id are required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        workflows = find_workflows_affected_by_email_template(session, portal_key, tid)
    finally:
        session.close()

    return {
        "portalId": portal_key,
        "templateId": tid,
        "count": len(workflows),
        "workflows": workflows,
    }


# ----------------------------------------------------------------------
# Property polling — manual triggers and inspection
# ----------------------------------------------------------------------


@router.post("/admin/properties/poll/{portal_id}")
def trigger_property_poll(
    portal_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Manually trigger a property-schema poll for one portal.

    Auth via the same ``X-OpsLens-Admin-Key`` header the workflow
    admin endpoints use.
    """
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise HTTPException(status_code=400, detail="portal_id is required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        try:
            return poll_portal_properties(session, portal_key)
        except Exception:  # noqa: BLE001
            session.rollback()
            raise
    finally:
        session.close()


@router.get("/admin/properties/{portal_id}")
def list_property_snapshot_counts(
    portal_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return per-object-type snapshot counts for one portal — useful
    for confirming the property poll is making progress.
    """
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise HTTPException(status_code=400, detail="portal_id is required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        rows = (
            session.query(PropertySnapshot)
            .filter(PropertySnapshot.portal_id == portal_key)
            .all()
        )
    finally:
        session.close()

    # Aggregate in Python — at most a few thousand rows per portal,
    # so the round-trip cost is negligible and we sidestep dialect
    # differences in `SUM(boolean)` semantics across SQLite/Postgres.
    counters: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = counters.setdefault(
            row.object_type_id,
            {"total": 0, "archived": 0, "deleted": 0},
        )
        bucket["total"] += 1
        if row.archived:
            bucket["archived"] += 1
        if row.deleted_at is not None:
            bucket["deleted"] += 1

    by_object_type = [
        {
            "objectTypeId": object_type_id,
            "total": bucket["total"],
            "archived": bucket["archived"],
            "deleted": bucket["deleted"],
            "active": max(0, bucket["total"] - bucket["archived"] - bucket["deleted"]),
        }
        for object_type_id, bucket in sorted(counters.items())
    ]

    return {
        "portalId": portal_key,
        "total": sum(item["total"] for item in by_object_type),
        "byObjectType": by_object_type,
    }


# ----------------------------------------------------------------------
# Alert correlation — manual trigger and per-portal listing
# ----------------------------------------------------------------------


@router.post("/admin/alerts/correlate")
def trigger_alert_correlation(
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run the alert correlator across every unprocessed change event.

    Useful for the demo and for backfilling alerts after the worker
    has been down. Returns the same summary shape as
    ``correlate_unprocessed_events``.
    """
    _require_admin_key(x_opslens_admin_key)

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        try:
            return correlate_unprocessed_events(session)
        except Exception:  # noqa: BLE001
            session.rollback()
            raise
    finally:
        session.close()


@router.get("/admin/alerts/{portal_id}")
def list_alerts_for_portal_endpoint(
    portal_id: str = Path(..., min_length=1),
    max_results: int = Query(default=50, ge=1, le=200, alias="maxResults"),
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Open + recently-resolved alerts for a portal, newest first.

    Capped at ``maxResults`` (default 50, max 200) so the demo
    dashboard can fetch a reasonable slice without paging logic.
    """
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise HTTPException(status_code=400, detail="portal_id is required.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        alerts = list_alerts_for_portal(session, portal_key, max_results=max_results)
    finally:
        session.close()

    return {
        "portalId": portal_key,
        "count": len(alerts),
        "alerts": alerts,
    }


# ----------------------------------------------------------------------
# Alert delivery — Slack and tickets
# ----------------------------------------------------------------------


def _run_session_scoped(callable_taking_session) -> dict[str, Any]:
    """Open a session, run the callable, close. Used by the delivery
    admin endpoints to keep handler bodies short.
    """
    session = get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        try:
            return callable_taking_session(session)
        except Exception:  # noqa: BLE001
            session.rollback()
            raise
    finally:
        session.close()


@router.post("/admin/alerts/rewrite")
def trigger_alert_rewrite(
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Rewrite every pending alert that doesn't yet have a
    plain-English explanation.

    Useful for the demo and after a kill-switch flip where alerts
    accumulated without rewrites. Same auth as the other admin
    endpoints.
    """
    _require_admin_key(x_opslens_admin_key)
    return _run_session_scoped(rewrite_pending_alerts)


@router.post("/admin/alerts/deliver/slack")
def trigger_slack_delivery(
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Push every pending Slack-undelivered alert to its portal's
    configured webhook. Same auth as the other admin endpoints.
    """
    _require_admin_key(x_opslens_admin_key)
    return _run_session_scoped(deliver_pending_alerts)


@router.post("/admin/alerts/deliver/tickets")
def trigger_ticket_delivery(
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Create HubSpot tickets for every pending un-ticketed alert."""
    _require_admin_key(x_opslens_admin_key)
    return _run_session_scoped(deliver_pending_tickets)


@router.post("/admin/alerts/deliver/all")
def trigger_all_delivery(
    x_opslens_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run Slack delivery first, then ticket creation. Returns the
    merged summary so an operator can see both numbers in one response.
    """
    _require_admin_key(x_opslens_admin_key)
    slack_result = _run_session_scoped(deliver_pending_alerts)
    ticket_result = _run_session_scoped(deliver_pending_tickets)
    return {
        "slack": slack_result,
        "tickets": ticket_result,
    }
