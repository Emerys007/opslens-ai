from datetime import datetime, timezone
from pathlib import Path
import hashlib
import hmac
import json
import os

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(prefix="/workflow-actions", tags=["workflow-actions"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "workflow_action_events.jsonl"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _public_request_uri(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    uri = f"{scheme}://{host}{request.url.path}"
    if request.url.query:
        uri += f"?{request.url.query}"
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

    return {
        "status": "ok",
        "message": "Workflow action event captured by OpsLens AI.",
        "loggedTo": str(LOG_FILE),
        "receivedAtUtc": received_at,
        "signatureValidated": validation["enabled"],
        "signatureVersion": validation["signatureVersion"],
        "callbackId": details["callbackId"],
    }
