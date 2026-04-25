from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import settings
from app.models.hubspot_installation import HubSpotInstallation
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


async def run_polling_cycle(session_factory: SessionFactory) -> dict[str, Any]:
    """Poll every active portal once. Returns a summary dict.

    This function is designed to be safe to call from anywhere — the
    scheduled background loop, a FastAPI lifespan hook, or the admin
    trigger endpoint. It does not raise on per-portal failures; it
    aggregates them into the returned summary.
    """
    summary: dict[str, Any] = {
        "portalsAttempted": 0,
        "portalsSucceeded": 0,
        "portalsSkipped": 0,
        "portalsErrored": 0,
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
        # Each portal gets a fresh session so a transient failure on one
        # portal cannot leave another portal's poll inside a half-rolled
        # back transaction.
        session = session_factory()
        if session is None:
            summary["status"] = "no_database"
            return summary
        try:
            try:
                portal_summary = poll_portal_workflows(session, portal_id)
            except Exception as exc:  # noqa: BLE001 — defensive
                logger.exception(
                    "workflow_polling_scheduler.portal_failed",
                    extra={"portal_id": portal_id, "error": repr(exc)},
                )
                portal_summary = {
                    "portalId": portal_id,
                    "status": "error",
                    "reason": f"unhandled_exception: {exc}",
                }
                # Roll back any partial writes from a failed poll.
                try:
                    session.rollback()
                except Exception:  # noqa: BLE001
                    pass

            summary["perPortal"].append(portal_summary)
            status_value = str(portal_summary.get("status") or "").lower()
            if status_value == "ok":
                summary["portalsSucceeded"] += 1
            elif status_value == "skipped":
                summary["portalsSkipped"] += 1
            else:
                summary["portalsErrored"] += 1
        finally:
            session.close()

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
