from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OpsLens AI"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    hubspot_redirect_uri: str = ""
    hubspot_app_id: str = ""
    hubspot_webhook_secret: str = ""

    hubspot_scopes: str = "oauth crm.objects.contacts.read crm.objects.contacts.write tickets"
    hubspot_optional_scopes: str = ""
    oauth_state_secret: str = ""
    oauth_state_ttl_seconds: int = 900

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()