from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

HUBSPOT_API_BASE = "https://api.hubapi.com"
HUBSPOT_TICKET_PIPELINE_ID = os.getenv("HUBSPOT_TICKET_PIPELINE_ID", "0")
HUBSPOT_TICKET_STAGE_ID = os.getenv("HUBSPOT_TICKET_STAGE_ID", "1")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _token() -> str:
    return _clean(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _headers() -> Dict[str, str]:
    token = _token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _parse_response_body(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"data": data}
    except json.JSONDecodeError:
        return {"raw": raw}


def _request(
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any]]:
    token = _token()
    if not token:
        return 401, {"message": "Missing HUBSPOT_PRIVATE_APP_TOKEN."}

    url = path if path.startswith("http") else f"{HUBSPOT_API_BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        method=method.upper(),
        headers=_headers(),
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.getcode(), _parse_response_body(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, _parse_response_body(raw)
    except Exception as exc:
        return 500, {"message": str(exc)}


def _humanize_delivery_status(value: str) -> str:
    raw = _clean(value).upper()
    mapping = {
        "SLACK_SENT": "Slack Sent",
        "SLACK_FAILED": "Slack Failed",
        "SLACK_SKIPPED_THRESHOLD": "Slack Skipped Threshold",
        "SLACK_SKIPPED_NO_WEBHOOK": "Slack Skipped No Webhook",
        "TICKET_CREATED": "Ticket Created",
        "TICKET_UPDATED": "Ticket Updated",
        "TICKET_FAILED": "Ticket Failed",
    }
    if raw in mapping:
        return mapping[raw]
    if not raw:
        return ""
    return raw.replace("_", " ").title()


def _build_ticket_subject(contact_id: str, workflow_id: str, severity_label: str) -> str:
    return f"OpsLens {severity_label.lower()} alert | Workflow {workflow_id} | Contact {contact_id}"


def _build_ticket_description(
    portal_id: str,
    contact_id: str,
    workflow_id: str,
    callback_id: str,
    severity_label: str,
    delivery_label: str,
    reason: str,
    analyst_note: str,
) -> str:
    lines = [
        "OpsLens created this ticket automatically.",
        f"Portal ID: {portal_id or '-'}",
        f"Contact ID: {contact_id or '-'}",
        f"Workflow ID: {workflow_id or '-'}",
        f"Callback ID: {callback_id or '-'}",
        f"Severity: {severity_label or '-'}",
        f"Delivery Status: {delivery_label or '-'}",
        f"Reason: {reason or '-'}",
        f"Analyst note: {analyst_note or '-'}",
    ]
    return "\n".join(lines)


def _ticket_properties_from_alert(
    alert: Dict[str, Any],
    *,
    include_stage_fields: bool,
) -> Dict[str, Any]:
    portal_id = _clean(alert.get("portalId") or alert.get("portalIdUsed"))
    contact_id = _clean(alert.get("objectId") or alert.get("contactId"))
    workflow_id = _clean(alert.get("workflowId") or alert.get("workflow_id"))
    callback_id = _clean(alert.get("callbackId"))
    analyst_note = _clean(alert.get("analystNote"))
    reason = _clean(
        alert.get("reason")
        or alert.get("ticketReason")
        or alert.get("deliveryReason")
        or alert.get("deliveryReasonUsed")
    )

    severity_raw = _clean(
        alert.get("severityUsed")
        or alert.get("severity")
        or alert.get("severityOverride")
        or "critical"
    ).lower()
    severity_label = severity_raw.capitalize() if severity_raw else "Critical"

    delivery_raw = _clean(
        alert.get("deliveryStatus")
        or alert.get("slackStatus")
        or alert.get("opslens_last_alert_delivery_status")
        or "SLACK_SENT"
    )
    delivery_label = _humanize_delivery_status(delivery_raw)

    props: Dict[str, Any] = {
        "subject": _build_ticket_subject(contact_id, workflow_id, severity_label),
        "content": _build_ticket_description(
            portal_id=portal_id,
            contact_id=contact_id,
            workflow_id=workflow_id,
            callback_id=callback_id,
            severity_label=severity_label,
            delivery_label=delivery_label,
            reason=reason,
            analyst_note=analyst_note,
        ),
        "opslens_ticket_callback_id": callback_id,
        "opslens_ticket_workflow_id": workflow_id,
        "opslens_ticket_severity": severity_label,
        "opslens_ticket_delivery_status": delivery_label,
        "opslens_ticket_contact_id": contact_id,
        "opslens_ticket_reason": reason,
    }

    if include_stage_fields:
        props["hs_pipeline"] = HUBSPOT_TICKET_PIPELINE_ID
        props["hs_pipeline_stage"] = HUBSPOT_TICKET_STAGE_ID

    return props


@lru_cache(maxsize=128)
def _get_ticket_stage_state(pipeline_id: str, stage_id: str) -> str:
    pipeline_id = _clean(pipeline_id)
    stage_id = _clean(stage_id)
    if not pipeline_id or not stage_id:
        return ""

    safe_pipeline = urllib.parse.quote(pipeline_id, safe="")
    safe_stage = urllib.parse.quote(stage_id, safe="")
    status, payload = _request(
        "GET",
        f"/crm/v3/pipelines/tickets/{safe_pipeline}/stages/{safe_stage}",
    )
    if status < 200 or status >= 300:
        return ""

    metadata = payload.get("metadata") or {}
    return _clean(metadata.get("ticketState")).upper()


def _find_matching_open_ticket(
    *,
    contact_id: str,
    workflow_id: str,
    severity_label: str,
) -> Optional[Dict[str, Any]]:
    if not contact_id or not workflow_id or not severity_label:
        return None

    body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "opslens_ticket_contact_id",
                        "operator": "EQ",
                        "value": contact_id,
                    },
                    {
                        "propertyName": "opslens_ticket_workflow_id",
                        "operator": "EQ",
                        "value": workflow_id,
                    },
                    {
                        "propertyName": "opslens_ticket_severity",
                        "operator": "EQ",
                        "value": severity_label,
                    },
                ]
            }
        ],
        "properties": [
            "subject",
            "hs_pipeline",
            "hs_pipeline_stage",
            "opslens_ticket_contact_id",
            "opslens_ticket_workflow_id",
            "opslens_ticket_severity",
            "opslens_ticket_callback_id",
            "opslens_ticket_delivery_status",
            "opslens_ticket_reason",
        ],
        "sorts": ["-createdate"],
        "limit": 100,
    }

    status, payload = _request("POST", "/crm/v3/objects/tickets/search", body)
    if status < 200 or status >= 300:
        return None

    for result in payload.get("results", []):
        props = result.get("properties") or {}
        pipeline_id = _clean(props.get("hs_pipeline"))
        stage_id = _clean(props.get("hs_pipeline_stage"))

        stage_state = _get_ticket_stage_state(pipeline_id, stage_id)

        # If HubSpot clearly says CLOSED, skip it.
        if stage_state == "CLOSED":
            continue

        # If HubSpot says OPEN, or the stage state could not be resolved,
        # treat the newest matching ticket as reusable.
        return result

    return None


