import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

BASE_URL = "https://api.hubapi.com"
TICKET_OBJECT_TYPE_ID = "0-5"
TICKET_TO_CONTACT_ASSOCIATION_TYPE_ID = 16


def _get_token() -> str:
    return os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()


def _hubspot_request(method: str, path: str, body: Optional[dict] = None) -> Tuple[int, dict]:
    token = _get_token()
    if not token:
        return 0, {"message": "HUBSPOT_PRIVATE_APP_TOKEN is not configured."}

    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.getcode(), (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw": raw}
        return exc.code, payload
    except Exception as exc:
        return 0, {"message": str(exc)}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return ""


def _resolve_ticket_pipeline_and_stage() -> Tuple[str, str]:
    env_pipeline = _clean(os.getenv("HUBSPOT_TICKET_PIPELINE_ID"))
    env_stage = _clean(os.getenv("HUBSPOT_TICKET_STAGE_ID"))
    if env_pipeline and env_stage:
        return env_pipeline, env_stage

    status, payload = _hubspot_request("GET", "/crm/pipelines/2026-03/tickets")
    if status != 200:
        return env_pipeline or "0", env_stage or "1"

    pipelines: List[dict] = []
    if isinstance(payload, list):
        pipelines = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            pipelines = payload["results"]
        elif isinstance(payload.get("pipelines"), list):
            pipelines = payload["pipelines"]

    for pipeline in pipelines:
        if pipeline.get("archived") is True:
            continue

        pipeline_id = _clean(pipeline.get("id")) or env_pipeline or "0"
        stages = pipeline.get("stages") or []

        open_stage_id = ""
        fallback_stage_id = ""

        for stage in stages:
            if stage.get("archived") is True:
                continue

            stage_id = _clean(stage.get("id"))
            if not fallback_stage_id and stage_id:
                fallback_stage_id = stage_id

            metadata = stage.get("metadata") or {}
            if _clean(metadata.get("ticketState")).upper() == "OPEN" and stage_id:
                open_stage_id = stage_id
                break

        chosen_stage_id = open_stage_id or fallback_stage_id or env_stage or "1"
        return pipeline_id, chosen_stage_id

    return env_pipeline or "0", env_stage or "1"


def _build_ticket_url(portal_id: str, ticket_id: str) -> str:
    if not portal_id or not ticket_id:
        return ""
    return f"https://app.hubspot.com/contacts/{portal_id}/record/{TICKET_OBJECT_TYPE_ID}/{ticket_id}"


def _search_existing_ticket(callback_id: str) -> Tuple[bool, str, str]:
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
        "limit": 1,
        "properties": [
            "subject",
            "opslens_ticket_callback_id",
            "hs_pipeline",
            "hs_pipeline_stage",
        ],
    }

    status, payload = _hubspot_request("POST", "/crm/v3/objects/tickets/search", body)
    if status != 200:
        return False, "", f"Ticket search failed: {status} {json.dumps(payload)}"

    results = payload.get("results") or []
    if not results:
        return False, "", ""

    ticket_id = _clean(results[0].get("id"))
    return True, ticket_id, ""


def _create_ticket(
    portal_id: str,
    contact_id: str,
    callback_id: str,
    workflow_id: str,
    severity: str,
    delivery_status: str,
    result_value: str,
    reason: str,
    analyst_note: str,
) -> Tuple[bool, str, str]:
    pipeline_id, stage_id = _resolve_ticket_pipeline_and_stage()

    subject = f"OpsLens critical alert | Workflow {workflow_id or 'unknown'} | Contact {contact_id}"
    content = "\n".join(
        [
            "OpsLens created this ticket automatically.",
            f"Portal ID: {portal_id or 'unknown'}",
            f"Contact ID: {contact_id}",
            f"Workflow ID: {workflow_id or 'unknown'}",
            f"Callback ID: {callback_id}",
            f"Severity: {severity or 'unknown'}",
            f"Result: {result_value or 'unknown'}",
            f"Delivery status: {delivery_status or 'unknown'}",
            f"Reason: {reason or 'None provided'}",
            f"Analyst note: {analyst_note or 'None provided'}",
        ]
    )

    body = {
        "properties": {
            "subject": subject,
            "content": content,
            "hs_pipeline": pipeline_id,
            "hs_pipeline_stage": stage_id,
            "hs_ticket_priority": "HIGH",
            "opslens_ticket_callback_id": callback_id,
            "opslens_ticket_workflow_id": workflow_id,
            "opslens_ticket_severity": severity,
            "opslens_ticket_delivery_status": delivery_status,
            "opslens_ticket_contact_id": contact_id,
            "opslens_ticket_reason": reason,
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": TICKET_TO_CONTACT_ASSOCIATION_TYPE_ID,
                    }
                ],
            }
        ],
    }

    status, payload = _hubspot_request("POST", "/crm/v3/objects/tickets", body)
    if status not in (200, 201):
        return False, "", f"Ticket create failed: {status} {json.dumps(payload)}"

    ticket_id = _clean(payload.get("id"))
    return True, ticket_id, ""


