from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app import db as db_module
from app.models.alert import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    STATUS_ACKNOWLEDGED,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Alert,
)
from app.services.portal_health import compute_portal_health

NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)


class PortalHealthTests(unittest.TestCase):
    PORTAL_ID = "51300126"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'health.sqlite')}"
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

    def _add(self, session, *, severity, status=STATUS_OPEN, created_at=None, resolved_at=None, n=1):
        for i in range(n):
            session.add(
                Alert(
                    portal_id=self.PORTAL_ID,
                    alert_signature=f"sig-{severity}-{status}-{i}-{(created_at or NOW).isoformat()}",
                    severity=severity,
                    status=status,
                    source_event_type="workflow_disabled",
                    source_event_kind="x",
                    title="Issue",
                    summary="{}",
                    created_at=created_at or NOW,
                    resolved_at=resolved_at,
                )
            )
        session.commit()

    def test_clean_portal_is_100_healthy(self) -> None:
        session = self._session()
        try:
            health = compute_portal_health(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()
        self.assertEqual(100, health["score"])
        self.assertEqual("healthy", health["grade"])
        self.assertEqual(0, health["activeTotal"])

    def test_one_open_critical_is_watch(self) -> None:
        session = self._session()
        try:
            self._add(session, severity=SEVERITY_CRITICAL)
            health = compute_portal_health(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()
        self.assertEqual(70, health["score"])  # 100 - 30
        self.assertEqual("watch", health["grade"])
        self.assertEqual(1, health["openCritical"])

    def test_two_open_criticals_is_at_risk(self) -> None:
        session = self._session()
        try:
            self._add(session, severity=SEVERITY_CRITICAL, n=2)
            health = compute_portal_health(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()
        self.assertEqual(40, health["score"])  # 100 - 60
        self.assertEqual("at_risk", health["grade"])

    def test_acknowledged_counts_at_reduced_weight(self) -> None:
        session = self._session()
        try:
            self._add(session, severity=SEVERITY_CRITICAL, status=STATUS_ACKNOWLEDGED)
            health = compute_portal_health(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()
        # 100 - 30*0.4 = 88 (vs 70 if it were open) — acknowledging lifts the score.
        self.assertEqual(88, health["score"])
        self.assertEqual(0, health["openCritical"])
        self.assertEqual(1, health["acknowledged"])

    def test_resolved_alerts_do_not_count(self) -> None:
        session = self._session()
        try:
            self._add(
                session,
                severity=SEVERITY_CRITICAL,
                status=STATUS_RESOLVED,
                resolved_at=NOW - timedelta(days=1),
            )
            health = compute_portal_health(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()
        self.assertEqual(100, health["score"])
        self.assertEqual(1, health["resolvedThisWeek"])

    def test_grade_thresholds_and_trend(self) -> None:
        session = self._session()
        try:
            # One high (=-14 -> 86 watch), plus a medium created this week.
            self._add(session, severity=SEVERITY_HIGH)
            self._add(session, severity=SEVERITY_MEDIUM, created_at=NOW - timedelta(days=2))
            health = compute_portal_health(session, self.PORTAL_ID, now=NOW)
        finally:
            session.close()
        self.assertEqual(81, health["score"])  # 100 - 14 - 5
        self.assertEqual("watch", health["grade"])
        self.assertEqual(2, health["newThisWeek"])
        self.assertEqual(1, health["openHigh"])

    def test_unknown_on_blank_portal(self) -> None:
        session = self._session()
        try:
            health = compute_portal_health(session, "", now=NOW)
        finally:
            session.close()
        self.assertIsNone(health["score"])
        self.assertEqual("unknown", health["grade"])


if __name__ == "__main__":
    unittest.main()
