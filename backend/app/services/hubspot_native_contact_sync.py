from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import urllib.error
import urllib.request

from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent
from app.services.hubspot_oauth import get_portal_access_token


HUBSPOT_API_BASE = "https://api.hubapi.com"


def _to_epoch_ms(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return str(int(dt.timestamp() * 1000))


def _fallback_private_app_token() -> str:
    return str(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "") or "").strip()


def _lookup_portal_id_from_alert_event(
    *,
    callback_id: str,
    contact_id: str,
    workflow_id: str,
) -> str:
    if not init_db():
        return ""

    session = get_session()
    if session is None:
        return ""

    try:
        if callback_id:
            stmt = (
                select(AlertEvent)
                .where(AlertEvent.callback_id == str(callback_id).strip())
                .order_by(desc(AlertEvent.received_at_utc))
                .limit(1)
            )
            row = session.execute(stmt).scalars().first()
            if row and str(row.portal_id or "").strip():
                return str(row.portal_id).strip()

        if contact_id and workflow_id:
            stmt = (
                select(AlertEvent)
                .where(AlertEvent.object_id == str(contact_id).strip())
                .where(AlertEvent.workflow_id == str(workflow_id).strip())
                .order_by(desc(AlertEvent.received_at_utc))
                .limit(1)
            )
            row = session.execute(stmt).scalars().first()
            if row and str(row.portal_id or "").strip():
                return str(row.portal_id).strip()

        return ""
    finally:
        session.close()


def _resolve_token(
    *,
    portal_id: str,
    callback_id: str,
    contact_id: str,
    workflow_id: str,
) -> tuple[str, str]:
    resolved_portal_id = str(portal_id or "").strip()

    if not resolved_portal_id:
        resolved_portal_id = _lookup_portal_id_from_alert_event(
            callback_id=callback_id,
            contact_id=contact_id,
            workflow_id=workflow_id,
        )

    if resolved_portal_id and init_db():
        session = get_session()
        if session is not None:
            try:
                return get_portal_access_token(session, resolved_portal_id), resolved_portal_id
            except Exception:
                pass
            finally:
                session.close()

    fallback = _fallback_private_app_token()
    if fallback:
        return fallback, resolved_portal_id

    if resolved_portal_id:
        raise RuntimeError(
            f"No HubSpot OAuth token is available for portal {resolved_portal_id} and no private-app fallback is configured."
        )

    raise RuntimeError(
        "No portal_id could be resolved for this contact sync and HUBSPOT_PRIVATE_APP_TOKEN fallback is not configured."
    )


def sync_latest_alert_to_hubspot_contact(
    *,
    contact_id: str,
    received_at_utc: str,
    workflow_id: str,
    callback_id: str,
    severity: str,
    result: str,
    reason: str,
    analyst_note: str,
    delivery_status: str,
    portal_id: str = "",
) -> tuple[bool, str, list[str]]:
    contact_id = str(contact_id or "").strip()
    if not contact_id:
        return False, "No contact_id was provided.", []

    try:
        token, _ = _resolve_token(
            portal_id=portal_id,
            callback_id=callback_id,
            contact_id=contact_id,
            workflow_id=workflow_id,
        )
    except Exception as exc:
        return False, str(exc), []

    properties = {
        "opslens_last_alert_at": _to_epoch_ms(received_at_utc),
        "opslens_last_alert_severity": str(severity or "").strip(),
        "opslens_last_alert_result": str(result or "").strip(),
        "opslens_last_alert_callback_id": str(callback_id or "").strip(),
        "opslens_last_alert_workflow_id": str(workflow_id or "").strip(),
        "opslens_last_alert_reason": str(reason or "").strip(),
        "opslens_last_alert_analyst_note": str(analyst_note or "").strip(),
        "opslens_last_alert_delivery_status": str(delivery_status or "").strip(),
    }

    body = json.dumps({"properties": properties}).encode("utf-8")

    request = urllib.request.Request(
        f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts/{contact_id}",
        data=body,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                return True, "", sorted(properties.keys())

            response_body = response.read().decode("utf-8", errors="replace")
            return False, response_body or f"Unexpected status {status_code}", []
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = str(exc)
        return False, body_text or str(exc), []
    except Exception as exc:
        return False, str(exc), []