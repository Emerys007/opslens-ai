import base64
from dataclasses import dataclass
import hashlib
import hmac
import time
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, Request, status

from app.config import settings

MAX_HUBSPOT_SIGNATURE_AGE_SECONDS = 300

URI_DECODE_MAP = {
    "%3A": ":",
    "%2F": "/",
    "%3F": "?",
    "%40": "@",
    "%21": "!",
    "%24": "$",
    "%27": "'",
    "%28": "(",
    "%29": ")",
    "%2A": "*",
    "%2C": ",",
    "%3B": ";",
}


@dataclass(frozen=True)
class HubSpotPortalRequest:
    portal_id: str
    user_id: str = ""
    user_email: str = ""
    app_id: str = ""


def _first_header_value(value: str | None) -> str:
    return str(value or "").split(",")[0].strip()


def _normalize_uri(uri: str) -> str:
    parsed = urlparse(uri)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return unquote(normalized)


def public_request_uri(request: Request) -> str:
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

    for encoded, decoded in URI_DECODE_MAP.items():
        uri = uri.replace(encoded, decoded).replace(encoded.lower(), decoded)

    return uri


def validate_hubspot_v3_signature(
    method: str,
    uri: str,
    body: bytes,
    signature: str | None,
    timestamp: str | None,
    max_age_seconds: int = MAX_HUBSPOT_SIGNATURE_AGE_SECONDS,
    secret: str | None = None,
) -> bool:
    signing_secret = str(secret if secret is not None else settings.hubspot_webhook_secret).strip()
    if not signing_secret:
        return False

    if not signature or not timestamp:
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    current_millis = int(time.time() * 1000)
    if abs(current_millis - timestamp_int) > max_age_seconds * 1000:
        return False

    source = (
        method.upper()
        + _normalize_uri(uri)
        + body.decode("utf-8")
        + timestamp
    ).encode("utf-8")

    digest = hmac.new(
        signing_secret.encode("utf-8"),
        source,
        hashlib.sha256,
    ).digest()

    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _hubspot_fetch_secret() -> str:
    return str(settings.hubspot_client_secret or settings.hubspot_webhook_secret or "").strip()


def _single_signed_query_value(
    request: Request,
    key: str,
    *,
    required: bool = False,
) -> str:
    values = [
        str(value or "").strip()
        for value in request.query_params.getlist(key)
        if str(value or "").strip()
    ]
    if not values:
        if required:
            raise HTTPException(status_code=400, detail=f"{key} is required.")
        return ""

    unique_values = set(values)
    if len(unique_values) > 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Conflicting signed {key} values.",
        )
    return values[0]


async def require_hubspot_portal_request(request: Request) -> HubSpotPortalRequest:
    secret = _hubspot_fetch_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HubSpot request signing is not configured.",
        )

    body = await request.body()
    valid = validate_hubspot_v3_signature(
        request.method,
        public_request_uri(request),
        body,
        request.headers.get("x-hubspot-signature-v3"),
        request.headers.get("x-hubspot-request-timestamp"),
        secret=secret,
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HubSpot request signature.",
        )

    portal_id = _single_signed_query_value(request, "portalId", required=True)
    app_id = _single_signed_query_value(request, "appId")
    expected_app_id = str(settings.hubspot_app_id or "").strip()
    if expected_app_id and app_id and app_id != expected_app_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signed appId does not match this OpsLens app.",
        )

    return HubSpotPortalRequest(
        portal_id=portal_id,
        user_id=_single_signed_query_value(request, "userId"),
        user_email=_single_signed_query_value(request, "userEmail"),
        app_id=app_id,
    )
