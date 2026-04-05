from pathlib import Path
import json
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TOKENS_DIR = WORKSPACE_ROOT / "oauth_tokens"
TOKENS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    hubspot_redirect_uri: str = "http://localhost:3000/oauth-callback"
    hubspot_scopes: str = ""
    hubspot_target_account_id: str = ""

    model_config = SettingsConfigDict(
        env_file=WORKSPACE_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
app = FastAPI(title="OpsLens Local OAuth Service", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def home():
    ready = bool(settings.hubspot_client_id and settings.hubspot_client_secret)
    return f"""
    <html>
      <head><title>OpsLens Local OAuth Service</title></head>
      <body style="font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto;">
        <h1>OpsLens Local OAuth Service</h1>
        <p>Status: <strong>{'ready' if ready else 'missing configuration'}</strong></p>
        <ul>
          <li>Client ID present: {bool(settings.hubspot_client_id)}</li>
          <li>Client Secret present: {bool(settings.hubspot_client_secret)}</li>
          <li>Redirect URI: {settings.hubspot_redirect_uri}</li>
          <li>Target Account ID: {settings.hubspot_target_account_id or 'not set'}</li>
        </ul>
        <p>If the service is configured, use <a href="/install">/install</a> to start OAuth manually.</p>
      </body>
    </html>
    """


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "opslens-local-oauth",
        "client_id_present": bool(settings.hubspot_client_id),
        "client_secret_present": bool(settings.hubspot_client_secret),
        "redirect_uri": settings.hubspot_redirect_uri,
    }


@app.get("/install")
def install():
    if not settings.hubspot_client_id:
        raise HTTPException(status_code=500, detail="HUBSPOT_CLIENT_ID is missing in .env")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.hubspot_client_id,
        "redirect_uri": settings.hubspot_redirect_uri,
        "state": state,
    }

    if settings.hubspot_scopes.strip():
        params["scope"] = settings.hubspot_scopes.strip()

    base = "https://app.hubspot.com/oauth/authorize"
    if settings.hubspot_target_account_id.strip():
        base = f"https://app.hubspot.com/oauth/{settings.hubspot_target_account_id.strip()}/authorize"

    return RedirectResponse(url=f"{base}?{urlencode(params)}")


@app.get("/oauth-callback", response_class=HTMLResponse)
async def oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    if error:
        return HTMLResponse(
            f"<h1>HubSpot OAuth returned an error</h1><p>{error}</p><p>{error_description or ''}</p>",
            status_code=400,
        )

    if not code:
        return HTMLResponse("<h1>Missing authorization code.</h1>", status_code=400)

    if not settings.hubspot_client_id or not settings.hubspot_client_secret:
        return HTMLResponse(
            "<h1>Missing HubSpot client credentials in .env.</h1>",
            status_code=500,
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.hubapi.com/oauth/v1/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.hubspot_client_id,
                "client_secret": settings.hubspot_client_secret,
                "redirect_uri": settings.hubspot_redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    payload = response.json()

    if response.status_code >= 400:
        return HTMLResponse(
            "<h1>Token exchange failed.</h1>"
            f"<pre>{json.dumps(payload, indent=2)}</pre>",
            status_code=400,
        )

    portal_id = str(payload.get("hub_id", "unknown"))
    token_file = TOKENS_DIR / f"hubspot_tokens_{portal_id}.json"
    token_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return f"""
    <html>
      <head><title>OpsLens OAuth Success</title></head>
      <body style="font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto;">
        <h1>OAuth connection succeeded</h1>
        <p>Hub ID: <strong>{portal_id}</strong></p>
        <p>State: <strong>{state or 'n/a'}</strong></p>
        <p>Tokens were saved locally to:</p>
        <pre>{token_file}</pre>
      </body>
    </html>
    """


@app.get("/latest-token")
def latest_token():
    files = sorted(TOKENS_DIR.glob("hubspot_tokens_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return JSONResponse({"status": "empty", "message": "No token file found yet."})
    latest = files[0]
    data = json.loads(latest.read_text(encoding="utf-8"))
    safe = {
        "hub_id": data.get("hub_id"),
        "scope": data.get("scope"),
        "token_type": data.get("token_type"),
        "expires_in": data.get("expires_in"),
        "file": str(latest),
    }
    return safe


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3000, reload=True)
