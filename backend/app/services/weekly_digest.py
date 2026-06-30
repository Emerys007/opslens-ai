"""Weekly digest for OpsLens.

Once a week, OpsLens posts a short "here's what we caught this week" summary
to each portal's connected Slack channel. Unlike per-alert messages, the
digest fires even on a *quiet* week — an "all clear" message is itself the
product proving it kept watch, which is what keeps a monitoring tool from
being forgotten (and churned). For Agency-tier portals the digest carries the
white-label brand, so an agency can forward a clean weekly "portal health"
note to each client.

Cadence is a simple 7-day gate driven by ``PortalSetting.last_digest_sent_at``
so the digest is sent at most once per week regardless of how often the
scheduler runs. Delivery reuses the same incoming-webhook plumbing and
white-label brand resolution as per-alert Slack delivery.

Standard library only; failures never raise — callers get ``(False, msg)`` or
a summary dict so a bad digest can never abort a polling cycle.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.alert import (
    ACTIVE_STATUSES,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    Alert,
)
from app.models.portal_setting import PortalSetting
from app.services.portal_entitlements import portal_delivery_blocked
from app.services.slack_delivery import _post_to_slack, _resolve_brand_name

logger = logging.getLogger(__name__)

DIGEST_INTERVAL_DAYS = 7

# Severity display, including ``critical`` (the per-alert sender omits it).
_SEVERITY_EMOJI = {
    SEVERITY_CRITICAL: "🚨",
    SEVERITY_HIGH: "🔴",
    SEVERITY_MEDIUM: "🟡",
    SEVERITY_LOW: "⚪",
}
_SEVERITY_LABEL = {
    SEVERITY_CRITICAL: "critical",
    SEVERITY_HIGH: "high",
    SEVERITY_MEDIUM: "medium",
    SEVERITY_LOW: "low",
}
_SEVERITY_ORDER = (SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW)
_SEVERITY_RANK = {sev: rank for rank, sev in enumerate(_SEVERITY_ORDER)}

# Human category from the alert's ``source_event_type`` prefix. "Segments" is
# the current HubSpot name for what the API still calls lists.
_CATEGORY_BY_PREFIX = (
    ("property_", "Properties"),
    ("workflow_", "Workflows"),
    ("list_", "Segments"),
    ("template_", "Email templates"),
    ("owner_", "Owners"),
    ("pipeline_", "Pipelines"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _category_for(event_type: str | None) -> str:
    name = str(event_type or "")
    for prefix, label in _CATEGORY_BY_PREFIX:
        if name.startswith(prefix):
            return label
    return "Other"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def build_portal_digest(
    session: Session,
    portal_id: str,
    *,
    now: datetime | None = None,
    window_days: int = DIGEST_INTERVAL_DAYS,
) -> dict[str, Any]:
    """Summarise one portal's alert activity over the trailing window.

    Counts are computed in Python after a single per-portal fetch so the
    result is identical on SQLite (tests) and Postgres regardless of how
    each stores timezone-aware datetimes. Dedup keeps the per-portal row
    count small, so this stays cheap.
    """
    now = _aware(now) or _utc_now()
    since = now - timedelta(days=window_days)

    rows = session.query(Alert).filter(Alert.portal_id == str(portal_id)).all()

    new_alerts: list[Alert] = []
    resolved_in_window = 0
    open_now = 0
    by_severity: dict[str, int] = {sev: 0 for sev in _SEVERITY_ORDER}
    by_category: dict[str, int] = {}

    for alert in rows:
        if alert.status in ACTIVE_STATUSES:
            open_now += 1

        resolved_at = _aware(alert.resolved_at)
        if resolved_at is not None and since <= resolved_at <= now:
            resolved_in_window += 1

        created_at = _aware(alert.created_at)
        if created_at is None or not (since <= created_at <= now):
            continue

        new_alerts.append(alert)
        severity = (alert.severity or SEVERITY_MEDIUM).lower()
        if severity in by_severity:
            by_severity[severity] += 1
        else:
            by_severity[severity] = by_severity.get(severity, 0) + 1
        category = _category_for(alert.source_event_type)
        by_category[category] = by_category.get(category, 0) + 1

    def _sort_key(alert: Alert) -> tuple[int, int, datetime]:
        severity = (alert.severity or SEVERITY_MEDIUM).lower()
        rank = _SEVERITY_RANK.get(severity, len(_SEVERITY_ORDER))
        created = _aware(alert.created_at) or since
        # Severity asc (critical first), repeat desc, recency desc.
        return (rank, -int(alert.repeat_count or 1), -created.timestamp())

    top = sorted(new_alerts, key=_sort_key)[:5]
    top_issues = [
        {
            "title": (a.title or "Workflow risk detected").strip(),
            "severity": (a.severity or SEVERITY_MEDIUM).lower(),
            "category": _category_for(a.source_event_type),
            "repeat_count": int(a.repeat_count or 1),
        }
        for a in top
    ]

    return {
        "portal_id": str(portal_id),
        "window_days": window_days,
        "since": since,
        "until": now,
        "new_total": len(new_alerts),
        "by_severity": by_severity,
        "by_category": by_category,
        "resolved": resolved_in_window,
        "open": open_now,
        "top_issues": top_issues,
        "quiet": len(new_alerts) == 0,
    }


# ---------------------------------------------------------------------------
# Slack payload
# ---------------------------------------------------------------------------


def _format_window(since: datetime, until: datetime) -> str:
    """e.g. 'Jun 22 – Jun 29'."""
    return f"{since.strftime('%b %d')} – {until.strftime('%b %d')}"


def _severity_line(by_severity: dict[str, int]) -> str:
    parts = [
        f"{_SEVERITY_EMOJI[sev]} {by_severity.get(sev, 0)} {_SEVERITY_LABEL[sev]}"
        for sev in _SEVERITY_ORDER
        if by_severity.get(sev, 0) > 0
    ]
    return "  ·  ".join(parts)


def _category_line(by_category: dict[str, int]) -> str:
    # Stable, readable order: known categories first, then any extras.
    known = [label for _prefix, label in _CATEGORY_BY_PREFIX]
    ordered = [c for c in known if by_category.get(c)] + [
        c for c in sorted(by_category) if c not in known and by_category.get(c)
    ]
    return ", ".join(f"*{by_category[c]}* {c}" for c in ordered)


def build_digest_payload(digest: dict[str, Any], *, brand_name: str = "OpsLens") -> dict[str, Any]:
    """Block Kit payload for the weekly digest."""
    window = _format_window(digest["since"], digest["until"])
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 {brand_name} weekly digest"[:150],
                "emoji": True,
            },
        }
    ]

    if digest["quiet"]:
        headline = (
            "✅ *All clear this week.* No workflow-breaking changes detected. "
            "OpsLens kept watch over your properties, workflows, segments, "
            "email templates, owners and deal pipelines."
        )
        if digest["open"] > 0:
            headline += f"\n\n*{digest['open']}* issue(s) from before are still open."
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": headline}})
    else:
        total = digest["new_total"]
        noun = "change" if total == 1 else "changes"
        headline = f"OpsLens caught *{total}* workflow-risk {noun} this week."
        tail = []
        if digest["resolved"] > 0:
            tail.append(f"*{digest['resolved']}* resolved")
        if digest["open"] > 0:
            tail.append(f"*{digest['open']}* still open")
        if tail:
            headline += "  (" + " · ".join(tail) + ")"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": headline}})

        severity_line = _severity_line(digest["by_severity"])
        if severity_line:
            blocks.append(
                {"type": "context", "elements": [{"type": "mrkdwn", "text": severity_line}]}
            )

        category_line = _category_line(digest["by_category"])
        if category_line:
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Where:* {category_line}"}}
            )

        if digest["top_issues"]:
            lines = []
            for issue in digest["top_issues"]:
                emoji = _SEVERITY_EMOJI.get(issue["severity"], "🟡")
                repeat = f"  _×{issue['repeat_count']}_" if issue["repeat_count"] > 1 else ""
                lines.append(f"{emoji} {issue['title']}{repeat}")
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Top issues*\n" + "\n".join(lines)[:2900]},
                }
            )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"{brand_name} • Portal {digest['portal_id']} • {window}",
                }
            ],
        }
    )
    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def send_portal_digest(
    session: Session,
    portal_id: str,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> tuple[bool, str]:
    """Build and post one portal's weekly digest. Returns ``(ok, message)``.

    ``force`` (used by the manual "send a sample" action) bypasses the
    ``digest_enabled`` / ``slack_delivery_enabled`` / entitlement gates so a
    user can preview the digest before turning it on — it still requires a
    connected webhook. ``force`` does NOT stamp ``last_digest_sent_at`` so a
    preview never delays the real weekly send. Never raises.
    """
    portal_id = str(portal_id or "").strip()
    if not portal_id:
        return False, "Missing portal id."

    row = session.get(PortalSetting, portal_id)
    if row is None:
        return False, "No settings found for this portal yet."

    if not force:
        if not getattr(row, "digest_enabled", True):
            return False, "Weekly digest is turned off for this portal."
        if not getattr(row, "slack_delivery_enabled", True):
            return False, "Slack delivery is turned off for this portal."
        if portal_delivery_blocked(session, portal_id):
            return False, "Delivery is paused for this portal (check plan / billing)."

    webhook_url = (getattr(row, "slack_webhook_url", "") or "").strip()
    if not webhook_url:
        return False, "No Slack channel is connected. Connect Slack first."

    now = _aware(now) or _utc_now()
    try:
        digest = build_portal_digest(session, portal_id, now=now)
        brand_name = _resolve_brand_name(session, portal_id, row)
        payload = build_digest_payload(digest, brand_name=brand_name)
    except Exception as exc:  # noqa: BLE001 — never raise to caller
        logger.exception("weekly_digest.build_failed", extra={"portal_id": portal_id})
        return False, f"Could not build the digest ({exc})."

    ok, status, body = _post_to_slack(webhook_url, payload)
    if not ok:
        logger.warning(
            "weekly_digest.post_failed",
            extra={"portal_id": portal_id, "status": status, "body": body[:300]},
        )
        return False, f"Slack rejected the digest (status {status}). Try reconnecting Slack."

    return True, "Weekly digest sent — check your Slack channel."


def send_due_digests(session: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """Send the weekly digest to every portal whose 7-day window has elapsed.

    Seeds ``last_digest_sent_at`` on first sight (so the first digest lands a
    week after install, not an empty one on day zero) and stamps it on every
    *attempt* (success or fail) so a transient Slack outage can't turn into a
    digest retried every polling cycle. Best-effort: one portal's failure
    never aborts the rest, and nothing here raises.
    """
    now = _aware(now) or _utc_now()
    interval = timedelta(days=DIGEST_INTERVAL_DAYS)
    summary: dict[str, Any] = {"sent": 0, "failed": 0, "skipped": 0, "seeded": 0}

    try:
        rows = session.query(PortalSetting).all()
    except Exception:  # noqa: BLE001
        logger.exception("weekly_digest.list_failed")
        return summary

    for row in rows:
        portal_id = str(getattr(row, "portal_id", "") or "").strip()
        if not portal_id:
            continue

        if not getattr(row, "digest_enabled", True):
            summary["skipped"] += 1
            continue
        if not getattr(row, "slack_delivery_enabled", True):
            summary["skipped"] += 1
            continue
        if not (getattr(row, "slack_webhook_url", "") or "").strip():
            summary["skipped"] += 1
            continue

        last = _aware(getattr(row, "last_digest_sent_at", None))
        if last is None:
            # First sight — start the clock without sending an empty digest.
            row.last_digest_sent_at = now
            summary["seeded"] += 1
            continue
        if (now - last) < interval:
            summary["skipped"] += 1
            continue

        # Due. Entitlement is re-checked here (not stamped) so a paused portal
        # gets its overdue digest once billing resumes.
        try:
            if portal_delivery_blocked(session, portal_id):
                summary["skipped"] += 1
                continue
        except Exception:  # noqa: BLE001
            logger.exception("weekly_digest.entitlement_check_failed", extra={"portal_id": portal_id})
            summary["skipped"] += 1
            continue

        try:
            ok, _msg = send_portal_digest(session, portal_id, now=now)
        except Exception:  # noqa: BLE001 — paranoid; send_portal_digest already guards
            logger.exception("weekly_digest.send_failed", extra={"portal_id": portal_id})
            ok = False

        # Advance the cadence on attempt so a broken webhook isn't retried
        # every 2-minute cycle for a week.
        row.last_digest_sent_at = now
        summary["sent" if ok else "failed"] += 1

    try:
        session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("weekly_digest.commit_failed")
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass

    return summary
