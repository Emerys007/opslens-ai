from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app
from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_KIND_PROPERTY,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Alert,
)
from app.models.portal_setting import PortalSetting


SEVERITY_CRITICAL = "critical"


class DashboardEndpointTests(unittest.TestCase):
    PORTAL_ID = "51300126"
    OTHER_PORTAL_ID = "99999999"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'dashboard-test.sqlite')}"
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

    def _seed_alert(
        self,
        session,
        *,
        portal_id: str | None = None,
        severity: str = SEVERITY_HIGH,
        status: str = STATUS_OPEN,
        title: str = "Property archived",
        plain_english_explanation: str | None = None,
        created_at: datetime | None = None,
        resolved_at: datetime | None = None,
    ) -> Alert:
        alert = Alert(
            portal_id=portal_id or self.PORTAL_ID,
            alert_signature=f"sig-{portal_id or self.PORTAL_ID}-{title}-{severity}",
            severity=severity,
            status=status,
            source_event_type=SOURCE_EVENT_PROPERTY_ARCHIVED,
            source_event_kind=SOURCE_KIND_PROPERTY,
            source_dependency_type="property",
            source_dependency_id="lead_source",
            source_object_type_id="0-1",
            impacted_workflow_id="1801077332",
            impacted_workflow_name="Lead Nurture",
            title=title,
            summary="{}",
            plain_english_explanation=plain_english_explanation,
            created_at=created_at or datetime.now(timezone.utc),
            resolved_at=resolved_at,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert

    def test_overview_returns_action_required_open_critical_and_high_newest_first_capped(
        self,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        session = self._session()
        try:
            seeded_ids = []
            for index in range(6):
                alert = self._seed_alert(
                    session,
                    severity=SEVERITY_CRITICAL if index % 2 else SEVERITY_HIGH,
                    title=f"Action {index}",
                    plain_english_explanation=(
                        "Newest plain-English explanation" if index == 5 else None
                    ),
                    created_at=base + timedelta(minutes=index),
                )
                seeded_ids.append(str(alert.id))
            self._seed_alert(
                session,
                severity=SEVERITY_MEDIUM,
                title="Watching only",
                created_at=base + timedelta(minutes=10),
            )
            self._seed_alert(
                session,
                severity=SEVERITY_HIGH,
                status=STATUS_RESOLVED,
                title="Resolved high",
                created_at=base + timedelta(minutes=11),
                resolved_at=base + timedelta(minutes=12),
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/overview?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(200, response.status_code)
        summary = response.json()["summary"]

        self.assertEqual(6, summary["actionRequiredCount"])
        self.assertEqual(5, len(summary["actionRequired"]))
        self.assertEqual(
            list(reversed(seeded_ids[1:])),
            [row["id"] for row in summary["actionRequired"]],
        )
        self.assertEqual(
            "Newest plain-English explanation",
            summary["actionRequired"][0]["title"],
        )
        self.assertEqual(
            {SEVERITY_CRITICAL, SEVERITY_HIGH},
            {row["severity"] for row in summary["actionRequired"]},
        )

    def test_overview_returns_watching_medium_open_alerts_newest_first_capped(
        self,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        session = self._session()
        try:
            seeded_ids = []
            for index in range(6):
                alert = self._seed_alert(
                    session,
                    severity=SEVERITY_MEDIUM,
                    title=f"Watching {index}",
                    created_at=base + timedelta(minutes=index),
                )
                seeded_ids.append(str(alert.id))
            self._seed_alert(
                session,
                severity=SEVERITY_HIGH,
                title="Action required",
                created_at=base + timedelta(minutes=10),
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/overview?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(200, response.status_code)
        summary = response.json()["summary"]

        self.assertEqual(6, summary["watchingCount"])
        self.assertEqual(5, len(summary["watching"]))
        self.assertEqual(
            list(reversed(seeded_ids[1:])),
            [row["id"] for row in summary["watching"]],
        )
        self.assertEqual(
            {SEVERITY_MEDIUM},
            {row["severity"] for row in summary["watching"]},
        )

    def test_overview_returns_resolved_this_week_count(self) -> None:
        now = datetime.now(timezone.utc)
        session = self._session()
        try:
            self._seed_alert(
                session,
                status=STATUS_RESOLVED,
                title="Resolved two days ago",
                resolved_at=now - timedelta(days=2),
            )
            self._seed_alert(
                session,
                status=STATUS_RESOLVED,
                title="Resolved six days ago",
                resolved_at=now - timedelta(days=6),
            )
            self._seed_alert(
                session,
                status=STATUS_RESOLVED,
                title="Resolved eight days ago",
                resolved_at=now - timedelta(days=8),
            )
            self._seed_alert(
                session,
                portal_id=self.OTHER_PORTAL_ID,
                status=STATUS_RESOLVED,
                title="Other portal resolved",
                resolved_at=now - timedelta(days=1),
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/overview?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["summary"]["resolvedThisWeekCount"])

    def test_overview_returns_slack_connected_from_portal_settings(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/overview?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["summary"]["slackConnected"])

        session = self._session()
        try:
            row = session.get(PortalSetting, self.PORTAL_ID)
            if row is None:
                row = PortalSetting(
                    portal_id=self.PORTAL_ID,
                    alert_threshold="medium",
                )
                session.add(row)
            row.slack_webhook_url = "https://hooks.slack.test/services/T/B/C"
            session.commit()
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/overview?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["summary"]["slackConnected"])

    def test_resolve_endpoint_sets_status_and_resolved_at(self) -> None:
        session = self._session()
        try:
            alert = self._seed_alert(session, title="Needs resolving")
            alert_id = alert.id
        finally:
            session.close()

        response = self.client.post(
            f"/api/v1/dashboard/alerts/{alert_id}/resolve?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("ok", payload["status"])
        self.assertEqual(str(alert_id), payload["alertId"])
        self.assertTrue(payload["resolvedAtUtc"])

        session = self._session()
        try:
            row = session.get(Alert, alert_id)
            self.assertEqual(STATUS_RESOLVED, row.status)
            self.assertIsNotNone(row.resolved_at)
        finally:
            session.close()

    def test_resolve_endpoint_returns_404_for_other_portal_alert(self) -> None:
        session = self._session()
        try:
            alert = self._seed_alert(
                session,
                portal_id=self.OTHER_PORTAL_ID,
                title="Different portal",
            )
            alert_id = alert.id
        finally:
            session.close()

        response = self.client.post(
            f"/api/v1/dashboard/alerts/{alert_id}/resolve?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(404, response.status_code)

    def test_resolve_endpoint_is_idempotent(self) -> None:
        resolved_at = datetime(2026, 4, 27, 13, 30, tzinfo=timezone.utc)
        session = self._session()
        try:
            alert = self._seed_alert(
                session,
                status=STATUS_RESOLVED,
                title="Already resolved",
                resolved_at=resolved_at,
            )
            alert_id = alert.id
        finally:
            session.close()

        first = self.client.post(
            f"/api/v1/dashboard/alerts/{alert_id}/resolve?portalId={self.PORTAL_ID}"
        )
        second = self.client.post(
            f"/api/v1/dashboard/alerts/{alert_id}/resolve?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual(
            first.json()["resolvedAtUtc"],
            second.json()["resolvedAtUtc"],
        )


if __name__ == "__main__":
    unittest.main()
