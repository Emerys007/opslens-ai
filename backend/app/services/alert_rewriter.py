"""Plain-English alert rewriter.

Takes an ``Alert.summary`` JSON blob and asks Anthropic's Haiku model
for a one-sentence consultant-friendly explanation plus a one-sentence
recommended action. Writes the results back to
``alert.plain_english_explanation`` and ``alert.recommended_action``
so Slack delivery and ticket creation pick them up automatically.

Standard library only — no ``anthropic`` SDK. Same urllib pattern as
``slack_delivery.py``. The rewriter is best-effort: every failure mode
returns ``False`` and leaves the alert untouched. Slack/ticket
delivery already falls back to the structured-summary rendering when
``plain_english_explanation`` is null, so a missing explanation
never blocks delivery.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import STATUS_OPEN, Alert

logger = logging.getLogger(__name__)


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_TIMEOUT_SECONDS = 15
ANTHROPIC_MAX_TOKENS = 300


# Fixed system prompt — the wording is product surface, do not edit
# casually. The downstream parser depends on the EXPLANATION:/ACTION:
# markers being emitted exactly.
SYSTEM_PROMPT = (
    "You are OpsLens, a HubSpot operational assistant.\n\n"
    "You are given a structured description of a HubSpot portal change "
    "that affects one or more workflows.\n\n"
    "Output exactly two sections, separated by a blank line:\n\n"
    "EXPLANATION: One sentence (max 25 words) explaining what changed "
    "and what will likely break, in language a HubSpot consultant "
    "understands. Use property names and workflow names verbatim from "
    "the input. Be direct. Do not say \"it appears,\" \"seems to,\" or "
    "\"may have.\" If unclear, say \"The cause is not clear from the "
    "available data.\"\n\n"
    "ACTION: One sentence (max 20 words) recommending what the "
    "consultant should do next.\n\n"
    "Do not include any preamble, headers other than "
    "EXPLANATION/ACTION, markdown, or commentary. Do not speculate "
    "beyond the input."
)


# ---------------------------------------------------------------------------
# Config / kill switch
# ---------------------------------------------------------------------------


def _rewriter_disabled_reason() -> str | None:
    """Return a human-readable reason if the rewriter is currently off,
    or None if it's enabled and ready to run.
    """
    if not bool(getattr(settings, "alert_rewriter_enabled", True)):
        return "kill_switch_off"
    if not str(getattr(settings, "anthropic_api_key", "") or "").strip():
        return "no_api_key"
    return None


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _build_messages_payload(summary_text: str) -> dict[str, Any]:
    return {
        "model": ANTHROPIC_MODEL,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": summary_text},
        ],
    }


def _post_to_anthropic(payload: dict[str, Any]) -> tuple[bool, int, str]:
    """POST the request to Anthropic. Returns ``(ok, status, body_text)``.
    Never raises — caller decides what to do with the failure.
    """
    api_key = str(getattr(settings, "anthropic_api_key", "") or "").strip()
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        ANTHROPIC_URL,
        data=body,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=ANTHROPIC_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8", errors="replace")
            return (200 <= response.status < 300), response.status, text
    except urllib.error.HTTPError as exc:
        try:
            text = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
        return False, int(getattr(exc, "code", 0) or 0), text
    except Exception as exc:  # noqa: BLE001
        return False, 0, repr(exc)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _extract_text_from_response(raw: str) -> str:
    """Pull the first text block out of an Anthropic Messages API
    response. Returns empty string when the shape doesn't match.
    """
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:  # noqa: BLE001
        return ""
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        return ""
    first = content[0]
    if not isinstance(first, dict):
        return ""
    if first.get("type") != "text":
        # Unknown content type — bail rather than guess.
        return ""
    text = first.get("text")
    return str(text or "").strip()


def _parse_explanation_and_action(text: str) -> tuple[str, str]:
    """Split a model response on the ``EXPLANATION:`` / ``ACTION:``
    markers and return ``(explanation, action)``. Returns
    ``("", "")`` when either marker is missing or yields an empty
    string — the caller treats that as a parse failure.
    """
    if not text:
        return "", ""
    upper = text.upper()
    exp_idx = upper.find("EXPLANATION:")
    act_idx = upper.find("ACTION:")
    if exp_idx < 0 or act_idx < 0:
        return "", ""
    if act_idx < exp_idx:
        # Wrong order — refuse rather than swap, so we don't accidentally
        # write garbage when the model skips EXPLANATION.
        return "", ""
    explanation = text[exp_idx + len("EXPLANATION:") : act_idx].strip()
    action = text[act_idx + len("ACTION:") :].strip()
    if not explanation or not action:
        return "", ""
    return explanation, action


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def rewrite_alert(session: Session, alert: Alert) -> bool:
    """Rewrite one alert's explanation/action via Anthropic. Returns
    True on success and stamps the fields onto ``alert`` (caller
    commits). Returns False on every failure mode without raising.
    """
    if (alert.plain_english_explanation or "").strip():
        # Already rewritten — never overwrite a populated field.
        return False

    disabled_reason = _rewriter_disabled_reason()
    if disabled_reason is not None:
        logger.info(
            "alert_rewriter.disabled",
            extra={"alert_id": alert.id, "reason": disabled_reason},
        )
        return False

    summary_text = (alert.summary or "").strip() or "{}"
    payload = _build_messages_payload(summary_text)
    ok, status, body = _post_to_anthropic(payload)
    if not ok:
        logger.warning(
            "alert_rewriter.api_call_failed",
            extra={
                "alert_id": alert.id,
                "status": status,
                "body": body[:500],
            },
        )
        return False

    text = _extract_text_from_response(body)
    explanation, action = _parse_explanation_and_action(text)
    if not explanation or not action:
        logger.warning(
            "alert_rewriter.parse_failed",
            extra={"alert_id": alert.id, "raw_excerpt": text[:300]},
        )
        return False

    alert.plain_english_explanation = explanation
    alert.recommended_action = action
    return True


def rewrite_pending_alerts(session: Session) -> dict[str, Any]:
    """Rewrite every open alert that doesn't yet have a plain-English
    explanation. Returns counters suitable for the scheduler summary.
    """
    summary: dict[str, Any] = {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_disabled": 0,
    }

    pending = (
        session.query(Alert)
        .filter(
            Alert.status == STATUS_OPEN,
            Alert.plain_english_explanation.is_(None),
        )
        .order_by(Alert.created_at.asc())
        .all()
    )

    disabled_reason = _rewriter_disabled_reason()
    if disabled_reason is not None:
        # Don't even attempt the rewrite — count every pending alert as
        # skipped so the cycle summary reflects the suppressed work.
        summary["skipped_disabled"] = len(pending)
        return summary

    for alert in pending:
        summary["attempted"] += 1
        try:
            ok = rewrite_alert(session, alert)
        except Exception:  # noqa: BLE001 — paranoid
            logger.exception(
                "alert_rewriter.unexpected_failure",
                extra={"alert_id": alert.id},
            )
            ok = False
        if ok:
            summary["succeeded"] += 1
        else:
            summary["failed"] += 1

    if summary["succeeded"] > 0:
        session.commit()
    else:
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass

    return summary