def sync_hubspot_ticket_for_alert(alert_payload: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "ticketAttempted": False,
        "ticketCreated": False,
        "ticketFoundExisting": False,
        "ticketId": "",
        "ticketUrl": "",
        "ticketError": "",
        "ticketSkippedReason": "",
        "ticketPipelineIdUsed": "",
        "ticketStageIdUsed": "",
    }

    if not _get_token():
        result["ticketSkippedReason"] = "missing_hubspot_private_app_token"
        return result

    severity = _first_non_empty(
        alert_payload.get("severityUsed"),
        alert_payload.get("severity"),
    ).lower()

    delivery_status = _first_non_empty(
        alert_payload.get("deliveryStatus"),
        alert_payload.get("opslens_last_alert_delivery_status"),
    ).upper()

    if severity != "critical":
        result["ticketSkippedReason"] = "severity_not_critical"
        return result

    if delivery_status != "SLACK_SENT":
        result["ticketSkippedReason"] = "delivery_not_slack_sent"
        return result

    portal_id = _first_non_empty(
        alert_payload.get("portalIdUsed"),
        alert_payload.get("portalIdUsedForSettings"),
        alert_payload.get("portalId"),
    )

    contact_id = _first_non_empty(
        alert_payload.get("objectId"),
        alert_payload.get("recordId"),
        alert_payload.get("contactId"),
    )

    callback_id = _first_non_empty(
        alert_payload.get("callbackId"),
        alert_payload.get("opslens_last_alert_callback_id"),
    )

    workflow_id = _first_non_empty(
        alert_payload.get("workflowId"),
        alert_payload.get("opslens_last_alert_workflow_id"),
    )

    result_value = _first_non_empty(
        alert_payload.get("result"),
        alert_payload.get("opslens_last_alert_result"),
    )

    reason = _first_non_empty(
        alert_payload.get("deliveryReason"),
        alert_payload.get("reason"),
        alert_payload.get("opslens_last_alert_reason"),
    )

    analyst_note = _first_non_empty(
        alert_payload.get("analystNote"),
        alert_payload.get("opslens_last_alert_analyst_note"),
    )

    if not contact_id:
        result["ticketSkippedReason"] = "missing_contact_id"
        return result

    if not callback_id:
        result["ticketSkippedReason"] = "missing_callback_id"
        return result

    pipeline_id, stage_id = _resolve_ticket_pipeline_and_stage()
    result["ticketPipelineIdUsed"] = pipeline_id
    result["ticketStageIdUsed"] = stage_id
    result["ticketAttempted"] = True

    found_existing, existing_ticket_id, search_error = _search_existing_ticket(callback_id)
    if search_error:
        result["ticketError"] = search_error
        return result

    if found_existing and existing_ticket_id:
        result["ticketFoundExisting"] = True
        result["ticketId"] = existing_ticket_id
        result["ticketUrl"] = _build_ticket_url(portal_id, existing_ticket_id)
        return result

    created, ticket_id, create_error = _create_ticket(
        portal_id=portal_id,
        contact_id=contact_id,
        callback_id=callback_id,
        workflow_id=workflow_id,
        severity=severity,
        delivery_status=delivery_status,
        result_value=result_value,
        reason=reason,
        analyst_note=analyst_note,
    )

    if not created:
        result["ticketError"] = create_error
        return result

    result["ticketCreated"] = True
    result["ticketId"] = ticket_id
    result["ticketUrl"] = _build_ticket_url(portal_id, ticket_id)
    return result