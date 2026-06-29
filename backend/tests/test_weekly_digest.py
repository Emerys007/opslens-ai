from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import db as db_module
from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Alert,
)
from app.models.portal_setting import PortalSetting
from app.services import weekly_digest

_POST = "app.services.weekly_digest._post_to_slack"
NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)


class _DigestBase(unittest.TestCase):
    PORTAL_ID = "51300126"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'digest.sqlite')}"
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
        self._tempdir.cleanup()

    def _session(self):
        s = db_module.get_session()
        self.assertIsNotNone(s)
        return s

    def _add_alert(
        self,
        session,
        *,
        severity=SEVERITY_MEDIUM,
        status=STATUS_OPEN,
        event_type="property_archived",
        title="Property archived",
        created_at=None,
        repeat_count=1,
        resolved_at=None,
        portal_id=None,
    ) -> None:
        session.add(
            Alert(
                portal_id=portal_id or self.PORTAL_ID,
                alert_signature=f"sig-{title}-{(created_at or NOW).isoformat()}-{repeat_count}",
                severity=severity,
                status=status,
                source_event_type=event_type,
                source_event_kind="x",
                title=title,
                summary="{}",
                created_at=created_at or NOW,
                repeat_count=repeat_count,
                resolved_at=resolved_at,
            )
        )
        session.commit()

    def _add_settings(self, session, **kwargs) -> None:
        defaults = dict(
            portal_id=self.PORTAL_ID,
            slack_webhook_url="https://hooks.slack.com/services/T/B/X",
            slack_delivery_enabled=True,
            digest_enabled=True,
        )
        defaults.update(kwargs)
        session.add(PortalSetting(**defaults))
        session.commit()


