import base64
import hashlib
import hmac
import time
from urllib.parse import unquote, urlparse

from app.config import settings


def _normalize_uri(uri: str) -> str:
    parsed = urlparse(uri)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return unquote(normalized)


def validate_hubspot_v3_signature(
    method: str,
    uri: str,
    body: bytes,
    signature: str | None,
    timestamp: str | None,
    max_age_seconds: int = 300,
) -> bool:
    if not settings.hubspot_webhook_secret:
        return False

    if not signature or not timestamp:
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    current_millis = int(time.time() * 1000)
    if abs(current_millis - timestamp_int) > max_age_seconds * 1000:
        return False

    source = (
        method.upper()
        + _normalize_uri(uri)
        + body.decode("utf-8")
        + timestamp
    ).encode("utf-8")

    digest = hmac.new(
        settings.hubspot_webhook_secret.encode("utf-8"),
        source,
        hashlib.sha256,
    ).digest()

    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)
