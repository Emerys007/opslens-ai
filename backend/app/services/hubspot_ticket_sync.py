from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

HUBSPOT_API_BASE = "https://api.hubapi.com"

OPSLENS_TICKET_PIPELINE_ID = "opslens_alerts"
OPSLENS_TICKET_STAGE_NEW = "opslens_new_alert"
OPSLENS_TICKET_STAGE_IN_PROGRESS = "opslens_in_progress"
OPSLENS_TICKET_STAGE_WAITING = "opslens_waiting"
OPSLENS_TICKET_STAGE_RESOLVED = "opslens_resolved"
OPSLENS_TICKET_STAGE_DUPLICATE = "opslens_duplicate_closed"

# HubSpot-defined association type for Ticket -> Contact
TICKET_TO_CONTACT_ASSOCIATION_TYPE_ID = 16


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_str(value: Any) -> str:
    return _clean(value)


def _token() -> str:
    return _clean(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _headers() -> Dict[str, str]:
    token = _token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _parse_json_body(raw: str) -> Dict[str, Any]:
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
            return resp.getcode(), _parse_json_body(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, _parse_json_body(raw)
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
        "TICKET_SYNCED": "Ticket Synced",
        "TICKET_FAILED": "Ticket Failed",
        "TICKET_SKIPPED": "Ticket Skipped",
    }
    if raw in mapping:
        return mapping[raw]
    if not raw:
        return ""
    return raw.replace("_", " ").title()


def _build_ticket_subject(contact_id: str, workflow_id: str, severity_label: str) -> str:
    return f"OpsLens {severity_label.lower()} alert | Workflow {workflow_id} | Contact {contact_id}"


def _build_ticket_description(
    *,
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
        alert.get("ticketReason")
        or alert.get("reason")
        or alert.get("deliveryReason")
        or alert.get("deliveryReasonUsed")
    )

    # INTERNAL enum value for HubSpot property
    severity_raw = _clean(
        alert.get("severityUsed")
        or alert.get("severity")
        or alert.get("severityOverride")
        or "critical"
    ).lower()

    # Human-readable label for description/body only
    severity_label = severity_raw.capitalize() if severity_raw else "Critical"

    # INTERNAL enum value for HubSpot property
    delivery_raw = _clean(
        alert.get("deliveryStatus")
        or alert.get("opslens_last_alert_delivery_status")
        or "SLACK_SENT"
    ).upper()

    # Human-readable label for description/body only
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
        # These MUST be internal option values, not labels
        "opslens_ticket_callback_id": callback_id,
        "opslens_ticket_workflow_id": workflow_id,
        "opslens_ticket_severity": severity_raw,
        "opslens_ticket_delivery_status": delivery_raw,
        "opslens_ticket_contact_id": contact_id,
        "opslens_ticket_reason": reason,
    }

    if include_stage_fields:
        props["hs_pipeline"] = OPSLENS_TICKET_PIPELINE_ID
        props["hs_pipeline_stage"] = OPSLENS_TICKET_STAGE_NEW

    return props


@lru_cache(maxsize=128)
def _hubspot_stage_state(
    *,
    pipeline_id: str,
    stage_id: str,
    object_type: str = "tickets",
) -> str:
    pipeline_id = _safe_str(pipeline_id)
    stage_id = _safe_str(stage_id)
    object_type = _safe_str(object_type) or "tickets"

    if not pipeline_id or not stage_id:
        return ""

    safe_object_type = urllib.parse.quote(object_type, safe="")
    safe_pipeline = urllib.parse.quote(pipeline_id, safe="")
    safe_stage = urllib.parse.quote(stage_id, safe="")

    status, payload = _request(
        "GET",
        f"/crm/v3/pipelines/{safe_object_type}/{safe_pipeline}/stages/{safe_stage}",
    )
    if status < 200 or status >= 300:
        return ""

    metadata = (payload or {}).get("metadata") or {}
    return _safe_str(metadata.get("ticketState")).upper()


def _search_ticket_by_callback_id(callback_id: str) -> Optional[Dict[str, Any]]:
    callback_id = _clean(callback_id)
    if not callback_id:
        return None

    body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "opslens_ticket_callback_id",
                        "operator": "EQ",
                        "value": callback_id,
                    }
                ]
            }
        ],
        "properties": [
            "subject",
            "hs_pipeline",
            "hs_pipeline_stage",
            "opslens_ticket_callback_id",
            "opslens_ticket_workflow_id",
            "opslens_ticket_severity",
            "opslens_ticket_contact_id",
            "opslens_ticket_delivery_status",
            "opslens_ticket_reason",
        ],
        "sorts": [
            {
                "propertyName": "createdate",
                "direction": "DESCENDING",
            }
        ],
        "limit": 10,
    }

    status, payload = _request("POST", "/crm/v3/objects/tickets/search", body)
    if status < 200 or status >= 300:
        return None

    results = payload.get("results", [])
    return results[0] if results else None