class BuildDigestTests(_DigestBase):
    def test_aggregates_by_severity_category_and_window(self) -> None:
        session = self._session()
        try:
            # In window.
            self._add_alert(
                session,
                severity=SEVERITY_HIGH,
                event_type="property_archived",
                title="Property X archived",
                created_at=NOW - timedelta(days=1),
            )
            self._add_alert(
                session,
                severity=SEVERITY_MEDIUM,
                event_type="workflow_disabled",
                title="Workflow Y disabled",
                created_at=NOW - timedelta(days=2),
                repeat_count=4,
            )
            # Out of window (10 days old) — must NOT count toward new_total.
            self._add_alert(
                session,
                severity=SEVERITY_LOW,
                event_type="list_archived",
                title="Old segment",
                created_at=NOW - timedelta(days=10),
            )
            # Created long ago but RESOLVED in window — counts as resolved only.
            self._add_alert(
                session,
                severity=SEVERITY_HIGH,
                status=STATUS_RESOLVED,
                event_type="template_edited",
                title="Template fixed",
                created_at=NOW - timedelta(days=20),
                resolved_at=NOW - timedelta(days=3),
            )

            digest = weekly_digest.build_portal_digest(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()

        self.assertEqual(2, digest["new_total"])
        self.assertEqual(1, digest["by_severity"][SEVERITY_HIGH])
        self.assertEqual(1, digest["by_severity"][SEVERITY_MEDIUM])
        self.assertEqual(0, digest["by_severity"][SEVERITY_LOW])
        self.assertEqual(1, digest["by_category"]["Properties"])
        self.assertEqual(1, digest["by_category"]["Workflows"])
        self.assertNotIn("Segments", digest["by_category"])  # the list event is out of window
        self.assertEqual(1, digest["resolved"])
        # 3 of the 4 alerts are still active (only the template one is resolved).
        self.assertEqual(3, digest["open"])
        self.assertFalse(digest["quiet"])
        # High severity sorts above medium in top issues.
        self.assertEqual(SEVERITY_HIGH, digest["top_issues"][0]["severity"])

    def test_quiet_week(self) -> None:
        session = self._session()
        try:
            self._add_alert(
                session,
                created_at=NOW - timedelta(days=30),  # outside window
            )
            digest = weekly_digest.build_portal_digest(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()

        self.assertEqual(0, digest["new_total"])
        self.assertTrue(digest["quiet"])

    def test_payload_quiet_and_active_shapes(self) -> None:
        quiet = {
            "portal_id": self.PORTAL_ID,
            "window_days": 7,
            "since": NOW - timedelta(days=7),
            "until": NOW,
            "new_total": 0,
            "by_severity": {},
            "by_category": {},
            "resolved": 0,
            "open": 0,
            "top_issues": [],
            "quiet": True,
        }
        payload = weekly_digest.build_digest_payload(quiet, brand_name="Acme Ops")
        text = json.dumps(payload)
        self.assertIn("All clear", text)
        self.assertIn("Acme Ops", text)  # brand in header + context
        self.assertEqual("header", payload["blocks"][0]["type"])

        active = dict(quiet)
        active.update(
            new_total=3,
            by_severity={SEVERITY_HIGH: 2, SEVERITY_MEDIUM: 1},
            by_category={"Workflows": 2, "Properties": 1},
            resolved=1,
            open=2,
            top_issues=[
                {"title": "WF disabled", "severity": SEVERITY_HIGH, "category": "Workflows", "repeat_count": 3},
            ],
            quiet=False,
        )
        payload = weekly_digest.build_digest_payload(active, brand_name="OpsLens")
        text = json.dumps(payload)
        self.assertIn("caught", text)
        self.assertIn("WF disabled", text)
        self.assertIn("Top issues", text)


class SendPortalDigestTests(_DigestBase):
    def test_force_preview_sends_without_stamping(self) -> None:
        session = self._session()
        try:
            self._add_settings(session, digest_enabled=False)  # disabled, but force overrides
            with patch(_POST, return_value=(True, 200, "ok")) as posted:
                ok, msg = weekly_digest.send_portal_digest(
                    session, self.PORTAL_ID, now=NOW, force=True
                )
            self.assertTrue(ok)
            posted.assert_called_once()
            row = session.get(PortalSetting, self.PORTAL_ID)
            # Preview must not advance the weekly cadence.
            self.assertIsNone(row.last_digest_sent_at)
        finally:
            session.close()

    def test_requires_webhook(self) -> None:
        session = self._session()
        try:
            self._add_settings(session, slack_webhook_url="")
            ok, msg = weekly_digest.send_portal_digest(
                session, self.PORTAL_ID, now=NOW, force=True
            )
            self.assertFalse(ok)
            self.assertIn("Slack", msg)
        finally:
            session.close()

    def test_non_force_respects_disabled(self) -> None:
        session = self._session()
        try:
            self._add_settings(session, digest_enabled=False)
            with patch(_POST, return_value=(True, 200, "ok")) as posted:
                ok, msg = weekly_digest.send_portal_digest(session, self.PORTAL_ID, now=NOW)
            self.assertFalse(ok)
            posted.assert_not_called()
        finally:
            session.close()


class SendDueDigestsTests(_DigestBase):
    def test_seeds_on_first_sight_without_sending(self) -> None:
        session = self._session()
        try:
            self._add_settings(session)  # last_digest_sent_at is None
            with patch(_POST, return_value=(True, 200, "ok")) as posted:
                summary = weekly_digest.send_due_digests(session, now=NOW)
            posted.assert_not_called()
            self.assertEqual(1, summary["seeded"])
            self.assertEqual(0, summary["sent"])
            row = session.get(PortalSetting, self.PORTAL_ID)
            self.assertEqual(NOW, row.last_digest_sent_at.replace(tzinfo=timezone.utc))
        finally:
            session.close()

    def test_sends_when_due_and_stamps(self) -> None:
        session = self._session()
        try:
            self._add_settings(session, last_digest_sent_at=NOW - timedelta(days=8))
            self._add_alert(session, created_at=NOW - timedelta(days=1))
            with patch(_POST, return_value=(True, 200, "ok")) as posted:
                summary = weekly_digest.send_due_digests(session, now=NOW)
            posted.assert_called_once()
            self.assertEqual(1, summary["sent"])
            row = session.get(PortalSetting, self.PORTAL_ID)
            self.assertEqual(NOW, row.last_digest_sent_at.replace(tzinfo=timezone.utc))
        finally:
            session.close()

    def test_skips_when_not_due(self) -> None:
        session = self._session()
        try:
            self._add_settings(session, last_digest_sent_at=NOW - timedelta(days=2))
            with patch(_POST, return_value=(True, 200, "ok")) as posted:
                summary = weekly_digest.send_due_digests(session, now=NOW)
            posted.assert_not_called()
            self.assertEqual(1, summary["skipped"])
            self.assertEqual(0, summary["sent"])
        finally:
            session.close()

    def test_failed_send_still_advances_cadence(self) -> None:
        session = self._session()
        try:
            self._add_settings(session, last_digest_sent_at=NOW - timedelta(days=9))
            with patch(_POST, return_value=(False, 500, "boom")):
                summary = weekly_digest.send_due_digests(session, now=NOW)
            self.assertEqual(1, summary["failed"])
            row = session.get(PortalSetting, self.PORTAL_ID)
            # Stamped on attempt so a broken webhook isn't retried every cycle.
            self.assertEqual(NOW, row.last_digest_sent_at.replace(tzinfo=timezone.utc))
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
