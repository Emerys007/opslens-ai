from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Header, HTTPException, Path, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.core.logging import logger
from app.db import get_session, init_db
from app.models.hubspot_installation import HubSpotInstallation
from app.models.marketplace_install_session import MarketplaceInstallSession
from app.services.hubspot_oauth import refresh_access_token
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
from app.services.marketplace_install_routing import (
    enriched_tenant_context,
    final_install_redirect_url,
    install_origin,
)
from app.services.portal_entitlements import (
    AUTO_TRIAL_DURATION,
    create_marketplace_install_session,
    get_marketplace_install_session,
    install_session_bootstrap_summary,
    install_session_can_activate,
    install_session_context,
    install_session_trial_query_params,
    mark_install_session_bootstrap,
    run_post_install_provisioner,
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
    # Defaults to True so that fresh installs go straight through the
    # 14-day auto-trial path. Re-installs whose portal already used a trial
    # are demoted at the OAuth callback by ``grant_auto_trial_for_install_session``.
    # Pass ``False`` explicitly to force the legacy paid-checkout flow.
    trialApproved: bool = True


def _resolved_install_return_url(return_url: str | None) -> str:
    cleaned = str(return_url or "").strip()
    if cleaned:
        return cleaned
    return final_install_redirect_url()


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
        tenant_context = enriched_tenant_context(
            payload.tenantContext,
            return_url=payload.returnUrl,
        )

        # Pre-stage the auto-trial timestamps when the install session is
        # being created in trial mode. The OAuth callback re-validates
        # eligibility per-portal and may revoke this if the portal has
        # already used a trial.
        trial_started_at: datetime | None = None
        trial_expires_at: datetime | None = None
        if payload.trialApproved:
            trial_started_at = datetime.now(timezone.utc)
            trial_expires_at = trial_started_at + AUTO_TRIAL_DURATION

        row = create_marketplace_install_session(
            session,
            install_session_id=install_session_id,
            plan=plan,
            billing_interval=billing_interval,
            return_url=payload.returnUrl,
            tenant_context=tenant_context,
            partner_user_id=payload.partnerUserId,
            partner_user_email=payload.partnerUserEmail,
            trial_approved=payload.trialApproved,
            trial_started_at=trial_started_at,
            trial_expires_at=trial_expires_at,
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
        origin = install_origin(context, row.return_url)
        normalized_bootstrap = str(row.bootstrap_status or "").strip().lower()
        # Every portal that completes OAuth lands on install/complete with
        # status=ok. The 14-day trial begins regardless of payment state;
        # billing is enforced later via the Stripe customer portal and
        # plan/feature gates rather than gating the install itself.
        # bootstrapStatus is still surfaced so the UI can offer a retry
        # banner when bootstrap failed (or schedule a follow-up for
        # payment_required portals).
        redirect_status = "ok"
        trial_params = install_session_trial_query_params(row)
        resolved_return_url = final_install_redirect_url(
            install_origin_value=origin,
            hubspot_return_url=row.return_url,
            portal_id=row.hubspot_portal_id,
            plan=row.requested_plan,
            billing_interval=row.billing_interval,
            bootstrap_status=row.bootstrap_status,
            status=redirect_status,
            message=row.install_error if normalized_bootstrap != "success" else "",
            trial=bool(trial_params.get("trial")),
            trial_expires_at=trial_params.get("trial_expires_at", ""),
        )

        trial_expires_iso = trial_params.get("trial_expires_at", "")

        return {
            "status": "ok",
            "installSessionId": row.install_session_id,
            "portalId": str(row.hubspot_portal_id or "").strip(),
            "plan": str(row.requested_plan or "").strip(),
            "billingInterval": str(row.billing_interval or "").strip(),
            "returnUrl": resolved_return_url,
            "subscriptionStatus": str(row.subscription_status or "").strip(),
            "trialApproved": bool(row.trial_approved),
            "trialExpiresAt": trial_expires_iso,
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


def _require_admin_key(supplied: str | None) -> None:
    expected = str(settings.maintenance_api_key or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin API key is not configured.")
    if str(supplied or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid admin key.")


def _latest_install_session_for_portal(
    session,
    portal_id: str,
) -> MarketplaceInstallSession | None:
    return (
        session.query(MarketplaceInstallSession)
        .filter(MarketplaceInstallSession.hubspot_portal_id == portal_id)
        .order_by(MarketplaceInstallSession.created_at.desc())
        .first()
    )


@router.post("/bootstrap/{portal_id}")
def retry_portal_bootstrap(
    portal_id: str = Path(..., min_length=1),
    x_opslens_admin_key: str | None = Header(default=None),
):
    """Re-run the post-install bootstrap for an already-installed portal.

    Authenticated via the `X-OpsLens-Admin-Key` header. Used to recover
    portals whose original install completed (OAuth tokens stored, billing
    in good standing) but whose schema bootstrap failed.
    """
    _require_admin_key(x_opslens_admin_key)

    portal_key = str(portal_id or "").strip()
    if not portal_key:
        raise HTTPException(status_code=400, detail="portal_id is required.")

    if not init_db():
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")

    session = get_session()
    if session is None:
        raise HTTPException(status_code=500, detail="Database session could not be created.")

    try:
        installation = session.get(HubSpotInstallation, portal_key)
        if installation is None:
            raise HTTPException(status_code=404, detail=f"No HubSpot installation found for portal {portal_key}.")

        # Refresh the token if it's near-expiry. We bypass get_portal_access_token
        # because that helper requires is_active=True and the failure case we're
        # recovering may have left the row inactive.
        now_utc = datetime.now(timezone.utc)
        expires_at = installation.access_token_expires_at
        if expires_at is None or expires_at <= (now_utc + timedelta(seconds=60)):
            installation = refresh_access_token(session, installation)

        token = str(installation.access_token or "").strip()
        if not token:
            raise HTTPException(status_code=409, detail=f"No access token is stored for portal {portal_key}.")

        try:
            bootstrap_summary = run_post_install_provisioner(
                session,
                token=token,
                portal_id=portal_key,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "post_install_bootstrap_retry_failed",
                extra={"portal_id": portal_key},
            )
            install_session = _latest_install_session_for_portal(session, portal_key)
            if install_session is not None:
                mark_install_session_bootstrap(
                    session,
                    install_session,
                    bootstrap_status="failed",
                    bootstrap_summary={},
                    install_error=str(exc),
                )
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        install_session = _latest_install_session_for_portal(session, portal_key)
        if install_session is not None:
            install_session = mark_install_session_bootstrap(
                session,
                install_session,
                bootstrap_status="success",
                bootstrap_summary=bootstrap_summary,
                install_error="",
            )
            sync_installation_activation_for_install_session(session, install_session)

        if not installation.is_active:
            installation.is_active = True
            session.commit()

        return {
            "status": "ok",
            "portalId": portal_key,
            "bootstrapStatus": "success",
            "createdAssetsSummary": bootstrap_summary,
        }
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