def _find_existing_open_opslens_ticket(
    *,
    contact_id: str,
    workflow_id: str,
) -> Optional[Dict[str, Any]]:
    contact_id = _safe_str(contact_id)
    workflow_id = _safe_str(workflow_id)

    if not contact_id or not workflow_id:
        return None

    body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "associations.contact",
                        "operator": "EQ",
                        "value": contact_id,
                    },
                    {
                        "propertyName": "opslens_ticket_workflow_id",
                        "operator": "EQ",
                        "value": workflow_id,
                    },
                    {
                        "propertyName": "hs_pipeline",
                        "operator": "EQ",
                        "value": OPSLENS_TICKET_PIPELINE_ID,
                    },
                ]
            }
        ],
        "properties": [
            "hs_pipeline",
            "hs_pipeline_stage",
            "opslens_ticket_contact_id",
            "opslens_ticket_workflow_id",
            "opslens_ticket_callback_id",
            "opslens_ticket_severity",
            "opslens_ticket_delivery_status",
            "subject",
        ],
        "sorts": [
            {
                "propertyName": "createdate",
                "direction": "DESCENDING",
            }
        ],
        "limit": 100,
    }

    status, payload = _request("POST", "/crm/v3/objects/tickets/search", body)
    if status < 200 or status >= 300:
        return None

    results = (payload or {}).get("results") or []

    for ticket in results:
        props = ticket.get("properties") or {}

        ticket_pipeline = _safe_str(props.get("hs_pipeline"))
        if ticket_pipeline != OPSLENS_TICKET_PIPELINE_ID:
            continue

        # Extra guards so we do not accidentally reuse the wrong ticket.
        ticket_contact_id = _safe_str(props.get("opslens_ticket_contact_id"))
        ticket_workflow_id = _safe_str(props.get("opslens_ticket_workflow_id"))

        if ticket_contact_id and ticket_contact_id != contact_id:
            continue
        if ticket_workflow_id and ticket_workflow_id != workflow_id:
            continue

        pipeline_id = _safe_str(props.get("hs_pipeline"))
        stage_id = _safe_str(props.get("hs_pipeline_stage"))
        ticket_state = _hubspot_stage_state(
            pipeline_id=pipeline_id,
            stage_id=stage_id,
            object_type="tickets",
        )

        if ticket_state == "OPEN":
            return ticket

    return None


def _read_ticket_with_contact_associations(ticket_id: str) -> Tuple[int, Dict[str, Any]]:
    safe_ticket = urllib.parse.quote(_clean(ticket_id), safe="")
    return _request(
        "GET",
        f"/crm/v3/objects/tickets/{safe_ticket}?associations=contacts",
    )


def _association_exists(ticket_id: str, contact_id: str) -> bool:
    ticket_id = _clean(ticket_id)
    contact_id = _clean(contact_id)
    if not ticket_id or not contact_id:
        return False

    status, payload = _read_ticket_with_contact_associations(ticket_id)
    if status < 200 or status >= 300:
        return False

    associations = payload.get("associations") or {}
    contacts_assoc = associations.get("contacts") or {}
    results = contacts_assoc.get("results") or []

    for item in results:
        if _clean(item.get("id")) == contact_id:
            return True

    return False


def _ensure_ticket_contact_association(ticket_id: str, contact_id: str) -> Tuple[bool, str]:
    ticket_id = _clean(ticket_id)
    contact_id = _clean(contact_id)

    if not ticket_id:
        return False, "Missing ticket ID for association."
    if not contact_id:
        return False, "Missing contact ID for association."

    # Already linked counts as success.
    if _association_exists(ticket_id, contact_id):
        return True, ""

    safe_ticket = urllib.parse.quote(ticket_id, safe="")
    safe_contact = urllib.parse.quote(contact_id, safe="")

    status, payload = _request(
        "PUT",
        f"/crm/v4/objects/tickets/{safe_ticket}/associations/default/contact/{safe_contact}",
    )

    if status in (200, 201, 204):
        if _association_exists(ticket_id, contact_id):
            return True, ""
        return False, "Association request succeeded but verification did not confirm the contact link."

    message = _clean(payload.get("message") or payload.get("raw") or payload)

    # Some odd cases can still already be associated even if the request response is not friendly.
    if _association_exists(ticket_id, contact_id):
        return True, ""

    return False, message or f"Association request failed with status {status}."


def _build_create_body(properties: Dict[str, Any], contact_id: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {"properties": properties}

    contact_id = _clean(contact_id)
    if contact_id:
        body["associations"] = [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": TICKET_TO_CONTACT_ASSOCIATION_TYPE_ID,
                    }
                ],
            }
        ]

    return body


