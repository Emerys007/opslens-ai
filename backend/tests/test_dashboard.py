from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import db as db_module
from app.api.v1.routes import dashboard as dashboard_module
from app.main import app
from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_EVENT_WORKFLOW_DISABLED,
    SOURCE_KIND_PROPERTY,
    SOURCE_KIND_WORKFLOW,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Alert,
)
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.models.hubspot_installation import HubSpotInstallation
from app.models.list_snapshot import ListSnapshot
from app.models.portal_entitlement import PortalEntitlement
from app.models.portal_setting import PortalSetting
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.slack_oauth import SlackOAuthError
from tests.hubspot_fetch_auth import SignedHubSpotTestClient


SEVERITY_CRITICAL = "critical"


class DependencyLocationsHelperTests(unittest.TestCase):
    """The blast-radius display reads dependency_locations off the alert
    summary. The serializer must surface them and never raise on bad data."""

    @staticmethod
    def _alert(summary):
        from types import SimpleNamespace

        return SimpleNamespace(summary=summary)

    def test_parses_dependency_locations_from_summary(self) -> None:
        import json as _json

        alert = self._alert(
            _json.dumps(
                {"impact": {"dependency_locations": ["Enrollment trigger", "If/then branch"]}}
            )
        )
        self.assertEqual(
            ["Enrollment trigger", "If/then branch"],
            dashboard_module._dependency_locations(alert),
        )

    def test_returns_empty_for_missing_or_malformed_summary(self) -> None:
        import json as _json

        self.assertEqual([], dashboard_module._dependency_locations(self._alert(None)))
        self.assertEqual([], dashboard_module._dependency_locations(self._alert("not json")))
        self.assertEqual(
            [], dashboard_module._dependency_locations(self._alert(_json.dumps({"impact": {}})))
        )
        self.assertEqual(
            [],
            dashboard_module._dependency_locations(
                self._alert(_json.dumps({"impact": {"dependency_locations": "x"}}))
            ),
        )

    def test_filters_blank_locations(self) -> None:
        import json as _json

        alert = self._alert(
            _json.dumps({"impact": {"dependency_locations": ["Enrollment trigger", "", "  "]}})
        )
        self.assertEqual(
            ["Enrollment trigger"], dashboard_module._dependency_locations(alert)
        )


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
        dashboard_module._LAST_POLL_AT.clear()
        db_module.init_db()
        self.client = SignedHubSpotTestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        dashboard_module._LAST_POLL_AT.clear()
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

    def _seed_workflow(
        self,
        session,
        *,
        portal_id: str | None = None,
        workflow_id: str = "workflow-1",
        name: str = "Workflow",
        is_enabled: bool = True,
    ) -> WorkflowSnapshot:
        row = WorkflowSnapshot(
            portal_id=portal_id or self.PORTAL_ID,
            workflow_id=workflow_id,
            name=name,
            is_enabled=is_enabled,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def _seed_workflow_dependency(
        self,
        session,
        *,
        workflow_id: str,
        dependency_type: str,
        dependency_id: str,
        location: str,
        dependency_object_type: str | None = None,
    ) -> None:
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                dependency_type=dependency_type,
                dependency_id=dependency_id,
                dependency_object_type=dependency_object_type,
                location=location,
                revision_id="1",
            )
        )
        session.commit()

    def test_dependents_lists_workflows_referencing_a_property(self) -> None:
        session = self._session()
        try:
            self._seed_workflow(session, workflow_id="100", name="Lead routing")
            self._seed_workflow_dependency(
                session,
                workflow_id="100",
                dependency_type="property",
                dependency_id="lead_source",
                dependency_object_type="0-1",
                location="Enrollment trigger",
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/dependents?portalId={self.PORTAL_ID}"
            "&type=property&id=lead_source&objectTypeId=0-1"
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(1, body["dependentCount"])
        dependent = body["dependents"][0]
        self.assertEqual("100", dependent["workflowId"])
        self.assertEqual("Lead routing", dependent["workflowName"])
        self.assertIn("Enrollment trigger", dependent["locations"])

    def test_dependents_excludes_other_portals(self) -> None:
        session = self._session()
        try:
            self._seed_workflow(
                session,
                portal_id=self.OTHER_PORTAL_ID,
                workflow_id="200",
                name="Other portal flow",
            )
            session.add(
                WorkflowDependency(
                    portal_id=self.OTHER_PORTAL_ID,
                    workflow_id="200",
                    dependency_type="owner",
                    dependency_id="55",
                    location="Rotate owner action",
                    revision_id="1",
                )
            )
            session.commit()
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/dependents?portalId={self.PORTAL_ID}&type=owner&id=55"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()["dependentCount"])

    def test_dependents_returns_empty_when_nothing_references_asset(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/dependents?portalId={self.PORTAL_ID}&type=owner&id=99999"
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(0, body["dependentCount"])
        self.assertEqual([], body["dependents"])

    def test_dependents_rejects_unknown_type(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/dependents?portalId={self.PORTAL_ID}&type=bogus&id=x"
        )
        self.assertEqual(400, response.status_code)

    def test_dependents_requires_id(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/dependents?portalId={self.PORTAL_ID}&type=property"
        )
        self.assertEqual(400, response.status_code)

    def _seed_workflow_disabled_alert(self, session, *, workflow_id: str = "500") -> Alert:
        alert = Alert(
            portal_id=self.PORTAL_ID,
            alert_signature=f"sig-wf-disabled-{workflow_id}",
            severity=SEVERITY_HIGH,
            status=STATUS_OPEN,
            source_event_type=SOURCE_EVENT_WORKFLOW_DISABLED,
            source_event_kind=SOURCE_KIND_WORKFLOW,
            source_dependency_type="workflow",
            source_dependency_id=workflow_id,
            impacted_workflow_id=workflow_id,
            impacted_workflow_name="Lead routing",
            title="Workflow 'Lead routing' disabled",
            summary="{}",
            created_at=datetime.now(timezone.utc),
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert

    def test_reenable_workflow_happy_path_resolves_alert(self) -> None:
        session = self._session()
        try:
            alert = self._seed_workflow_disabled_alert(session)
            alert_id = str(alert.id)
        finally:
            session.close()

        with patch(
            "app.api.v1.routes.dashboard.reenable_workflow",
            return_value={
                "status": "ok",
                "workflowId": "500",
                "isEnabled": True,
                "alreadyEnabled": False,
            },
        ):
            response = self.client.post(
                f"/api/v1/dashboard/alerts/{alert_id}/reenable-workflow"
                f"?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("500", body["workflowId"])
        self.assertTrue(body["isEnabled"])
        self.assertIsNotNone(body["resolvedAtUtc"])

        session = self._session()
        try:
            refreshed = session.get(Alert, int(alert_id))
            self.assertEqual(STATUS_RESOLVED, refreshed.status)
        finally:
            session.close()

    def test_reenable_rejects_non_workflow_alert(self) -> None:
        session = self._session()
        try:
            alert = self._seed_alert(session)  # property_archived
            alert_id = str(alert.id)
        finally:
            session.close()

        response = self.client.post(
            f"/api/v1/dashboard/alerts/{alert_id}/reenable-workflow?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(400, response.status_code)

    def test_reenable_surfaces_remediation_error_as_502(self) -> None:
        from app.services.workflow_remediation import WorkflowRemediationError

        session = self._session()
        try:
            alert = self._seed_workflow_disabled_alert(session)
            alert_id = str(alert.id)
        finally:
            session.close()

        with patch(
            "app.api.v1.routes.dashboard.reenable_workflow",
            side_effect=WorkflowRemediationError("That workflow no longer exists in HubSpot."),
        ):
            response = self.client.post(
                f"/api/v1/dashboard/alerts/{alert_id}/reenable-workflow"
                f"?portalId={self.PORTAL_ID}"
            )
        self.assertEqual(502, response.status_code)

        # The alert must remain open when the fix failed.
        session = self._session()
        try:
            refreshed = session.get(Alert, int(alert_id))
            self.assertEqual(STATUS_OPEN, refreshed.status)
        finally:
            session.close()

    def test_run_install_diagnostic_returns_fresh_summary(self) -> None:
        with patch(
            "app.api.v1.routes.dashboard.run_install_diagnostic",
            return_value={
                "status": "completed",
                "issuesFound": 2,
                "portalId": self.PORTAL_ID,
            },
        ) as mocked:
            response = self.client.post(
                f"/api/v1/dashboard/install-diagnostic/run?portalId={self.PORTAL_ID}"
            )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("completed", body["summary"]["status"])
        self.assertEqual(2, body["summary"]["issuesFound"])
        # Forced re-run.
        _, kwargs = mocked.call_args
        self.assertTrue(kwargs.get("force"))

    def test_run_install_diagnostic_surfaces_failure_as_502(self) -> None:
        with patch(
            "app.api.v1.routes.dashboard.run_install_diagnostic",
            side_effect=RuntimeError("HubSpot unreachable"),
        ):
            response = self.client.post(
                f"/api/v1/dashboard/install-diagnostic/run?portalId={self.PORTAL_ID}"
            )
        self.assertEqual(502, response.status_code)

    def _seed_list(
        self,
        session,
        *,
        portal_id: str | None = None,
        list_id: str = "list-1",
        list_name: str = "List",
        is_archived: bool = False,
    ) -> ListSnapshot:
        row = ListSnapshot(
            portal_id=portal_id or self.PORTAL_ID,
            list_id=list_id,
            list_name=list_name,
            is_archived=is_archived,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def _seed_template(
        self,
        session,
        *,
        portal_id: str | None = None,
        template_id: str = "template-1",
        template_name: str = "Template",
        subject: str = "Hello",
        is_archived: bool = False,
    ) -> EmailTemplateSnapshot:
        row = EmailTemplateSnapshot(
            portal_id=portal_id or self.PORTAL_ID,
            template_id=template_id,
            template_name=template_name,
            subject=subject,
            is_archived=is_archived,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

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

    def test_overview_action_page_size_3_returns_up_to_3(self) -> None:
        session = self._session()
        try:
            self._seed_action_alerts(session, count=12)
        finally:
            session.close()

        summary = self._overview_summary("actionPageSize=3")

        self.assertEqual(12, summary["actionRequiredCount"])
        self.assertEqual(3, len(summary["actionRequired"]))
        self.assertEqual(
            ["Plain-English first action", "Action 02", "Action 03"],
            self._action_titles(summary),
        )

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

    def test_workflows_endpoint_returns_sorted_rows_capped_at_200(self) -> None:
        session = self._session()
        try:
            for index in range(205):
                self._seed_workflow(
                    session,
                    workflow_id=f"workflow-{index:03d}",
                    name=f"Workflow {205 - index:03d}",
                    is_enabled=index % 2 == 0,
                )
            self._seed_workflow(
                session,
                portal_id=self.OTHER_PORTAL_ID,
                workflow_id="other-workflow",
                name="A different portal",
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/workflows?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(200, len(payload))
        self.assertEqual("Workflow 001", payload[0]["name"])
        self.assertEqual("Workflow 200", payload[-1]["name"])
        self.assertEqual({"id", "name", "isEnabled"}, set(payload[0].keys()))
        self.assertNotIn("other-workflow", {row["id"] for row in payload})

    def test_workflows_endpoint_returns_empty_array_without_rows(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/workflows?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_lists_endpoint_returns_sorted_rows_capped_at_200(self) -> None:
        session = self._session()
        try:
            for index in range(205):
                self._seed_list(
                    session,
                    list_id=f"list-{index:03d}",
                    list_name=f"List {205 - index:03d}",
                    is_archived=index % 2 == 0,
                )
            self._seed_list(
                session,
                portal_id=self.OTHER_PORTAL_ID,
                list_id="other-list",
                list_name="A different portal",
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/lists?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(200, len(payload))
        self.assertEqual("List 001", payload[0]["name"])
        self.assertEqual("List 200", payload[-1]["name"])
        self.assertEqual({"id", "name", "isArchived"}, set(payload[0].keys()))
        self.assertNotIn("other-list", {row["id"] for row in payload})

    def test_lists_endpoint_returns_empty_array_without_rows(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/lists?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_templates_endpoint_returns_sorted_rows_capped_at_200(self) -> None:
        session = self._session()
        try:
            for index in range(205):
                self._seed_template(
                    session,
                    template_id=f"template-{index:03d}",
                    template_name=f"Template {205 - index:03d}",
                    subject=f"Subject {index:03d}",
                    is_archived=index % 2 == 0,
                )
            self._seed_template(
                session,
                portal_id=self.OTHER_PORTAL_ID,
                template_id="other-template",
                template_name="A different portal",
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/templates?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(200, len(payload))
        self.assertEqual("Template 001", payload[0]["name"])
        self.assertEqual("Template 200", payload[-1]["name"])
        self.assertEqual(
            {"id", "name", "subject", "isArchived"},
            set(payload[0].keys()),
        )
        self.assertNotIn("other-template", {row["id"] for row in payload})

    def test_templates_endpoint_returns_empty_array_without_rows(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/templates?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_properties_endpoint_returns_shape_when_hubspot_api_succeeds(self) -> None:
        hubspot_payload = {
            "results": [
                {"name": "z_internal", "label": "Zeta", "type": "string"},
                {"name": "lead_source", "label": "Lead Source", "type": "enumeration"},
            ]
        }

        with (
            patch(
                "app.api.v1.routes.dashboard.get_portal_access_token",
                return_value="access-token",
            ) as token_mock,
            patch(
                "app.api.v1.routes.dashboard._hubspot_get_json",
                return_value=hubspot_payload,
            ) as get_json_mock,
        ):
            response = self.client.get(
                f"/api/v1/dashboard/properties?portalId={self.PORTAL_ID}&objectTypeId=0-1"
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                {
                    "name": "lead_source",
                    "label": "Lead Source",
                    "type": "enumeration",
                },
                {"name": "z_internal", "label": "Zeta", "type": "string"},
            ],
            response.json(),
        )
        token_mock.assert_called_once()
        called_url, called_token = get_json_mock.call_args.args
        self.assertIn("/crm/v3/properties/contacts", called_url)
        self.assertEqual("access-token", called_token)

    def test_properties_endpoint_returns_empty_array_when_portal_has_no_token(self) -> None:
        with patch("app.api.v1.routes.dashboard._hubspot_get_json") as get_json_mock:
            response = self.client.get(
                f"/api/v1/dashboard/properties?portalId={self.PORTAL_ID}&objectTypeId=0-1"
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())
        get_json_mock.assert_not_called()

    def test_properties_endpoint_passes_invalid_object_type_id_without_crashing(
        self,
    ) -> None:
        with (
            patch(
                "app.api.v1.routes.dashboard.get_portal_access_token",
                return_value="access-token",
            ),
            patch(
                "app.api.v1.routes.dashboard._hubspot_get_json",
                return_value={"results": []},
            ) as get_json_mock,
        ):
            response = self.client.get(
                f"/api/v1/dashboard/properties?portalId={self.PORTAL_ID}&objectTypeId=custom-object"
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())
        called_url, _called_token = get_json_mock.call_args.args
        self.assertIn("/crm/v3/properties/custom-object", called_url)

    def test_poll_now_endpoint_runs_polling_for_portal(self) -> None:
        with (
            patch(
                "app.api.v1.routes.dashboard.poll_portal_workflows",
                return_value={
                    "status": "ok",
                    "createdEvents": 1,
                    "editedEvents": 2,
                },
            ) as workflow_mock,
            patch(
                "app.api.v1.routes.dashboard.poll_portal_properties",
                return_value={
                    "status": "ok",
                    "archivedEvents": 1,
                    "typeChangedEvents": 1,
                },
            ) as property_mock,
            patch(
                "app.api.v1.routes.dashboard.poll_portal_lists",
                return_value={
                    "status": "ok",
                    "archivedEvents": 1,
                    "criteriaChangedEvents": 1,
                },
            ) as list_mock,
            patch(
                "app.api.v1.routes.dashboard.poll_portal_email_templates",
                return_value={"status": "ok", "editedEvents": 1},
            ) as template_mock,
            patch(
                "app.api.v1.routes.dashboard.poll_portal_owners",
                return_value={"status": "ok", "deactivatedEvents": 1},
            ) as owner_mock,
            patch(
                "app.api.v1.routes.dashboard.correlate_unprocessed_events",
                return_value={"alerts_created": 6},
            ) as correlation_mock,
        ):
            response = self.client.post(
                f"/api/v1/dashboard/poll-now?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"status": "ok", "eventsDetected": 9, "alertsCreated": 6},
            response.json(),
        )
        workflow_mock.assert_called_once()
        property_mock.assert_called_once()
        list_mock.assert_called_once()
        template_mock.assert_called_once()
        owner_mock.assert_called_once()
        correlation_mock.assert_called_once()
        self.assertEqual(self.PORTAL_ID, workflow_mock.call_args.args[1])
        self.assertEqual(self.PORTAL_ID, property_mock.call_args.args[1])
        self.assertEqual(self.PORTAL_ID, list_mock.call_args.args[1])
        self.assertEqual(self.PORTAL_ID, template_mock.call_args.args[1])
        self.assertEqual(self.PORTAL_ID, owner_mock.call_args.args[1])

    def test_poll_now_endpoint_returns_429_when_called_twice_within_30s(self) -> None:
        with (
            patch(
                "app.api.v1.routes.dashboard.poll_portal_workflows",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.poll_portal_properties",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.poll_portal_lists",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.poll_portal_email_templates",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.poll_portal_owners",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.correlate_unprocessed_events",
                return_value={"alerts_created": 0},
            ),
        ):
            first = self.client.post(
                f"/api/v1/dashboard/poll-now?portalId={self.PORTAL_ID}"
            )
            second = self.client.post(
                f"/api/v1/dashboard/poll-now?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(200, first.status_code)
        self.assertEqual(429, second.status_code)

    def test_poll_now_endpoint_resets_rate_limit_after_window(self) -> None:
        dashboard_module._LAST_POLL_AT[self.PORTAL_ID] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=31)

        with (
            patch(
                "app.api.v1.routes.dashboard.poll_portal_workflows",
                return_value={"status": "ok", "createdEvents": 1},
            ) as workflow_mock,
            patch(
                "app.api.v1.routes.dashboard.poll_portal_properties",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.poll_portal_lists",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.poll_portal_email_templates",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.poll_portal_owners",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.routes.dashboard.correlate_unprocessed_events",
                return_value={"alerts_created": 1},
            ),
        ):
            response = self.client.post(
                f"/api/v1/dashboard/poll-now?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["eventsDetected"])
        workflow_mock.assert_called_once()

    def test_slack_status_reports_connected_when_webhook_present(self) -> None:
        session = self._session()
        try:
            session.add(
                PortalSetting(
                    portal_id=self.PORTAL_ID,
                    slack_webhook_url="https://hooks.slack.com/services/T/B/x",
                    slack_channel_name="#ops-alerts",
                    slack_team_name="Acme",
                )
            )
            session.commit()
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/slack/status?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["connected"])
        self.assertEqual("#ops-alerts", payload["channel"])
        self.assertEqual("Acme", payload["team"])

    def test_slack_status_reports_not_connected_without_webhook(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/slack/status?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertFalse(payload["connected"])
        self.assertEqual("", payload["channel"])

    def test_slack_install_url_returns_authorization_url(self) -> None:
        with patch(
            "app.api.v1.routes.dashboard.build_slack_authorize_url",
            return_value="https://slack.com/oauth/v2/authorize?state=abc",
        ) as build_mock:
            response = self.client.get(
                f"/api/v1/dashboard/slack/install-url?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            "https://slack.com/oauth/v2/authorize?state=abc",
            response.json()["authorizationUrl"],
        )
        self.assertEqual(self.PORTAL_ID, build_mock.call_args.args[0])

    def test_slack_install_url_returns_503_when_not_configured(self) -> None:
        with patch(
            "app.api.v1.routes.dashboard.build_slack_authorize_url",
            side_effect=SlackOAuthError("Slack is not configured (SLACK_CLIENT_ID)."),
        ):
            response = self.client.get(
                f"/api/v1/dashboard/slack/install-url?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(503, response.status_code)

    def test_slack_disconnect_clears_connection(self) -> None:
        session = self._session()
        try:
            session.add(
                PortalSetting(
                    portal_id=self.PORTAL_ID,
                    slack_webhook_url="https://hooks.slack.com/services/T/B/x",
                    slack_channel_name="#ops-alerts",
                    slack_team_name="Acme",
                )
            )
            session.commit()
        finally:
            session.close()

        response = self.client.post(
            f"/api/v1/dashboard/slack/disconnect?portalId={self.PORTAL_ID}"
        )

        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["connected"])

        session = self._session()
        try:
            row = session.get(PortalSetting, self.PORTAL_ID)
            self.assertEqual("", row.slack_webhook_url)
            self.assertEqual("", row.slack_channel_name)
            self.assertEqual("", row.slack_team_name)
        finally:
            session.close()

    def test_slack_test_sends_message_when_connected(self) -> None:
        session = self._session()
        try:
            session.add(
                PortalSetting(
                    portal_id=self.PORTAL_ID,
                    slack_webhook_url="https://hooks.slack.com/services/T/B/x",
                )
            )
            session.commit()
        finally:
            session.close()

        with patch(
            "app.services.slack_delivery._post_to_slack",
            return_value=(True, 200, "ok"),
        ) as post_mock:
            response = self.client.post(
                f"/api/v1/dashboard/slack/test?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])
        post_mock.assert_called_once()
        called_webhook = post_mock.call_args.args[0]
        self.assertEqual("https://hooks.slack.com/services/T/B/x", called_webhook)

    def test_slack_test_returns_400_when_not_connected(self) -> None:
        with patch("app.services.slack_delivery._post_to_slack") as post_mock:
            response = self.client.post(
                f"/api/v1/dashboard/slack/test?portalId={self.PORTAL_ID}"
            )

        self.assertEqual(400, response.status_code)
        post_mock.assert_not_called()


    def _seed_installation(self, session, portal_id: str, email: str) -> None:
        session.add(
            HubSpotInstallation(
                portal_id=portal_id,
                installing_user_email=email,
                access_token="AT",
                refresh_token="RT",
                is_active=True,
            )
        )
        session.commit()

    def _seed_entitlement(self, session, portal_id: str, plan: str) -> None:
        session.add(
            PortalEntitlement(
                portal_id=portal_id,
                plan=plan,
                billing_interval="monthly",
                subscription_status="active",
                trial_approved=False,
            )
        )
        session.commit()

    def test_overview_topline_counts_come_from_v2_alert_table(self) -> None:
        session = self._session()
        try:
            self._seed_alert(
                session, severity=SEVERITY_CRITICAL, status=STATUS_OPEN, title="Crit"
            )
            self._seed_alert(
                session, severity=SEVERITY_HIGH, status=STATUS_OPEN, title="High"
            )
            self._seed_alert(
                session, severity=SEVERITY_MEDIUM, status=STATUS_OPEN, title="Med"
            )
            self._seed_workflow(session, workflow_id="w1", name="WF1")
            self._seed_workflow(session, workflow_id="w2", name="WF2")
        finally:
            session.close()

        summary = self._overview_summary()
        self.assertEqual(3, summary["openIncidents"])
        self.assertEqual(1, summary["criticalIssues"])
        self.assertEqual(2, summary["monitoredWorkflows"])
        self.assertEqual([], summary["activeIncidents"])

    def test_portfolio_non_agency_returns_only_current_portal(self) -> None:
        session = self._session()
        try:
            self._seed_entitlement(session, self.PORTAL_ID, "professional")
            # Another portal by the same partner — must NOT leak into a non-agency view.
            self._seed_installation(session, "88888888", "partner@agency.test")
            self._seed_entitlement(session, "88888888", "agency")
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/portfolio?portalId={self.PORTAL_ID}"
            f"&userEmail=partner@agency.test"
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertFalse(body["agencyEnabled"])
        self.assertEqual(1, body["totals"]["portalCount"])
        self.assertEqual(self.PORTAL_ID, body["portals"][0]["portalId"])

    def test_portfolio_agency_aggregates_partner_portals(self) -> None:
        session = self._session()
        try:
            self._seed_entitlement(session, self.PORTAL_ID, "agency")
            self._seed_installation(session, self.PORTAL_ID, "partner@agency.test")
            self._seed_installation(session, "88888888", "partner@agency.test")
            self._seed_entitlement(session, "88888888", "agency")
            self._seed_alert(
                session,
                portal_id="88888888",
                severity=SEVERITY_HIGH,
                status=STATUS_OPEN,
                title="Workflow disabled in client portal",
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/portfolio?portalId={self.PORTAL_ID}"
            f"&userEmail=partner@agency.test"
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertTrue(body["agencyEnabled"])
        self.assertEqual(2, body["totals"]["portalCount"])
        self.assertGreaterEqual(body["totals"]["actionRequiredTotal"], 1)
        portal_ids = {row["portalId"] for row in body["portals"]}
        self.assertEqual({self.PORTAL_ID, "88888888"}, portal_ids)


if __name__ == "__main__":
    unittest.main()
