"""Portal health score.

Condenses a portal's current alert burden into a single 0-100 score with a
grade (Healthy / Needs attention / At risk). A clean portal sits at 100; open
issues subtract from it, weighted by severity, and acknowledged issues count
at a reduced weight because someone is already on them. Surfaced on the
dashboard and per-client in the agency portfolio so a consultant can gauge
every portal at a glance.

Pure read. Never raises to the caller — on any error it returns an honest
``grade: "unknown"`` / ``score: None`` shape the frontend can render.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import (
    ACTIVE_STATUSES,
    STATUS_ACKNOWLEDGED,
    STATUS_RESOLVED,
    Alert,
)

logger = logging.getLogger(__name__)

# Points subtracted from a perfect 100 per OPEN alert of each severity.
# Acknowledged alerts count at ACK_FACTOR of these (still unresolved, but being
# handled — so they hurt less and using "acknowledge" nudges the score up).
SEVERITY_WEIGHT = {"critical": 30.0, "high": 14.0, "medium": 5.0, "low": 1.0}
ACK_FACTOR = 0.4

_GRADE_LABEL = {
    "healthy": "Healthy",
    "watch": "Needs attention",
    "at_risk": "At risk",
    "unknown": "Unknown",
}
# Maps to HubSpot Tag/Status tones the settings/home pages already use.
_GRADE_TONE = {
    "healthy": "success",
    "watch": "warning",
    "at_risk": "danger",
    "unknown": "default",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _grade_for(score: int) -> str:
    if score >= 90:
        return "healthy"
    if score >= 70:
        return "watch"
    return "at_risk"


def _unknown_health() -> dict:
    return {
        "score": None,
        "grade": "unknown",
        "label": _GRADE_LABEL["unknown"],
        "tone": _GRADE_TONE["unknown"],
        "activeTotal": 0,
        "openCritical": 0,
        "openHigh": 0,
        "acknowledged": 0,
        "newThisWeek": 0,
        "resolvedThisWeek": 0,
    }


def compute_portal_health(
    session: Session, portal_id: str, *, now: datetime | None = None
) -> dict:
    """Return the portal's health score + grade + the factors behind it."""
    portal_id = str(portal_id or "").strip()
    if not portal_id:
        return _unknown_health()

    now = now or _utc_now()
    week_ago = now - timedelta(days=7)

    try:
        open_by_sev: dict[str, int] = defaultdict(int)
        ack_by_sev: dict[str, int] = defaultdict(int)

        rows = session.execute(
            select(func.lower(Alert.severity), Alert.status, func.count())
            .where(Alert.portal_id == portal_id, Alert.status.in_(ACTIVE_STATUSES))
            .group_by(func.lower(Alert.severity), Alert.status)
        ).all()
        for severity, status, count in rows:
            sev = str(severity or "medium")
            if status == STATUS_ACKNOWLEDGED:
                ack_by_sev[sev] += int(count or 0)
            else:
                open_by_sev[sev] += int(count or 0)

        penalty = 0.0
        for sev, weight in SEVERITY_WEIGHT.items():
            penalty += weight * open_by_sev.get(sev, 0)
            penalty += weight * ACK_FACTOR * ack_by_sev.get(sev, 0)

        score = max(0, min(100, round(100 - penalty)))
        grade = _grade_for(score)

        def _count(*filters) -> int:
            return int(
                session.execute(
                    select(func.count())
                    .select_from(Alert)
                    .where(Alert.portal_id == portal_id, *filters)
                ).scalar()
                or 0
            )

        new_this_week = _count(Alert.created_at >= week_ago)
        resolved_this_week = _count(
            Alert.status == STATUS_RESOLVED, Alert.resolved_at >= week_ago
        )
        active_total = sum(open_by_sev.values()) + sum(ack_by_sev.values())

        return {
            "score": score,
            "grade": grade,
            "label": _GRADE_LABEL[grade],
            "tone": _GRADE_TONE[grade],
            "activeTotal": active_total,
            "openCritical": open_by_sev.get("critical", 0),
            "openHigh": open_by_sev.get("high", 0),
            "acknowledged": sum(ack_by_sev.values()),
            "newThisWeek": new_this_week,
            "resolvedThisWeek": resolved_this_week,
        }
    except Exception:  # noqa: BLE001 — health must never break the dashboard
        logger.exception("portal_health.compute_failed", extra={"portal_id": portal_id})
        return _unknown_health()