def _create_ticket(body: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    status, payload = _request("POST", "/crm/v3/objects/tickets", body)
    if status in (200, 201):
        return True, "", payload
    message = _clean(payload.get("message") or payload.get("raw") or payload)
    return False, message or f"Ticket create failed with status {status}.", payload


def _update_ticket(ticket_id: str, properties: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    safe_ticket = urllib.parse.quote(_clean(ticket_id), safe="")
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
        "matchedExistingTicket": False,
        "matchedByCallbackId": False,
        "matchedByOpenTicket": False,
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

    contact_id = _safe_str(alert.get("objectId") or alert.get("contactId"))
    workflow_id = _safe_str(alert.get("workflowId") or alert.get("workflow_id"))
    callback_id = _safe_str(alert.get("callbackId"))

    if not contact_id or not workflow_id:
        result["ticketReason"] = "HubSpot ticket sync was skipped because contact ID or workflow ID is missing."
        return result

    result["ticketSyncAttempted"] = True

    # 1) Exact callbackId match = retry/idempotency path.
    existing_ticket = _search_ticket_by_callback_id(callback_id) if callback_id else None
    if existing_ticket:
        ticket_id = _safe_str(existing_ticket.get("id"))
        props = _ticket_properties_from_alert(alert, include_stage_fields=False)

        ok, error_message, _ = _update_ticket(ticket_id, props)
        if not ok:
            result["ticketId"] = ticket_id
            result["ticketSyncError"] = error_message
            result["ticketReason"] = error_message or "HubSpot ticket update failed."
            return result

        association_ok, association_error = _ensure_ticket_contact_association(ticket_id, contact_id)

        result["ticketId"] = ticket_id
        result["ticketUpdated"] = True
        result["ticketAssociationOk"] = association_ok
        result["ticketSyncOk"] = association_ok
        result["matchedExistingTicket"] = True
        result["matchedByCallbackId"] = True

        if association_ok:
            result["ticketReason"] = "HubSpot ticket updated successfully."
            result["ticketSyncError"] = ""
        else:
            result["ticketReason"] = "HubSpot ticket updated, but contact association failed."
            result["ticketSyncError"] = association_error or "Unknown ticket association error."

        return result

    # 2) Existing OPEN OpsLens ticket for the same contact + workflow = reuse instead of duplicate create.
    existing_ticket = _find_existing_open_opslens_ticket(
        contact_id=contact_id,
        workflow_id=workflow_id,
    )
    if existing_ticket:
        ticket_id = _safe_str(existing_ticket.get("id"))
        props = _ticket_properties_from_alert(alert, include_stage_fields=False)

        ok, error_message, _ = _update_ticket(ticket_id, props)
        if not ok:
            result["ticketId"] = ticket_id
            result["ticketSyncError"] = error_message
            result["ticketReason"] = error_message or "HubSpot ticket update failed."
            return result

        association_ok, association_error = _ensure_ticket_contact_association(ticket_id, contact_id)

        result["ticketId"] = ticket_id
        result["ticketUpdated"] = True
        result["ticketAssociationOk"] = association_ok
        result["ticketSyncOk"] = association_ok
        result["matchedExistingTicket"] = True
        result["matchedByOpenTicket"] = True

        if association_ok:
            result["ticketReason"] = "Existing open OpsLens ticket found and updated successfully."
            result["ticketSyncError"] = ""
        else:
            result["ticketReason"] = "Existing open OpsLens ticket was updated, but contact association failed."
            result["ticketSyncError"] = association_error or "Unknown ticket association error."

        return result

    # 3) No matching OPEN ticket found = create a new ticket.
    props = _ticket_properties_from_alert(alert, include_stage_fields=True)
    body = _build_create_body(props, contact_id)

    ok, error_message, payload = _create_ticket(body)
    if not ok:
        result["ticketSyncError"] = error_message
        result["ticketReason"] = error_message or "HubSpot ticket create failed."
        return result

    ticket_id = _safe_str(payload.get("id"))

    # Association may already exist because we included it in create payload.
    association_ok = _association_exists(ticket_id, contact_id)
    association_error = ""

    if not association_ok:
        association_ok, association_error = _ensure_ticket_contact_association(ticket_id, contact_id)

    result["ticketId"] = ticket_id
    result["ticketCreated"] = True
    result["ticketAssociationOk"] = association_ok
    result["ticketSyncOk"] = association_ok

    if association_ok:
        result["ticketReason"] = "HubSpot ticket created successfully."
        result["ticketSyncError"] = ""
    else:
        result["ticketReason"] = "HubSpot ticket created, but contact association failed."
        result["ticketSyncError"] = association_error or "Unknown ticket association error."

    return result
