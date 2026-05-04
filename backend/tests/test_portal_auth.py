from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import db as db_module
from app.config import settings
from app.main import app
from app.models.portal_entitlement import PortalEntitlement
from app.models.portal_setting import PortalSetting
from tests.hubspot_fetch_auth import (
    HUBSPOT_TEST_APP_ID,
    HUBSPOT_TEST_SECRET,
    signed_hubspot_headers,
)


class PortalAuthTests(unittest.TestCase):
    PORTAL_ID = "51300126"
    OTHER_PORTAL_ID = "99999999"

    def setUp(self) -> None:
        self._previous_client_secret = settings.hubspot_client_secret
        self._previous_app_id = settings.hubspot_app_id
        settings.hubspot_client_secret = HUBSPOT_TEST_SECRET
        settings.hubspot_app_id = HUBSPOT_TEST_APP_ID

        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'portal-auth-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        settings.hubspot_client_secret = self._previous_client_secret
        settings.hubspot_app_id = self._previous_app_id
        self._tempdir.cleanup()

    def _session(self):
        session = db_module.get_session()
        self.assertIsNotNone(session)
        return session

    def _seed_active_entitlement(self, portal_id: str = PORTAL_ID) -> None:
        session = self._session()
        try:
            session.add(
                PortalEntitlement(
                    portal_id=portal_id,
                    plan="professional",
                    billing_interval="monthly",
                    subscription_status="active",
                    trial_approved=False,
                )
            )
            session.commit()
        finally:
            session.close()

    def _signed_json_post(self, url: str, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "content-type": "application/json",
            **signed_hubspot_headers("POST", url, body),
        }
        return self.client.post(url, content=body, headers=headers)

    def test_settings_write_rejects_unsigned_request(self) -> None:
        self._seed_active_entitlement()

        response = self.client.post(
            f"/api/v1/settings-store?portalId={self.PORTAL_ID}",
            json={
                "slackWebhookUrl": "https://hooks.slack.test/services/T/B/C",
                "alertThreshold": "high",
            },
        )

        self.assertEqual(401, response.status_code)

    def test_settings_write_rejects_conflicting_portal_metadata(self) -> None:
        self._seed_active_entitlement()
        url = (
            f"/api/v1/settings-store?portalId={self.PORTAL_ID}"
            f"&portalId={self.OTHER_PORTAL_ID}"
            f"&appId={HUBSPOT_TEST_APP_ID}"
        )

        response = self._signed_json_post(
            url,
            {
                "slackWebhookUrl": "https://hooks.slack.test/services/T/B/C",
                "alertThreshold": "high",
            },
        )

        self.assertEqual(403, response.status_code)

        session = self._session()
        try:
            self.assertIsNone(session.get(PortalSetting, self.PORTAL_ID))
        finally:
            session.close()

    def test_settings_write_accepts_valid_hubspot_signed_request(self) -> None:
        self._seed_active_entitlement()
        url = f"/api/v1/settings-store?portalId={self.PORTAL_ID}&appId={HUBSPOT_TEST_APP_ID}"

        response = self._signed_json_post(
            url,
            {
                "slackWebhookUrl": "https://hooks.slack.test/services/T/B/C",
                "alertThreshold": "high",
                "slackDeliveryEnabled": True,
                "ticketDeliveryEnabled": False,
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("ok", payload["status"])
        self.assertEqual(self.PORTAL_ID, payload["portalId"])
        self.assertEqual(
            "https://hooks.slack.test/services/T/B/C",
            payload["settings"]["slackWebhookUrl"],
        )
        self.assertEqual("high", payload["settings"]["alertThreshold"])
        self.assertTrue(payload["settings"]["slackDeliveryEnabled"])
        self.assertFalse(payload["settings"]["ticketDeliveryEnabled"])


if __name__ == "__main__":
    unittest.main()
