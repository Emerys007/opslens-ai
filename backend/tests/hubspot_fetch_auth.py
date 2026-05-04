from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import _normalize_uri


HUBSPOT_TEST_SECRET = "test-hubspot-client-secret"
HUBSPOT_TEST_APP_ID = "app-123"


def _absolute_test_url(url: str) -> str:
    value = str(url)
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if not value.startswith("/"):
        value = f"/{value}"
    return f"http://testserver{value}"


def signed_hubspot_headers(
    method: str,
    url: str,
    body: bytes = b"",
    *,
    secret: str = HUBSPOT_TEST_SECRET,
) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    source = (
        method.upper()
        + _normalize_uri(_absolute_test_url(url))
        + body.decode("utf-8")
        + timestamp
    ).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), source, hashlib.sha256).digest()
    return {
        "x-hubspot-signature-v3": base64.b64encode(digest).decode("utf-8"),
        "x-hubspot-request-timestamp": timestamp,
    }


class SignedHubSpotTestClient:
    def __init__(self, app, *, secret: str = HUBSPOT_TEST_SECRET):
        self._client = TestClient(app)
        self._secret = secret
        self._previous_client_secret = settings.hubspot_client_secret
        self._previous_app_id = settings.hubspot_app_id
        settings.hubspot_client_secret = secret
        settings.hubspot_app_id = HUBSPOT_TEST_APP_ID

    def close(self) -> None:
        self._client.close()
        settings.hubspot_client_secret = self._previous_client_secret
        settings.hubspot_app_id = self._previous_app_id

    def request(self, method: str, url: str, **kwargs: Any):
        headers = dict(kwargs.pop("headers", {}) or {})
        body = b""
        if "json" in kwargs:
            body = json.dumps(kwargs.pop("json")).encode("utf-8")
            kwargs["content"] = body
            headers.setdefault("content-type", "application/json")
        elif "content" in kwargs:
            content = kwargs["content"]
            if isinstance(content, bytes):
                body = content
            elif isinstance(content, str):
                body = content.encode("utf-8")
            elif content is not None:
                body = bytes(content)
        elif "data" in kwargs:
            data = kwargs["data"]
            if isinstance(data, bytes):
                body = data
            elif isinstance(data, str):
                body = data.encode("utf-8")

        headers.update(signed_hubspot_headers(method, url, body, secret=self._secret))
        return self._client.request(method, url, headers=headers, **kwargs)

    def get(self, url: str, **kwargs: Any):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any):
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any):
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any):
        return self.request("DELETE", url, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._client, name)
