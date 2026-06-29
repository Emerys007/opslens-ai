"""Cross-replica leader election via a single DB lease row.

``try_acquire_lease`` atomically takes or renews a named lease: it succeeds
only if the caller already holds it or the existing lease has expired. With
multiple Render replicas each calling this before a polling cycle, exactly one
runs the cycle at a time — preventing duplicate HubSpot polling and, more
importantly, double Slack/ticket delivery.

All timestamps are naive UTC so ``expires_at <= now`` is correct on both
SQLite and Postgres.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.scheduler_lease import SchedulerLease

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def try_acquire_lease(
    session: Session, lease_name: str, holder: str, ttl_seconds: int
) -> bool:
    """Take or renew ``lease_name`` for ``holder``. Returns True if held."""
    now = _utc_now()
    expires = now + timedelta(seconds=int(ttl_seconds))

    # Atomic take-or-renew: only when we already hold it OR it's expired/unset.
    stmt = (
        update(SchedulerLease)
        .where(SchedulerLease.lease_name == lease_name)
        .where(
            or_(
                SchedulerLease.holder == holder,
                SchedulerLease.expires_at.is_(None),
                SchedulerLease.expires_at <= now,
            )
        )
        .values(holder=holder, expires_at=expires)
    )
    result = session.execute(stmt)
    if (result.rowcount or 0) > 0:
        session.commit()
        return True

    # Nothing updated: either the row doesn't exist yet, or another replica
    # holds a still-valid lease.
    existing = session.get(SchedulerLease, lease_name)
    if existing is None:
        session.add(
            SchedulerLease(lease_name=lease_name, holder=holder, expires_at=expires)
        )
        try:
            session.commit()
            return True
        except IntegrityError:
            # Another replica inserted first — they win this round.
            session.rollback()
            return False

    session.rollback()
    return False
