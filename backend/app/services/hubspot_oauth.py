from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.hubspot_installation import HubSpotInstallation

HUBSPOT_AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/2026-03/token"
HUBSPOT_INTROSPECT_URL = "https://api.hubapi.com/oauth/2026-03/token/introspect"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_scopes(value: str) -> str:
    parts = [part.strip() for part in str(value or "").replace(",", " ").split() if part.strip()]
    return " ".join(parts)


def _required_scopes() -> str:
    scopes = _normalized_scopes(settings.hubspot_scopes)
    if not scopes:
        raise RuntimeError("HUBSPOT_SCOPES is not configured.")
    return scopes


def _optional_scopes() -> str:
    return _normalized_scopes(settings.hubspot_optional_scopes)


def _state_secret() -> str:
    secret = str(settings.oauth_state_secret or "").strip()
    if secret:
        return secret

    client_secret = str(settings.hubspot_client_secret or "").strip()
    if client_secret:
        return client_secret

    raise RuntimeError(
        "OAUTH_STATE_SECRET is not configured and no HUBSPOT_CLIENT_SECRET fallback is available."
    )


def _require_oauth_config() -> None:
    if not str(settings.hubspot_client_id or "").strip():
        raise RuntimeError("HUBSPOT_CLIENT_ID is not configured.")
    if not str(settings.hubspot_client_secret or "").strip():
        raise RuntimeError("HUBSPOT_CLIENT_SECRET is not configured.")
    if not str(settings.hubspot_redirect_uri or "").strip():
        raise RuntimeError("HUBSPOT_REDIRECT_URI is not configured.")


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(text: str) -> bytes:
    padded = text + ("=" * (-len(text) % 4))
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _safe_return_to(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    parsed = urllib.parse.urlparse(text)
    if parsed.scheme == "https" and parsed.netloc:
        return text

    if parsed.scheme == "http" and parsed.netloc.startswith("localhost"):
        return text

    return ""


def build_signed_state(return_to: str | None = None) -> str:
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "ts": int(_utc_now().timestamp()),
        "returnTo": _safe_return_to(return_to),
    }

    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(
        _state_secret().encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return _urlsafe_b64encode(f"{signature}.{raw}".encode("utf-8"))


def parse_signed_state(state: str) -> dict[str, Any]:
    text = str(state or "").strip()
    if not text:
        raise ValueError("Missing OAuth state.")

    try:
        decoded = _urlsafe_b64decode(text).decode("utf-8")
        signature, raw = decoded.split(".", 1)
    except Exception as exc:
        raise ValueError("OAuth state could not be decoded.") from exc

    expected = hmac.new(
        _state_secret().encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise ValueError("OAuth state signature is invalid.")

    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise ValueError("OAuth state payload is invalid JSON.") from exc

    ts = int(payload.get("ts") or 0)
    now_ts = int(_utc_now().timestamp())
    if ts <= 0 or (now_ts - ts) > int(settings.oauth_state_ttl_seconds):
        raise ValueError("OAuth state has expired.")

    payload["returnTo"] = _safe_return_to(payload.get("returnTo"))
    return payload


def build_authorization_url(return_to: str | None = None) -> str:
    _require_oauth_config()

    params = {
        "client_id": settings.hubspot_client_id,
        "scope": _required_scopes(),
        "redirect_uri": settings.hubspot_redirect_uri,
        "state": build_signed_state(return_to),
    }

    optional_scopes = _optional_scopes()
    if optional_scopes:
        params["optional_scope"] = optional_scopes

    return f"{HUBSPOT_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, form: dict[str, str]) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body or str(exc)}
        raise RuntimeError(f"HubSpot OAuth request failed: {parsed}") from exc


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    _require_oauth_config()

    auth_code = str(code or "").strip()
    if not auth_code:
        raise RuntimeError("Missing OAuth authorization code.")

    return _post_form(
        HUBSPOT_TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "client_id": settings.hubspot_client_id,
            "client_secret": settings.hubspot_client_secret,
            "redirect_uri": settings.hubspot_redirect_uri,
            "code": auth_code,
        },
    )


def introspect_access_token(access_token: str) -> dict[str, Any]:
    _require_oauth_config()

    token = str(access_token or "").strip()
    if not token:
        raise RuntimeError("Missing access token for introspection.")

    payload = _post_form(
        HUBSPOT_INTROSPECT_URL,
        {
            "client_id": settings.hubspot_client_id,
            "client_secret": settings.hubspot_client_secret,
            "token_type_hint": "access_token",
            "access_token": token,
        },
    )

    if not payload:
        raise RuntimeError("HubSpot token introspection returned an empty response.")

    return payload


def _token_expiry_from_payload(token_payload: dict[str, Any], metadata: dict[str, Any]) -> datetime | None:
    expires_in = (
        token_payload.get("expires_in")
        or token_payload.get("expiresIn")
        or metadata.get("expires_in")
        or 0
    )

    try:
        expires_seconds = int(expires_in)
    except Exception:
        expires_seconds = 0

    if expires_seconds <= 0:
        return None

    return _utc_now() + timedelta(seconds=expires_seconds)


def upsert_installation(
    session: Session,
    *,
    token_payload: dict[str, Any],
    metadata: dict[str, Any],
) -> HubSpotInstallation:
    portal_id = str(
        metadata.get("hub_id")
        or metadata.get("hubId")
        or ""
    ).strip()
    if not portal_id:
        raise RuntimeError("HubSpot OAuth metadata did not include a hub_id / portal_id.")

    scopes = metadata.get("scopes") or token_payload.get("scopes") or []
    if isinstance(scopes, str):
        scopes = [part for part in scopes.replace(",", " ").split() if part.strip()]
    elif not isinstance(scopes, list):
        scopes = []

    access_token = str(
        token_payload.get("access_token")
        or token_payload.get("accessToken")
        or ""
    ).strip()
    refresh_token = str(
        token_payload.get("refresh_token")
        or token_payload.get("refreshToken")
        or ""
    ).strip()
    token_type = str(
        token_payload.get("token_type")
        or token_payload.get("tokenType")
        or "Bearer"
    ).strip() or "Bearer"

    if not access_token:
        raise RuntimeError("HubSpot token response did not include an access token.")
    if not refresh_token:
        raise RuntimeError("HubSpot token response did not include a refresh token.")

    row = session.get(HubSpotInstallation, portal_id)
    if row is None:
        row = HubSpotInstallation(portal_id=portal_id)
        session.add(row)

    row.hub_domain = str(metadata.get("hub_domain") or metadata.get("hubDomain") or "").strip()
    row.installing_user_email = str(metadata.get("user") or "").strip()
    row.user_id = str(metadata.get("user_id") or metadata.get("userId") or "").strip()
    row.app_id = str(metadata.get("app_id") or metadata.get("appId") or settings.hubspot_app_id or "").strip()

    row.access_token = access_token
    row.refresh_token = refresh_token
    row.token_type = token_type
    row.scopes_json = json.dumps(sorted(scopes))
    row.access_token_expires_at = _token_expiry_from_payload(token_payload, metadata)
    row.is_active = True

    session.commit()
    session.refresh(row)
    return row


def refresh_access_token(session: Session, row: HubSpotInstallation) -> HubSpotInstallation:
    _require_oauth_config()

    refresh_token = str(row.refresh_token or "").strip()
    if not refresh_token:
        raise RuntimeError("No refresh token is stored for this HubSpot installation.")

    token_payload = _post_form(
        HUBSPOT_TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "client_id": settings.hubspot_client_id,
            "client_secret": settings.hubspot_client_secret,
            "redirect_uri": settings.hubspot_redirect_uri,
            "refresh_token": refresh_token,
        },
    )

    access_token = str(
        token_payload.get("access_token")
        or token_payload.get("accessToken")
        or ""
    ).strip()
    if not access_token:
        raise RuntimeError("HubSpot refresh response did not include an access token.")

    row.access_token = access_token

    new_refresh = str(
        token_payload.get("refresh_token")
        or token_payload.get("refreshToken")
        or ""
    ).strip()
    if new_refresh:
        row.refresh_token = new_refresh

    row.token_type = str(
        token_payload.get("token_type")
        or token_payload.get("tokenType")
        or row.token_type
        or "Bearer"
    ).strip() or "Bearer"

    row.access_token_expires_at = _token_expiry_from_payload(token_payload, {})
    row.is_active = True

    session.commit()
    session.refresh(row)
    return row


def get_portal_access_token(session: Session, portal_id: str) -> str:
    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise RuntimeError("portal_id is required.")

    row = session.get(HubSpotInstallation, portal_key)
    if row is None or not row.is_active:
        raise RuntimeError(f"No active HubSpot OAuth installation was found for portal {portal_key}.")

    expires_at = row.access_token_expires_at
    if expires_at is None or expires_at <= (_utc_now() + timedelta(seconds=60)):
        row = refresh_access_token(session, row)

    token = str(row.access_token or "").strip()
    if not token:
        raise RuntimeError(f"No access token is stored for portal {portal_key}.")

    return token