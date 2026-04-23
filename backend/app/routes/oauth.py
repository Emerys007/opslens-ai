from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.db import get_session, init_db
from app.services.hubspot_oauth import (
    build_authorization_url,
    exchange_code_for_tokens,
    introspect_access_token,
    parse_signed_state,
    upsert_installation,
)
from app.services.marketplace_billing import (
    checkout_session_is_paid,
    plan_from_price_id,
    retrieve_checkout_session,
    retrieve_subscription,
    subscription_price_id,
    subscription_status_text,
)
from app.services.marketplace_install_routing import (
    final_install_redirect_url,
    install_origin,
    is_hubspot_return_url,
)
from app.services.portal_entitlements import (
    get_marketplace_install_session,
    install_session_context,
    install_session_is_billable_active,
    mark_install_session_bootstrap,
    mark_install_session_oauth_completed,
    run_post_install_provisioner,
    sync_installation_activation_for_install_session,
    update_install_session_billing,
)

router = APIRouter(tags=["oauth"])


def _callback_redirect_target(
    *,
    install_session=None,
    state_return_to: str = "",
    portal_id: str = "",
    plan: str = "",
    billing_interval: str = "",
    bootstrap_status: str = "",
    status: str = "",
    message: str = "",
) -> str:
    tenant_context = install_session_context(install_session) if install_session is not None else {}
    install_session_return_url = str((install_session.return_url if install_session is not None else "") or "").strip()
    origin = install_origin(tenant_context, install_session_return_url or state_return_to)

    hubspot_return_url = ""
    if is_hubspot_return_url(install_session_return_url):
        hubspot_return_url = install_session_return_url
    elif is_hubspot_return_url(state_return_to):
        hubspot_return_url = str(state_return_to or "").strip()

    return final_install_redirect_url(
        install_origin_value=origin,
        hubspot_return_url=hubspot_return_url,
        portal_id=portal_id,
        plan=plan,
        billing_interval=billing_interval,
        bootstrap_status=bootstrap_status,
        status=status,
        message=message,
    )


def _authorize_checkout_session(
    *,
    checkout_session_id: str,
    install_session_id: str,
) -> None:
    if not init_db():
        raise RuntimeError("DATABASE_URL is not configured.")

    session = get_session()
    if session is None:
        raise RuntimeError("Database session could not be created.")

    try:
        install_session = get_marketplace_install_session(session, install_session_id)
        checkout = retrieve_checkout_session(checkout_session_id)
        checkout_install_session_id = str(
            checkout.get("client_reference_id")
            or (checkout.get("metadata") or {}).get("install_session_id")
            or ""
        ).strip()
        if checkout_install_session_id != install_session.install_session_id:
            raise RuntimeError("Stripe checkout session does not match the install session.")
        if not checkout_session_is_paid(checkout):
            raise RuntimeError("Stripe checkout has not completed successfully yet.")

        subscription_id = str(checkout.get("subscription") or "").strip()
        subscription_payload = retrieve_subscription(subscription_id) if subscription_id else {}
        plan, billing_interval = install_session.requested_plan, install_session.billing_interval
        derived_plan, derived_interval = ("", "")
        price_id = subscription_price_id(subscription_payload)
        if price_id:
            derived_plan, derived_interval = plan_from_price_id(price_id)
        if derived_plan:
            plan = derived_plan
        if derived_interval:
            billing_interval = derived_interval
        update_install_session_billing(
            session,
            install_session,
            stripe_customer_id=str(checkout.get("customer") or "").strip(),
            stripe_checkout_session_id=checkout_session_id,
            stripe_subscription_id=subscription_id,
            subscription_status=subscription_status_text(subscription_payload, "active"),
            plan=plan,
            billing_interval=billing_interval,
            payment_completed=True,
        )
        sync_installation_activation_for_install_session(session, install_session)
    finally:
        session.close()


