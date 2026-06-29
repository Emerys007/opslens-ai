"""Slack OAuth callback: stores the incoming-webhook connection on the portal.

Slack redirects here after the user approves and picks a channel. We verify
the signed state (which carries the portal id), exchange the code for the
incoming-webhook URL, persist it on PortalSetting, and bounce the user back
to the OpsLens Settings tab inside their HubSpot portal.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.logging import logger
from app.db import get_session, init_db
from app.models.portal_setting import PortalSetting
from app.services.marketplace_install_routing import hubspot_app_settings_url
from app.services.slack_oauth import (
    SlackOAuthError,
    exchange_slack_code,
    parse_slack_state,
)

router = APIRouter(tags=["slack"])

_FALLBACK_REDIRECT = "https://app-sync.com/opslens"


def _redirect_target(portal_id: str) -> str:
    return hubspot_app_settings_url(portal_id) or _FALLBACK_REDIRECT


@router.get("/slack/oauth-callback")
def slack_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    portal_id = ""
    try:
        portal_id = parse_slack_state(state or "")
        if error:
            raise SlackOAuthError(f"Slack returned an error: {error}.")
        if not str(code or "").strip():
            raise SlackOAuthError("Missing Slack authorization code.")

        result = exchange_slack_code(code or "")

        if not init_db():
            raise SlackOAuthError("Database is not configured.")
        session = get_session()
        if session is None:
            raise SlackOAuthError("Database session could not be created.")
        try:
            row = session.get(PortalSetting, portal_id)
            if row is None:
                row = PortalSetting(portal_id=portal_id)
                session.add(row)
            row.slack_webhook_url = result["webhook_url"]
            row.slack_channel_name = result.get("channel", "")
            row.slack_team_name = result.get("team_name", "")
            row.slack_delivery_enabled = True
            session.commit()
        finally:
            session.close()
    except SlackOAuthError as exc:
        logger.exception(
            "slack_oauth_failed", extra={"portal_id": portal_id, "error": str(exc)}
        )
        return RedirectResponse(_redirect_target(portal_id), status_code=302)
    except Exception:  # noqa: BLE001
        logger.exception("slack_oauth_unexpected", extra={"portal_id": portal_id})
        return RedirectResponse(_redirect_target(portal_id), status_code=302)

    return RedirectResponse(_redirect_target(portal_id), status_code=302)
