from __future__ import annotations

from urllib.parse import urlencode, urlparse

from app.config import settings


INSTALL_ORIGIN_EXTERNAL = "external"
INSTALL_ORIGIN_MARKETPLACE = "marketplace"


def _app_public_base_url() -> str:
    app_base = str(settings.app_public_base_url or "").strip().rstrip("/")
    if not app_base:
        app_base = "https://app-sync.com"
    return app_base


def default_external_install_complete_url() -> str:
    return f"{_app_public_base_url()}/opslens/install/complete/"


def is_hubspot_return_url(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False

    parsed = urlparse(text)
    host = str(parsed.netloc or "").strip().lower()
    return bool(parsed.scheme in {"https", "http"} and host and "hubspot" in host)


def install_origin(tenant_context: dict | None = None, return_url: str | None = None) -> str:
    context = tenant_context or {}

    for key in ("installOrigin", "origin"):
        value = str(context.get(key) or "").strip().lower()
        if value in {INSTALL_ORIGIN_EXTERNAL, INSTALL_ORIGIN_MARKETPLACE}:
            return value

    return INSTALL_ORIGIN_MARKETPLACE if is_hubspot_return_url(return_url) else INSTALL_ORIGIN_EXTERNAL


def enriched_tenant_context(
    tenant_context: dict | None = None,
    *,
    return_url: str | None = None,
) -> dict:
    context = dict(tenant_context or {})
    context["installOrigin"] = install_origin(context, return_url)
    return context


def external_install_complete_url(
    *,
    portal_id: str = "",
    plan: str = "",
    billing_interval: str = "",
    bootstrap_status: str = "",
    status: str = "",
    message: str = "",
    trial: bool = False,
    trial_expires_at: str = "",
) -> str:
    base = default_external_install_complete_url()
    params: dict[str, str] = {}

    if str(portal_id or "").strip():
        params["portalId"] = str(portal_id).strip()
    if str(plan or "").strip():
        params["plan"] = str(plan).strip()
    if str(billing_interval or "").strip():
        params["billingInterval"] = str(billing_interval).strip()
    if str(bootstrap_status or "").strip():
        params["bootstrapStatus"] = str(bootstrap_status).strip()
    if str(status or "").strip():
        params["status"] = str(status).strip()
    if str(message or "").strip():
        params["message"] = str(message).strip()
    if bool(trial):
        params["trial"] = "1"
    if str(trial_expires_at or "").strip():
        params["trial_expires_at"] = str(trial_expires_at).strip()

    if not params:
        return base

    return f"{base}?{urlencode(params)}"


def final_install_redirect_url(
    *,
    install_origin_value: str = "",
    hubspot_return_url: str = "",
    portal_id: str = "",
    plan: str = "",
    billing_interval: str = "",
    bootstrap_status: str = "",
    status: str = "",
    message: str = "",
    trial: bool = False,
    trial_expires_at: str = "",
) -> str:
    normalized_status = str(status or "").strip().lower()
    success_statuses = {"", "ok", "success"}

    if (
        normalized_status in success_statuses
        and str(install_origin_value or "").strip().lower() == INSTALL_ORIGIN_MARKETPLACE
        and is_hubspot_return_url(hubspot_return_url)
    ):
        return str(hubspot_return_url).strip()

    return external_install_complete_url(
        portal_id=portal_id,
        plan=plan,
        billing_interval=billing_interval,
        bootstrap_status=bootstrap_status,
        status=status,
        message=message,
        trial=trial,
        trial_expires_at=trial_expires_at,
    )
