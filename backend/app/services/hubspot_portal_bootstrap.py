from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.error
import urllib.request

from app.services.hubspot_ticket_pipeline import (
    DEFAULT_PIPELINE_LABEL,
    PIPELINES_API_VERSION,
    PIPELINE_OBJECT_TYPE,
    REQUIRED_TICKET_STAGES,
    build_ticket_pipeline_config,
    fetch_ticket_pipelines,
    select_ticket_pipeline,
    stage_id_by_label,
    stage_ticket_state,
)


BASE_URL = "https://api.hubapi.com"


@dataclass(frozen=True)
class PropertyGroupSpec:
    object_type: str
    name: str
    label: str


@dataclass(frozen=True)
class PropertySpec:
    object_type: str
    group_name: str
    name: str
    label: str
    value_type: str
    field_type: str
    description: str = ""


CONTACT_GROUP = PropertyGroupSpec(
    object_type="contacts",
    name="opslens_ai",
    label="OpsLens AI",
)

TICKET_GROUP = PropertyGroupSpec(
    object_type="tickets",
    name="opslens_ai_tickets",
    label="OpsLens AI Tickets",
)


CONTACT_PROPERTIES = (
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_at",
        label="OpsLens Last Alert At",
        value_type="datetime",
        field_type="date",
        description="UTC timestamp for the most recent alert recorded by OpsLens.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_severity",
        label="OpsLens Last Alert Severity",
        value_type="string",
        field_type="text",
        description="Severity used for the most recent OpsLens alert.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_result",
        label="OpsLens Last Alert Result",
        value_type="string",
        field_type="text",
        description="Outcome recorded for the most recent OpsLens alert.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_callback_id",
        label="OpsLens Last Alert Callback ID",
        value_type="string",
        field_type="text",
        description="HubSpot callback ID for the most recent OpsLens alert.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_workflow_id",
        label="OpsLens Last Alert Workflow ID",
        value_type="string",
        field_type="text",
        description="HubSpot workflow ID for the most recent OpsLens alert.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_reason",
        label="OpsLens Last Alert Reason",
        value_type="string",
        field_type="textarea",
        description="Delivery or routing reason recorded for the most recent OpsLens alert.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_analyst_note",
        label="OpsLens Last Alert Analyst Note",
        value_type="string",
        field_type="textarea",
        description="Analyst note captured for the most recent OpsLens alert.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_last_alert_delivery_status",
        label="OpsLens Last Alert Delivery Status",
        value_type="string",
        field_type="text",
        description="Delivery status recorded for the most recent OpsLens alert.",
    ),
    PropertySpec(
        object_type="contacts",
        group_name=CONTACT_GROUP.name,
        name="opslens_healthy_signal_at",
        label="OpsLens Healthy Signal At",
        value_type="datetime",
        field_type="date",
        description="UTC timestamp of the latest healthy follow-up signal tracked by OpsLens.",
    ),
)


TICKET_PROPERTIES = (
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_callback_id",
        label="OpsLens Callback ID",
        value_type="string",
        field_type="text",
        description="HubSpot callback ID for the alert that opened or updated the ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_workflow_id",
        label="OpsLens Workflow ID",
        value_type="string",
        field_type="text",
        description="HubSpot workflow ID for the alert that opened or updated the ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_severity",
        label="OpsLens Severity",
        value_type="string",
        field_type="text",
        description="Severity used for the alert represented by the ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_delivery_status",
        label="OpsLens Delivery Status",
        value_type="string",
        field_type="text",
        description="Delivery status recorded for the alert represented by the ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_contact_id",
        label="OpsLens Contact ID",
        value_type="string",
        field_type="text",
        description="HubSpot contact ID associated with the OpsLens alert ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_reason",
        label="OpsLens Alert Reason",
        value_type="string",
        field_type="textarea",
        description="Reason or delivery explanation recorded for the alert ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_first_alert_at",
        label="OpsLens First Alert At",
        value_type="datetime",
        field_type="date",
        description="UTC timestamp of the first alert represented by the ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_last_alert_at",
        label="OpsLens Last Alert At",
        value_type="datetime",
        field_type="date",
        description="UTC timestamp of the latest alert represented by the ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_repeat_count",
        label="OpsLens Repeat Count",
        value_type="number",
        field_type="number",
        description="Number of repeated alerts consolidated into the ticket.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_resolved_at",
        label="OpsLens Resolved At",
        value_type="datetime",
        field_type="date",
        description="UTC timestamp when OpsLens resolved the ticket automatically.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_ticket_resolution_reason",
        label="OpsLens Resolution Reason",
        value_type="string",
        field_type="textarea",
        description="Reason recorded when OpsLens resolved the ticket automatically.",
    ),
)


