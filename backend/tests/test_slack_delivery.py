"""Tests for `app.services.slack_delivery`.

Covers:

1. Pending alert with valid webhook → POST sent, ``slack_delivered_at`` stamped, returns True.
2. No webhook configured → returns False, no stamp.
3. Slack returns 4xx → returns False, no stamp.
4. Slack returns 200 → stamp set, returns True.
5. Severity below threshold → skipped, counted in ``skipped_below_threshold``.
6. Already-delivered alert → skipped silently.
7. ``deliver_pending_alerts`` processes multiple alerts in one call.
8. Slack delivery disabled at portal level → entire portal's alerts skipped.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch

from app import db as db_module
from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_KIND_PROPERTY,
    STATUS_OPEN,
    Alert,
)
from app.models.portal_setting import PortalSetting
from app.services import slack_delivery


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _FakeResponse:
    def __init__(self, *, status: int = 200, body: bytes = b"ok"):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _BaseSlackCase(unittest.TestCase):
    PORTAL_ID = "12345"
    WEBHOOK_URL = "https://hooks.slack.test/services/T1/B2/abcdef"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'slack-delivery-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

    def tearDown(self) -> None:
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

    def _seed_settings(
        self,
        session,
        *,
        webhook_url: str | None = None,
        threshold: str = "medium",
        slack_enabled: bool = True,
        ticket_enabled: bool = True,
    ) -> None:
        url = self.WEBHOOK_URL if webhook_url is None else webhook_url
        session.add(
            PortalSetting(
                portal_id=self.PORTAL_ID,
                slack_webhook_url=url,
                alert_threshold=threshold,
                slack_delivery_enabled=slack_enabled,
                ticket_delivery_enabled=ticket_enabled,
            )
        )
        session.commit()

    def _seed_alert(
        self,
        session,
        *,
        severity: str = SEVERITY_HIGH,
        title: str = "Property 'lifecyclestage' archived — 1 workflow(s) affected",
        slack_delivered_at: datetime | None = None,
        repeat_count: int = 1,
        impacted_workflow_id: str | None = "67890",
    ) -> Alert:
        alert = Alert(
            portal_id=self.PORTAL_ID,
            alert_signature=f"sig-{title}-{severity}",
            severity=severity,
            status=STATUS_OPEN,
            source_event_type=SOURCE_EVENT_PROPERTY_ARCHIVED,
            source_event_kind=SOURCE_KIND_PROPERTY,
            source_dependency_type="property",
            source_dependency_id="lifecyclestage",
            source_object_type_id="0-1",
            impacted_workflow_id=impacted_workflow_id,
            impacted_workflow_name="Lead Nurture",
            title=title,
            summary=json.dumps(
                {
                    "kind": "property_archived",
                    "change": {
                        "property_label": "Lifecycle Stage",
                        "property_name": "lifecyclestage",
                        "previous_archived": False,
                        "new_archived": True,
                    },
                    "impact": {
                        "workflow_id": impacted_workflow_id,
                        "workflow_name": "Lead Nurture",
                        "dependency_locations": ["actions[3].fields.property_name"],
                    },
                }
            ),
            slack_delivered_at=slack_delivered_at,
            repeat_count=repeat_count,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert


# ---------------------------------------------------------------------------
# deliver_alert_to_slack
# ---------------------------------------------------------------------------


class DeliverAlertToSlackTests(_BaseSlackCase):
    def test_happy_path_posts_payload_and_stamps_delivered_at(self) -> None:
        captured: dict = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = request.data.decode("utf-8")
            return _FakeResponse(status=200, body=b"ok")

        session = self._session()
        try:
            self._seed_settings(session)
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok = slack_delivery.deliver_alert_to_slack(session, alert)
            session.commit()
            session.refresh(alert)
        finally:
            session.close()

        self.assertTrue(ok)
        self.assertEqual(self.WEBHOOK_URL, captured["url"])
        payload = json.loads(captured["body"])
        self.assertIn("blocks", payload)
        self.assertEqual(3, len(payload["blocks"]))
        # Header carries the severity emoji.
        header_text = payload["blocks"][0]["text"]["text"]
        self.assertIn("🔴", header_text)
        # Section body references the workflow link.
        section_text = payload["blocks"][1]["text"]["text"]
        self.assertIn("https://app.hubspot.com/workflows/", section_text)
        self.assertIsNotNone(alert.slack_delivered_at)

    def test_no_webhook_configured_returns_false(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session, webhook_url="")
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen") as mock_urlopen:
                ok = slack_delivery.deliver_alert_to_slack(session, alert)

            self.assertFalse(ok)
            mock_urlopen.assert_not_called()
            self.assertIsNone(alert.slack_delivered_at)
        finally:
            session.close()

    def test_4xx_response_returns_false_and_does_not_stamp(self) -> None:
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                url=request.full_url, code=403, msg="Forbidden",
                hdrs=None, fp=io.BytesIO(b'{"error":"invalid_token"}'),
            )

        session = self._session()
        try:
            self._seed_settings(session)
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok = slack_delivery.deliver_alert_to_slack(session, alert)

            self.assertFalse(ok)
            self.assertIsNone(alert.slack_delivered_at)
        finally:
            session.close()

    def test_200_response_stamps_delivered_at(self) -> None:
        # Re-asserts the happy path's invariant in isolation so a
        # regression is easy to localise.
        def fake_urlopen(request, timeout):
            return _FakeResponse(status=200, body=b"ok")

        session = self._session()
        try:
            self._seed_settings(session)
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok = slack_delivery.deliver_alert_to_slack(session, alert)
            session.commit()
            session.refresh(alert)

            self.assertTrue(ok)
            self.assertIsNotNone(alert.slack_delivered_at)
        finally:
            session.close()


# ---------------------------------------------------------------------------
# deliver_pending_alerts (batch)
# ---------------------------------------------------------------------------


class DeliverPendingAlertsTests(_BaseSlackCase):
    def test_below_threshold_alerts_are_skipped(self) -> None:
        session = self._session()
        try:
            # Threshold set to high → only HIGH alerts should deliver.
            self._seed_settings(session, threshold=SEVERITY_HIGH)
            self._seed_alert(session, severity=SEVERITY_LOW, title="Low alert")
            self._seed_alert(session, severity=SEVERITY_MEDIUM, title="Medium alert")
            self._seed_alert(session, severity=SEVERITY_HIGH, title="High alert")

            posted_count = {"n": 0}

            def fake_urlopen(request, timeout):
                posted_count["n"] += 1
                return _FakeResponse(status=200, body=b"ok")

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                summary = slack_delivery.deliver_pending_alerts(session)
        finally:
            session.close()

        self.assertEqual(1, posted_count["n"])
        self.assertEqual(2, summary["skipped_below_threshold"])
        self.assertEqual(1, summary["succeeded"])
        self.assertEqual(0, summary["failed"])

    def test_already_delivered_alerts_are_skipped(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session)
            already = self._seed_alert(
                session, severity=SEVERITY_HIGH, title="Already done",
                slack_delivered_at=_utc_now(),
            )
            fresh = self._seed_alert(
                session, severity=SEVERITY_HIGH, title="Brand new",
            )
            _ = (already, fresh)

            with patch("urllib.request.urlopen", return_value=_FakeResponse()):
                summary = slack_delivery.deliver_pending_alerts(session)
        finally:
            session.close()

        # Only the fresh alert was attempted.
        self.assertEqual(1, summary["attempted"])
        self.assertEqual(1, summary["succeeded"])

    def test_processes_multiple_pending_alerts(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session)
            for i in range(3):
                self._seed_alert(
                    session, severity=SEVERITY_HIGH, title=f"Alert {i}",
                )

            with patch("urllib.request.urlopen", return_value=_FakeResponse()):
                summary = slack_delivery.deliver_pending_alerts(session)
        finally:
            session.close()

        self.assertEqual(3, summary["attempted"])
        self.assertEqual(3, summary["succeeded"])
        self.assertEqual(0, summary["failed"])

    def test_portal_level_disable_skips_entire_portal(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session, slack_enabled=False)
            self._seed_alert(session, severity=SEVERITY_HIGH, title="Suppressed")

            with patch("urllib.request.urlopen") as mock_urlopen:
                summary = slack_delivery.deliver_pending_alerts(session)
                mock_urlopen.assert_not_called()
        finally:
            session.close()

        self.assertEqual(0, summary["attempted"])
        self.assertGreaterEqual(summary["skipped_disabled_or_unconfigured"], 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
