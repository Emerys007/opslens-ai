from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.routes import email_importer_gateway as gateway


class FakeAsyncClient:
    last_request: dict[str, object] | None = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def request(self, method, url, *, content, headers):
        self.__class__.last_request = {
            "method": method,
            "url": url,
            "content": content,
            "headers": headers,
        }
        return httpx.Response(
            201,
            content=b"proxied",
            headers={
                "content-type": "text/plain",
                "connection": "keep-alive",
                "location": (
                    "https://historic-email-importer-worker.onrender.com"
                    "/email-importer/auth/gmail/callback"
                ),
            },
        )


class EmailImporterGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._old_origin = gateway.settings.email_importer_origin
        self._old_backend_base = gateway.settings.backend_public_base_url
        gateway.settings.email_importer_origin = (
            "https://historic-email-importer-worker.onrender.com"
        )
        gateway.settings.backend_public_base_url = "https://api.app-sync.com"
        FakeAsyncClient.last_request = None

    def tearDown(self) -> None:
        self.client.close()
        gateway.settings.email_importer_origin = self._old_origin
        gateway.settings.backend_public_base_url = self._old_backend_base

    def test_proxy_preserves_path_query_body_and_safe_headers(self):
        with patch.object(gateway.httpx, "AsyncClient", FakeAsyncClient):
            response = self.client.post(
                "/email-importer/api/status?deep=true",
                content=b'{"hello":"world"}',
                headers={
                    "authorization": "Bearer test-token",
                    "content-type": "application/json",
                    "accept": "application/json",
                    "user-agent": "gateway-test",
                    "x-admin-token": "admin-token",
                    "x-hubspot-signature": "signature-v1",
                    "x-hubspot-signature-v3": "signature-v3",
                    "x-not-forwarded": "nope",
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.content, b"proxied")
        self.assertEqual(
            response.headers["location"],
            "https://api.app-sync.com/email-importer/auth/gmail/callback",
        )
        self.assertNotIn("connection", response.headers)

        upstream = FakeAsyncClient.last_request
        self.assertIsNotNone(upstream)
        assert upstream is not None
        self.assertEqual(upstream["method"], "POST")
        self.assertEqual(
            upstream["url"],
            (
                "https://historic-email-importer-worker.onrender.com"
                "/email-importer/api/status?deep=true"
            ),
        )
        self.assertEqual(upstream["content"], b'{"hello":"world"}')

        headers = upstream["headers"]
        assert isinstance(headers, dict)
        self.assertEqual(headers["authorization"], "Bearer test-token")
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["accept"], "application/json")
        self.assertEqual(headers["user-agent"], "gateway-test")
        self.assertEqual(headers["x-admin-token"], "admin-token")
        self.assertEqual(headers["x-hubspot-signature"], "signature-v1")
        self.assertEqual(headers["x-hubspot-signature-v3"], "signature-v3")
        self.assertNotIn("x-not-forwarded", headers)
        self.assertEqual(headers["x-forwarded-prefix"], "/email-importer")
        self.assertEqual(headers["x-app-sync-gateway"], "email-importer")

    def test_root_email_importer_path_proxies_to_origin_prefix(self):
        with patch.object(gateway.httpx, "AsyncClient", FakeAsyncClient):
            response = self.client.get("/email-importer")

        self.assertEqual(response.status_code, 201)
        upstream = FakeAsyncClient.last_request
        self.assertIsNotNone(upstream)
        assert upstream is not None
        self.assertEqual(
            upstream["url"],
            "https://historic-email-importer-worker.onrender.com/email-importer",
        )


if __name__ == "__main__":
    unittest.main()
