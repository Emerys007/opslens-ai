"""Re-open snoozed alerts whose snooze window has elapsed.

Snooze is implemented as ``status=ACKNOWLEDGED`` + ``snoozed_until`` (see the
dashboard ``/alerts/{id}/snooze`` endpoint). This pass — run each scheduler
cycle — flips such alerts back to OPEN once the time passes so they re-enter
the 'needs action' views, and clears ``slack_delivered_at`` so the alert
re-notifies: a snooze is a "remind me in N days", not a permanent mute. The
existing HubSpot ticket id is left intact so we don't create a duplicate
ticket.

Best-effort: never raises to the caller.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import STATUS_ACKNOWLEDGED, STATUS_OPEN, Alert

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def reopen_expired_snoozes(session: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """Re-open every acknowledged alert whose ``snoozed_until`` has passed.
    Returns ``{"reopened": n}``."""
    now = now or _utc_now()
    summary: dict[str, Any] = {"reopened": 0}
    try:
        rows = (
            session.execute(
                select(Alert).where(
                    Alert.status == STATUS_ACKNOWLEDGED,
                    Alert.snoozed_until.isnot(None),
                    Alert.snoozed_until <= now,
                )
            )
            .scalars()
            .all()
        )
        for alert in rows:
            alert.status = STATUS_OPEN
            alert.snoozed_until = None
            # Re-notify on Slack: the snooze was "remind me later". Keep the
            # ticket id so we don't open a second ticket for the same issue.
            alert.slack_delivered_at = None
            summary["reopened"] += 1
        if summary["reopened"]:
            session.commit()
    except Exception:  # noqa: BLE001 — must never abort the polling cycle
        logger.exception("alert_snooze.reopen_failed")
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
    return summary
