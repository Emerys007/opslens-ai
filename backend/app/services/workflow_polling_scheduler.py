from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import settings
from app.models.hubspot_installation import HubSpotInstallation
from app.models.scheduler_lease import SchedulerLease  # noqa: F401 — register table
from app.services.scheduler_lease import try_acquire_lease
from app.services.alert_correlation import correlate_unprocessed_events
from app.services.alert_rewriter import rewrite_pending_alerts
from app.services.email_template_polling import poll_portal_email_templates
from app.services.list_polling import poll_portal_lists
from app.services.owner_polling import poll_portal_owners
from app.services.property_polling import poll_portal_properties
from app.services.alert_snooze import reopen_expired_snoozes
from app.services.slack_delivery import deliver_pending_alerts
from app.services.ticket_delivery import deliver_pending_tickets
from app.services.weekly_digest import send_due_digests
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


def run_polling_cycle_sync(session_factory: SessionFactory) -> dict[str, Any]:
    """Poll every active portal once for both workflows AND property
    schema. Returns a summary dict.

    Synchronous: all HubSpot/Slack/ticket I/O here is blocking urllib, so this
    must be run in a worker thread (see ``run_polling_cycle``) to avoid
    blocking the FastAPI event loop.

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
        "listsPolled": 0,
        "listEventsEmitted": 0,
        "templatesPolled": 0,
        "templateEventsEmitted": 0,
        "ownersPolled": 0,
        "ownerEventsEmitted": 0,
        "alertsCreated": 0,
        "alertsRewritten": 0,
        "alertsRewriteFailed": 0,
        "slackDelivered": 0,
        "slackFailed": 0,
        "ticketsCreated": 0,
        "ticketsFailed": 0,
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
        list_summary = _run_portal_pass(
            session_factory,
            portal_id,
            poll_portal_lists,
            "list_polling_scheduler",
        )
        template_summary = _run_portal_pass(
            session_factory,
            portal_id,
            poll_portal_email_templates,
            "email_template_polling_scheduler",
        )
        property_summary = _run_portal_pass(
            session_factory,
            portal_id,
            poll_portal_properties,
            "property_polling_scheduler",
        )
        owner_summary = _run_portal_pass(
            session_factory,
            portal_id,
            poll_portal_owners,
            "owner_polling_scheduler",
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

        if isinstance(list_summary, dict):
            summary["listsPolled"] += int(list_summary.get("polled") or 0)
            summary["listEventsEmitted"] += int(
                list_summary.get("events_emitted") or 0
            )

        if isinstance(template_summary, dict):
            summary["templatesPolled"] += int(template_summary.get("polled") or 0)
            summary["templateEventsEmitted"] += int(
                template_summary.get("events_emitted") or 0
            )

        if isinstance(owner_summary, dict):
            summary["ownersPolled"] += int(owner_summary.get("polled") or 0)
            summary["ownerEventsEmitted"] += int(
                owner_summary.get("events_emitted") or 0
            )

        summary["perPortal"].append(
            {
                "portalId": portal_id,
                "workflow": workflow_summary,
                "list": list_summary,
                "template": template_summary,
                "property": property_summary,
                "owner": owner_summary,
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

    # Plain-English rewriter — calls Anthropic's Haiku to populate
    # ``plain_english_explanation`` and ``recommended_action`` on
    # freshly-created alerts. Runs BEFORE Slack/ticket delivery so
    # those bodies pick up the rewritten text. Failures are
    # best-effort: the delivery layer falls back to the structured
    # rendering when ``plain_english_explanation`` is null.
    rewrite_summary: dict[str, Any] = {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_disabled": 0,
    }
    rewrite_session = session_factory()
    if rewrite_session is not None:
        try:
            try:
                rewrite_summary = rewrite_pending_alerts(rewrite_session)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "alert_rewriter_scheduler.cycle_failed",
                    extra={"error": repr(exc)},
                )
                try:
                    rewrite_session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                rewrite_summary = {
                    "attempted": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "skipped_disabled": 0,
                    "error": f"unhandled_exception: {exc}",
                }
        finally:
            rewrite_session.close()

    summary["alertsRewritten"] = int(rewrite_summary.get("succeeded") or 0)
    summary["alertsRewriteFailed"] = int(rewrite_summary.get("failed") or 0)
    summary["rewriter"] = rewrite_summary

    # Re-open snoozed alerts whose window elapsed. Runs BEFORE the delivery
    # passes so a "remind me in N days" snooze re-notifies in this same cycle
    # (reopen clears slack_delivered_at). Best-effort.
    snooze_session = session_factory()
    if snooze_session is not None:
        try:
            try:
                snooze_summary = reopen_expired_snoozes(snooze_session)
                summary["snoozesReopened"] = int(snooze_summary.get("reopened") or 0)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "alert_snooze_scheduler.cycle_failed", extra={"error": repr(exc)}
                )
                try:
                    snooze_session.rollback()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            snooze_session.close()

    # Deliver fresh alerts to Slack and to the OpsLens Alerts ticket
    # pipeline. Both run on their own session, both are best-effort:
    # a failure in one does not block the other and never aborts the
    # cycle. Re-attempts happen automatically next cycle because
    # ``slack_delivered_at`` / ``hubspot_ticket_id`` stay null on
    # failure.
    slack_summary: dict[str, Any] = {"attempted": 0, "succeeded": 0, "failed": 0}
    slack_session = session_factory()
    if slack_session is not None:
        try:
            try:
                slack_summary = deliver_pending_alerts(slack_session)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "slack_delivery_scheduler.cycle_failed",
                    extra={"error": repr(exc)},
                )
                try:
                    slack_session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                slack_summary = {
                    "attempted": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "error": f"unhandled_exception: {exc}",
                }
        finally:
            slack_session.close()

    ticket_summary: dict[str, Any] = {"attempted": 0, "succeeded": 0, "failed": 0}
    ticket_session = session_factory()
    if ticket_session is not None:
        try:
            try:
                ticket_summary = deliver_pending_tickets(ticket_session)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "ticket_delivery_scheduler.cycle_failed",
                    extra={"error": repr(exc)},
                )
                try:
                    ticket_session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                ticket_summary = {
                    "attempted": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "error": f"unhandled_exception: {exc}",
                }
        finally:
            ticket_session.close()

    summary["slackDelivered"] = int(slack_summary.get("succeeded") or 0)
    summary["slackFailed"] = int(slack_summary.get("failed") or 0)
    summary["ticketsCreated"] = int(ticket_summary.get("succeeded") or 0)
    summary["ticketsFailed"] = int(ticket_summary.get("failed") or 0)
    summary["slack"] = slack_summary
    summary["tickets"] = ticket_summary

    # Weekly digest — send the once-a-week summary to any portal whose 7-day
    # window has elapsed. Own session, best-effort: the internal cadence gate
    # makes this safe to call every cycle (it only sends when due), and a
    # failure here never aborts the cycle.
    digest_summary: dict[str, Any] = {"sent": 0, "failed": 0, "skipped": 0, "seeded": 0}
    digest_session = session_factory()
    if digest_session is not None:
        try:
            try:
                digest_summary = send_due_digests(digest_session)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "weekly_digest_scheduler.cycle_failed",
                    extra={"error": repr(exc)},
                )
                try:
                    digest_session.rollback()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            digest_session.close()

    summary["digestsSent"] = int(digest_summary.get("sent") or 0)
    summary["digests"] = digest_summary

    summary["status"] = summary.get("status") or "ok"
    return summary


async def run_polling_cycle(session_factory: SessionFactory) -> dict[str, Any]:
    """Async wrapper that runs the blocking polling cycle in a worker thread so
    the FastAPI event loop stays responsive during a poll. Manual triggers (the
    admin endpoint) call this directly and are NOT leader-gated."""
    return await asyncio.to_thread(run_polling_cycle_sync, session_factory)


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
        # Leader election: a unique id per process; the lease must outlive one
        # interval so the active leader keeps renewing it, but expire soon after
        # a crash so another replica can take over.
        self._holder_id = str(uuid.uuid4())
        self._lease_name = "polling_cycle"
        self._lease_ttl_seconds = self._interval_seconds + 60

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
                # Lease check + the blocking cycle both run off the event loop.
                await asyncio.to_thread(self._run_cycle_if_leader)
            except Exception:  # noqa: BLE001 — never let the loop die
                logger.exception("workflow_polling_scheduler.cycle_crashed")

    def _run_cycle_if_leader(self) -> None:
        """Acquire the leader lease, then (if leader) run one polling cycle.
        Runs entirely in a worker thread. Fails OPEN on lease errors so a broken
        lease mechanism can't silently stop polling on a single instance."""
        acquired = False
        lease_ok = True
        session = self._session_factory()
        if session is not None:
            try:
                acquired = try_acquire_lease(
                    session,
                    self._lease_name,
                    self._holder_id,
                    self._lease_ttl_seconds,
                )
            except Exception:  # noqa: BLE001 — lease must not kill polling
                logger.exception("workflow_polling_scheduler.lease_error")
                lease_ok = False
            finally:
                session.close()

        if not acquired and lease_ok:
            # Another replica legitimately holds the lease — skip this cycle.
            logger.debug(
                "workflow_polling_scheduler.not_leader",
                extra={"holder": self._holder_id},
            )
            return

        run_polling_cycle_sync(self._session_factory)

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
