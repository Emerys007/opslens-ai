from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.db import get_session, init_db
from app.services.hubspot_oauth import get_portal_access_token
from app.services.hubspot_ticket_pipeline import (
    PortalProvisioningRequiredError,
    TicketPipelineConfig,
    load_portal_ticket_pipeline_config,
)


BASE_URL = "https://api.hubapi.com"

VISIBLE_TICKET_PROPERTIES = [
    "subject",
    "hs_pipeline",
    "hs_pipeline_stage",
    "hs_lastmodifieddate",
    "opslens_ticket_callback_id",
    "opslens_ticket_workflow_id",
    "opslens_ticket_contact_id",
    "opslens_ticket_severity",
    "opslens_ticket_delivery_status",
    "opslens_ticket_reason",
    "opslens_ticket_first_alert_at",
    "opslens_ticket_last_alert_at",
    "opslens_ticket_repeat_count",
    "opslens_ticket_resolved_at",
    "opslens_ticket_resolution_reason",
]


def _resolve_token_for_portal(portal_id: str) -> str:
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id:
        raise RuntimeError("portal_id is required to resolve a HubSpot OAuth token.")

    if not init_db():
        raise RuntimeError("Database is not available, so the OAuth installation token could not be resolved.")

    session = get_session()
    if session is None:
        raise RuntimeError("Database session could not be created, so the OAuth installation token could not be resolved.")

    try:
        return get_portal_access_token(session, cleaned_portal_id)
    finally:
        session.close()


def _headers(token: str) -> dict[str, str]:
    auth_token = str(token or "").strip()
    if not auth_token:
        raise RuntimeError("A HubSpot access token is required.")
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


def _request_json(token: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=_headers(token),
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed


def _search_visible_tickets(
    token: str,
    pipeline_config: TicketPipelineConfig,
    limit: int,
) -> tuple[int, dict]:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "hs_pipeline",
                        "operator": "EQ",
                        "value": pipeline_config.pipeline_id,
                    },
                    {
                        "propertyName": "opslens_ticket_contact_id",
                        "operator": "HAS_PROPERTY",
                    },
                ]
            }
        ],
        "properties": VISIBLE_TICKET_PROPERTIES,
        "sorts": ["-hs_lastmodifieddate"],
        "limit": max(1, min(limit, 20)),
    }
    return _request_json(token, "POST", "/crm/v3/objects/tickets/search", payload)


def load_ticket_visibility(*, portal_id: str, limit: int = 4) -> dict:
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id:
        raise RuntimeError("portal_id is required.")

    token = _resolve_token_for_portal(cleaned_portal_id)

    try:
        pipeline_config = load_portal_ticket_pipeline_config(
            token=token,
            portal_id=cleaned_portal_id,
        )
    except PortalProvisioningRequiredError as exc:
        return {
            "status": "ok",
            "portalId": cleaned_portal_id,
            "provisioned": False,
            "reason": str(exc),
            "total": 0,
            "results": [],
        }

    status, body = _search_visible_tickets(token, pipeline_config, limit)
    if status != 200:
        raise RuntimeError(f"Ticket search failed: {body}")

    return {
        "status": "ok",
        "portalId": cleaned_portal_id,
        "provisioned": True,
        "pipelineId": pipeline_config.pipeline_id,
        "total": int(body.get("total") or 0),
        "results": body.get("results") or [],
    }