@router.get("/oauth/install-url")
def oauth_install_url(
    returnTo: str | None = Query(default=None),
    installSessionId: str | None = Query(default=None),
):
    try:
        return {
            "status": "ok",
            "authorizationUrl": build_authorization_url(returnTo, installSessionId),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/oauth/start")
def oauth_start(
    returnTo: str | None = Query(default=None),
    installSessionId: str | None = Query(default=None),
):
    try:
        return RedirectResponse(build_authorization_url(returnTo, installSessionId), status_code=302)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/marketplace/install/authorize")
def marketplace_install_authorize(
    installSessionId: str = Query(...),
    checkoutSessionId: str | None = Query(default=None),
):
    try:
        if checkoutSessionId:
            _authorize_checkout_session(
                checkout_session_id=str(checkoutSessionId or "").strip(),
                install_session_id=str(installSessionId or "").strip(),
            )

        if not init_db():
            raise RuntimeError("DATABASE_URL is not configured.")

        session = get_session()
        if session is None:
            raise RuntimeError("Database session could not be created.")

        try:
            install_session = get_marketplace_install_session(session, installSessionId)
            if not install_session_is_billable_active(install_session):
                raise RuntimeError("A paid or trial-approved install session is required before HubSpot activation.")
            return RedirectResponse(
                build_authorization_url(
                    install_session.return_url,
                    install_session.install_session_id,
                ),
                status_code=302,
            )
        finally:
            session.close()
    except Exception as exc:
        return RedirectResponse(
            _callback_redirect_target(
                portal_id="",
                plan="",
                billing_interval="",
                bootstrap_status="failed",
                status="error",
                message=str(exc),
            ),
            status_code=302,
        )


@router.get("/oauth-callback")
def oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    signed_state = str(state or "").strip()

    if error:
        message = error_description or error or "HubSpot OAuth returned an error."
        state_payload = {}
        try:
            state_payload = parse_signed_state(signed_state) if signed_state else {}
        except Exception:
            state_payload = {}
        return RedirectResponse(
            _callback_redirect_target(
                state_return_to=str(state_payload.get("returnTo") or ""),
                bootstrap_status="failed",
                status="error",
                message=message,
            ),
            status_code=302,
        )

    auth_code = str(code or "").strip()

    if not auth_code:
        return RedirectResponse(
            _callback_redirect_target(
                bootstrap_status="failed",
                status="error",
                message="Missing OAuth code.",
            ),
            status_code=302,
        )
    if not signed_state:
        return RedirectResponse(
            _callback_redirect_target(
                bootstrap_status="failed",
                status="error",
                message="Missing OAuth state.",
            ),
            status_code=302,
        )

    try:
        state_payload = parse_signed_state(signed_state)
        token_payload = exchange_code_for_tokens(auth_code)

        access_token = str(
            token_payload.get("access_token")
            or token_payload.get("accessToken")
            or ""
        ).strip()
        metadata = introspect_access_token(access_token)

        if not init_db():
            raise RuntimeError("DATABASE_URL is not configured.")

        session = get_session()
        if session is None:
            raise RuntimeError("Database session could not be created.")

        bootstrap_started = False
        install_session = None
        redirect_payload = {}

        try:
            install_session_id = str(state_payload.get("installSessionId") or "").strip()
            if install_session_id:
                install_session = get_marketplace_install_session(session, install_session_id)

            installation = upsert_installation(
                session,
                token_payload=token_payload,
                metadata=metadata,
                active=False,
            )

            if install_session is not None:
                install_session = mark_install_session_oauth_completed(
                    session,
                    install_session,
                    portal_id=installation.portal_id,
                    hub_domain=installation.hub_domain,
                )

                if not install_session_is_billable_active(install_session):
                    install_session = mark_install_session_bootstrap(
                        session,
                        install_session,
                        bootstrap_status="payment_required",
                        bootstrap_summary={},
                        install_error="Stripe payment must complete before the portal can be activated.",
                    )
                    sync_installation_activation_for_install_session(session, install_session)
                    raise RuntimeError("Stripe payment must complete before the portal can be activated.")

            bootstrap_started = True
            bootstrap_summary = run_post_install_provisioner(
                session,
                token=access_token,
                portal_id=installation.portal_id,
            )

            if install_session is not None:
                install_session = mark_install_session_bootstrap(
                    session,
                    install_session,
                    bootstrap_status="success",
                    bootstrap_summary=bootstrap_summary,
                )
                sync_installation_activation_for_install_session(session, install_session)
            else:
                installation.is_active = True
                session.commit()
                session.refresh(installation)

            redirect_payload = {
                "redirect_url": _callback_redirect_target(
                    install_session=install_session,
                    state_return_to=str(state_payload.get("returnTo") or ""),
                    portal_id=str(installation.portal_id or "").strip(),
                    plan=str((install_session.requested_plan if install_session is not None else "") or ""),
                    billing_interval=str((install_session.billing_interval if install_session is not None else "") or ""),
                    bootstrap_status=str((install_session.bootstrap_status if install_session is not None else "success") or "success"),
                    status="ok",
                )
            }
        except Exception as exc:
            if install_session is not None and "session" in locals():
                current_bootstrap_status = str(install_session.bootstrap_status or "").strip().lower()
                if current_bootstrap_status not in {"payment_required", "success"}:
                    install_session = mark_install_session_bootstrap(
                        session,
                        install_session,
                        bootstrap_status="failed" if bootstrap_started else "pending",
                        bootstrap_summary={},
                        install_error=str(exc),
                    )
                sync_installation_activation_for_install_session(session, install_session)
            installation = locals().get("installation")
            redirect_payload = {
                "redirect_url": _callback_redirect_target(
                    install_session=install_session,
                    state_return_to=str(state_payload.get("returnTo") or ""),
                    portal_id=str(
                        (
                            installation.portal_id
                            if installation is not None
                            else (install_session.hubspot_portal_id if install_session is not None else "")
                        )
                        or ""
                    ).strip(),
                    plan=str((install_session.requested_plan if install_session is not None else "") or ""),
                    billing_interval=str((install_session.billing_interval if install_session is not None else "") or ""),
                    bootstrap_status=str(
                        (
                            install_session.bootstrap_status
                            if install_session is not None and str(install_session.bootstrap_status or "").strip()
                            else ("failed" if bootstrap_started else "failed")
                        )
                    ),
                    status="error",
                    message=str(exc),
                )
            }
            raise
        finally:
            session.close()

        return RedirectResponse(
            redirect_payload["redirect_url"],
            status_code=302,
        )
    except Exception as exc:
        redirect_payload = locals().get("redirect_payload") or {}
        redirect_url = redirect_payload.get("redirect_url")
        if not redirect_url:
            state_payload = locals().get("state_payload") or {}
            install_session = locals().get("install_session")
            redirect_url = _callback_redirect_target(
                install_session=install_session,
                state_return_to=str(state_payload.get("returnTo") or ""),
                portal_id="",
                plan="",
                billing_interval="",
                bootstrap_status="failed",
                status="error",
                message=str(exc),
            )
        return RedirectResponse(
            redirect_url,
            status_code=302,
        )
