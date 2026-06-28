from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request


BASE_URL = "https://api.hubapi.com"
PIPELINES_API_VERSION = "2026-03"
PIPELINE_OBJECT_TYPE = "tickets"
DEFAULT_PIPELINE_LABEL = "OpsLens Alerts"

DEFAULT_PIPELINE_ID = os.getenv("HUBSPOT_OPSLENS_PIPELINE_ID", "").strip()

STAGE_LABEL_NEW_ALERT = "New Alert"
STAGE_LABEL_INVESTIGATING = "Investigating"
STAGE_LABEL_WAITING = "Waiting / Monitoring"
STAGE_LABEL_RESOLVED = "Resolved"
STAGE_LABEL_DUPLICATE = "Closed as Duplicate"

# Free / Starter HubSpot tiers cap ticket pipelines at 1. When the
# bootstrap can't create a dedicated "OpsLens Alerts" pipeline it falls
# back to attaching OpsLens-prefixed stages to whatever pipeline already
# exists. The prefix avoids clobbering the customer's own stage labels.
SHARED_STAGE_LABEL_PREFIX = "OpsLens "

PIPELINE_MODE_DEDICATED = "dedicated"
PIPELINE_MODE_SHARED = "shared"


def shared_mode_stage_label(label: str) -> str:
    """Map a dedicated-mode stage label to the shared-pipeline equivalent."""
    return f"{SHARED_STAGE_LABEL_PREFIX}{label}"


class PortalProvisioningRequiredError(RuntimeError):
    pass


@dataclass(frozen=True)
class RequiredTicketStage:
    label: str
    ticket_state: str


REQUIRED_TICKET_STAGES = (
    RequiredTicketStage(label=STAGE_LABEL_NEW_ALERT, ticket_state="OPEN"),
    RequiredTicketStage(label=STAGE_LABEL_INVESTIGATING, ticket_state="OPEN"),
    RequiredTicketStage(label=STAGE_LABEL_WAITING, ticket_state="OPEN"),
    RequiredTicketStage(label=STAGE_LABEL_RESOLVED, ticket_state="CLOSED"),
    RequiredTicketStage(label=STAGE_LABEL_DUPLICATE, ticket_state="CLOSED"),
)


@dataclass(frozen=True)
class TicketPipelineConfig:
    portal_id: str
    pipeline_id: str
    pipeline_label: str
    stage_new_alert: str
    stage_investigating: str
    stage_waiting: str
    stage_resolved: str
    stage_duplicate: str
    pipeline_mode: str = PIPELINE_MODE_DEDICATED

    @property
    def open_stage_ids(self) -> set[str]:
        return {
            self.stage_new_alert,
            self.stage_investigating,
            self.stage_waiting,
        }

    @property
    def closed_stage_ids(self) -> set[str]:
        return {
            self.stage_resolved,
            self.stage_duplicate,
        }

    def next_repeated_alert_stage(self, current_stage_id: str) -> str:
        current = str(current_stage_id or "").strip()

        if current == self.stage_new_alert:
            return self.stage_investigating

        if current == self.stage_investigating:
            return self.stage_waiting

        if current == self.stage_waiting:
            return self.stage_waiting

        return self.stage_investigating

    def stage_label(self, stage_id: str) -> str:
        mapping = {
            self.stage_new_alert: STAGE_LABEL_NEW_ALERT,
            self.stage_investigating: STAGE_LABEL_INVESTIGATING,
            self.stage_waiting: STAGE_LABEL_WAITING,
            self.stage_resolved: STAGE_LABEL_RESOLVED,
            self.stage_duplicate: STAGE_LABEL_DUPLICATE,
        }
        return mapping.get(str(stage_id or "").strip(), str(stage_id or "").strip() or "Unknown")


def _headers(token: str) -> dict[str, str]:
    auth_token = str(token or "").strip()
    if not auth_token:
        raise RuntimeError("A HubSpot access token is required.")
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


