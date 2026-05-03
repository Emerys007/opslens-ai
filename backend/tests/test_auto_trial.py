"""Tests for the v2 14-day auto-trial flow on fresh OAuth installs.

These tests cover four scenarios:

1. A fresh portal completing OAuth gets a 14-day trial, no Stripe checkout
   is created, and the install-complete redirect carries ``trial=1`` and
   ``trial_expires_at=<ISO>`` query params.
2. Re-installing into a portal that already used its trial does NOT grant a
   second trial; the OAuth callback falls into the existing
   ``payment_required`` branch.
3. ``subscription_is_active`` returns False once a trial has expired, even
   when ``trial_approved`` is still True on the row.
4. The pre-existing Stripe-checkout install path is still reachable when the
   client explicitly opts out of the auto-trial via ``trialApproved: False``.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app
from app.models.portal_entitlement import PortalEntitlement
from app.services.marketplace_billing import subscription_is_active, trial_is_active
from app.services.portal_entitlements import (
    AUTO_TRIAL_DURATION,
    create_marketplace_install_session,
    get_marketplace_install_session,
    grant_auto_trial_for_install_session,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutoTrialFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'auto-trial-test.sqlite')}"
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
        self._tempdir.cleanup()

    def _session(self):
        session = db_module.get_session()
        self.assertIsNotNone(session)
        return session

    # ------------------------------------------------------------------
    # 1. Fresh install grants a 14-day trial, no Stripe.
    # ------------------------------------------------------------------
    def test_fresh_install_grants_14_day_trial_without_stripe(self) -> None:
        with (
            patch(
                "app.api.v1.routes.marketplace.settings.backend_public_base_url",
                "https://api.app-sync.com",
            ),
            patch(
                "app.api.v1.routes.marketplace.settings.app_public_base_url",
                "https://app-sync.com",
            ),
            patch("app.api.v1.routes.marketplace.create_customer") as create_customer,
            patch(
                "app.api.v1.routes.marketplace.create_checkout_session"
            ) as create_checkout,
        ):
            start = self.client.post(
                "/api/v1/marketplace/install/start",
                json={
                    "plan": "professional",
                    "billingInterval": "monthly",
                    "returnUrl": "https://app-sync.com/install/complete",
                    "tenantContext": {"tenantSlug": "fresh-trial-co"},
                    "partnerUserId": "user-fresh",
                    "partnerUserEmail": "owner@example.com",
                    # No trialApproved — must default to True (auto-trial).
                },
            )

        self.assertEqual(200, start.status_code)
        start_payload = start.json()
        install_session_id = start_payload["installSessionId"]
        self.assertEqual("ok", start_payload["status"])
        self.assertTrue(start_payload["trialApproved"])
        self.assertFalse(start_payload["paymentRequired"])
        self.assertEqual("", start_payload["checkoutUrl"])
        # Stripe must not be touched on auto-trial installs.
        create_customer.assert_not_called()
        create_checkout.assert_not_called()

        # Drive the OAuth callback to completion and observe the redirect.
        with (
            patch(
                "app.routes.oauth.parse_signed_state",
                return_value={
                    "installSessionId": install_session_id,
                    "returnTo": "https://app-sync.com/install/complete",
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
                    "hub_id": "1111111",
                    "hub_domain": "portal-fresh.test",
                    "user": "owner@example.com",
                    "user_id": "user-fresh",
                    "app_id": "app-123",
                    "scopes": ["oauth", "tickets"],
                },
            ),
            patch(
                "app.services.portal_entitlements.ensure_portal_bootstrap",
                return_value={
                    "portalId": "1111111",
                    "pipelineId": "p-1",
                    "contactPropertyGroupCreated": True,
                    "ticketPropertyGroupCreated": True,
                    "contactPropertiesCreated": [],
                    "ticketPropertiesCreated": [],
                    "pipelineCreated": True,
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
        self.assertTrue(
            location.startswith("https://app-sync.com/opslens/install/complete/?")
        )
        self.assertIn("portalId=1111111", location)
        self.assertIn("bootstrapStatus=success", location)
        self.assertIn("trial=1", location)
        # ISO 8601 UTC ``Z`` timestamp must be present.
        self.assertIn("trial_expires_at=", location)
        self.assertIn("Z", location.split("trial_expires_at=", 1)[1])

        # Inspect the persisted entitlement: trial windows must be set on it.
        session = self._session()
        try:
            entitlement = session.get(PortalEntitlement, "1111111")
            self.assertIsNotNone(entitlement)
            self.assertTrue(entitlement.trial_approved)
            self.assertIsNotNone(entitlement.trial_started_at)
            self.assertIsNotNone(entitlement.trial_expires_at)
            delta = entitlement.trial_expires_at - entitlement.trial_started_at
            self.assertEqual(AUTO_TRIAL_DURATION, delta)
        finally:
            session.close()

        # Success endpoint exposes the trial expiry timestamp.
        success = self.client.get(
            f"/api/v1/marketplace/install/success?installSessionId={install_session_id}"
        )
        self.assertEqual(200, success.status_code)
        success_payload = success.json()
        self.assertTrue(success_payload["trialApproved"])
        self.assertTrue(success_payload["active"])
        self.assertTrue(str(success_payload["trialExpiresAt"]).endswith("Z"))
        self.assertIn("trial=1", success_payload["returnUrl"])

    # ------------------------------------------------------------------
    # 2. Re-install: portal that already used a trial does not get another.
    # ------------------------------------------------------------------
    def test_reinstall_does_not_grant_a_second_trial(self) -> None:
        portal_id = "2222222"

        # Pre-seed an entitlement that already burned its trial 30 days ago.
        seeded_started = _utc_now() - timedelta(days=30)
        seeded_expired = _utc_now() - timedelta(days=16)
        session = self._session()
        try:
            session.add(
                PortalEntitlement(
                    portal_id=portal_id,
                    plan="professional",
                    billing_interval="monthly",
                    subscription_status="canceled",
                    trial_approved=True,
                    trial_started_at=seeded_started,
                    trial_expires_at=seeded_expired,
                )
            )
            session.commit()
        finally:
            session.close()

        # The user starts a fresh install (the install_start path doesn't
        # know the portal_id yet, so it stages an auto-trial that the OAuth
        # callback must revoke).
        with (
            patch(
                "app.api.v1.routes.marketplace.settings.backend_public_base_url",
                "https://api.app-sync.com",
            ),
            patch(
                "app.api.v1.routes.marketplace.settings.app_public_base_url",
                "https://app-sync.com",
            ),
            patch("app.api.v1.routes.marketplace.create_customer") as create_customer,
            patch(
                "app.api.v1.routes.marketplace.create_checkout_session"
            ) as create_checkout,
        ):
            start = self.client.post(
                "/api/v1/marketplace/install/start",
                json={
                    "plan": "professional",
                    "billingInterval": "monthly",
                    "returnUrl": "https://app-sync.com/install/complete",
                    "tenantContext": {"tenantSlug": "reinstall-co"},
                    "partnerUserId": "user-reinstall",
                    "partnerUserEmail": "owner@example.com",
                },
            )

        self.assertEqual(200, start.status_code)
        install_session_id = start.json()["installSessionId"]
        create_customer.assert_not_called()
        create_checkout.assert_not_called()

        with (
            patch(
                "app.routes.oauth.parse_signed_state",
                return_value={
                    "installSessionId": install_session_id,
                    "returnTo": "https://app-sync.com/install/complete",
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
                    "hub_id": portal_id,
                    "hub_domain": "portal-reinstall.test",
                    "user": "owner@example.com",
                    "user_id": "user-reinstall",
                    "app_id": "app-123",
                    "scopes": ["oauth", "tickets"],
                },
            ),
        ):
            callback = self.client.get(
                "/oauth-callback?code=auth-code&state=signed-state",
                follow_redirects=False,
            )

        self.assertEqual(302, callback.status_code)
        location = callback.headers["location"]
        # Re-install must NOT advertise a fresh trial in the redirect.
        self.assertNotIn("trial=1", location)
        # Bootstrap should have short-circuited to payment_required.
        self.assertIn("bootstrapStatus=payment_required", location)

        # The portal entitlement must still carry the original trial windows;
        # the auto-trial code must not have overwritten them.
        #
        # NOTE: SQLite (used in these tests) does not preserve timezone info
        # on write — datetimes round-trip back as naive values. Postgres in
        # production preserves the offset correctly. To keep the assertion
        # backend-agnostic we treat any naive datetime read from the DB as
        # UTC (attaching tzinfo without converting), and compare using a
        # 1-second tolerance which is plenty given that the seeded values
        # are 30 / 16 days from "now" and we only care that they were not
        # overwritten by the OAuth-callback's auto-trial path.
        def _as_utc(value):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        session = self._session()
        try:
            entitlement = session.get(PortalEntitlement, portal_id)
            self.assertIsNotNone(entitlement)
            tolerance = timedelta(seconds=1)
            self.assertLessEqual(
                abs(_as_utc(entitlement.trial_started_at) - seeded_started),
                tolerance,
            )
            self.assertLessEqual(
                abs(_as_utc(entitlement.trial_expires_at) - seeded_expired),
                tolerance,
            )
            self.assertFalse(
                subscription_is_active(
                    entitlement.subscription_status,
                    trial_approved=entitlement.trial_approved,
                    trial_expires_at=entitlement.trial_expires_at,
                )
            )

            # The install-session-level grant helper must also refuse, even
            # if called directly (defensive — service-layer guarantee).
            install_session = get_marketplace_install_session(
                session, install_session_id
            )
            install_session, granted = grant_auto_trial_for_install_session(
                session,
                install_session,
                portal_id=portal_id,
            )
            self.assertFalse(granted)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 3. subscription_is_active honors trial expiry.
    # ------------------------------------------------------------------
    def test_subscription_is_active_returns_false_after_trial_expiry(self) -> None:
        now = _utc_now()
        future = now + timedelta(days=1)
        past = now - timedelta(seconds=1)

        # No subscription_status, but a non-expired trial → active.
        self.assertTrue(
            subscription_is_active(
                "pending",
                trial_approved=True,
                trial_expires_at=future,
            )
        )
        # Trial expired in the past with no paid subscription → inactive.
        self.assertFalse(
            subscription_is_active(
                "pending",
                trial_approved=True,
                trial_expires_at=past,
            )
        )
        # An active paid subscription survives an expired trial.
        self.assertTrue(
            subscription_is_active(
                "active",
                trial_approved=True,
                trial_expires_at=past,
            )
        )
        # trial_is_active works on naive datetimes too — they're treated as UTC.
        naive_past = past.replace(tzinfo=None)
        self.assertFalse(trial_is_active(True, naive_past))
        # A trial without an expiry (legacy row) is still treated as active
        # when trial_approved is True. This is the back-compat invariant.
        self.assertTrue(trial_is_active(True, None))

    # ------------------------------------------------------------------
    # 4. Existing Stripe path is still reachable on opt-out.
    # ------------------------------------------------------------------
    def test_legacy_paid_path_is_reachable_when_trial_disabled(self) -> None:
        with (
            patch(
                "app.services.marketplace_billing.settings.stripe_price_professional_monthly",
                "price_prof_month",
            ),
            patch(
                "app.api.v1.routes.marketplace.settings.backend_public_base_url",
                "https://api.app-sync.com",
            ),
            patch(
                "app.api.v1.routes.marketplace.settings.app_public_base_url",
                "https://app-sync.com",
            ),
            patch(
                "app.api.v1.routes.marketplace.create_customer",
                return_value={"id": "cus_legacy"},
            ) as create_customer,
            patch(
                "app.api.v1.routes.marketplace.create_checkout_session",
                return_value={
                    "id": "cs_legacy",
                    "url": "https://checkout.stripe.test/session",
                },
            ) as create_checkout,
        ):
            response = self.client.post(
                "/api/v1/marketplace/install/start",
                json={
                    "plan": "professional",
                    "billingInterval": "monthly",
                    "returnUrl": "https://app-sync.com/install/complete",
                    "tenantContext": {"tenantSlug": "legacy-paid"},
                    "partnerUserId": "user-legacy",
                    "partnerUserEmail": "owner@example.com",
                    "trialApproved": False,
                },
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["paymentRequired"])
        self.assertFalse(payload["trialApproved"])
        self.assertEqual(
            "https://checkout.stripe.test/session", payload["checkoutUrl"]
        )
        create_customer.assert_called_once()
        create_checkout.assert_called_once()


if __name__ == "__main__":
    unittest.main()
