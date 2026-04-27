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

    def _seed_action_alerts(
        self,
        session,
        *,
        count: int,
        severity: str = SEVERITY_HIGH,
        title_prefix: str = "Action",
        base: datetime | None = None,
    ) -> list[Alert]:
        base_time = base or datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        alerts = []
        for index in range(count):
            alerts.append(
                self._seed_alert(
                    session,
                    severity=severity,
                    title=f"{title_prefix} {index + 1:02d}",
                    plain_english_explanation=(
                        "Plain-English first action" if index == 0 else None
                    ),
                    created_at=base_time - timedelta(minutes=index),
                )
            )
        return alerts

    def _overview_summary(self, query: str = "") -> dict:
        separator = "&" if query else ""
        response = self.client.get(
            f"/api/v1/dashboard/overview?portalId={self.PORTAL_ID}{separator}{query}"
        )
        self.assertEqual(200, response.status_code)
        return response.json()["summary"]

    def _action_titles(self, summary: dict) -> list[str]:
        return [row["title"] for row in summary["actionRequired"]]

    def test_overview_default_action_page_returns_10_rows_and_total_count(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=12)
            self._seed_alert(
                session,
                severity=SEVERITY_MEDIUM,
                title="Watching only",
            )
            self._seed_alert(
                session,
                severity=SEVERITY_HIGH,
                status=STATUS_RESOLVED,
                title="Resolved high",
                resolved_at=datetime(2026, 4, 27, 13, 0, tzinfo=timezone.utc),
            )
        finally:
            session.close()

        summary = self._overview_summary()

        self.assertEqual(12, summary["actionRequiredCount"])
        self.assertEqual(10, len(summary["actionRequired"]))
        self.assertEqual(
            "Plain-English first action",
            summary["actionRequired"][0]["title"],
        )
        self.assertEqual(
            [f"Action {index:02d}" for index in range(2, 11)],
            self._action_titles(summary)[1:],
        )
        self.assertEqual(
            {SEVERITY_HIGH},
            {row["severity"] for row in summary["actionRequired"]},
        )

    def test_overview_action_page_size_25_returns_up_to_25(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=30)
        finally:
            session.close()

        summary = self._overview_summary("actionPageSize=25")

        self.assertEqual(30, summary["actionRequiredCount"])
        self.assertEqual(25, len(summary["actionRequired"]))
        self.assertEqual("Plain-English first action", summary["actionRequired"][0]["title"])
        self.assertEqual("Action 25", summary["actionRequired"][-1]["title"])

    def test_overview_action_page_size_50_returns_up_to_50(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=55)
        finally:
            session.close()

        summary = self._overview_summary("actionPageSize=50")

        self.assertEqual(55, summary["actionRequiredCount"])
        self.assertEqual(50, len(summary["actionRequired"]))
        self.assertEqual("Action 50", summary["actionRequired"][-1]["title"])

    def test_overview_invalid_action_page_size_clamps_to_10(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=12)
        finally:
            session.close()

        summary = self._overview_summary("actionPageSize=999")

        self.assertEqual(12, summary["actionRequiredCount"])
        self.assertEqual(10, len(summary["actionRequired"]))

    def test_overview_action_page_2_returns_rows_11_to_20(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=25)
        finally:
            session.close()

        summary = self._overview_summary("actionPage=2&actionPageSize=10")

        self.assertEqual(25, summary["actionRequiredCount"])
        self.assertEqual(
            [f"Action {index:02d}" for index in range(11, 21)],
            self._action_titles(summary),
        )

    def test_overview_action_page_3_returns_remaining_rows(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=25)
        finally:
            session.close()

        summary = self._overview_summary("actionPage=3&actionPageSize=10")

        self.assertEqual(25, summary["actionRequiredCount"])
        self.assertEqual(5, len(summary["actionRequired"]))
        self.assertEqual(
            [f"Action {index:02d}" for index in range(21, 26)],
            self._action_titles(summary),
        )

    def test_overview_action_required_count_is_unaffected_by_pagination(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=25)
        finally:
            session.close()

        summary = self._overview_summary("actionPage=2&actionPageSize=10")

        self.assertEqual(25, summary["actionRequiredCount"])
        self.assertEqual(10, len(summary["actionRequired"]))

    def test_overview_action_page_zero_clamps_to_first_page(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=12)
        finally:
            session.close()

        first_page = self._overview_summary("actionPage=1&actionPageSize=10")
        zero_page = self._overview_summary("actionPage=0&actionPageSize=10")

        self.assertEqual(self._action_titles(first_page), self._action_titles(zero_page))

    def test_overview_action_page_negative_clamps_to_first_page(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=12)
        finally:
            session.close()

        first_page = self._overview_summary("actionPage=1&actionPageSize=10")
        negative_page = self._overview_summary("actionPage=-5&actionPageSize=10")

        self.assertEqual(
            self._action_titles(first_page),
            self._action_titles(negative_page),
        )

    def test_overview_action_required_sorts_critical_before_high_then_recent(
        self,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        session = self._session()
        try:
            self._seed_alert(
                session,
                severity=SEVERITY_HIGH,
                title="High newest",
                created_at=base + timedelta(minutes=5),
            )
            self._seed_alert(
                session,
                severity=SEVERITY_CRITICAL,
                title="Critical older",
                created_at=base + timedelta(minutes=1),
            )
            self._seed_alert(
                session,
                severity=SEVERITY_CRITICAL,
                title="Critical newest",
                created_at=base + timedelta(minutes=3),
            )
        finally:
            session.close()

        summary = self._overview_summary()

        self.assertEqual(
            ["Critical newest", "Critical older", "High newest"],
            self._action_titles(summary),
        )

    def test_overview_returns_watching_medium_open_alerts_newest_first_capped(
        self,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        session = self._session()
        try:
            seeded_ids = []
            for index in range(12):
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

        self.assertEqual(12, summary["watchingCount"])
        self.assertEqual(10, len(summary["watching"]))
        self.assertEqual(
            list(reversed(seeded_ids[2:])),
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
