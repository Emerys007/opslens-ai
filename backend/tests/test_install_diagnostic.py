from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app import db as db_module
from app.main import app
from app.models.alert import (
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_KIND_INSTALL_DIAGNOSTIC,
    Alert,
)
from app.models.owner_snapshot import OwnerSnapshot
from app.models.portal_entitlement import PortalEntitlement
from app.models.portal_setting import PortalSetting
from app.models.property_snapshot import PropertySnapshot
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.install_diagnostic import run_install_diagnostic
from tests.hubspot_fetch_auth import SignedHubSpotTestClient


class InstallDiagnosticTests(unittest.TestCase):
    PORTAL_ID = "51300126"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'install-diagnostic-test.sqlite')}"
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

    def _seed_workflow(
        self,
        session,
        *,
        workflow_id: str = "workflow-1",
        workflow_name: str = "Lead Nurture",
    ) -> None:
        session.add(
            WorkflowSnapshot(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                name=workflow_name,
                object_type_id="0-1",
                is_enabled=True,
            )
        )

    def _seed_property_dependency(
        self,
        session,
        *,
        workflow_id: str = "workflow-1",
        property_name: str = "lead_source",
    ) -> None:
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                dependency_type="property",
                dependency_id=property_name,
                dependency_object_type="0-1",
                location="actions[0].propertyName",
            )
        )

    def _seed_property_snapshot(
        self,
        session,
        *,
        property_name: str = "lead_source",
        label: str = "Lead Source",
        archived: bool = False,
        deleted: bool = False,
    ) -> None:
        session.add(
            PropertySnapshot(
                portal_id=self.PORTAL_ID,
                object_type_id="0-1",
                property_name=property_name,
                label=label,
                archived=archived,
                deleted_at=datetime.now(timezone.utc) if deleted else None,
            )
        )

    def _rewrite_alert(self, session, alert: Alert) -> bool:
        alert.plain_english_explanation = "Lead Source is broken for Lead Nurture."
        alert.recommended_action = "Repair the workflow dependency."
        return True

    def _run_diagnostic(self, session, *, force: bool = False):
        with (
            patch(
                "app.services.install_diagnostic.poll_portal_workflows",
                return_value={"status": "skipped"},
            ),
            patch(
                "app.services.install_diagnostic.poll_portal_properties",
                return_value={"status": "skipped"},
            ),
            patch(
                "app.services.install_diagnostic.poll_portal_lists",
                return_value={"status": "skipped"},
            ),
            patch(
                "app.services.install_diagnostic.poll_portal_email_templates",
                return_value={"status": "skipped"},
            ),
            patch(
                "app.services.install_diagnostic.poll_portal_owners",
                return_value={"status": "skipped"},
            ),
            patch(
                "app.services.install_diagnostic.rewrite_alert",
                side_effect=self._rewrite_alert,
            ),
        ):
            return run_install_diagnostic(self.PORTAL_ID, session, force=force)

    def test_broken_property_dependency_creates_alert(self) -> None:
        session = self._session()
        try:
            self._seed_workflow(session)
            self._seed_property_dependency(session)
            self._seed_property_snapshot(session, archived=True)
            session.commit()

            summary = self._run_diagnostic(session)

            alerts = session.query(Alert).all()
            self.assertEqual(1, len(alerts))
            self.assertEqual(1, summary["issuesFound"])
            self.assertEqual(1, summary["alertsCreated"])
            self.assertEqual(SOURCE_KIND_INSTALL_DIAGNOSTIC, alerts[0].source_event_kind)
            self.assertEqual(SOURCE_EVENT_PROPERTY_ARCHIVED, alerts[0].source_event_type)
            self.assertEqual("lead_source", alerts[0].source_dependency_id)
            self.assertEqual("workflow-1", alerts[0].impacted_workflow_id)
            self.assertEqual(
                "Lead Source is broken for Lead Nurture.",
                alerts[0].plain_english_explanation,
            )
        finally:
            session.close()

    def _seed_owner_issue(self, session, *, plan: str) -> None:
        self._seed_workflow(session)
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id="workflow-1",
                dependency_type="owner",
                dependency_id="9",
                location="actions[0].fields.owner_id",
            )
        )
        session.add(
            OwnerSnapshot(
                portal_id=self.PORTAL_ID,
                owner_id="9",
                email="rep@acme.test",
                is_active=False,
            )
        )
        session.add(
            PortalEntitlement(
                portal_id=self.PORTAL_ID,
                plan=plan,
                billing_interval="monthly",
                subscription_status="active",
                trial_approved=False,
            )
        )
        session.commit()

    def test_owner_issue_gated_out_for_starter_plan(self) -> None:
        # Owner detection is Agency-only — the diagnostic must not surface or
        # alert on an owner issue for a Starter portal.
        session = self._session()
        try:
            self._seed_owner_issue(session, plan="starter")
            summary = self._run_diagnostic(session)
            self.assertEqual(0, summary["issuesFound"])
            self.assertEqual(0, session.query(Alert).count())
        finally:
            session.close()

    def test_owner_issue_present_for_agency_plan(self) -> None:
        session = self._session()
        try:
            self._seed_owner_issue(session, plan="agency")
            summary = self._run_diagnostic(session)
            self.assertGreaterEqual(summary["issuesFound"], 1)
            self.assertGreaterEqual(session.query(Alert).count(), 1)
        finally:
            session.close()

    def test_clean_portal_creates_zero_alerts(self) -> None:
        session = self._session()
        try:
            self._seed_workflow(session)
            self._seed_property_dependency(session)
            self._seed_property_snapshot(session)
            session.commit()

            summary = self._run_diagnostic(session)

            self.assertEqual(0, summary["issuesFound"])
            self.assertEqual(0, session.query(Alert).count())
        finally:
            session.close()

    def test_summary_persisted_on_portal_settings(self) -> None:
        session = self._session()
        try:
            self._seed_workflow(session)
            self._seed_property_dependency(session)
            self._seed_property_snapshot(session)
            session.commit()

            summary = self._run_diagnostic(session)

            settings = session.get(PortalSetting, self.PORTAL_ID)
            self.assertIsNotNone(settings)
            self.assertEqual(summary, settings.install_diagnostic_summary)
            self.assertEqual("completed", settings.install_diagnostic_summary["status"])
        finally:
            session.close()

    def test_diagnostic_is_idempotent(self) -> None:
        session = self._session()
        try:
            self._seed_workflow(session)
            self._seed_property_dependency(session)
            self._seed_property_snapshot(session, archived=True)
            session.commit()

            with (
                patch(
                    "app.services.install_diagnostic.poll_portal_workflows",
                    return_value={"status": "skipped"},
                ) as workflow_poll,
                patch(
                    "app.services.install_diagnostic.poll_portal_properties",
                    return_value={"status": "skipped"},
                ),
                patch(
                    "app.services.install_diagnostic.poll_portal_lists",
                    return_value={"status": "skipped"},
                ),
                patch(
                    "app.services.install_diagnostic.poll_portal_email_templates",
                    return_value={"status": "skipped"},
                ),
                patch(
                    "app.services.install_diagnostic.poll_portal_owners",
                    return_value={"status": "skipped"},
                ),
                patch(
                    "app.services.install_diagnostic.rewrite_alert",
                    side_effect=self._rewrite_alert,
                ) as rewrite,
            ):
                first = run_install_diagnostic(self.PORTAL_ID, session)
                second = run_install_diagnostic(self.PORTAL_ID, session)

            self.assertEqual(first, second)
            self.assertEqual(1, session.query(Alert).count())
            self.assertEqual(1, workflow_poll.call_count)
            self.assertEqual(1, rewrite.call_count)
        finally:
            session.close()

    def test_dashboard_endpoint_returns_latest_summary(self) -> None:
        session = self._session()
        try:
            session.add(
                PortalSetting(
                    portal_id=self.PORTAL_ID,
                    install_diagnostic_summary={
                        "status": "completed",
                        "portalId": self.PORTAL_ID,
                        "issuesFound": 2,
                    },
                )
            )
            session.commit()
        finally:
            session.close()

        client = SignedHubSpotTestClient(app)
        try:
            response = client.get(
                f"/api/v1/dashboard/install-diagnostic?portalId={self.PORTAL_ID}"
            )
        finally:
            client.close()

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("ok", payload["status"])
        self.assertEqual(2, payload["summary"]["issuesFound"])
