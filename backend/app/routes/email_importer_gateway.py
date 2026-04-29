from __future__ import annotations

from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.core.logging import logger

EMAIL_IMPORTER_PREFIX = "/email-importer"
DEFAULT_EMAIL_IMPORTER_ORIGIN = "https://historic-email-importer-worker.onrender.com"
PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

SAFE_REQUEST_HEADERS = {
    "authorization",
    "content-type",
    "accept",
    "user-agent",
    "x-admin-token",
    "x-hubspot-signature",
    "x-hubspot-signature-v3",
}

HOP_BY_HOP_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

router = APIRouter(tags=["email-importer-gateway"])


def _email_importer_origin() -> str:
    configured_origin = str(settings.email_importer_origin or "").strip()
    return (configured_origin or DEFAULT_EMAIL_IMPORTER_ORIGIN).rstrip("/")


def _gateway_base() -> str:
    public_base = str(settings.backend_public_base_url or "https://api.app-sync.com").strip()
    return f"{public_base.rstrip('/')}{EMAIL_IMPORTER_PREFIX}"


def _target_url(request: Request) -> str:
    raw_path = request.scope.get("raw_path") or b""
    request_path = raw_path.decode("latin-1") if raw_path else request.url.path

    if not request_path.startswith(EMAIL_IMPORTER_PREFIX):
        request_path = EMAIL_IMPORTER_PREFIX

    target = f"{_email_importer_origin()}{request_path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"

    return target


def _forward_headers(request: Request) -> dict[str, str]:
    headers = {
        name.lower(): value
        for name, value in request.headers.items()
        if name.lower() in SAFE_REQUEST_HEADERS
    }

    headers["x-forwarded-host"] = request.headers.get("host", "api.app-sync.com")
    headers["x-forwarded-proto"] = request.url.scheme
    headers["x-forwarded-prefix"] = EMAIL_IMPORTER_PREFIX
    headers["x-app-sync-gateway"] = "email-importer"

    return headers


def _rewrite_location(value: str) -> str:
    location = str(value or "").strip()
    if not location:
        return location

    origin = _email_importer_origin()
    if not location.startswith(origin):
        return location

    suffix = location[len(origin) :]
    if suffix.startswith(EMAIL_IMPORTER_PREFIX):
        suffix = suffix[len(EMAIL_IMPORTER_PREFIX) :]

    if suffix and not suffix.startswith("/"):
        suffix = f"/{suffix}"

    return f"{_gateway_base()}{suffix}"


def _response_headers(upstream_headers: httpx.Headers) -> dict[str, str]:
    response_headers: dict[str, str] = {}

    for name, value in upstream_headers.items():
        lower_name = name.lower()
        if lower_name in HOP_BY_HOP_RESPONSE_HEADERS or lower_name in {
            "content-encoding",
            "content-length",
        }:
            continue

        response_headers[name] = _rewrite_location(value) if lower_name == "location" else value

    return response_headers


def _proxied_path_for_log(request: Request) -> str:
    parsed = urlsplit(str(request.url))
    return parsed.path


@router.api_route("/email-importer", methods=PROXY_METHODS)
@router.api_route("/email-importer/{path:path}", methods=PROXY_METHODS)
async def proxy_email_importer(request: Request, path: str = "") -> Response:
    target_url = _target_url(request)
    request_body = await request.body()
    proxied_path = _proxied_path_for_log(request)

    logger.info(
        "email_importer_gateway_proxy method=%s path=%s",
        request.method,
        proxied_path,
    )

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
            upstream_response = await client.request(
                request.method,
                target_url,
                content=request_body,
                headers=_forward_headers(request),
            )
    except httpx.RequestError as exc:
        logger.warning(
            "email_importer_gateway_upstream_error method=%s path=%s error=%s",
            request.method,
            proxied_path,
            exc.__class__.__name__,
        )
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": "Historic Email Importer upstream is unavailable.",
            },
        )

    logger.info(
        "email_importer_gateway_upstream_response method=%s path=%s status=%s",
        request.method,
        proxied_path,
        upstream_response.status_code,
    )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=_response_headers(upstream_response.headers),
    )
