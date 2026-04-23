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
        success_url = create_checkout.call_args.kwargs["success_url"]
        self.assertIn("{CHECKOUT_SESSION_ID}", success_url)
        self.assertNotIn("%7BCHECKOUT_SESSION_ID%7D", success_url)
        self.assertIn(f"installSessionId={payload['installSessionId']}", success_url)

        session = self._session()
        try:
            row = get_marketplace_install_session(session, payload["installSessionId"])
            self.assertEqual("professional", row.requested_plan)
            self.assertEqual("monthly", row.billing_interval)
            self.assertEqual("cus_123", row.stripe_customer_id)
            self.assertEqual("cs_123", row.stripe_checkout_session_id)
            self.assertEqual(
                '{"installOrigin": "external", "tenantSlug": "demo-co"}',
                row.tenant_context_json,
            )
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

        self.assertEqual(302, response.status_code)
        self.assertIn("/opslens/install/complete/?", response.headers["location"])
        self.assertIn("bootstrapStatus=failed", response.headers["location"])
        self.assertIn("status=error", response.headers["location"])

    def test_marketplace_origin_oauth_callback_redirects_to_hubspot_return_url(self) -> None:
        hubspot_return_url = (
            "https://app.hubspot.com/marketplace-preview"
            "?returnToken=hubspot-provided-token"
            "&portalId=8886743"
        )
        session = self._session()
        try:
            create_marketplace_install_session(
                session,
                install_session_id="marketplace-callback-session",
                plan="business",
                billing_interval="yearly",
                return_url=hubspot_return_url,
                tenant_context={
                    "tenantSlug": "marketplace-callback",
                    "installOrigin": "marketplace",
                },
                partner_user_email="owner@example.com",
                trial_approved=True,
            )
        finally:
            session.close()

        with (
            patch(
                "app.routes.oauth.parse_signed_state",
                return_value={
                    "installSessionId": "marketplace-callback-session",
                    "returnTo": hubspot_return_url,
                },
            ),
            patch(
                "app.routes.oauth.exchange_code_for_tokens",
                return_value={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
            patch(
                "app.routes.oauth.introspect_access_token",
                return_value={
                    "hub_id": "8886743",
                    "hub_domain": "portal-8886743.test",
                    "user": "owner@example.com",
                    "user_id": "user-123",
                    "app_id": "app-123",
                    "scopes": ["oauth", "tickets"],
                },
            ),
            patch(
                "app.services.portal_entitlements.ensure_portal_bootstrap",
                return_value={
                    "portalId": "8886743",
                    "pipelineId": "892158537",
                    "contactPropertyGroupCreated": False,
                    "ticketPropertyGroupCreated": False,
                    "contactPropertiesCreated": [],
                    "ticketPropertiesCreated": [],
                    "pipelineCreated": False,
                    "stagesCreated": [],
                    "stagesUpdated": [],
                },
            ),
        ):
            callback = self.client.get(
                "/oauth-callback?code=auth-code&state=signed-state",
                follow_redirects=False,
            )

        self.assertEqual(302, callback.status_code)
        self.assertEqual(hubspot_return_url, callback.headers["location"])

        success = self.client.get(
            "/api/v1/marketplace/install/success?installSessionId=marketplace-callback-session"
        )
        self.assertEqual(200, success.status_code)
        success_payload = success.json()
        self.assertEqual("ok", success_payload["status"])
        self.assertEqual("8886743", success_payload["portalId"])
        self.assertEqual("success", success_payload["bootstrapStatus"])
        self.assertEqual(hubspot_return_url, success_payload["returnUrl"])
        self.assertTrue(success_payload["active"])

        overview = self.client.get("/api/v1/dashboard/overview?portalId=8886743")
        self.assertEqual(200, overview.status_code)
        self.assertEqual("ok", overview.json()["status"])

        settings = self.client.get("/api/v1/settings-store?portalId=8886743")
        self.assertEqual(200, settings.status_code)
        self.assertEqual("ok", settings.json()["status"])

    def test_external_origin_trial_install_redirects_to_public_complete_route(self) -> None:
        session = self._session()
        try:
            create_marketplace_install_session(
                session,
                install_session_id="external-trial-session",
                plan="business",
                billing_interval="yearly",
                return_url="https://apps.app-sync.com/install/complete",
                tenant_context={"tenantSlug": "external-trial"},
                partner_user_email="owner@example.com",
                trial_approved=True,
            )
        finally:
            session.close()

        with (
            patch(
                "app.routes.oauth.parse_signed_state",
                return_value={
                    "installSessionId": "external-trial-session",
                    "returnTo": "https://apps.app-sync.com/install/complete",
                },
            ),
            patch(
                "app.routes.oauth.exchange_code_for_tokens",
                return_value={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
            patch(
                "app.routes.oauth.introspect_access_token",
                return_value={
                    "hub_id": "8886743",
                    "hub_domain": "portal-8886743.test",
                    "user": "owner@example.com",
                    "user_id": "user-123",
                    "app_id": "app-123",
                    "scopes": ["oauth", "tickets"],
                },
            ),
            patch(
                "app.services.portal_entitlements.ensure_portal_bootstrap",
                return_value={
                    "portalId": "8886743",
                    "pipelineId": "892158537",
                    "contactPropertyGroupCreated": False,
                    "ticketPropertyGroupCreated": False,
                    "contactPropertiesCreated": [],
                    "ticketPropertiesCreated": [],
                    "pipelineCreated": False,
                    "stagesCreated": [],
                    "stagesUpdated": [],
                },
            ),
        ):
            callback = self.client.get(
                "/oauth-callback?code=auth-code&state=signed-state",
                follow_redirects=False,
            )

        self.assertEqual(302, callback.status_code)
        location = callback.headers["location"]
        self.assertTrue(location.startswith("https://apps.app-sync.com/opslens/install/complete/?"))
        self.assertIn("portalId=8886743", location)
        self.assertIn("plan=business", location)
        self.assertIn("billingInterval=yearly", location)
        self.assertIn("bootstrapStatus=success", location)

        success = self.client.get(
            "/api/v1/marketplace/install/success?installSessionId=external-trial-session"
        )
        self.assertEqual(200, success.status_code)
        success_payload = success.json()
        self.assertEqual("ok", success_payload["status"])
        self.assertEqual("8886743", success_payload["portalId"])
        self.assertEqual("success", success_payload["bootstrapStatus"])
        self.assertIn("/opslens/install/complete/?portalId=8886743", success_payload["returnUrl"])
        self.assertTrue(success_payload["active"])

    def test_paid_install_start_authorize_and_oauth_callback_complete_after_checkout(self) -> None:
        with (
            patch("app.services.marketplace_billing.settings.stripe_price_professional_monthly", "price_prof_month"),
            patch("app.api.v1.routes.marketplace.settings.backend_public_base_url", "https://api.app-sync.com"),
            patch("app.api.v1.routes.marketplace.settings.app_public_base_url", "https://apps.app-sync.com"),
            patch("app.api.v1.routes.marketplace.create_customer", return_value={"id": "cus_paid_123"}),
            patch(
                "app.api.v1.routes.marketplace.create_checkout_session",
                return_value={"id": "cs_paid_123", "url": "https://checkout.stripe.test/session"},
            ) as create_checkout,
        ):
            start = self.client.post(
                "/api/v1/marketplace/install/start",
                json={
                    "plan": "professional",
                    "billingInterval": "monthly",
                    "returnUrl": "https://apps.app-sync.com/install/complete",
                    "tenantContext": {"tenantSlug": "paid-callback"},
                    "partnerUserId": "user-456",
                    "partnerUserEmail": "owner@example.com",
                    "trialApproved": False,
                },
            )

        self.assertEqual(200, start.status_code)
        start_payload = start.json()
        install_session_id = start_payload["installSessionId"]
        self.assertEqual("ok", start_payload["status"])
        self.assertEqual("https://checkout.stripe.test/session", start_payload["checkoutUrl"])
        success_url = create_checkout.call_args.kwargs["success_url"]
        self.assertIn("{CHECKOUT_SESSION_ID}", success_url)
        self.assertNotIn("%7BCHECKOUT_SESSION_ID%7D", success_url)
        self.assertIn(f"installSessionId={install_session_id}", success_url)

        with (
            patch(
                "app.routes.oauth.retrieve_checkout_session",
                return_value={
                    "id": "cs_paid_123",
                    "client_reference_id": install_session_id,
                    "payment_status": "paid",
                    "status": "complete",
                    "subscription": "sub_paid_123",
                    "customer": "cus_paid_123",
                },
            ),
            patch(
                "app.routes.oauth.retrieve_subscription",
                return_value={
                    "id": "sub_paid_123",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "unknown_price"}}]},
                },
            ),
            patch("app.routes.oauth.build_authorization_url", return_value="https://hubspot.test/oauth"),
        ):
            authorize = self.client.get(
                f"/marketplace/install/authorize?installSessionId={install_session_id}&checkoutSessionId=cs_paid_123",
                follow_redirects=False,
            )

        self.assertEqual(302, authorize.status_code)
        self.assertEqual("https://hubspot.test/oauth", authorize.headers["location"])

        with (
            patch(
                "app.routes.oauth.parse_signed_state",
                return_value={
                    "installSessionId": install_session_id,
                    "returnTo": "https://apps.app-sync.com/install/complete",
                },
            ),
            patch(
                "app.routes.oauth.exchange_code_for_tokens",
                return_value={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
            patch(
                "app.routes.oauth.introspect_access_token",
                return_value={
                    "hub_id": "9999999",
                    "hub_domain": "portal-new.test",
                    "user": "owner@example.com",
                    "user_id": "user-456",
                    "app_id": "app-123",
                    "scopes": ["oauth", "tickets"],
                },
            ),
            patch(
                "app.services.portal_entitlements.ensure_portal_bootstrap",
                return_value={
                    "portalId": "9999999",
                    "pipelineId": "912345678",
                    "contactPropertyGroupCreated": True,
                    "ticketPropertyGroupCreated": True,
                    "contactPropertiesCreated": ["opslens_healthy_signal_at"],
                    "ticketPropertiesCreated": ["opslens_ticket_contact_id"],
                    "pipelineCreated": True,
                    "stagesCreated": ["New Alert"],
                    "stagesUpdated": [],
                },
            ),
        ):
            callback = self.client.get(
                "/oauth-callback?code=auth-code&state=signed-state",
                follow_redirects=False,
            )

        self.assertEqual(302, callback.status_code)
        callback_location = callback.headers["location"]
        self.assertTrue(callback_location.startswith("https://apps.app-sync.com/opslens/install/complete/?"))
        self.assertIn("portalId=9999999", callback_location)
        self.assertIn("plan=professional", callback_location)
        self.assertIn("billingInterval=monthly", callback_location)
        self.assertIn("bootstrapStatus=success", callback_location)

        success = self.client.get(
            f"/api/v1/marketplace/install/success?installSessionId={install_session_id}"
        )
        self.assertEqual(200, success.status_code)
        success_payload = success.json()
        self.assertEqual("ok", success_payload["status"])
        self.assertEqual("9999999", success_payload["portalId"])
        self.assertEqual("success", success_payload["bootstrapStatus"])
        self.assertIn("/opslens/install/complete/?portalId=9999999", success_payload["returnUrl"])
        self.assertTrue(success_payload["active"])

        overview = self.client.get("/api/v1/dashboard/overview?portalId=9999999")
        self.assertEqual(200, overview.status_code)
        self.assertEqual("ok", overview.json()["status"])

        settings = self.client.get("/api/v1/settings-store?portalId=9999999")
        self.assertEqual(200, settings.status_code)
        self.assertEqual("ok", settings.json()["status"])

    def test_failed_bootstrap_redirects_to_error_safe_destination(self) -> None:
        session = self._session()
        try:
            create_marketplace_install_session(
                session,
                install_session_id="failed-bootstrap-session",
                plan="business",
                billing_interval="yearly",
                return_url="https://apps.app-sync.com/install/complete",
                tenant_context={"tenantSlug": "failed-bootstrap"},
                partner_user_email="owner@example.com",
                trial_approved=True,
            )
        finally:
            session.close()

        with (
            patch(
                "app.routes.oauth.parse_signed_state",
                return_value={
                    "installSessionId": "failed-bootstrap-session",
                    "returnTo": "https://apps.app-sync.com/install/complete",
                },
            ),
            patch(
                "app.routes.oauth.exchange_code_for_tokens",
                return_value={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
            patch(
                "app.routes.oauth.introspect_access_token",
                return_value={
                    "hub_id": "7777777",
                    "hub_domain": "portal-fallback.test",
                    "user": "owner@example.com",
                    "user_id": "user-789",
                    "app_id": "app-123",
                    "scopes": ["oauth", "tickets"],
                },
            ),
            patch(
                "app.services.portal_entitlements.ensure_portal_bootstrap",
                side_effect=RuntimeError("bootstrap exploded"),
            ),
        ):
            callback = self.client.get(
                "/oauth-callback?code=auth-code&state=signed-state",
                follow_redirects=False,
            )

        self.assertEqual(302, callback.status_code)
        location = callback.headers["location"]
        self.assertTrue(location.startswith("https://apps.app-sync.com/opslens/install/complete/?"))
        self.assertIn("portalId=7777777", location)
        self.assertIn("plan=business", location)
        self.assertIn("billingInterval=yearly", location)
        self.assertIn("bootstrapStatus=failed", location)
        self.assertIn("status=error", location)

        success = self.client.get(
            "/api/v1/marketplace/install/success?installSessionId=failed-bootstrap-session"
        )
        self.assertEqual(200, success.status_code)
        success_payload = success.json()
        self.assertEqual("failed", success_payload["bootstrapStatus"])
        self.assertIn("/opslens/install/complete/?portalId=7777777", success_payload["returnUrl"])
        self.assertIn("status=error", success_payload["returnUrl"])

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
        self.assertIn("/opslens/install/complete/?portalId=8886743", payload["returnUrl"])
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
