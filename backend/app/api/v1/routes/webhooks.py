from fastapi import APIRouter, Header, Request

from app.core.security import validate_hubspot_v3_signature

router = APIRouter(prefix="/webhooks/hubspot", tags=["hubspot-webhooks"])


@router.get("/test")
def hubspot_webhook_test():
    return {
        "status": "ok",
        "message": "HubSpot webhook route is wired correctly.",
    }


@router.post("/validate-demo")
async def validate_demo(
    request: Request,
    x_hubspot_signature_v3: str | None = Header(default=None),
    x_hubspot_request_timestamp: str | None = Header(default=None),
):
    raw_body = await request.body()
    is_valid = validate_hubspot_v3_signature(
        method=request.method,
        uri=str(request.url),
        body=raw_body,
        signature=x_hubspot_signature_v3,
        timestamp=x_hubspot_request_timestamp,
    )
    return {
        "received": True,
        "signature_present": bool(x_hubspot_signature_v3),
        "timestamp_present": bool(x_hubspot_request_timestamp),
        "signature_valid": is_valid,
    }
