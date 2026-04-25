from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import settings
from app.models.hubspot_installation import HubSpotInstallation
from app.services.alert_correlation import correlate_unprocessed_events
from app.services.property_polling import poll_portal_properties
from app.services.workflow_polling import poll_portal_workflows

logger = logging.getLogger(__name__)

# Type alias: a zero-arg factory returning an open SQLAlchemy Session
# (or None if the database is not configured for the current process).
SessionFactory = Callable[[], "Session | None"]


def _list_active_portal_ids(session: Session) -> list[str]:
    """All HubSpot installations currently flagged active."""
    rows = (
        session.query(HubSpotInstallation.portal_id)
        .filter(HubSpotInstallation.is_active.is_(True))
        .all()
    )
    portal_ids: list[str] = []
    for row in rows:
        portal_id = str(getattr(row, "portal_id", "") or "").strip()
        if portal_id:
            portal_ids.append(portal_id)
    return portal_ids


def _run_portal_pass(
    session_factory: SessionFactory,
    portal_id: str,
    poll_fn: Callable[[Session, str], dict[str, Any]],
    log_key: str,
) -> dict[str, Any]:
    """Run one polling function against one portal in a fresh session.

    Failures are caught and converted to an ``error`` summary so a
    transient bug in one polling pass cannot abort the rest of the
    cycle. Each pass gets its own session so a rollback in one cannot
    poison the other.
    """
    session = session_factory()
    if session is None:
        return {
            "portalId": portal_id,
            "status": "error",
            "reason": "no_database",
        }
    try:
        try:
            return poll_fn(session, portal_id)
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.exception(
                f"{log_key}.portal_failed",
                extra={"portal_id": portal_id, "error": repr(exc)},
            )
            try:
                session.rollback()
            except Exception:  # noqa: BLE001
                pass
            return {
                "portalId": portal_id,
                "status": "error",
                "reason": f"unhandled_exception: {exc}",
            }
    finally:
        session.close()


def _accumulate_status(summary: dict[str, Any], status_value: str) -> None:
    """Increment the cycle-level success / skip / error counters
    based on a per-portal status string.
    """
    status = str(status_value or "").lower()
    if status == "ok":
        summary["portalsSucceeded"] += 1
    elif status == "skipped":
        summary["portalsSkipped"] += 1
    else:
        summary["portalsErrored"] += 1


async def run_polling_cycle(session_factory: SessionFactory) -> dict[str, Any]:
    """Poll every active portal once for both workflows AND property
    schema. Returns a summary dict.

    Each portal gets two sequential passes per cycle (workflows, then
    properties). Each pass runs in its own session so a transient
    failure in one cannot leak into the other. The cadence is the
    same — every ``workflow_poll_interval_seconds`` — because the alert
    correlation engine joins both data sources and skewed cadences
    would create stale joins.

    The per-portal entry in ``perPortal`` carries both summaries
    keyed by ``workflow`` and ``property``. The cycle-level
    success/skip/error counters use the workflow-pass status as the
    canonical signal for backward compatibility with the existing
    workflow-only callers; the property pass adds dedicated
    ``propertiesPolled`` and ``propertyEventsEmitted`` counters.
    """
    summary: dict[str, Any] = {
        "portalsAttempted": 0,
        "portalsSucceeded": 0,
        "portalsSkipped": 0,
        "portalsErrored": 0,
        "propertiesPolled": 0,
        "propertyEventsEmitted": 0,
        "alertsCreated": 0,
        "perPortal": [],
    }

    session = session_factory()
    if session is None:
        summary["status"] = "no_database"
        return summary

    try:
        portal_ids = _list_active_portal_ids(session)
    finally:
        session.close()

    summary["portalsAttempted"] = len(portal_ids)

    for portal_id in portal_ids:
        workflow_summary = _run_portal_pass(
            session_factory,
            portal_id,
            poll_portal_workflows,
            "workflow_polling_scheduler",
        )
        property_summary = _run_portal_pass(
            session_factory,
            portal_id,
            poll_portal_properties,
            "property_polling_scheduler",
        )

        if isinstance(property_summary, dict):
            summary["propertiesPolled"] += int(property_summary.get("polled") or 0)
            summary["propertyEventsEmitted"] += sum(
                int(property_summary.get(key) or 0)
                for key in (
                    "createdEvents",
                    "archivedEvents",
                    "unarchivedEvents",
                    "typeChangedEvents",
                    "renamedEvents",
                    "deletedEvents",
                )
            )

        summary["perPortal"].append(
            {
                "portalId": portal_id,
                "workflow": workflow_summary,
                "property": property_summary,
            }
        )
        _accumulate_status(summary, workflow_summary.get("status"))

    # Correlate every unprocessed change event from every portal in a
    # single pass after polling completes. Doing it once at the end
    # avoids re-querying the events table per portal (correlation is
    # global by design — `processed_at IS NULL` is the only filter).
    # Failures here are logged but never abort the cycle: a buggy
    # correlator should not block the next polling round.
    correlation_summary: dict[str, Any] = {
        "events_processed": 0,
        "alerts_created": 0,
        "alerts_updated_repeat": 0,
    }
    correlation_session = session_factory()
    if correlation_session is not None:
        try:
            try:
                correlation_summary = correlate_unprocessed_events(correlation_session)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "alert_correlation_scheduler.cycle_failed",
                    extra={"error": repr(exc)},
                )
                try:
                    correlation_session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                correlation_summary = {
                    "events_processed": 0,
                    "alerts_created": 0,
                    "alerts_updated_repeat": 0,
                    "error": f"unhandled_exception: {exc}",
                }
        finally:
            correlation_session.close()

    summary["alertsCreated"] = int(correlation_summary.get("alerts_created") or 0)
    summary["correlation"] = correlation_summary

    summary["status"] = summary.get("status") or "ok"
    return summary


class WorkflowPollingScheduler:
    """In-process polling loop with a fixed interval.

    Intentionally simple: one asyncio task on the FastAPI event loop,
    one cycle every `settings.workflow_poll_interval_seconds`. The first
    cycle runs after the interval (not immediately) so app startup
    isn't blocked by HubSpot latency.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        interval_seconds: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._interval_seconds = max(
            1,
            int(
                interval_seconds
                if interval_seconds is not None
                else settings.workflow_poll_interval_seconds
            ),
        )
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=self._interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
            else:
                # _stopping was set during the wait; exit.
                return

            try:
                await run_polling_cycle(self._session_factory)
            except Exception:  # noqa: BLE001 — never let the loop die
                logger.exception("workflow_polling_scheduler.cycle_crashed")

    def start(self) -> None:
        if self.is_running():
            return
        self._stopping.clear()
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                logger.exception("workflow_polling_scheduler.stop_observed_error")
