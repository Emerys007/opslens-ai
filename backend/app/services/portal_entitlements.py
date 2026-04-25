from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from sqlalchemy.orm import Session

from app.models.hubspot_installation import HubSpotInstallation
from app.models.marketplace_install_session import MarketplaceInstallSession
from app.models.portal_entitlement import PortalEntitlement
from app.services.hubspot_portal_bootstrap import ensure_portal_bootstrap
from app.services.marketplace_billing import (
    normalize_billing_interval,
    normalize_plan,
    plan_from_price_id,
    subscription_is_active,
    trial_is_active,
)
from app.services.portal_settings import ensure_default_portal_settings


AUTO_TRIAL_DURATION = timedelta(days=14)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _iso_utc(value: datetime | None) -> str:
    aware = _aware(value)
    if aware is None:
        return ""
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_json(value: dict | None) -> str:
    return json.dumps(value or {}, sort_keys=True)


def create_marketplace_install_session(
    session: Session,
    *,
    install_session_id: str,
    plan: str,
    billing_interval: str,
    return_url: str = "",
    tenant_context: dict | None = None,
    partner_user_id: str = "",
    partner_user_email: str = "",
    trial_approved: bool = False,
    trial_started_at: datetime | None = None,
    trial_expires_at: datetime | None = None,
) -> MarketplaceInstallSession:
    row = MarketplaceInstallSession(
        install_session_id=str(install_session_id),
        requested_plan=normalize_plan(plan),
        billing_interval=normalize_billing_interval(billing_interval),
        return_url=str(return_url or "").strip(),
        tenant_context_json=_safe_json(tenant_context),
        partner_user_id=str(partner_user_id or "").strip(),
        partner_user_email=str(partner_user_email or "").strip(),
        trial_approved=bool(trial_approved),
        trial_started_at=_aware(trial_started_at),
        trial_expires_at=_aware(trial_expires_at),
        subscription_status="trial_approved" if trial_approved else "pending",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_marketplace_install_session(
    session: Session,
    install_session_id: str,
) -> MarketplaceInstallSession:
    install_key = str(install_session_id or "").strip()
    if not install_key:
        raise RuntimeError("installSessionId is required.")
    row = session.get(MarketplaceInstallSession, install_key)
    if row is None:
        raise RuntimeError(f"No marketplace install session was found for {install_key}.")
    return row


def install_session_context(row: MarketplaceInstallSession) -> dict:
    try:
        return json.loads(str(row.tenant_context_json or "{}"))
    except Exception:
        return {}


def install_session_bootstrap_summary(row: MarketplaceInstallSession) -> dict:
    try:
        return json.loads(str(row.bootstrap_summary_json or "{}"))
    except Exception:
        return {}


def update_install_session_billing(
    session: Session,
    row: MarketplaceInstallSession,
    *,
    stripe_customer_id: str = "",
    stripe_checkout_session_id: str = "",
    stripe_subscription_id: str = "",
    subscription_status: str | None = None,
    plan: str | None = None,
    billing_interval: str | None = None,
    payment_completed: bool = False,
) -> MarketplaceInstallSession:
    if stripe_customer_id:
        row.stripe_customer_id = str(stripe_customer_id).strip()
    if stripe_checkout_session_id:
        row.stripe_checkout_session_id = str(stripe_checkout_session_id).strip()
    if stripe_subscription_id:
        row.stripe_subscription_id = str(stripe_subscription_id).strip()
    if subscription_status is not None:
        row.subscription_status = str(subscription_status or "").strip().lower() or "pending"
    if plan:
        row.requested_plan = normalize_plan(plan)
    if billing_interval:
        row.billing_interval = normalize_billing_interval(billing_interval)
    if payment_completed:
        row.payment_completed_at = _utc_now()
    session.commit()
    session.refresh(row)
    return row


def mark_install_session_oauth_completed(
    session: Session,
    row: MarketplaceInstallSession,
    *,
    portal_id: str,
    hub_domain: str,
) -> MarketplaceInstallSession:
    row.hubspot_portal_id = str(portal_id or "").strip()
    row.hub_domain = str(hub_domain or "").strip()
    row.oauth_completed_at = _utc_now()
    session.commit()
    session.refresh(row)
    return row


def mark_install_session_bootstrap(
    session: Session,
    row: MarketplaceInstallSession,
    *,
    bootstrap_status: str,
    bootstrap_summary: dict | None = None,
    install_error: str = "",
) -> MarketplaceInstallSession:
    row.bootstrap_status = str(bootstrap_status or "").strip() or "pending"
    row.bootstrap_summary_json = _safe_json(bootstrap_summary)
    row.install_error = str(install_error or "").strip()
    session.commit()
    session.refresh(row)
    return row


def install_session_is_billable_active(row: MarketplaceInstallSession) -> bool:
    return subscription_is_active(
        row.subscription_status,
        trial_approved=row.trial_approved,
        trial_expires_at=_aware(row.trial_expires_at),
    )


def install_session_trial_query_params(row: MarketplaceInstallSession | None) -> dict[str, str]:
    """Return query-string fragments that signal an active auto-trial.

    Empty dict if no trial was granted, the trial is not currently active, or
    the trial has expired. Callers append these to the install-complete URL.
    """
    if row is None:
        return {}
    if not trial_is_active(bool(row.trial_approved), _aware(row.trial_expires_at)):
        return {}
    expires_iso = _iso_utc(row.trial_expires_at)
    if not expires_iso:
        return {}
    return {"trial": "1", "trial_expires_at": expires_iso}


def install_session_can_activate(row: MarketplaceInstallSession) -> bool:
    return (
        bool(str(row.hubspot_portal_id or "").strip())
        and install_session_is_billable_active(row)
        and str(row.bootstrap_status or "").strip().lower() == "success"
    )


def entitlement_payload(row: PortalEntitlement | None, portal_id: str = "") -> dict:
    if row is None:
        return {
            "portalId": str(portal_id or "").strip(),
            "plan": "",
            "billingInterval": "",
            "subscriptionStatus": "pending",
            "trialApproved": False,
            "trialStartedAt": "",
            "trialExpiresAt": "",
            "active": False,
            "stripeCustomerId": "",
            "stripeSubscriptionId": "",
        }

    return {
        "portalId": str(row.portal_id or "").strip(),
        "plan": str(row.plan or "").strip(),
        "billingInterval": str(row.billing_interval or "").strip(),
        "subscriptionStatus": str(row.subscription_status or "").strip(),
        "trialApproved": bool(row.trial_approved),
        "trialStartedAt": _iso_utc(row.trial_started_at),
        "trialExpiresAt": _iso_utc(row.trial_expires_at),
        "active": subscription_is_active(
            row.subscription_status,
            trial_approved=row.trial_approved,
            trial_expires_at=_aware(row.trial_expires_at),
        ),
        "stripeCustomerId": str(row.stripe_customer_id or "").strip(),
        "stripeSubscriptionId": str(row.stripe_subscription_id or "").strip(),
    }


def get_portal_entitlement(session: Session | None, portal_id: str) -> dict:
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id or session is None:
        return entitlement_payload(None, cleaned_portal_id)

    row = session.get(PortalEntitlement, cleaned_portal_id)
    return entitlement_payload(row, cleaned_portal_id)


def portal_is_entitled(payload: dict) -> bool:
    return bool(payload.get("active"))


def upsert_portal_entitlement_from_install_session(
    session: Session,
    *,
    portal_id: str,
    install_session: MarketplaceInstallSession,
) -> PortalEntitlement:
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id:
        raise RuntimeError("portal_id is required.")

    row = session.get(PortalEntitlement, cleaned_portal_id)
    if row is None:
        row = PortalEntitlement(portal_id=cleaned_portal_id)
        session.add(row)

    row.install_session_id = str(install_session.install_session_id or "").strip()
    row.plan = normalize_plan(install_session.requested_plan or "professional")
    row.billing_interval = normalize_billing_interval(install_session.billing_interval or "monthly")
    row.subscription_status = str(install_session.subscription_status or "").strip().lower() or "pending"
    row.trial_approved = bool(install_session.trial_approved)
    row.stripe_customer_id = str(install_session.stripe_customer_id or "").strip()
    row.stripe_checkout_session_id = str(install_session.stripe_checkout_session_id or "").strip()
    row.stripe_subscription_id = str(install_session.stripe_subscription_id or "").strip()
    # Trial timestamps: a portal can only have one trial in its lifetime, so
    # never overwrite an existing trial_started_at. trial_expires_at is allowed
    # to refresh from the install session (e.g. a re-install during the trial
    # window inherits the same expiry, not a brand new 14 days).
    install_trial_started_at = _aware(install_session.trial_started_at)
    install_trial_expires_at = _aware(install_session.trial_expires_at)
    if row.trial_started_at is None and install_trial_started_at is not None:
        row.trial_started_at = install_trial_started_at
    if row.trial_started_at is not None and row.trial_expires_at is None and install_trial_expires_at is not None:
        row.trial_expires_at = install_trial_expires_at
    if subscription_is_active(
        row.subscription_status,
        trial_approved=row.trial_approved,
        trial_expires_at=_aware(row.trial_expires_at),
    ):
        row.activated_at = row.activated_at or _utc_now()

    session.commit()
    session.refresh(row)
    return row


def _revoke_optimistic_install_session_trial(
    session: Session,
    install_session: MarketplaceInstallSession,
) -> MarketplaceInstallSession:
    """Roll back the optimistic auto-trial that ``install_start`` stages.

    Called when the OAuth callback discovers that the portal is not eligible
    for an auto-trial (it has a prior trial or an active paid subscription).
    The install session must not advertise an active trial in that case.
    """
    install_session.trial_approved = False
    install_session.trial_started_at = None
    install_session.trial_expires_at = None
    if str(install_session.subscription_status or "").strip().lower() == "trial_approved":
        install_session.subscription_status = "pending"
    session.commit()
    session.refresh(install_session)
    return install_session


def grant_auto_trial_for_install_session(
    session: Session,
    install_session: MarketplaceInstallSession,
    *,
    portal_id: str,
    duration: timedelta = AUTO_TRIAL_DURATION,
) -> tuple[MarketplaceInstallSession, bool]:
    """Grant a 14-day auto-trial to the install session if the portal is eligible.

    Eligibility:
      * The portal has no existing PortalEntitlement, OR
      * The portal entitlement has no prior trial_started_at AND its current
        subscription_status is not an active paid one.

    Behavior:
      * Eligible — grant a fresh trial (overwriting any optimistic timestamps
        from ``install_start``) and return ``granted=True``.
      * Ineligible due to active paid subscription — leave the install session
        as-is and return ``granted=False``; the entitlement's own active flag
        will keep the portal usable.
      * Ineligible due to a prior trial — REVOKE the optimistic install-session
        trial so the existing payment-required path takes over. Return
        ``granted=False``.
    """
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id:
        return install_session, False

    # If the install session is already attached to an active paid Stripe
    # subscription (the legacy ``trialApproved=False`` path), do not stomp it
    # with a trial. The customer just paid and we should respect that.
    if subscription_is_active(install_session.subscription_status, trial_approved=False):
        return install_session, False

    entitlement = session.get(PortalEntitlement, cleaned_portal_id)

    # If a paid subscription is already active for this portal, don't replace
    # it with a trial. Leave the install session as-is; sync_installation_activation
    # will rely on the existing entitlement record.
    if entitlement is not None and subscription_is_active(
        entitlement.subscription_status,
        trial_approved=False,
    ):
        return install_session, False

    # If the portal has previously been granted a trial, never grant another.
    # Revoke the optimistic install-session trial so the caller's
    # ``install_session_is_billable_active`` gate falls into payment_required.
    if entitlement is not None and entitlement.trial_started_at is not None:
        install_session = _revoke_optimistic_install_session_trial(session, install_session)
        return install_session, False

    started_at = _utc_now()
    expires_at = started_at + duration

    install_session.trial_approved = True
    install_session.trial_started_at = started_at
    install_session.trial_expires_at = expires_at
    install_session.subscription_status = "trial_approved"
    session.commit()
    session.refresh(install_session)
    return install_session, True


def sync_installation_activation_for_install_session(
    session: Session,
    install_session: MarketplaceInstallSession,
) -> bool:
    portal_id = str(install_session.hubspot_portal_id or "").strip()
    if portal_id:
        upsert_portal_entitlement_from_install_session(
            session,
            portal_id=portal_id,
            install_session=install_session,
        )
        set_installation_activation(
            session,
            portal_id=portal_id,
            active=install_session_can_activate(install_session),
        )
    return install_session_can_activate(install_session)


def set_installation_activation(
    session: Session,
    *,
    portal_id: str,
    active: bool,
) -> None:
    row = session.get(HubSpotInstallation, str(portal_id or "").strip())
    if row is None:
        return
    row.is_active = bool(active)
    session.commit()


def update_entitlement_from_subscription(
    session: Session,
    *,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    subscription_status: str,
    price_id: str,
    checkout_session_id: str = "",
    payment_failed: bool = False,
) -> PortalEntitlement | None:
    customer_id = str(stripe_customer_id or "").strip()
    subscription_id = str(stripe_subscription_id or "").strip()
    if not customer_id and not subscription_id:
        return None

    row = None
    if subscription_id:
        row = (
            session.query(PortalEntitlement)
            .filter(PortalEntitlement.stripe_subscription_id == subscription_id)
            .one_or_none()
        )
    if row is None and customer_id:
        row = (
            session.query(PortalEntitlement)
            .filter(PortalEntitlement.stripe_customer_id == customer_id)
            .one_or_none()
        )
    if row is None:
        return None

    plan, billing_interval = plan_from_price_id(price_id)
    if plan:
        row.plan = plan
    if billing_interval:
        row.billing_interval = billing_interval
    if customer_id:
        row.stripe_customer_id = customer_id
    if subscription_id:
        row.stripe_subscription_id = subscription_id
    if checkout_session_id:
        row.stripe_checkout_session_id = str(checkout_session_id).strip()
    row.subscription_status = str(subscription_status or "").strip().lower() or row.subscription_status
    if payment_failed:
        row.last_payment_failed_at = _utc_now()
    is_active = subscription_is_active(
        row.subscription_status,
        trial_approved=row.trial_approved,
        trial_expires_at=_aware(row.trial_expires_at),
    )
    if is_active:
        row.activated_at = row.activated_at or _utc_now()

    session.commit()
    session.refresh(row)
    if not is_active:
        set_installation_activation(
            session,
            portal_id=row.portal_id,
            active=False,
        )
    return row


def update_install_session_from_subscription(
    session: Session,
    *,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    subscription_status: str,
    price_id: str,
    checkout_session_id: str = "",
    payment_failed: bool = False,
) -> MarketplaceInstallSession | None:
    customer_id = str(stripe_customer_id or "").strip()
    subscription_id = str(stripe_subscription_id or "").strip()
    if not customer_id and not subscription_id:
        return None

    row = None
    if subscription_id:
        row = (
            session.query(MarketplaceInstallSession)
            .filter(MarketplaceInstallSession.stripe_subscription_id == subscription_id)
            .one_or_none()
        )
    if row is None and customer_id:
        row = (
            session.query(MarketplaceInstallSession)
            .filter(MarketplaceInstallSession.stripe_customer_id == customer_id)
            .one_or_none()
        )
    if row is None:
        return None

    plan, billing_interval = plan_from_price_id(price_id)
    update_install_session_billing(
        session,
        row,
        stripe_customer_id=customer_id,
        stripe_checkout_session_id=checkout_session_id,
        stripe_subscription_id=subscription_id,
        subscription_status=subscription_status,
        plan=plan or row.requested_plan,
        billing_interval=billing_interval or row.billing_interval,
        payment_completed=subscription_is_active(
            subscription_status,
            trial_approved=row.trial_approved,
            trial_expires_at=_aware(row.trial_expires_at),
        ),
    )
    if payment_failed:
        row.install_error = "Stripe reported a payment failure for this install session."
        session.commit()
        session.refresh(row)
    return row


def run_post_install_provisioner(
    session: Session,
    *,
    token: str,
    portal_id: str,
) -> dict:
    bootstrap_summary = ensure_portal_bootstrap(
        token=token,
        portal_id=portal_id,
    )
    default_settings, settings_created = ensure_default_portal_settings(session, portal_id)
    return {
        **bootstrap_summary,
        "defaultPortalSettingsCreated": bool(settings_created),
        "defaultPortalSettings": default_settings,
    }
