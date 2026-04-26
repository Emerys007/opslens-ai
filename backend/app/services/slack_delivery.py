"""Slack delivery for OpsLens v2 alerts.

Pushes one Block Kit message per alert into the portal's configured
incoming webhook. Per-portal config and severity threshold come from
``PortalSetting`` (``slack_webhook_url``, ``alert_threshold``,
``slack_delivery_enabled``).

Standard library only — no ``requests``. Same urllib pattern as
``workflow_polling.py``. Failures never raise: callers (the scheduler)
get ``False`` back so they can move on. The next scheduler cycle will
re-attempt because the alert's ``slack_delivered_at`` stays null.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    STATUS_OPEN,
    Alert,
)
from app.models.portal_setting import PortalSetting
from app.services.portal_settings import severity_meets_threshold

logger = logging.getLogger(__name__)

SLACK_TIMEOUT_SECONDS = 10

SEVERITY_EMOJI = {
    SEVERITY_HIGH: "🔴",
    SEVERITY_MEDIUM: "🟡",
    SEVERITY_LOW: "⚪",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# ---------------------------------------------------------------------------
# Payload formatting
# ---------------------------------------------------------------------------


def _format_relative_time(when: datetime | None) -> str:
    """Short, friendly relative-time string for the message footer."""
    aware = _aware(when)
    if aware is None:
        return "just now"
    delta = _utc_now() - aware
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86_400}d ago"


def _hubspot_workflow_link(portal_id: str, workflow_id: str | None) -> str | None:
    """Deep link into the workflow editor for the impacted workflow.

    Returns None when there isn't a workflow to link to (e.g. property
    events whose impacted workflow id is missing).
    """
    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key or not workflow_key:
        return None
    return f"https://app.hubspot.com/workflows/{portal_key}/platform/flow/{workflow_key}/edit"


def _structured_summary_lines(summary: dict[str, Any]) -> list[str]:
    """Render the alert summary JSON as a small bulleted list of
    ``*Field:* value`` pairs. Used as the fallback body when the LLM
    rewriter hasn't populated ``plain_english_explanation`` yet.
    """
    if not isinstance(summary, dict):
        return []

    lines: list[str] = []
    change = summary.get("change") or {}
    if isinstance(change, dict):
        for key, label in (
            ("property_label", "Property"),
            ("property_name", "Property name"),
            ("workflow_name", "Workflow"),
            ("workflow_id", "Workflow id"),
            ("previous_type", "Previous type"),
            ("new_type", "New type"),
            ("previous_label", "Previous label"),
            ("new_label", "New label"),
            ("previous_revision_id", "Previous revision"),
            ("new_revision_id", "New revision"),
            ("previous_archived", "Previously archived"),
            ("new_archived", "Now archived"),
            ("previous_is_enabled", "Previously enabled"),
            ("new_is_enabled", "Now enabled"),
        ):
            if key in change and change[key] is not None:
                lines.append(f"• *{label}:* {change[key]}")

    impact = summary.get("impact")
    if isinstance(impact, dict):
        workflow_name = impact.get("workflow_name")
        if workflow_name:
            lines.append(f"• *Impacted workflow:* {workflow_name}")
        locations = impact.get("dependency_locations") or []
        if isinstance(locations, list) and locations:
            joined = ", ".join(f"`{loc}`" for loc in locations[:6] if loc)
            if joined:
                more = "" if len(locations) <= 6 else f" (+{len(locations) - 6} more)"
                lines.append(f"• *References:* {joined}{more}")
    return lines


def _format_alert_body(alert: Alert) -> str:
    """Markdown body for the Slack section block."""
    parts: list[str] = []

    explanation = (alert.plain_english_explanation or "").strip()
    if explanation:
        parts.append(explanation)
    else:
        try:
            summary_obj = json.loads(alert.summary or "{}")
        except Exception:  # noqa: BLE001
            summary_obj = {}
        structured = _structured_summary_lines(summary_obj)
        if structured:
            parts.append("\n".join(structured))

    recommended = (alert.recommended_action or "").strip()
    if recommended:
        parts.append(f"*Recommended action:* {recommended}")

    workflow_link = _hubspot_workflow_link(alert.portal_id, alert.impacted_workflow_id)
    if workflow_link:
        workflow_name = alert.impacted_workflow_name or alert.impacted_workflow_id or "workflow"
        parts.append(f"<{workflow_link}|Open '{workflow_name}' in HubSpot>")

    repeat = int(alert.repeat_count or 1)
    if repeat > 1:
        parts.append(f"_Repeat #{repeat} — last seen {_format_relative_time(alert.last_repeated_at)}_")

    if not parts:
        # Last-resort fallback so we never POST an empty section.
        parts.append(alert.title or "OpsLens alert")
    return "\n\n".join(parts)


def _build_slack_payload(alert: Alert) -> dict[str, Any]:
    severity = (alert.severity or SEVERITY_MEDIUM).lower()
    emoji = SEVERITY_EMOJI.get(severity, "🟡")
    title_text = (alert.title or "OpsLens alert").strip()
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    # Slack header text is capped at 150 chars.
                    "text": f"{emoji} {title_text}"[:150],
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    # Slack section text is capped at 3000 chars.
                    "text": _format_alert_body(alert)[:3000],
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"OpsLens • Portal {alert.portal_id} • "
                            f"Detected {_format_relative_time(alert.created_at)}"
                        ),
                    }
                ],
            },
        ]
    }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _post_to_slack(webhook_url: str, payload: dict[str, Any]) -> tuple[bool, int, str]:
    """POST the payload to the Slack webhook. Returns
    ``(ok, status, body)``. Never raises — caller decides what to do
    with the failure shape.
    """
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=SLACK_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8", errors="replace")
            return (200 <= response.status < 300), response.status, text
    except urllib.error.HTTPError as exc:
        try:
            text = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
        return False, int(getattr(exc, "code", 0) or 0), text
    except Exception as exc:  # noqa: BLE001 — transport error
        return False, 0, repr(exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deliver_alert_to_slack(session: Session, alert: Alert) -> bool:
    """Send one alert to its portal's configured webhook. Returns True
    on HTTP 2xx; stamps ``slack_delivered_at`` in that case.
    """
    portal_id = str(alert.portal_id or "").strip()
    if not portal_id:
        logger.warning("slack_delivery.alert_missing_portal_id", extra={"alert_id": alert.id})
        return False

    portal_setting = session.get(PortalSetting, portal_id)
    if portal_setting is None:
        logger.info(
            "slack_delivery.no_portal_settings",
            extra={"alert_id": alert.id, "portal_id": portal_id},
        )
        return False

    if not getattr(portal_setting, "slack_delivery_enabled", True):
        logger.info(
            "slack_delivery.disabled_for_portal",
            extra={"alert_id": alert.id, "portal_id": portal_id},
        )
        return False

    webhook_url = (portal_setting.slack_webhook_url or "").strip()
    if not webhook_url:
        logger.info(
            "slack_delivery.no_webhook_configured",
            extra={"alert_id": alert.id, "portal_id": portal_id},
        )
        return False

    payload = _build_slack_payload(alert)
    ok, status, body = _post_to_slack(webhook_url, payload)
    if not ok:
        logger.warning(
            "slack_delivery.post_failed",
            extra={
                "alert_id": alert.id,
                "portal_id": portal_id,
                "status": status,
                "body": body[:500],
            },
        )
        return False

    alert.slack_delivered_at = _utc_now()
    return True


def deliver_pending_alerts(session: Session) -> dict[str, Any]:
    """Find every open, undelivered alert across all portals and
    deliver each that meets its portal's severity threshold.
    """
    summary: dict[str, Any] = {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_below_threshold": 0,
        "skipped_disabled_or_unconfigured": 0,
    }

    pending = (
        session.query(Alert)
        .filter(
            Alert.status == STATUS_OPEN,
            Alert.slack_delivered_at.is_(None),
        )
        .order_by(Alert.created_at.asc())
        .all()
    )

    # Group by portal so we only fetch each portal's settings once.
    settings_cache: dict[str, PortalSetting | None] = {}

    for alert in pending:
        portal_id = str(alert.portal_id or "").strip()
        if not portal_id:
            summary["failed"] += 1
            continue

        if portal_id not in settings_cache:
            settings_cache[portal_id] = session.get(PortalSetting, portal_id)
        portal_setting = settings_cache[portal_id]

        if portal_setting is None or not getattr(
            portal_setting, "slack_delivery_enabled", True
        ):
            summary["skipped_disabled_or_unconfigured"] += 1
            continue

        if not (portal_setting.slack_webhook_url or "").strip():
            summary["skipped_disabled_or_unconfigured"] += 1
            continue

        if not severity_meets_threshold(alert.severity, portal_setting.alert_threshold):
            summary["skipped_below_threshold"] += 1
            continue

        summary["attempted"] += 1
        try:
            ok = deliver_alert_to_slack(session, alert)
        except Exception:  # noqa: BLE001 — paranoid
            logger.exception(
                "slack_delivery.deliver_failed_unexpected",
                extra={"alert_id": alert.id, "portal_id": portal_id},
            )
            ok = False

        if ok:
            summary["succeeded"] += 1
        else:
            summary["failed"] += 1

    if summary["succeeded"] > 0:
        session.commit()
    elif summary["failed"] > 0 or summary["skipped_below_threshold"] > 0:
        # Nothing to commit, but rollback any stray autogenerated
        # state so the session is clean for the next caller.
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass

    return summary


# Re-export for tests / callers that don't want to import app.config directly.
def _is_slack_globally_disabled() -> bool:  # pragma: no cover — placeholder hook
    return bool(getattr(app_settings, "disable_slack_delivery", False))
