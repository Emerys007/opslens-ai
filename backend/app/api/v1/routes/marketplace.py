from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.db import get_session, init_db
from app.services.marketplace_billing import (
    create_checkout_session,
    create_customer,
    create_install_session_id,
    normalize_billing_interval,
    normalize_plan,
    plan_from_price_id,
    price_id_for,
    retrieve_subscription,
    subscription_price_id,
    subscription_is_active,
    subscription_status_text,
    verify_stripe_webhook_signature,
)
from app.services.portal_entitlements import (
    create_marketplace_install_session,
    get_marketplace_install_session,
    install_session_bootstrap_summary,
    install_session_can_activate,
    install_session_context,
    sync_installation_activation_for_install_session,
    update_entitlement_from_subscription,
    update_install_session_billing,
    update_install_session_from_subscription,
)


router = APIRouter(prefix="/marketplace", tags=["marketplace"])


class MarketplaceInstallStartRequest(BaseModel):
    plan: str
    billingInterval: str
    returnUrl: str = ""
    tenantContext: dict[str, Any] = Field(default_factory=dict)
    partnerUserId: str = ""
    partnerUserEmail: str = ""
    trialApproved: bool = False


def _default_install_return_url() -> str:
    app_base = str(settings.app_public_base_url or "").strip().rstrip("/")
    if not app_base:
        app_base = "https://apps.app-sync.com"
    return f"{app_base}/opslens/install/complete"


def _resolved_install_return_url(return_url: str | None) -> str:
    cleaned = str(return_url or "").strip()
    if cleaned:
        return cleaned
    return _default_install_return_url()


