"""One-click remediation: re-enable a disabled HubSpot workflow.

This is the only detection-type fix HubSpot's public API supports cleanly
today. Archived properties / lists / templates have NO un-archive endpoint
(restore is UI-only), so those stay guided-steps-only.

Grounded in the v4 Automation API: GET the flow for its full definition,
flip ``isEnabled`` to True, and PUT the WHOLE object back. A partial PUT
would drop every field not included (per HubSpot's docs), so we never strip
the flow down — we round-trip exactly what we received with one field
changed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.services.hubspot_oauth import get_portal_access_token

HUBSPOT_FLOW_DETAIL_URL = "https://api.hubapi.com/automation/v4/flows/{flow_id}"
_TIMEOUT_SECONDS = 30


class WorkflowRemediationError(RuntimeError):
    """Raised when the workflow could not be re-enabled. The message is safe
    to surface to the user."""


def _request_json(
    url: str,
    access_token: str,
    *,
    method: str,
    body: dict | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


def reenable_workflow(
    session: Session,
    portal_id: str,
    workflow_id: str,
) -> dict[str, Any]:
    """Re-enable the given workflow in HubSpot. Returns a small result dict.

    Raises WorkflowRemediationError (with a user-safe message) on any failure.
    """
    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key or not workflow_key:
        raise WorkflowRemediationError("portal_id and workflow_id are required.")

    try:
        access_token = get_portal_access_token(session, portal_key)
    except Exception as exc:  # noqa: BLE001 - normalize to a user-safe error
        raise WorkflowRemediationError(
            "No active HubSpot connection for this portal."
        ) from exc

    url = HUBSPOT_FLOW_DETAIL_URL.format(
        flow_id=urllib.parse.quote(workflow_key, safe=""),
    )

    try:
        flow = _request_json(url, access_token, method="GET")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise WorkflowRemediationError(
                "That workflow no longer exists in HubSpot."
            ) from exc
        raise WorkflowRemediationError(
            f"Could not load the workflow from HubSpot (HTTP {exc.code})."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise WorkflowRemediationError(
            "Could not reach HubSpot to load the workflow."
        ) from exc

    if not isinstance(flow, dict) or not flow:
        raise WorkflowRemediationError("HubSpot returned an unexpected workflow shape.")

    if flow.get("isEnabled") is True:
        return {
            "status": "ok",
            "workflowId": workflow_key,
            "isEnabled": True,
            "alreadyEnabled": True,
        }

    # Round-trip the FULL flow with only isEnabled flipped on.
    flow["isEnabled"] = True

    try:
        updated = _request_json(url, access_token, method="PUT", body=flow)
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            raise WorkflowRemediationError(
                "The workflow changed in HubSpot since this alert. Refresh and try again."
            ) from exc
        raise WorkflowRemediationError(
            f"HubSpot rejected the update (HTTP {exc.code})."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise WorkflowRemediationError(
            "Could not reach HubSpot to update the workflow."
        ) from exc

    enabled = True
    if isinstance(updated, dict) and "isEnabled" in updated:
        enabled = bool(updated.get("isEnabled"))
    return {
        "status": "ok",
        "workflowId": workflow_key,
        "isEnabled": enabled,
        "alreadyEnabled": False,
    }
