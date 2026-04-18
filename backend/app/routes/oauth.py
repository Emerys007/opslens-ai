from __future__ import annotations

import html

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import get_session, init_db
from app.services.hubspot_oauth import (
    build_authorization_url,
    exchange_code_for_tokens,
    introspect_access_token,
    parse_signed_state,
    upsert_installation,
)

router = APIRouter(tags=["oauth"])


def _success_html(
    *,
    portal_id: str,
    hub_domain: str,
    installing_user_email: str,
    return_to: str,
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
      <p>HubSpot OAuth completed successfully and the installation was saved in Postgres.</p>
      <p><strong>Portal ID:</strong> <code>{html.escape(portal_id)}</code></p>
      <p><strong>Hub domain:</strong> <code>{html.escape(hub_domain or "-")}</code></p>
      <p><strong>Installing user:</strong> <code>{html.escape(installing_user_email or "-")}</code></p>
      {link_html}
      <p>You can close this tab.</p>
    </div>
  </body>
</html>"""


def _error_html(message: str) -> str:
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
    </div>
  </body>
</html>"""


@router.get("/oauth/install-url")
def oauth_install_url(returnTo: str | None = Query(default=None)):
    try:
        return {
            "status": "ok",
            "authorizationUrl": build_authorization_url(returnTo),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/oauth/start")
def oauth_start(returnTo: str | None = Query(default=None)):
    try:
        return RedirectResponse(build_authorization_url(returnTo), status_code=302)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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

        try:
            installation = upsert_installation(
                session,
                token_payload=token_payload,
                metadata=metadata,
            )
        finally:
            session.close()

        return HTMLResponse(
            _success_html(
                portal_id=installation.portal_id,
                hub_domain=installation.hub_domain,
                installing_user_email=installation.installing_user_email,
                return_to=str(state_payload.get("returnTo") or ""),
            ),
            status_code=200,
        )
    except Exception as exc:
        return HTMLResponse(_error_html(str(exc)), status_code=400)