def _request_json(token: str, method: str, path: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
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


def _pipeline_id(pipeline: dict) -> str:
    return str(pipeline.get("id") or pipeline.get("pipelineId") or "").strip()


def _pipeline_label(pipeline: dict) -> str:
    return str(pipeline.get("label") or "").strip()


def select_ticket_pipeline(
    pipelines: list[dict],
    *,
    preferred_pipeline_id: str = DEFAULT_PIPELINE_ID,
) -> dict | None:
    preferred_id = str(preferred_pipeline_id or "").strip()
    if preferred_id:
        for pipeline in pipelines:
            if _pipeline_id(pipeline) == preferred_id:
                return pipeline

    for pipeline in pipelines:
        if _pipeline_label(pipeline) == DEFAULT_PIPELINE_LABEL:
            return pipeline

    return None


def stage_id_by_label(pipeline: dict, label: str) -> str:
    stages = pipeline.get("stages") or []
    for stage in stages:
        if str(stage.get("label") or "").strip() == label:
            return str(stage.get("id") or stage.get("stageId") or "").strip()
    return ""


def stage_ticket_state(pipeline: dict, label: str) -> str:
    stages = pipeline.get("stages") or []
    for stage in stages:
        if str(stage.get("label") or "").strip() == label:
            metadata = stage.get("metadata") or {}
            return str(metadata.get("ticketState") or "").strip().upper()
    return ""


def fetch_ticket_pipelines(token: str) -> list[dict]:
    status, payload = _request_json(
        token,
        "GET",
        f"/crm/pipelines/{PIPELINES_API_VERSION}/{PIPELINE_OBJECT_TYPE}",
    )
    if status != 200:
        raise RuntimeError(f"Failed to load HubSpot ticket pipelines: {payload}")

    return payload.get("results") or payload.get("pipelines") or []


def build_ticket_pipeline_config(portal_id: str, pipeline: dict) -> TicketPipelineConfig:
    pipeline_id = _pipeline_id(pipeline)
    if not pipeline_id:
        raise RuntimeError(f"OpsLens ticket pipeline is missing an id for portal {portal_id}.")

    pipeline_label = _pipeline_label(pipeline) or DEFAULT_PIPELINE_LABEL

    stage_new_alert = stage_id_by_label(pipeline, STAGE_LABEL_NEW_ALERT)
    stage_investigating = stage_id_by_label(pipeline, STAGE_LABEL_INVESTIGATING)
    stage_waiting = stage_id_by_label(pipeline, STAGE_LABEL_WAITING)
    stage_resolved = stage_id_by_label(pipeline, STAGE_LABEL_RESOLVED)
    stage_duplicate = stage_id_by_label(pipeline, STAGE_LABEL_DUPLICATE)

    missing_labels = [
        label
        for label, value in [
            (STAGE_LABEL_NEW_ALERT, stage_new_alert),
            (STAGE_LABEL_INVESTIGATING, stage_investigating),
            (STAGE_LABEL_WAITING, stage_waiting),
            (STAGE_LABEL_RESOLVED, stage_resolved),
            (STAGE_LABEL_DUPLICATE, stage_duplicate),
        ]
        if not value
    ]
    if missing_labels:
        labels_text = ", ".join(missing_labels)
        raise PortalProvisioningRequiredError(
            f"OpsLens ticket pipeline for portal {portal_id} is missing expected stages: {labels_text}."
        )

    return TicketPipelineConfig(
        portal_id=str(portal_id or "").strip(),
        pipeline_id=pipeline_id,
        pipeline_label=pipeline_label,
        stage_new_alert=stage_new_alert,
        stage_investigating=stage_investigating,
        stage_waiting=stage_waiting,
        stage_resolved=stage_resolved,
        stage_duplicate=stage_duplicate,
    )


def _config_from_portal_settings(portal_id: str, row) -> TicketPipelineConfig | None:
    """Build a TicketPipelineConfig from a PortalSetting row when all
    five OpsLens stage IDs have been persisted. Returns ``None`` if the
    settings row is missing fields — callers should fall back to the
    HubSpot lookup path.
    """
    if row is None:
        return None
    pipeline_id = str(getattr(row, "opslens_ticket_pipeline_id", "") or "").strip()
    if not pipeline_id:
        return None

    stage_new_alert = str(getattr(row, "opslens_stage_new_alert_id", "") or "").strip()
    stage_investigating = str(getattr(row, "opslens_stage_investigating_id", "") or "").strip()
    stage_waiting = str(getattr(row, "opslens_stage_waiting_id", "") or "").strip()
    stage_resolved = str(getattr(row, "opslens_stage_resolved_id", "") or "").strip()
    stage_duplicate = str(getattr(row, "opslens_stage_duplicate_id", "") or "").strip()

    if not all((stage_new_alert, stage_investigating, stage_waiting, stage_resolved, stage_duplicate)):
        return None

    pipeline_mode = str(getattr(row, "opslens_pipeline_mode", "") or PIPELINE_MODE_DEDICATED).strip()
    if pipeline_mode not in (PIPELINE_MODE_DEDICATED, PIPELINE_MODE_SHARED):
        pipeline_mode = PIPELINE_MODE_DEDICATED

    return TicketPipelineConfig(
        portal_id=str(portal_id or "").strip(),
        pipeline_id=pipeline_id,
        pipeline_label=DEFAULT_PIPELINE_LABEL,
        stage_new_alert=stage_new_alert,
        stage_investigating=stage_investigating,
        stage_waiting=stage_waiting,
        stage_resolved=stage_resolved,
        stage_duplicate=stage_duplicate,
        pipeline_mode=pipeline_mode,
    )


def load_portal_ticket_pipeline_config(
    *,
    token: str,
    portal_id: str,
    session=None,
) -> TicketPipelineConfig:
    """Resolve the ticket pipeline config for a portal.

    Order of preference:
      1. Persisted IDs in ``portal_settings`` (no HubSpot call needed).
         This is the post-bootstrap state for both dedicated and shared
         pipelines, and it's how tickets get routed at runtime.
      2. Fetch ticket pipelines from HubSpot and locate the dedicated
         "OpsLens Alerts" pipeline by label. Used when bootstrap has not
         yet run / persisted IDs.

    Raises ``PortalProvisioningRequiredError`` if neither source produces
    a usable config.
    """
    portal_key = str(portal_id or "").strip()

    if session is not None and portal_key:
        # Lazy import to avoid a circular dependency between services and models
        # at module-load time.
        from app.models.portal_setting import PortalSetting

        row = session.get(PortalSetting, portal_key)
        config = _config_from_portal_settings(portal_key, row)
        if config is not None:
            return config

    pipelines = fetch_ticket_pipelines(token)
    pipeline = select_ticket_pipeline(pipelines)
    if pipeline is None:
        raise PortalProvisioningRequiredError(
            f"OpsLens Alerts ticket pipeline was not found for portal {portal_id}."
        )

    return build_ticket_pipeline_config(portal_id, pipeline)