def _headers(token: str) -> dict[str, str]:
    auth_token = str(token or "").strip()
    if not auth_token:
        raise RuntimeError("A HubSpot access token is required.")

    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


def _request_json(
    token: str,
    method: str,
    path: str,
    payload: dict | None = None,
) -> tuple[int, dict]:
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
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body or str(exc)}
        return exc.code, parsed


def _body_text(body: dict) -> str:
    try:
        return json.dumps(body, sort_keys=True).lower()
    except Exception:
        return str(body).lower()


def _already_exists_response(status: int, body: dict) -> bool:
    if status == 409:
        return True

    if status == 400:
        body_text = _body_text(body)
        return any(text in body_text for text in ("already exists", "duplicate", "conflict", "taken"))

    return False


def _scope_hint(object_type: str) -> str:
    if object_type == "contacts":
        return "crm.schemas.contacts.write"
    return "tickets"


def _ensure_group(
    *,
    token: str,
    portal_id: str,
    spec: PropertyGroupSpec,
) -> bool:
    read_status, read_body = _request_json(
        token,
        "GET",
        f"/crm/v3/properties/{spec.object_type}/groups/{spec.name}",
    )
    if read_status == 200:
        return False
    if read_status != 404:
        raise RuntimeError(
            f"Failed to read HubSpot property group {spec.name} for portal {portal_id}. "
            f"This step requires the `{_scope_hint(spec.object_type)}` scope. Response: {read_body}"
        )

    status, body = _request_json(
        token,
        "POST",
        f"/crm/v3/properties/{spec.object_type}/groups",
        {
            "name": spec.name,
            "label": spec.label,
            "displayOrder": -1,
        },
    )
    if status in (200, 201):
        return True
    if _already_exists_response(status, body):
        return False

    raise RuntimeError(
        f"Failed to ensure HubSpot property group {spec.name} for portal {portal_id}. "
        f"This step requires the `{_scope_hint(spec.object_type)}` scope. Response: {body}"
    )


def _ensure_property(
    *,
    token: str,
    portal_id: str,
    spec: PropertySpec,
) -> bool:
    payload = {
        "groupName": spec.group_name,
        "name": spec.name,
        "label": spec.label,
        "type": spec.value_type,
        "fieldType": spec.field_type,
    }
    if spec.description:
        payload["description"] = spec.description

    status, body = _request_json(
        token,
        "POST",
        f"/crm/v3/properties/{spec.object_type}",
        payload,
    )
    if status in (200, 201):
        return True
    if _already_exists_response(status, body):
        return False

    raise RuntimeError(
        f"Failed to ensure HubSpot property {spec.name} for portal {portal_id}. "
        f"This step requires the `{_scope_hint(spec.object_type)}` scope. Response: {body}"
    )


def _pipeline_id(pipeline: dict) -> str:
    return str(pipeline.get("id") or pipeline.get("pipelineId") or "").strip()


