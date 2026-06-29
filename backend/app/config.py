from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OpsLens AI"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    backend_public_base_url: str = "https://api.app-sync.com"
    app_public_base_url: str = "https://app-sync.com"
    email_importer_origin: str = "https://historic-email-importer-worker.onrender.com"

    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    hubspot_redirect_uri: str = ""
    hubspot_app_id: str = ""
    hubspot_webhook_secret: str = ""

    hubspot_scopes: str = "oauth crm.objects.contacts.read crm.objects.contacts.write crm.schemas.contacts.write tickets automation crm.schemas.contacts.read crm.schemas.companies.read crm.schemas.deals.read crm.lists.read content crm.objects.owners.read"
    hubspot_optional_scopes: str = ""
    oauth_state_secret: str = ""
    oauth_state_ttl_seconds: int = 900

    # Encryption-at-rest for stored HubSpot OAuth tokens. A urlsafe-base64
    # 32-byte Fernet key. When empty, tokens are stored as plaintext (legacy
    # behavior); setting it encrypts tokens going forward. Must stay stable.
    token_encryption_key: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter_monthly: str = ""
    stripe_price_starter_yearly: str = ""
    stripe_price_professional_monthly: str = ""
    stripe_price_professional_yearly: str = ""
    stripe_price_agency_monthly: str = ""
    stripe_price_agency_yearly: str = ""
    # Legacy "business" tier prices, retained for back-compat with any live
    # subscriptions created before the starter/professional/agency rename.
    stripe_price_business_monthly: str = ""
    stripe_price_business_yearly: str = ""

    # Slack "Connect" OAuth (incoming-webhook flow). The redirect URI must be
    # registered on the Slack app as https://api.app-sync.com/slack/oauth-callback.
    slack_client_id: str = ""
    slack_client_secret: str = ""

    # Background workflow polling.
    workflow_poll_interval_seconds: int = 120
    maintenance_api_key: str = ""

    # Alert rewriter (Anthropic Claude). Empty key OR
    # ``alert_rewriter_enabled=False`` disables the rewriter — the
    # scheduler skips the rewrite pass and Slack/ticket bodies fall
    # back to the structured rendering of the alert summary.
    anthropic_api_key: str = ""
    alert_rewriter_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
