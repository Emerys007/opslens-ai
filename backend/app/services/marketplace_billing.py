from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

from app.config import settings


STRIPE_API_BASE = "https://api.stripe.com/v1"
VALID_PLANS = {"professional", "business"}
VALID_INTERVALS = {"monthly", "yearly"}
ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stripe_secret_key() -> str:
    value = str(settings.stripe_secret_key or "").strip()
    if not value:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    return value


def normalize_plan(plan: str | None) -> str:
    value = str(plan or "").strip().lower()
    if value not in VALID_PLANS:
        raise ValueError("plan must be one of: professional, business.")
    return value


def normalize_billing_interval(value: str | None) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "month": "monthly",
        "monthly": "monthly",
        "year": "yearly",
        "yearly": "yearly",
    }
    normalized = aliases.get(text, "")
    if normalized not in VALID_INTERVALS:
        raise ValueError("billingInterval must be one of: monthly, yearly.")
    return normalized


def price_id_for(plan: str, billing_interval: str) -> str:
    normalized_plan = normalize_plan(plan)
    normalized_interval = normalize_billing_interval(billing_interval)

    mapping = {
        ("professional", "monthly"): str(settings.stripe_price_professional_monthly or "").strip(),
        ("professional", "yearly"): str(settings.stripe_price_professional_yearly or "").strip(),
        ("business", "monthly"): str(settings.stripe_price_business_monthly or "").strip(),
        ("business", "yearly"): str(settings.stripe_price_business_yearly or "").strip(),
    }
    price_id = mapping[(normalized_plan, normalized_interval)]
    if not price_id:
        raise RuntimeError(
            f"No Stripe price id is configured for {normalized_plan} {normalized_interval}."
        )
    return price_id


def trial_is_active(trial_approved: bool, trial_expires_at: datetime | None = None) -> bool:
    """Return True if a trial grant is currently in force.

    A trial is considered active when it has been approved AND either has no
    explicit expiry (legacy rows pre-dating auto-trial) or its expiry is in
    the future. Comparison is done in UTC.
    """
    if not bool(trial_approved):
        return False
    if trial_expires_at is None:
        return True
    expiry = trial_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return _utc_now() < expiry


def subscription_is_active(
    subscription_status: str | None,
    *,
    trial_approved: bool = False,
    trial_expires_at: datetime | None = None,
) -> bool:
    if trial_is_active(trial_approved, trial_expires_at):
        return True
    status = str(subscription_status or "").strip().lower()
    return status in ACTIVE_SUBSCRIPTION_STATUSES


def plan_code(plan: str, billing_interval: str) -> str:
    return f"{normalize_plan(plan)}_{normalize_billing_interval(billing_interval)}"


def plan_from_price_id(price_id: str | None) -> tuple[str, str]:
    cleaned = str(price_id or "").strip()
    mapping = {
        str(settings.stripe_price_professional_monthly or "").strip(): ("professional", "monthly"),
        str(settings.stripe_price_professional_yearly or "").strip(): ("professional", "yearly"),
        str(settings.stripe_price_business_monthly or "").strip(): ("business", "monthly"),
        str(settings.stripe_price_business_yearly or "").strip(): ("business", "yearly"),
    }
    if cleaned in mapping and all(mapping[cleaned]):
        return mapping[cleaned]
    return "", ""


def subscription_price_id(subscription_payload: dict | None) -> str:
    items = (((subscription_payload or {}).get("items") or {}).get("data") or [])
    if not items:
        return ""
    first_item = items[0] or {}
    price = first_item.get("price") or {}
    return str(price.get("id") or "").strip()


def subscription_status_text(subscription_payload: dict | None, fallback: str = "pending") -> str:
    return str((subscription_payload or {}).get("status") or fallback).strip().lower() or fallback


def checkout_session_is_paid(checkout_payload: dict | None) -> bool:
    payment_status = str((checkout_payload or {}).get("payment_status") or "").strip().lower()
    checkout_status = str((checkout_payload or {}).get("status") or "").strip().lower()
    return payment_status == "paid" or checkout_status == "complete"


def _stripe_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_stripe_secret_key()}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def _stripe_request(
    method: str,
    path: str,
    fields: list[tuple[str, str]] | None = None,
) -> dict:
    data = None
    if fields is not None:
        data = urllib.parse.urlencode(fields).encode("utf-8")

    request = urllib.request.Request(
        f"{STRIPE_API_BASE}{path}",
        data=data,
        headers=_stripe_headers(),
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body or str(exc)}
        raise RuntimeError(f"Stripe request failed: {parsed}") from exc


def create_customer(
    *,
    email: str = "",
    metadata: dict[str, str] | None = None,
) -> dict:
    fields: list[tuple[str, str]] = []
    if str(email or "").strip():
        fields.append(("email", str(email).strip()))
    for key, value in (metadata or {}).items():
        fields.append((f"metadata[{key}]", str(value)))
    return _stripe_request("POST", "/customers", fields)


def create_checkout_session(
    *,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    install_session_id: str,
    plan: str,
    billing_interval: str,
) -> dict:
    fields = [
        ("mode", "subscription"),
        ("customer", str(customer_id)),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("client_reference_id", install_session_id),
        ("line_items[0][price]", str(price_id)),
        ("line_items[0][quantity]", "1"),
        ("metadata[install_session_id]", install_session_id),
        ("metadata[plan]", normalize_plan(plan)),
        ("metadata[billing_interval]", normalize_billing_interval(billing_interval)),
    ]
    return _stripe_request("POST", "/checkout/sessions", fields)


def retrieve_checkout_session(checkout_session_id: str) -> dict:
    cleaned = str(checkout_session_id or "").strip()
    if not cleaned:
        raise RuntimeError("checkout_session_id is required.")
    return _stripe_request("GET", f"/checkout/sessions/{urllib.parse.quote(cleaned)}")


def retrieve_subscription(subscription_id: str) -> dict:
    cleaned = str(subscription_id or "").strip()
    if not cleaned:
        raise RuntimeError("subscription_id is required.")
    return _stripe_request("GET", f"/subscriptions/{urllib.parse.quote(cleaned)}")


def create_install_session_id() -> str:
    return secrets.token_urlsafe(24)


def verify_stripe_webhook_signature(payload: bytes, signature_header: str | None) -> bool:
    secret = str(settings.stripe_webhook_secret or "").strip()
    signature_text = str(signature_header or "").strip()
    if not secret or not signature_text or not payload:
        return False

    pieces = {}
    for part in signature_text.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        pieces.setdefault(key.strip(), []).append(value.strip())

    timestamp = str((pieces.get("t") or [""])[0]).strip()
    signatures = [value for value in pieces.get("v1", []) if value]
    if not timestamp or not signatures:
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    if abs(int(_utc_now().timestamp()) - timestamp_int) > 300:
        return False

    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)