def _ensure_pipeline_and_stages(
    *,
    token: str,
    portal_id: str,
) -> tuple[bool, list[str], list[str], str]:
    pipeline_created = False
    created_stages: list[str] = []
    updated_stages: list[str] = []

    pipelines = fetch_ticket_pipelines(token)
    pipeline = select_ticket_pipeline(pipelines)

    if pipeline is None:
        status, body = _request_json(
            token,
            "POST",
            f"/crm/pipelines/{PIPELINES_API_VERSION}/{PIPELINE_OBJECT_TYPE}",
            {
                "displayOrder": 0,
                "label": DEFAULT_PIPELINE_LABEL,
                "stages": [
                    {
                        "displayOrder": display_order,
                        "label": stage.label,
                        "metadata": {"ticketState": stage.ticket_state},
                    }
                    for display_order, stage in enumerate(REQUIRED_TICKET_STAGES)
                ],
            },
        )
        if status not in (200, 201):
            raise RuntimeError(
                f"Failed to create the OpsLens Alerts ticket pipeline for portal {portal_id}. "
                f"This step depends on the installing portal allowing ticket pipeline management with the `tickets` scope. "
                f"Response: {body}"
            )

        pipeline_created = True
        pipeline = body

    pipeline_id = _pipeline_id(pipeline)
    if not pipeline_id:
        raise RuntimeError(f"OpsLens ticket pipeline could not be resolved for portal {portal_id}.")

    for display_order, required_stage in enumerate(REQUIRED_TICKET_STAGES):
        current_stage_id = stage_id_by_label(pipeline, required_stage.label)
        current_ticket_state = stage_ticket_state(pipeline, required_stage.label)

        if not current_stage_id:
            status, body = _request_json(
                token,
                "POST",
                f"/crm/pipelines/{PIPELINES_API_VERSION}/{PIPELINE_OBJECT_TYPE}/{pipeline_id}/stages",
                {
                    "displayOrder": display_order,
                    "label": required_stage.label,
                    "metadata": {"ticketState": required_stage.ticket_state},
                },
            )
            if status not in (200, 201):
                raise RuntimeError(
                    f"Failed to create the HubSpot ticket stage {required_stage.label} for portal {portal_id}. "
                    f"Response: {body}"
                )
            created_stages.append(required_stage.label)
            continue

        if current_ticket_state != required_stage.ticket_state:
            status, body = _request_json(
                token,
                "PATCH",
                f"/crm/pipelines/{PIPELINES_API_VERSION}/{PIPELINE_OBJECT_TYPE}/{pipeline_id}/stages/{current_stage_id}",
                {
                    "displayOrder": display_order,
                    "label": required_stage.label,
                    "metadata": {"ticketState": required_stage.ticket_state},
                },
            )
            if status != 200:
                raise RuntimeError(
                    f"Failed to normalize the HubSpot ticket stage {required_stage.label} for portal {portal_id}. "
                    f"Response: {body}"
                )
            updated_stages.append(required_stage.label)

    refreshed_pipeline = select_ticket_pipeline(fetch_ticket_pipelines(token))
    if refreshed_pipeline is None:
        raise RuntimeError(f"OpsLens ticket pipeline could not be reloaded for portal {portal_id}.")

    config = build_ticket_pipeline_config(portal_id, refreshed_pipeline)
    return pipeline_created, created_stages, updated_stages, config.pipeline_id


def ensure_portal_bootstrap(*, token: str, portal_id: str) -> dict:
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id:
        raise RuntimeError("portal_id is required for HubSpot portal bootstrap.")

    summary = {
        "portalId": cleaned_portal_id,
        "contactPropertyGroupCreated": False,
        "ticketPropertyGroupCreated": False,
        "contactPropertiesCreated": [],
        "ticketPropertiesCreated": [],
        "pipelineCreated": False,
        "stagesCreated": [],
        "stagesUpdated": [],
        "pipelineId": "",
    }

    summary["contactPropertyGroupCreated"] = _ensure_group(
        token=token,
        portal_id=cleaned_portal_id,
        spec=CONTACT_GROUP,
    )
    summary["ticketPropertyGroupCreated"] = _ensure_group(
        token=token,
        portal_id=cleaned_portal_id,
        spec=TICKET_GROUP,
    )

    for spec in CONTACT_PROPERTIES:
        created = _ensure_property(
            token=token,
            portal_id=cleaned_portal_id,
            spec=spec,
        )
        if created:
            summary["contactPropertiesCreated"].append(spec.name)

    for spec in TICKET_PROPERTIES:
        created = _ensure_property(
            token=token,
            portal_id=cleaned_portal_id,
            spec=spec,
        )
        if created:
            summary["ticketPropertiesCreated"].append(spec.name)

    (
        summary["pipelineCreated"],
        summary["stagesCreated"],
        summary["stagesUpdated"],
        summary["pipelineId"],
    ) = _ensure_pipeline_and_stages(
        token=token,
        portal_id=cleaned_portal_id,
    )

    return summary