def _backend_public_url(path: str, **query: str) -> str:
    base = str(settings.backend_public_base_url or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("BACKEND_PUBLIC_BASE_URL is not configured.")

    suffix = path if path.startswith("/") else f"/{path}"
    if not query:
        return f"{base}{suffix}"
    return f"{base}{suffix}?{urlencode(query)}"


def _stripe_checkout_success_url(install_session_id: str) -> str:
    base = str(settings.backend_public_base_url or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("BACKEND_PUBLIC_BASE_URL is not configured.")

    encoded_install_session_id = quote(str(install_session_id or "").strip(), safe="")
    return (
        f"{base}/marketplace/install/authorize"
        f"?installSessionId={encoded_install_session_id}"
        "&checkoutSessionId={CHECKOUT_SESSION_ID}"
    )


def _default_cancel_url(return_url: str) -> str:
    return _resolved_install_return_url(return_url)


def _update_billing_state(
    *,
    install_session_id: str = "",
    stripe_customer_id: str = "",
    stripe_subscription_id: str = "",
    stripe_checkout_session_id: str = "",
    subscription_status: str,
    price_id: str = "",
    payment_failed: bool = False,
):
    if not init_db():
        raise RuntimeError("DATABASE_URL is not configured.")

    session = get_session()
    if session is None:
        raise RuntimeError("Database session could not be created.")

    try:
        install_row = None
        if install_session_id:
            try:
                install_row = get_marketplace_install_session(session, install_session_id)
            except Exception:
                install_row = None

        if install_row is not None:
            plan, billing_interval = plan_from_price_id(price_id)
            install_row = update_install_session_billing(
                session,
                install_row,
                stripe_customer_id=stripe_customer_id,
                stripe_checkout_session_id=stripe_checkout_session_id,
                stripe_subscription_id=stripe_subscription_id,
                subscription_status=subscription_status,
                plan=plan or install_row.requested_plan,
                billing_interval=billing_interval or install_row.billing_interval,
                payment_completed=subscription_is_active(
                    subscription_status,
                    trial_approved=install_row.trial_approved,
                ),
            )
            if payment_failed:
                install_row.install_error = "Stripe reported a payment failure for this install session."
                session.commit()
                session.refresh(install_row)
        else:
            install_row = update_install_session_from_subscription(
                session,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                subscription_status=subscription_status,
                price_id=price_id,
                checkout_session_id=stripe_checkout_session_id,
                payment_failed=payment_failed,
            )

        update_entitlement_from_subscription(
            session,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            subscription_status=subscription_status,
            price_id=price_id,
            checkout_session_id=stripe_checkout_session_id,
            payment_failed=payment_failed,
        )

        if install_row is not None:
            sync_installation_activation_for_install_session(session, install_row)

        return install_row
    finally:
        session.close()


def _next_step_checklist(bootstrap_status: str, portal_id: str) -> list[str]:
    cleaned_status = str(bootstrap_status or "").strip().lower()
    cleaned_portal_id = str(portal_id or "").strip()
    if cleaned_status != "success":
        return [
            "Confirm the Stripe subscription is active or explicitly trial-approved.",
            "Retry the HubSpot install callback after the subscription is active.",
            "Verify the OpsLens HubSpot schema bootstrap completes before enabling customer use.",
        ]

    return [
        f"Open OpsLens App Home in portal {cleaned_portal_id or 'the installed portal'} and confirm plan plus billing state.",
        "Run the workflow action once and verify an OpsLens Alerts ticket is created in the portal-specific pipeline.",
        "Confirm the auto-resolve job can close a waiting ticket after a quiet-period or healthy-signal follow-up.",
    ]


@router.post("/install/start")
def marketplace_install_start(payload: MarketplaceInstallStartRequest):
    if not init_db():
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=500, detail="Database session could not be created.")

    try:
        plan = normalize_plan(payload.plan)
        billing_interval = normalize_billing_interval(payload.billingInterval)
        install_session_id = create_install_session_id()

        row = create_marketplace_install_session(
            session,
            install_session_id=install_session_id,
            plan=plan,
            billing_interval=billing_interval,
            return_url=payload.returnUrl,
            tenant_context=payload.tenantContext,
            partner_user_id=payload.partnerUserId,
            partner_user_email=payload.partnerUserEmail,
            trial_approved=payload.trialApproved,
        )

        authorize_url = _backend_public_url(
            "/marketplace/install/authorize",
            installSessionId=install_session_id,
        )
        success_endpoint = _backend_public_url(
            "/api/v1/marketplace/install/success",
            installSessionId=install_session_id,
        )

        checkout_url = ""
        if not row.trial_approved:
            customer = create_customer(
                email=row.partner_user_email,
                metadata={
                    "install_session_id": row.install_session_id,
                    "plan": row.requested_plan,
                    "billing_interval": row.billing_interval,
                },
            )
            customer_id = str(customer.get("id") or "").strip()
            price_id = price_id_for(row.requested_plan, row.billing_interval)

            checkout = create_checkout_session(
                customer_id=customer_id,
                price_id=price_id,
                success_url=_stripe_checkout_success_url(row.install_session_id),
                cancel_url=_default_cancel_url(row.return_url),
                install_session_id=row.install_session_id,
                plan=row.requested_plan,
                billing_interval=row.billing_interval,
            )
            checkout_url = str(checkout.get("url") or "").strip()

            update_install_session_billing(
                session,
                row,
                stripe_customer_id=customer_id,
                stripe_checkout_session_id=str(checkout.get("id") or "").strip(),
            )

        return {
            "status": "ok",
            "installSessionId": row.install_session_id,
            "plan": row.requested_plan,
            "billingInterval": row.billing_interval,
            "subscriptionStatus": row.subscription_status,
            "trialApproved": bool(row.trial_approved),
            "paymentRequired": not bool(row.trial_approved),
            "checkoutUrl": checkout_url,
            "authorizationUrl": authorize_url,
            "installSuccessUrl": success_endpoint,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        session.close()


@router.get("/install/success")
def marketplace_install_success(installSessionId: str):
    if not init_db():
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=500, detail="Database session could not be created.")

    try:
        row = get_marketplace_install_session(session, installSessionId)
        bootstrap_summary = install_session_bootstrap_summary(row)
        context = install_session_context(row)

        return {
            "status": "ok",
            "installSessionId": row.install_session_id,
            "portalId": str(row.hubspot_portal_id or "").strip(),
            "plan": str(row.requested_plan or "").strip(),
            "billingInterval": str(row.billing_interval or "").strip(),
            "returnUrl": _resolved_install_return_url(row.return_url),
            "subscriptionStatus": str(row.subscription_status or "").strip(),
            "trialApproved": bool(row.trial_approved),
            "active": install_session_can_activate(row),
            "bootstrapStatus": str(row.bootstrap_status or "").strip(),
            "createdAssetsSummary": bootstrap_summary,
            "tenantContext": context,
            "nextStepChecklist": _next_step_checklist(row.bootstrap_status, row.hubspot_portal_id),
            "error": str(row.install_error or "").strip(),
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        session.close()


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    payload = await request.body()
    if not verify_stripe_webhook_signature(payload, stripe_signature):
        raise HTTPException(status_code=401, detail="Stripe webhook signature validation failed.")

    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Stripe webhook body was not valid JSON.") from exc

    event_type = str(event.get("type") or "").strip()
    data = ((event.get("data") or {}).get("object") or {})

    try:
        if event_type == "checkout.session.completed":
            install_session_id = str(
                data.get("client_reference_id")
                or (data.get("metadata") or {}).get("install_session_id")
                or ""
            ).strip()
            checkout_session_id = str(data.get("id") or "").strip()
            stripe_customer_id = str(data.get("customer") or "").strip()
            stripe_subscription_id = str(data.get("subscription") or "").strip()

            subscription_payload = (
                retrieve_subscription(stripe_subscription_id)
                if stripe_subscription_id
                else {}
            )
            _update_billing_state(
                install_session_id=install_session_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                stripe_checkout_session_id=checkout_session_id,
                subscription_status=subscription_status_text(subscription_payload, "active"),
                price_id=subscription_price_id(subscription_payload),
            )

        elif event_type == "customer.subscription.updated":
            stripe_customer_id = str(data.get("customer") or "").strip()
            stripe_subscription_id = str(data.get("id") or "").strip()
            _update_billing_state(
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                subscription_status=subscription_status_text(data, "pending"),
                price_id=subscription_price_id(data),
            )

        elif event_type == "customer.subscription.deleted":
            stripe_customer_id = str(data.get("customer") or "").strip()
            stripe_subscription_id = str(data.get("id") or "").strip()
            _update_billing_state(
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                subscription_status=subscription_status_text(data, "canceled"),
                price_id=subscription_price_id(data),
            )

        elif event_type == "invoice.payment_failed":
            stripe_customer_id = str(data.get("customer") or "").strip()
            stripe_subscription_id = str(data.get("subscription") or "").strip()
            subscription_payload = (
                retrieve_subscription(stripe_subscription_id)
                if stripe_subscription_id
                else {}
            )
            _update_billing_state(
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                subscription_status=subscription_status_text(subscription_payload, "past_due"),
                price_id=subscription_price_id(subscription_payload),
                payment_failed=True,
            )

        return {
            "status": "ok",
            "eventType": event_type,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
