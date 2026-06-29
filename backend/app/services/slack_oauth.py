"""Slack "Connect" via OAuth v2 (incoming-webhook flow).

The user clicks Connect -> Slack shows its own channel picker -> Slack returns
a per-channel incoming-webhook URL, which OpsLens stores in
``PortalSetting.slack_webhook_url`` and posts alerts to via the existing
(unchanged) delivery path. The OAuth ``state`` carries the authenticated
portal id so the callback knows which portal to attach the connection to.

Standard library only (same urllib pattern as the rest of the codebase).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.config import settings

SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_SCOPE = "incoming-webhook"
_STATE_TTL_SECONDS = 900
_TIMEOUT_SECONDS = 15


class SlackOAuthError(RuntimeError):
    """Raised when the Slack connection cannot be completed. Message is
    safe to surface to the user."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _state_secret() -> str:
    secret = str(
        settings.oauth_state_secret or settings.hubspot_client_secret or ""
    ).strip()
    if not secret:
        raise SlackOAuthError("OAUTH_STATE_SECRET is not configured.")
    return secret


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _redirect_uri() -> str:
    base = str(settings.backend_public_base_url or "https://api.app-sync.com").strip().rstrip("/")
    return f"{base}/slack/oauth-callback"


def sign_slack_state(portal_id: str) -> str:
    payload = {
        "portalId": str(portal_id or "").strip(),
        "ts": int(_utc_now().timestamp()),
        "nonce": secrets.token_urlsafe(12),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(
        _state_secret().encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return _b64encode(f"{signature}.{raw}".encode("utf-8"))


def parse_slack_state(state: str) -> str:
    """Verify the signed state and return the portal id it was minted for."""
    text = str(state or "").strip()
    if not text:
        raise SlackOAuthError("Missing Slack OAuth state.")
    try:
        decoded = _b64decode(text).decode("utf-8")
        signature, raw = decoded.split(".", 1)
    except Exception as exc:  # noqa: BLE001
        raise SlackOAuthError("Slack OAuth state could not be decoded.") from exc
    expected = hmac.new(
        _state_secret().encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise SlackOAuthError("Slack OAuth state signature is invalid.")
    try:
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise SlackOAuthError("Slack OAuth state payload is invalid.") from exc
    ts = int(payload.get("ts") or 0)
    if ts <= 0 or (int(_utc_now().timestamp()) - ts) > _STATE_TTL_SECONDS:
        raise SlackOAuthError("Slack OAuth state has expired. Try connecting again.")
    portal_id = str(payload.get("portalId") or "").strip()
    if not portal_id:
        raise SlackOAuthError("Slack OAuth state is missing the portal id.")
    return portal_id


def build_slack_authorize_url(portal_id: str) -> str:
    client_id = str(settings.slack_client_id or "").strip()
    if not client_id:
        raise SlackOAuthError("Slack is not configured (SLACK_CLIENT_ID).")
    params = {
        "client_id": client_id,
        "scope": SLACK_SCOPE,
        "redirect_uri": _redirect_uri(),
        "state": sign_slack_state(portal_id),
    }
    return f"{SLACK_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_slack_code(code: str) -> dict[str, Any]:
    """Exchange the OAuth code for an incoming-webhook URL + channel/team."""
    client_id = str(settings.slack_client_id or "").strip()
    client_secret = str(settings.slack_client_secret or "").strip()
    if not client_id or not client_secret:
        raise SlackOAuthError("Slack is not configured (SLACK_CLIENT_ID/SECRET).")

    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": str(code or "").strip(),
            "redirect_uri": _redirect_uri(),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        SLACK_TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise SlackOAuthError("Could not reach Slack to complete the connection.") from exc

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:  # noqa: BLE001
        raise SlackOAuthError("Slack returned an unexpected response.") from exc

    if not payload.get("ok"):
        raise SlackOAuthError(
            f"Slack rejected the connection: {payload.get('error') or 'unknown error'}."
        )

    webhook = payload.get("incoming_webhook") or {}
    webhook_url = str(webhook.get("url") or "").strip()
    if not webhook_url:
        raise SlackOAuthError(
            "Slack did not return an incoming webhook. Add the 'incoming-webhook' "
            "scope to the OpsLens Slack app."
        )
    return {
        "webhook_url": webhook_url,
        "channel": str(webhook.get("channel") or "").strip(),
        "team_name": str((payload.get("team") or {}).get("name") or "").strip(),
    }
