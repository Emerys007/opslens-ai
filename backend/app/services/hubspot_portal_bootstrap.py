from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.error
import urllib.request

from app.services.hubspot_ticket_pipeline import (
    DEFAULT_PIPELINE_LABEL,
    PIPELINE_MODE_DEDICATED,
    PIPELINE_MODE_SHARED,
    PIPELINES_API_VERSION,
    PIPELINE_OBJECT_TYPE,
    REQUIRED_TICKET_STAGES,
    STAGE_LABEL_DUPLICATE,
    STAGE_LABEL_INVESTIGATING,
    STAGE_LABEL_NEW_ALERT,
    STAGE_LABEL_RESOLVED,
    STAGE_LABEL_WAITING,
    build_ticket_pipeline_config,
    fetch_ticket_pipelines,
    select_ticket_pipeline,
    shared_mode_stage_label,
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
    # ---- v2 alert-correlation properties ---------------------------------
    # These are the link from a HubSpot ticket back to its source row in
    # the ``alerts`` table. Created here so install bootstrap is the
    # single owner of every OpsLens-owned ticket property.
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_alert_id",
        label="OpsLens Alert ID",
        value_type="string",
        field_type="text",
        description="Internal OpsLens alert id this ticket was created from.",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_severity",
        label="OpsLens Alert Severity",
        value_type="string",
        field_type="text",
        description="Severity of the OpsLens alert this ticket represents (high/medium/low).",
    ),
    PropertySpec(
        object_type="tickets",
        group_name=TICKET_GROUP.name,
        name="opslens_signature",
        label="OpsLens Alert Signature",
        value_type="string",
        field_type="text",
        description="Deterministic hash used to deduplicate OpsLens alerts.",
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


def _is_pipeline_limit_response(status: int, body: dict) -> bool:
    """Detect HubSpot's "max ticket pipelines reached" 400 response.

    Free / Starter portals are capped at 1 ticket pipeline. The response
    looks like:

        {
          "category": "API_LIMIT",
          "message": "You have reached your limit of 1 ticket pipelines.",
          "context": {"maximum pipelines": ["1"]}
        }

    Match defensively on both ``category`` and the ``maximum pipelines``
    context key — HubSpot has been known to localize messages.
    """
    if status != 400:
        return False

    category = str((body or {}).get("category") or "").strip().upper()
    if category == "API_LIMIT":
        context_keys = list(((body or {}).get("context") or {}).keys())
        if any("pipeline" in str(key).lower() for key in context_keys):
            return True

    body_text = _body_text(body)
    return "limit" in body_text and "pipeline" in body_text


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


def _ensure_dedicated_pipeline_stages(
    *,
    token: str,
    portal_id: str,
    pipeline: dict,
    stage_labels: tuple[str, ...] | None = None,
) -> tuple[list[str], list[str]]:
    """Create or normalize the OpsLens stages on a pipeline we own.

    Returns ``(created_labels, updated_labels)``. Used for the dedicated
    "OpsLens Alerts" pipeline path; in shared mode the stages get
    OpsLens-prefixed labels so we use a different code path.
    """
    pipeline_id = _pipeline_id(pipeline)
    created_stages: list[str] = []
    updated_stages: list[str] = []

    for display_order, required_stage in enumerate(REQUIRED_TICKET_STAGES):
        target_label = required_stage.label
        if stage_labels is not None:
            target_label = stage_labels[display_order]

        current_stage_id = stage_id_by_label(pipeline, target_label)
        current_ticket_state = stage_ticket_state(pipeline, target_label)

        if not current_stage_id:
            status, body = _request_json(
                token,
                "POST",
                f"/crm/pipelines/{PIPELINES_API_VERSION}/{PIPELINE_OBJECT_TYPE}/{pipeline_id}/stages",
                {
                    "displayOrder": display_order,
                    "label": target_label,
                    "metadata": {"ticketState": required_stage.ticket_state},
                },
            )
            if status not in (200, 201):
                raise RuntimeError(
                    f"Failed to create the HubSpot ticket stage {target_label} for portal {portal_id}. "
                    f"Response: {body}"
                )
            created_stages.append(target_label)
            continue

        if current_ticket_state != required_stage.ticket_state:
            status, body = _request_json(
                token,
                "PATCH",
                f"/crm/pipelines/{PIPELINES_API_VERSION}/{PIPELINE_OBJECT_TYPE}/{pipeline_id}/stages/{current_stage_id}",
                {
                    "displayOrder": display_order,
                    "label": target_label,
                    "metadata": {"ticketState": required_stage.ticket_state},
                },
            )
            if status != 200:
                raise RuntimeError(
                    f"Failed to normalize the HubSpot ticket stage {target_label} for portal {portal_id}. "
                    f"Response: {body}"
                )
            updated_stages.append(target_label)

    return created_stages, updated_stages


def _resolve_stage_ids(pipeline: dict, stage_labels: tuple[str, ...]) -> dict[str, str]:
    """Map each ``REQUIRED_TICKET_STAGES`` entry to its persisted stage id.

    ``stage_labels`` is parallel to ``REQUIRED_TICKET_STAGES`` and is the
    actual label used in this pipeline (prefixed in shared mode).
    """
    return {
        required.label: stage_id_by_label(pipeline, label)
        for required, label in zip(REQUIRED_TICKET_STAGES, stage_labels)
    }


def _ensure_pipeline_and_stages(
    *,
    token: str,
    portal_id: str,
) -> tuple[bool, list[str], list[str], str, str, dict[str, str]]:
    """Provision the OpsLens ticket pipeline (or fall back to a shared one).

    Returns ``(pipeline_created, stages_created, stages_updated,
    pipeline_id, pipeline_mode, stage_ids_by_canonical_label)``.

    ``stage_ids_by_canonical_label`` maps the *dedicated-mode* label
    (e.g. ``"New Alert"``) to the actual stage id in HubSpot — same keys
    in both modes so callers can persist them uniformly.
    """
    pipeline_created = False
    created_stages: list[str] = []
    updated_stages: list[str] = []
    pipeline_mode = PIPELINE_MODE_DEDICATED

    pipelines = fetch_ticket_pipelines(token)
    pipeline = select_ticket_pipeline(pipelines)
    stage_labels: tuple[str, ...] = tuple(stage.label for stage in REQUIRED_TICKET_STAGES)

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

        if status in (200, 201):
            pipeline_created = True
            pipeline = body
        elif _is_pipeline_limit_response(status, body):
            # Free / Starter portals can't host a dedicated OpsLens
            # pipeline. Fall back to attaching OpsLens-prefixed stages to
            # whichever pipeline already exists.
            if not pipelines:
                # Defensive: HubSpot said the limit is 1, so there must be
                # at least one pipeline. If somehow there isn't, surface
                # the original error rather than silently doing nothing.
                raise RuntimeError(
                    f"HubSpot reported the ticket pipeline limit but returned no existing "
                    f"pipelines for portal {portal_id}. Response: {body}"
                )
            pipeline = pipelines[0]
            pipeline_mode = PIPELINE_MODE_SHARED
            stage_labels = tuple(shared_mode_stage_label(stage.label) for stage in REQUIRED_TICKET_STAGES)
        else:
            raise RuntimeError(
                f"Failed to create the OpsLens Alerts ticket pipeline for portal {portal_id}. "
                f"This step depends on the installing portal allowing ticket pipeline management with the `tickets` scope. "
                f"Response: {body}"
            )

    pipeline_id = _pipeline_id(pipeline)
    if not pipeline_id:
        raise RuntimeError(f"OpsLens ticket pipeline could not be resolved for portal {portal_id}.")

    created_stages, updated_stages = _ensure_dedicated_pipeline_stages(
        token=token,
        portal_id=portal_id,
        pipeline=pipeline,
        stage_labels=stage_labels,
    )

    refreshed_pipelines = fetch_ticket_pipelines(token)
    refreshed_pipeline: dict | None = None
    for candidate in refreshed_pipelines:
        if _pipeline_id(candidate) == pipeline_id:
            refreshed_pipeline = candidate
            break
    if refreshed_pipeline is None:
        raise RuntimeError(f"OpsLens ticket pipeline could not be reloaded for portal {portal_id}.")

    stage_ids = _resolve_stage_ids(refreshed_pipeline, stage_labels)

    missing = [label for label, value in stage_ids.items() if not value]
    if missing:
        raise RuntimeError(
            f"OpsLens ticket pipeline for portal {portal_id} is missing stage ids "
            f"after provisioning: {', '.join(missing)}."
        )

    return pipeline_created, created_stages, updated_stages, pipeline_id, pipeline_mode, stage_ids


def _persist_pipeline_settings(
    *,
    session,
    portal_id: str,
    pipeline_id: str,
    pipeline_mode: str,
    stage_ids: dict[str, str],
) -> None:
    """Write the resolved pipeline + stage ids onto the portal's
    ``PortalSetting`` row. Creates the row if it does not yet exist so
    the bootstrap is the single point that materializes routing state.
    """
    if session is None:
        return

    # Lazy import: this module is also exercised in tests that mock the
    # underlying HubSpot calls without touching the DB layer.
    from app.models.portal_setting import PortalSetting

    row = session.get(PortalSetting, portal_id)
    if row is None:
        row = PortalSetting(portal_id=portal_id)
        session.add(row)

    row.opslens_pipeline_mode = pipeline_mode
    row.opslens_ticket_pipeline_id = pipeline_id
    row.opslens_stage_new_alert_id = stage_ids.get(STAGE_LABEL_NEW_ALERT, "")
    row.opslens_stage_investigating_id = stage_ids.get(STAGE_LABEL_INVESTIGATING, "")
    row.opslens_stage_waiting_id = stage_ids.get(STAGE_LABEL_WAITING, "")
    row.opslens_stage_resolved_id = stage_ids.get(STAGE_LABEL_RESOLVED, "")
    row.opslens_stage_duplicate_id = stage_ids.get(STAGE_LABEL_DUPLICATE, "")

    session.commit()


def ensure_portal_bootstrap(*, token: str, portal_id: str, session=None) -> dict:
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
        "pipelineMode": PIPELINE_MODE_DEDICATED,
        "stageIds": {},
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
        summary["pipelineMode"],
        summary["stageIds"],
    ) = _ensure_pipeline_and_stages(
        token=token,
        portal_id=cleaned_portal_id,
    )

    _persist_pipeline_settings(
        session=session,
        portal_id=cleaned_portal_id,
        pipeline_id=summary["pipelineId"],
        pipeline_mode=summary["pipelineMode"],
        stage_ids=summary["stageIds"],
    )

    return summary
