from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db as db_module
from app.config import settings
from app.main import app
from app.models.hubspot_installation import HubSpotInstallation
from app.models.portal_entitlement import PortalEntitlement
from app.models.portal_setting import PortalSetting
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.hubspot_oauth import (
    HubSpotDeauthorizedError,
    refresh_access_token,
)
from app.services.portal_purge import purge_portal_data

_POST_FORM = "app.services.hubspot_oauth._post_form"


class _LifecycleBase(unittest.TestCase):
    PORTAL_ID = "51300126"

    def setUp(self) -> None:
        self._prev = (
            settings.hubspot_client_id,
            settings.hubspot_client_secret,
            settings.hubspot_redirect_uri,
            settings.maintenance_api_key,
        )
        settings.hubspot_client_id = "client-id"
        settings.hubspot_client_secret = "client-secret"
        settings.hubspot_redirect_uri = "https://api.app-sync.com/oauth-callback"
        settings.maintenance_api_key = "test-admin-key"

        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'lifecycle.sqlite')}"
        )
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

    def tearDown(self) -> None:
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        (
            settings.hubspot_client_id,
            settings.hubspot_client_secret,
            settings.hubspot_redirect_uri,
            settings.maintenance_api_key,
        ) = self._prev
        self._tempdir.cleanup()

    def _session(self):
        s = db_module.get_session()
        self.assertIsNotNone(s)
        return s


class DeauthorizationTests(_LifecycleBase):
    def _seed_installation(self) -> None:
        session = self._session()
        try:
            session.add(
                HubSpotInstallation(
                    portal_id=self.PORTAL_ID,
                    access_token="AT-old",
                    refresh_token="RT-old",
                    is_active=True,
                )
            )
            session.commit()
        finally:
            session.close()

    def test_invalid_refresh_token_deauthorizes_and_clears_tokens(self) -> None:
        self._seed_installation()
        session = self._session()
        try:
            row = session.get(HubSpotInstallation, self.PORTAL_ID)
            with patch(
                _POST_FORM,
                side_effect=RuntimeError(
                    "HubSpot OAuth request failed: {'status': 'BAD_REFRESH_TOKEN'}"
                ),
            ):
                with self.assertRaises(HubSpotDeauthorizedError):
                    refresh_access_token(session, row)
        finally:
            session.close()

        session = self._session()
        try:
            row = session.get(HubSpotInstallation, self.PORTAL_ID)
            self.assertFalse(row.is_active)
            self.assertEqual("", row.access_token)
            self.assertEqual("", row.refresh_token)
        finally:
            session.close()

    def test_transient_error_does_not_deauthorize(self) -> None:
        self._seed_installation()
        session = self._session()
        try:
            row = session.get(HubSpotInstallation, self.PORTAL_ID)
            with patch(
                _POST_FORM,
                side_effect=RuntimeError(
                    "HubSpot OAuth request failed: {'status': 'INTERNAL_ERROR'}"
                ),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    refresh_access_token(session, row)
                self.assertNotIsInstance(ctx.exception, HubSpotDeauthorizedError)
        finally:
            session.close()

        session = self._session()
        try:
            row = session.get(HubSpotInstallation, self.PORTAL_ID)
            self.assertTrue(row.is_active)
            self.assertEqual("RT-old", row.refresh_token)
        finally:
            session.close()


class PurgeTests(_LifecycleBase):
    def _seed(self) -> None:
        session = self._session()
        try:
            session.add(PortalSetting(portal_id=self.PORTAL_ID))
            session.add(
                WorkflowSnapshot(
                    portal_id=self.PORTAL_ID,
                    workflow_id="wf-1",
                    name="Lead routing",
                    is_enabled=True,
                )
            )
            session.add(
                PortalEntitlement(
                    portal_id=self.PORTAL_ID,
                    plan="professional",
                    billing_interval="monthly",
                    subscription_status="active",
                    trial_approved=False,
                )
            )
            session.commit()
        finally:
            session.close()

    def test_purge_clears_operational_data_keeps_billing_by_default(self) -> None:
        self._seed()
        session = self._session()
        try:
            purge_portal_data(session, self.PORTAL_ID)
        finally:
            session.close()

        session = self._session()
        try:
            self.assertIsNone(session.get(PortalSetting, self.PORTAL_ID))
            self.assertEqual(
                0,
                session.query(WorkflowSnapshot)
                .filter(WorkflowSnapshot.portal_id == self.PORTAL_ID)
                .count(),
            )
            # Billing row preserved unless include_billing.
            self.assertIsNotNone(session.get(PortalEntitlement, self.PORTAL_ID))
        finally:
            session.close()

    def test_purge_include_billing_removes_entitlement(self) -> None:
        self._seed()
        session = self._session()
        try:
            purge_portal_data(session, self.PORTAL_ID, include_billing=True)
        finally:
            session.close()

        session = self._session()
        try:
            self.assertIsNone(session.get(PortalEntitlement, self.PORTAL_ID))
        finally:
            session.close()


class AdminPurgeEndpointTests(_LifecycleBase):
    def setUp(self) -> None:
        super().setUp()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        super().tearDown()

    def test_set_plan_requires_key_and_sets_agency(self) -> None:
        unsigned = self.client.post(
            f"/api/v1/admin/portals/{self.PORTAL_ID}/plan?plan=agency"
        )
        self.assertEqual(401, unsigned.status_code)

        response = self.client.post(
            f"/api/v1/admin/portals/{self.PORTAL_ID}/plan?plan=agency",
            headers={"X-OpsLens-Admin-Key": "test-admin-key"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("agency", response.json()["plan"])

        session = self._session()
        try:
            row = session.get(PortalEntitlement, self.PORTAL_ID)
            self.assertEqual("agency", row.plan)
            self.assertEqual("active", row.subscription_status)
        finally:
            session.close()

    def test_set_plan_rejects_invalid_plan(self) -> None:
        response = self.client.post(
            f"/api/v1/admin/portals/{self.PORTAL_ID}/plan?plan=bogus",
            headers={"X-OpsLens-Admin-Key": "test-admin-key"},
        )
        self.assertEqual(400, response.status_code)

    def test_purge_endpoint_requires_admin_key(self) -> None:
        response = self.client.post(
            f"/api/v1/admin/portals/{self.PORTAL_ID}/purge"
        )
        self.assertEqual(401, response.status_code)

    def test_purge_endpoint_with_key_succeeds(self) -> None:
        session = self._session()
        try:
            session.add(PortalSetting(portal_id=self.PORTAL_ID))
            session.commit()
        finally:
            session.close()

        response = self.client.post(
            f"/api/v1/admin/portals/{self.PORTAL_ID}/purge",
            headers={"X-OpsLens-Admin-Key": "test-admin-key"},
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("ok", body["status"])
        self.assertIn("portal_settings", body["deleted"])

        session = self._session()
        try:
            self.assertIsNone(session.get(PortalSetting, self.PORTAL_ID))
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
