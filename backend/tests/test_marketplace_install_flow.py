import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app
from app.models.hubspot_installation import HubSpotInstallation
from app.models.marketplace_install_session import MarketplaceInstallSession
from app.models.portal_entitlement import PortalEntitlement
from app.services.portal_entitlements import (
    create_marketplace_install_session,
    get_marketplace_install_session,
    sync_installation_activation_for_install_session,
)


class MarketplaceInstallFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = f"sqlite:///{os.path.join(self._tempdir.name, 'marketplace-test.sqlite')}"
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
        self._tempdir.cleanup()

    def _session(self):
        session = db_module.get_session()
        self.assertIsNotNone(session)
        return session

    def test_install_start_creates_paid_checkout_session(self) -> None:
        with (
            patch("app.services.marketplace_billing.settings.stripe_price_professional_monthly", "price_prof_month"),
            patch("app.api.v1.routes.marketplace.settings.backend_public_base_url", "https://api.app-sync.com"),
            patch("app.api.v1.routes.marketplace.settings.app_public_base_url", "https://apps.app-sync.com"),
            patch("app.api.v1.routes.marketplace.create_customer", return_value={"id": "cus_123"}) as create_customer,
            patch(
                "app.api.v1.routes.marketplace.create_checkout_session",
                return_value={"id": "cs_123", "url": "https://checkout.stripe.test/session"},
            ) as create_checkout,
        ):
            response = self.client.post(
                "/api/v1/marketplace/install/start",
                json={
                    "plan": "professional",
                    "billingInterval": "monthly",
                    "returnUrl": "https://apps.app-sync.com/install/complete",
                    "tenantContext": {"tenantSlug": "demo-co"},
                    "partnerUserId": "user_123",
                    "partnerUserEmail": "owner@example.com",
                },
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("ok", payload["status"])
        self.assertTrue(payload["paymentRequired"])
        self.assertEqual("professional", payload["plan"])
        self.assertEqual("monthly", payload["billingInterval"])
        self.assertEqual("https://checkout.stripe.test/session", payload["checkoutUrl"])
        create_customer.assert_called_once()
        create_checkout.assert_called_once()

        session = self._session()
        try:
            row = get_marketplace_install_session(session, payload["installSessionId"])
            self.assertEqual("professional", row.requested_plan)
            self.assertEqual("monthly", row.billing_interval)
            self.assertEqual("cus_123", row.stripe_customer_id)
            self.assertEqual("cs_123", row.stripe_checkout_session_id)
            self.assertEqual('{"tenantSlug": "demo-co"}', row.tenant_context_json)
        finally:
            session.close()

    def test_trial_approved_install_authorize_redirects_to_hubspot(self) -> None:
        session = self._session()
        try:
            row = create_marketplace_install_session(
                session,
                install_session_id="trial-session",
                plan="business",
                billing_interval="yearly",
                return_url="https://apps.app-sync.com/install/return",
                tenant_context={"tenantSlug": "trial-co"},
                partner_user_email="owner@example.com",
                trial_approved=True,
            )
        finally:
            session.close()

        with patch("app.routes.oauth.build_authorization_url", return_value="https://hubspot.test/oauth"):
            response = self.client.get(
                f"/marketplace/install/authorize?installSessionId={row.install_session_id}",
                follow_redirects=False,
            )

        self.assertEqual(302, response.status_code)
        self.assertEqual("https://hubspot.test/oauth", response.headers["location"])

    def test_install_authorize_blocks_unpaid_install_session(self) -> None:
        session = self._session()
        try:
            create_marketplace_install_session(
                session,
                install_session_id="pending-session",
                plan="professional",
                billing_interval="monthly",
                return_url="https://apps.app-sync.com/install/return",
                tenant_context={"tenantSlug": "pending-co"},
                partner_user_email="owner@example.com",
                trial_approved=False,
            )
        finally:
            session.close()

        response = self.client.get(
            "/marketplace/install/authorize?installSessionId=pending-session",
            follow_redirects=False,
        )

        self.assertEqual(400, response.status_code)
        self.assertIn("paid or trial-approved install session", response.text)

    def test_install_success_contract_reports_bootstrap_summary(self) -> None:
        session = self._session()
        try:
            row = create_marketplace_install_session(
                session,
                install_session_id="success-session",
                plan="professional",
                billing_interval="monthly",
                return_url="https://apps.app-sync.com/install/return",
                tenant_context={"tenantSlug": "success-co"},
                partner_user_email="owner@example.com",
                trial_approved=True,
            )
            row.hubspot_portal_id = "8886743"
            row.subscription_status = "trial_approved"
            row.bootstrap_status = "success"
            row.bootstrap_summary_json = json.dumps(
                {
                    "pipelineId": "892158537",
                    "contactPropertyGroupCreated": True,
                    "ticketPropertyGroupCreated": True,
                }
            )
            session.commit()
        finally:
            session.close()

        response = self.client.get("/api/v1/marketplace/install/success?installSessionId=success-session")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("8886743", payload["portalId"])
        self.assertEqual("professional", payload["plan"])
        self.assertEqual("success", payload["bootstrapStatus"])
        self.assertTrue(payload["active"])
        self.assertEqual("892158537", payload["createdAssetsSummary"]["pipelineId"])
        self.assertEqual(3, len(payload["nextStepChecklist"]))

    def test_sync_installation_activation_requires_bootstrap_success(self) -> None:
        session = self._session()
        try:
            installation = HubSpotInstallation(
                portal_id="8886743",
                access_token="token",
                refresh_token="refresh",
                is_active=False,
            )
            session.add(installation)
            session.commit()

            install_session = create_marketplace_install_session(
                session,
                install_session_id="activation-session",
                plan="business",
                billing_interval="monthly",
                return_url="https://apps.app-sync.com/install/return",
                tenant_context={"tenantSlug": "activation-co"},
                partner_user_email="owner@example.com",
                trial_approved=False,
            )
            install_session.hubspot_portal_id = "8886743"
            install_session.subscription_status = "active"
            install_session.bootstrap_status = "pending"
            session.commit()

            activated = sync_installation_activation_for_install_session(session, install_session)
            session.refresh(installation)
            entitlement = session.get(PortalEntitlement, "8886743")

            self.assertFalse(activated)
            self.assertFalse(installation.is_active)
            self.assertIsNotNone(entitlement)
            self.assertEqual("business", entitlement.plan)

            install_session.bootstrap_status = "success"
            session.commit()

            activated = sync_installation_activation_for_install_session(session, install_session)
            session.refresh(installation)

            self.assertTrue(activated)
            self.assertTrue(installation.is_active)
        finally:
            session.close()

    def test_settings_save_is_blocked_for_inactive_entitlement(self) -> None:
        session = self._session()
        try:
            session.add(
                PortalEntitlement(
                    portal_id="8886743",
                    plan="professional",
                    billing_interval="monthly",
                    subscription_status="pending",
                    trial_approved=False,
                )
            )
            session.commit()
        finally:
            session.close()

        response = self.client.post(
            "/api/v1/settings-store?portalId=8886743",
            json={
                "slackWebhookUrl": "",
                "alertThreshold": "high",
                "criticalWorkflows": "",
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("error", payload["status"])
        self.assertEqual("8886743", payload["portalId"])
        self.assertEqual("professional", payload["entitlement"]["plan"])
        self.assertFalse(payload["entitlement"]["active"])


if __name__ == "__main__":
    unittest.main()
