from __future__ import annotations

import html

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
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
from app.services.portal_entitlements import (
    get_marketplace_install_session,
    install_session_is_billable_active,
    mark_install_session_bootstrap,
    mark_install_session_oauth_completed,
    run_post_install_provisioner,
    sync_installation_activation_for_install_session,
    update_install_session_billing,
)

router = APIRouter(tags=["oauth"])


def _default_install_return_url() -> str:
    app_base = str(settings.app_public_base_url or "").strip().rstrip("/")
    if not app_base:
        app_base = "https://apps.app-sync.com"
    return f"{app_base}/opslens/install/complete"


def _resolved_install_return_url(
    *,
    install_session_return_url: str = "",
    state_return_to: str = "",
) -> str:
    install_url = str(install_session_return_url or "").strip()
    if install_url:
        return install_url

    state_url = str(state_return_to or "").strip()
    if state_url:
        return state_url

    return _default_install_return_url()


def _success_html(
    *,
    portal_id: str,
    hub_domain: str,
    installing_user_email: str,
    return_to: str,
    plan: str = "",
    billing_interval: str = "",
    bootstrap_status: str = "success",
) -> str:
    link_html = ""
    if return_to:
        safe_url = html.escape(return_to, quote=True)
        link_html = (
            f'<p><a href="{safe_url}" '
            'style="display:inline-block;padding:10px 14px;background:#2563eb;'
            'color:#fff;text-decoration:none;border-radius:8px;">Return</a></p>'
        )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>OpsLens OAuth complete</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body {{
        font-family: Arial, sans-serif;
        background: #f7f9fc;
        color: #1f2937;
        margin: 0;
        padding: 40px 20px;
      }}
      .card {{
        max-width: 720px;
        margin: 0 auto;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
      }}
      h1 {{
        margin-top: 0;
      }}
      code {{
        background: #f3f4f6;
        padding: 2px 6px;
        border-radius: 6px;
      }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>OpsLens installation complete</h1>
      <p>HubSpot OAuth completed successfully, the installation was saved in Postgres, and the OpsLens HubSpot schema was verified.</p>
      <p><strong>Portal ID:</strong> <code>{html.escape(portal_id)}</code></p>
      <p><strong>Hub domain:</strong> <code>{html.escape(hub_domain or "-")}</code></p>
      <p><strong>Installing user:</strong> <code>{html.escape(installing_user_email or "-")}</code></p>
      <p><strong>Plan:</strong> <code>{html.escape(plan or "-")}</code></p>
      <p><strong>Billing interval:</strong> <code>{html.escape(billing_interval or "-")}</code></p>
      <p><strong>Bootstrap status:</strong> <code>{html.escape(bootstrap_status or "-")}</code></p>
      {link_html}
      <p>You can close this tab.</p>
    </div>
  </body>
</html>"""


def _error_html(message: str, return_to: str = "") -> str:
    link_html = ""
    if return_to:
        safe_url = html.escape(return_to, quote=True)
        link_html = (
            f'<p><a href="{safe_url}" '
            'style="display:inline-block;padding:10px 14px;background:#9a3412;'
            'color:#fff;text-decoration:none;border-radius:8px;">Return</a></p>'
        )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>OpsLens OAuth error</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body {{
        font-family: Arial, sans-serif;
        background: #fff7ed;
        color: #7c2d12;
        margin: 0;
        padding: 40px 20px;
      }}
      .card {{
        max-width: 720px;
        margin: 0 auto;
        background: #ffffff;
        border: 1px solid #fdba74;
        border-radius: 12px;
        padding: 24px;
      }}
      h1 {{
        margin-top: 0;
      }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>OpsLens OAuth failed</h1>
      <p>{html.escape(message)}</p>
      {link_html}
    </div>
  </body>
</html>"""


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
                    _resolved_install_return_url(
                        install_session_return_url=install_session.return_url,
                    ),
                    install_session.install_session_id,
                ),
                status_code=302,
            )
        finally:
            session.close()
    except Exception as exc:
        return HTMLResponse(
            _error_html(str(exc)),
            status_code=400,
        )


@router.get("/oauth-callback", response_class=HTMLResponse)
def oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    if error:
        message = error_description or error or "HubSpot OAuth returned an error."
        return HTMLResponse(_error_html(message), status_code=400)

    auth_code = str(code or "").strip()
    signed_state = str(state or "").strip()

    if not auth_code:
        return HTMLResponse(_error_html("Missing OAuth code."), status_code=400)
    if not signed_state:
        return HTMLResponse(_error_html("Missing OAuth state."), status_code=400)

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
        success_payload = {}

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

            success_payload = {
                "portal_id": str(installation.portal_id or "").strip(),
                "hub_domain": str(installation.hub_domain or "").strip(),
                "installing_user_email": str(installation.installing_user_email or "").strip(),
                "return_to": _resolved_install_return_url(
                    install_session_return_url=(install_session.return_url if install_session is not None else ""),
                    state_return_to=str(state_payload.get("returnTo") or ""),
                ),
                "plan": str((install_session.requested_plan if install_session is not None else "") or ""),
                "billing_interval": str((install_session.billing_interval if install_session is not None else "") or ""),
                "bootstrap_status": str((install_session.bootstrap_status if install_session is not None else "success") or "success"),
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
            raise
        finally:
            session.close()

        return HTMLResponse(
            _success_html(
                portal_id=success_payload["portal_id"],
                hub_domain=success_payload["hub_domain"],
                installing_user_email=success_payload["installing_user_email"],
                return_to=success_payload["return_to"],
                plan=success_payload["plan"],
                billing_interval=success_payload["billing_interval"],
                bootstrap_status=success_payload["bootstrap_status"],
            ),
            status_code=200,
        )
    except Exception as exc:
        message = str(exc)
        state_payload = locals().get("state_payload") or {}
        install_session = locals().get("install_session")
        return_to = _resolved_install_return_url(
            install_session_return_url=(install_session.return_url if install_session is not None else ""),
            state_return_to=str(state_payload.get("returnTo") or ""),
        )
        if "bootstrap_started" in locals() and bootstrap_started:
            message = f"HubSpot install completed, but OpsLens bootstrap failed: {exc}"
        return HTMLResponse(
            _error_html(message, return_to),
            status_code=400,
        )
