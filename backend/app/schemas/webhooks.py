from pydantic import BaseModel


class HubSpotWebhookValidationResult(BaseModel):
    received: bool
    signature_present: bool
    timestamp_present: bool
    signature_valid: bool
