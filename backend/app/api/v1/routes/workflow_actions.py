from datetime import datetime, timezone
from pathlib import Path
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Request, status

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent
from app.services.portal_settings import load_portal_settings, normalize_severity

router = APIRouter(prefix="/workflow-actions", tags=["workflow-actions"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "workflow_action_events.jsonl"

SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _first_header_value(value: str | None) -> str:
    return str(value or "").split(",")[0].strip()


def _public_request_uri(request: Request) -> str:
    scheme = _first_header_value(request.headers.get("x-forwarded-proto")) or request.url.scheme
    host = (
        _first_header_value(request.headers.get("x-forwarded-host"))
        or _first_header_value(request.headers.get("host"))
        or request.url.netloc
    )

    path = request.scope.get("raw_path", b"").decode("utf-8") or request.url.path
    query_string = request.scope.get("query_string", b"").decode("utf-8")

    uri = f"{scheme}://{host}{path}"
    if query_string:
        uri += f"?{query_string}"
    return uri


def _expected_v2_signature(
    *,
    client_secret: str,
    method: str,
    uri: str,
    body_bytes: bytes,
) -> str:
    body_text = body_bytes.decode("utf-8") if body_bytes else ""
    source = f"{client_secret}{method.upper()}{uri}{body_text}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _append_event(event: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _extract_payload_details(payload: dict) -> dict:
    origin = payload.get("origin") or {}
    context = payload.get("context") or {}
    obj = payload.get("object") or {}
    input_fields = payload.get("inputFields") or {}

    return {
        "callbackId": payload.get("callbackId"),
        "portalId": origin.get("portalId"),
        "actionDefinitionId": origin.get("actionDefinitionId"),
        "actionDefinitionVersion": origin.get("actionDefinitionVersion"),
        "workflowId": context.get("workflowId"),
        "workflowSource": context.get("source"),
        "objectType": obj.get("objectType"),
        "objectId": obj.get("objectId"),
        "severityOverride": input_fields.get("severityOverride"),
        "analystNote": input_fields.get("analystNote"),
    }


def _save_event_to_db(event: dict, details: dict, payload: dict, validation: dict) -> tuple[bool, str]:
    session = None
    try:
        init_db()
        session = get_session()
        if session is None:
            return False, "DATABASE_URL not configured"

        row = AlertEvent(
            received_at_utc=datetime.fromisoformat(event["receivedAtUtc"]),
            callback_id=details.get("callbackId"),
            portal_id=str(details.get("portalId")) if details.get("portalId") is not None else None,
            action_definition_id=str(details.get("actionDefinitionId")) if details.get("actionDefinitionId") is not None else None,
            action_definition_version=str(details.get("actionDefinitionVersion")) if details.get("actionDefinitionVersion") is not None else None,
            workflow_id=str(details.get("workflowId")) if details.get("workflowId") is not None else None,
            workflow_source=details.get("workflowSource"),
            object_type=details.get("objectType"),
            object_id=str(details.get("objectId")) if details.get("objectId") is not None else None,
            severity_override=details.get("severityOverride"),
            analyst_note=details.get("analystNote"),
            result=event.get("result"),
            reason=event.get("reason"),
            signature_version=validation.get("signatureVersion"),
            uri=validation.get("uri"),
            payload_json=json.dumps(payload),
        )
        session.add(row)
        session.commit()
        return True, ""
    except Exception as exc:
        if session is not None:
            session.rollback()
        return False, str(exc)
    finally:
        if session is not None:
            session.close()


def _normalize_slack_severity(value: str | None, fallback: str = "high") -> str:
    return normalize_severity(value, fallback)


def _should_send_to_slack(event_severity: str, threshold: str) -> bool:
    return SEVERITY_RANK[_normalize_slack_severity(event_severity)] >= SEVERITY_RANK[_normalize_slack_severity(threshold)]


def _load_portal_settings_for_workflow(portal_id: str) -> dict:
    session = None
    try:
        db_ready = init_db()
        session = get_session()

        if not db_ready or session is None:
            return load_portal_settings(None, portal_id)

        return load_portal_settings(session, portal_id)
    except Exception:
        return load_portal_settings(None, portal_id)
    finally:
        if session is not None:
            session.close()


def _send_slack_webhook(webhook_url: str, text: str) -> dict:
    body = json.dumps({"text": text}).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            response_body = response.read().decode("utf-8", errors="replace")
            return {
                "ok": 200 <= status_code < 300,
                "statusCode": status_code,
                "body": response_body,
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = str(exc)

        return {
            "ok": False,
            "statusCode": exc.code,
            "body": error_body,
            "error": error_body or str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "statusCode": None,
            "body": "",
            "error": str(exc),
        }


def _build_slack_message(details: dict, portal_id: str, severity: str) -> str:
    workflow_id = str(details.get("workflowId", "unknown"))
    object_type = str(details.get("objectType", "unknown"))
    object_id = str(details.get("objectId", "unknown"))
    callback_id = str(details.get("callbackId", "") or "")
    analyst_note = str(details.get("analystNote", "") or "").strip()

    lines = [
        "OpsLens alert received",
        f"Severity: {severity.upper()}",
        f"Portal ID: {portal_id}",
        f"Workflow ID: {workflow_id}",
        f"Object: {object_type} / {object_id}",
    ]

    if callback_id:
        lines.append(f"Callback ID: {callback_id}")

    if analyst_note:
        lines.append(f"Analyst note: {analyst_note}")

    return "\n".join(lines)


@router.post("/notify")
async def notify(request: Request):
    raw_body = await request.body()

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be valid JSON.",
        ) from exc

    client_secret = os.getenv("HUBSPOT_CLIENT_SECRET", "").strip()
    validate_signature = _truthy(os.getenv("HUBSPOT_VALIDATE_SIGNATURE", "true"))

    signature_version = request.headers.get("x-hubspot-signature-version", "")
    provided_signature = request.headers.get("x-hubspot-signature", "")
    uri = _public_request_uri(request)

    details = _extract_payload_details(payload)
    received_at = datetime.now(timezone.utc).isoformat()

    validation = {
        "enabled": validate_signature,
        "signatureVersion": signature_version or "missing",
        "signaturePresent": bool(provided_signature),
        "signatureValid": False,
        "uri": uri,
        "hostHeader": request.headers.get("host", ""),
        "forwardedHost": request.headers.get("x-forwarded-host", ""),
        "forwardedProto": request.headers.get("x-forwarded-proto", ""),
    }

    if validate_signature:
        if not client_secret:
            event = {
                "receivedAtUtc": received_at,
                "result": "rejected",
                "reason": "missing_client_secret",
                "validation": validation,
                "http": {
                    "method": request.method,
                    "clientIp": request.client.host if request.client else None,
                    "userAgent": request.headers.get("user-agent", ""),
                },
                **details,
                "payload": payload,
            }
            _append_event(event)
            _save_event_to_db(event, details, payload, validation)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="HUBSPOT_CLIENT_SECRET is not configured.",
            )

        if signature_version != "v2":
            event = {
                "receivedAtUtc": received_at,
                "result": "rejected",
                "reason": "unexpected_signature_version",
                "validation": validation,
                "http": {
                    "method": request.method,
                    "clientIp": request.client.host if request.client else None,
                    "userAgent": request.headers.get("user-agent", ""),
                },
                **details,
                "payload": payload,
            }
            _append_event(event)
            _save_event_to_db(event, details, payload, validation)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unexpected HubSpot signature version.",
            )

        expected_signature = _expected_v2_signature(
            client_secret=client_secret,
            method=request.method,
            uri=uri,
            body_bytes=raw_body,
        )

        validation["signatureValid"] = hmac.compare_digest(
            expected_signature,
            provided_signature,
        )

        if not validation["signatureValid"]:
            event = {
                "receivedAtUtc": received_at,
                "result": "rejected",
                "reason": "invalid_signature",
                "validation": validation,
                "http": {
                    "method": request.method,
                    "clientIp": request.client.host if request.client else None,
                    "userAgent": request.headers.get("user-agent", ""),
                },
                **details,
                "payload": payload,
            }
            _append_event(event)
            _save_event_to_db(event, details, payload, validation)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HubSpot signature.",
            )
    else:
        validation["signatureValid"] = True

    event = {
        "receivedAtUtc": received_at,
        "result": "accepted",
        "validation": validation,
        "http": {
            "method": request.method,
            "clientIp": request.client.host if request.client else None,
            "userAgent": request.headers.get("user-agent", ""),
        },
        **details,
        "payload": payload,
    }
    _append_event(event)
    db_saved, db_error = _save_event_to_db(event, details, payload, validation)

    slack_attempted = False
    slack_sent = False
    slack_status_code = None
    slack_error = ""
    slack_threshold = "high"
    slack_webhook_configured = False
    portal_id_used_for_settings = ""
    settings_storage = "unknown"

    try:
        portal_id_used_for_settings = str(
            details.get("portalId")
            or request.query_params.get("portalId")
            or ""
        ).strip()

        portal_settings = _load_portal_settings_for_workflow(portal_id_used_for_settings)
        slack_webhook_url = str(portal_settings.get("slackWebhookUrl", "") or "").strip()
        slack_threshold = _normalize_slack_severity(
            portal_settings.get("alertThreshold"),
            "high",
        )
        slack_webhook_configured = bool(slack_webhook_url)
        settings_storage = str(portal_settings.get("storage", "unknown") or "unknown")

        raw_severity = details.get("severityOverride")
        if str(raw_severity or "").strip().lower() == "use_settings":
            incoming_severity = slack_threshold
        else:
            incoming_severity = _normalize_slack_severity(raw_severity, "high")

        if slack_webhook_url and _should_send_to_slack(incoming_severity, slack_threshold):
            slack_attempted = True
            slack_text = _build_slack_message(
                details=details,
                portal_id=portal_id_used_for_settings or "not-provided",
                severity=incoming_severity,
            )
            slack_result = _send_slack_webhook(slack_webhook_url, slack_text)
            slack_sent = bool(slack_result["ok"])
            slack_status_code = slack_result["statusCode"]
            slack_error = str(slack_result["error"] or "")
    except Exception as exc:
        slack_error = str(exc)

    return {
        "status": "ok",
        "message": "Workflow action event captured by OpsLens AI.",
        "loggedTo": str(LOG_FILE),
        "receivedAtUtc": received_at,
        "signatureValidated": validation["enabled"],
        "signatureVersion": validation["signatureVersion"],
        "callbackId": details["callbackId"],
        "uriUsedForValidation": validation["uri"],
        "portalIdUsedForSettings": portal_id_used_for_settings or "not-provided",
        "settingsStorage": settings_storage,
        "dbSaved": db_saved,
        "dbError": db_error,
        "slackAttempted": slack_attempted,
        "slackSent": slack_sent,
        "slackStatusCode": slack_status_code,
        "slackError": slack_error,
        "slackThreshold": slack_threshold,
        "slackWebhookConfigured": slack_webhook_configured,
    }