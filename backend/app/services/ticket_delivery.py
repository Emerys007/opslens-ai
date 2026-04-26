"""HubSpot ticket creation for OpsLens v2 alerts.

Creates one ticket per alert in the portal's OpsLens Alerts pipeline,
in the ``New Alert`` stage. Pipeline lookup is delegated to the
existing ``hubspot_ticket_pipeline.load_portal_ticket_pipeline_config``
so OpsLens has one canonical pipeline-discovery code path. Ticket
creation itself is a thin POST against ``/crm/v3/objects/tickets``
because v2 alerts are not associated to contacts/companies the way the
v1 contact-risk action's tickets were — that meant the existing
``hubspot_ticket_sync.upsert_*`` helpers (which are very contact /
note / association heavy) didn't fit cleanly. We use the same urllib
HTTP pattern the rest of the codebase uses.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.alert import STATUS_OPEN, Alert
from app.models.portal_setting import PortalSetting
from app.services.hubspot_oauth import get_portal_access_token
from app.services.hubspot_ticket_pipeline import (
    PortalProvisioningRequiredError,
    TicketPipelineConfig,
    load_portal_ticket_pipeline_config,
)
from app.services.portal_settings import severity_meets_threshold
from app.services.slack_delivery import _format_alert_body  # body parity

logger = logging.getLogger(__name__)

HUBSPOT_BASE_URL = "https://api.hubapi.com"
HUBSPOT_TICKETS_PATH = "/crm/v3/objects/tickets"
HUBSPOT_TIMEOUT_SECONDS = 30

# HubSpot's `subject` field is capped at 255 chars; we keep ours
# tighter to leave room for any prefixes consumers add later.
TICKET_SUBJECT_MAX = 240


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _truncate(text: str | None, max_length: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {str(token or '').strip()}",
        "Content-Type": "application/json",
    }


def _post_ticket(token: str, properties: dict[str, str]) -> tuple[bool, str, str]:
    """POST a new ticket. Returns ``(ok, ticket_id, error_text)``."""
    body = json.dumps({"properties": properties}, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        f"{HUBSPOT_BASE_URL}{HUBSPOT_TICKETS_PATH}",
        data=body,
        method="POST",
        headers=_headers(token),
    )
    try:
        with urllib.request.urlopen(request, timeout=HUBSPOT_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(text) if text.strip() else {}
            except Exception:  # noqa: BLE001
                payload = {"raw": text}
            ticket_id = str(payload.get("id") or "").strip()
            if not (200 <= response.status < 300) or not ticket_id:
                return False, "", text[:500]
            return True, ticket_id, ""
    except urllib.error.HTTPError as exc:
        try:
            text = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
        return False, "", f"HTTP {getattr(exc, 'code', 0)}: {text[:500]}"
    except Exception as exc:  # noqa: BLE001
        return False, "", repr(exc)


# ---------------------------------------------------------------------------
# Property assembly
# ---------------------------------------------------------------------------


def _build_ticket_properties(
    alert: Alert,
    *,
    pipeline_config: TicketPipelineConfig,
) -> dict[str, str]:
    """Map an Alert row onto the HubSpot ticket-create properties
    object. Pipes through the same body renderer Slack uses so the
    ticket and Slack message read identically.

    Only properties that bootstrap is guaranteed to provision are
    included — the v1 ``opslens_ticket_*`` family was added speculatively
    in an earlier draft, but those keys aren't in
    ``hubspot_portal_bootstrap.TICKET_PROPERTIES`` and HubSpot rejects
    create calls referencing unknown properties. Anything new added
    here MUST also be appended to ``TICKET_PROPERTIES``.
    """
    body = _format_alert_body(alert)
    return {
        "subject": _truncate(alert.title, TICKET_SUBJECT_MAX),
        "content": body,
        "hs_pipeline": pipeline_config.pipeline_id,
        "hs_pipeline_stage": pipeline_config.stage_new_alert,
        "opslens_alert_id": str(alert.id or ""),
        "opslens_severity": str(alert.severity or ""),
        "opslens_signature": str(alert.alert_signature or ""),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deliver_alert_to_ticket(session: Session, alert: Alert) -> str | None:
    """Create a HubSpot ticket for one alert. Returns the new ticket
    id on success and stamps ``alert.hubspot_ticket_id``. Returns
    ``None`` and logs on every kind of failure — never raises.
    """
    portal_id = str(alert.portal_id or "").strip()
    if not portal_id:
        logger.warning("ticket_delivery.alert_missing_portal_id", extra={"alert_id": alert.id})
        return None

    if (alert.hubspot_ticket_id or "").strip():
        logger.info(
            "ticket_delivery.alert_already_ticketed",
            extra={"alert_id": alert.id, "ticket_id": alert.hubspot_ticket_id},
        )
        return alert.hubspot_ticket_id

    try:
        token = get_portal_access_token(session, portal_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ticket_delivery.no_access_token",
            extra={"alert_id": alert.id, "portal_id": portal_id, "error": repr(exc)},
        )
        return None

    try:
        pipeline_config = load_portal_ticket_pipeline_config(
            token=token, portal_id=portal_id,
        )
    except PortalProvisioningRequiredError as exc:
        logger.warning(
            "ticket_delivery.pipeline_not_provisioned",
            extra={"alert_id": alert.id, "portal_id": portal_id, "error": str(exc)},
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ticket_delivery.pipeline_lookup_failed",
            extra={"alert_id": alert.id, "portal_id": portal_id, "error": repr(exc)},
        )
        return None

    properties = _build_ticket_properties(alert, pipeline_config=pipeline_config)
    ok, ticket_id, error = _post_ticket(token, properties)
    if not ok:
        logger.warning(
            "ticket_delivery.create_failed",
            extra={
                "alert_id": alert.id,
                "portal_id": portal_id,
                "error": error,
            },
        )
        return None

    alert.hubspot_ticket_id = ticket_id
    return ticket_id


def deliver_pending_tickets(session: Session) -> dict[str, Any]:
    """Find every open, un-ticketed alert across all portals and create
    a ticket for each that meets its portal's severity threshold and
    has ticket delivery enabled.
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
            Alert.hubspot_ticket_id.is_(None),
        )
        .order_by(Alert.created_at.asc())
        .all()
    )

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
            portal_setting, "ticket_delivery_enabled", True
        ):
            summary["skipped_disabled_or_unconfigured"] += 1
            continue

        if not severity_meets_threshold(alert.severity, portal_setting.alert_threshold):
            summary["skipped_below_threshold"] += 1
            continue

        summary["attempted"] += 1
        try:
            ticket_id = deliver_alert_to_ticket(session, alert)
        except Exception:  # noqa: BLE001 — paranoid
            logger.exception(
                "ticket_delivery.deliver_failed_unexpected",
                extra={"alert_id": alert.id, "portal_id": portal_id},
            )
            ticket_id = None

        if ticket_id:
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