def _ensure_ticket_contact_association(ticket_id: str, contact_id: str) -> Tuple[bool, str]:
    ticket_id = _clean(ticket_id)
    contact_id = _clean(contact_id)

    if not ticket_id:
        return False, "Missing ticket ID for association."
    if not contact_id:
        return False, "Missing contact ID for association."

    safe_ticket = urllib.parse.quote(ticket_id, safe="")
    safe_contact = urllib.parse.quote(contact_id, safe="")
    status, payload = _request(
        "PUT",
        f"/crm/v4/objects/tickets/{safe_ticket}/associations/default/contact/{safe_contact}",
    )

    if status in (200, 201, 204):
        return True, ""

    error_message = _clean(payload.get("message") or payload.get("raw") or payload)
    return False, error_message or f"Association request failed with status {status}."


def _create_ticket(properties: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    status, payload = _request(
        "POST",
        "/crm/v3/objects/tickets",
        {"properties": properties},
    )
    if status in (200, 201):
        return True, "", payload
    message = _clean(payload.get("message") or payload.get("raw") or payload)
    return False, message or f"Ticket create failed with status {status}.", payload


def _update_ticket(ticket_id: str, properties: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    safe_ticket = urllib.parse.quote(ticket_id, safe="")
    status, payload = _request(
        "PATCH",
        f"/crm/v3/objects/tickets/{safe_ticket}",
        {"properties": properties},
    )
    if status in (200, 201):
        return True, "", payload
    message = _clean(payload.get("message") or payload.get("raw") or payload)
    return False, message or f"Ticket update failed with status {status}.", payload


def sync_hubspot_ticket_for_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ticketSyncAttempted": False,
        "ticketSyncOk": False,
        "ticketId": "",
        "ticketCreated": False,
        "ticketUpdated": False,
        "ticketAssociationOk": False,
        "ticketReason": "",
        "ticketSyncError": "",
    }

    if not _token():
        result["ticketReason"] = "HubSpot ticket sync was skipped because HUBSPOT_PRIVATE_APP_TOKEN is missing."
        return result

    severity_raw = _clean(
        alert.get("severityUsed")
        or alert.get("severity")
        or alert.get("severityOverride")
        or "critical"
    ).lower()

    if severity_raw != "critical":
        result["ticketReason"] = "HubSpot ticket sync was skipped because the alert severity is not critical."
        return result

    contact_id = _clean(alert.get("objectId") or alert.get("contactId"))
    workflow_id = _clean(alert.get("workflowId") or alert.get("workflow_id"))
    if not contact_id or not workflow_id:
        result["ticketReason"] = "HubSpot ticket sync was skipped because contact ID or workflow ID is missing."
        return result

    severity_label = severity_raw.capitalize()
    result["ticketSyncAttempted"] = True

    existing_ticket = _find_matching_open_ticket(
        contact_id=contact_id,
        workflow_id=workflow_id,
        severity_label=severity_label,
    )

    if existing_ticket:
        ticket_id = _clean(existing_ticket.get("id"))
        update_properties = _ticket_properties_from_alert(
            alert,
            include_stage_fields=False,
        )

        ok, error_message, _ = _update_ticket(ticket_id, update_properties)
        if not ok:
            result["ticketId"] = ticket_id
            result["ticketSyncError"] = error_message
            result["ticketReason"] = error_message or "HubSpot ticket update failed."
            return result

        association_ok, association_error = _ensure_ticket_contact_association(ticket_id, contact_id)

        result["ticketId"] = ticket_id
        result["ticketUpdated"] = association_ok
        result["ticketAssociationOk"] = association_ok
        result["ticketSyncOk"] = association_ok

        if association_ok:
            result["ticketReason"] = "HubSpot ticket updated successfully."
            result["ticketSyncError"] = ""
        else:
            result["ticketReason"] = "HubSpot ticket updated, but contact association failed."
            result["ticketSyncError"] = association_error or "Unknown ticket association error."

        return result

    create_properties = _ticket_properties_from_alert(
        alert,
        include_stage_fields=True,
    )

    ok, error_message, payload = _create_ticket(create_properties)
    if not ok:
        result["ticketSyncError"] = error_message
        result["ticketReason"] = error_message or "HubSpot ticket create failed."
        return result

    ticket_id = _clean(payload.get("id"))
    association_ok, association_error = _ensure_ticket_contact_association(ticket_id, contact_id)

    result["ticketId"] = ticket_id
    result["ticketCreated"] = association_ok
    result["ticketAssociationOk"] = association_ok
    result["ticketSyncOk"] = association_ok

    if association_ok:
        result["ticketReason"] = "HubSpot ticket created successfully."
        result["ticketSyncError"] = ""
    else:
        result["ticketReason"] = "HubSpot ticket created, but contact association failed."
        result["ticketSyncError"] = association_error or "Unknown ticket association error."

    return result