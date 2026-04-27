"""Tests for `app.services.alert_correlation`.

Covers each correlation rule plus dedup behaviour. The tests seed the
DB directly (no HTTP mocks) so the correlation logic is exercised
without dragging the polling layer into scope.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app import db as db_module
from app.models.alert import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SOURCE_EVENT_LIST_ARCHIVED,
    SOURCE_EVENT_LIST_CRITERIA_CHANGED,
    SOURCE_EVENT_OWNER_DEACTIVATED,
    SOURCE_EVENT_OWNER_DELETED,
    SOURCE_EVENT_TEMPLATE_ARCHIVED,
    SOURCE_EVENT_TEMPLATE_EDITED,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_EVENT_PROPERTY_DELETED,
    SOURCE_EVENT_PROPERTY_RENAMED,
    SOURCE_EVENT_PROPERTY_TYPE_CHANGED,
    SOURCE_EVENT_WORKFLOW_DELETED,
    SOURCE_EVENT_WORKFLOW_DISABLED,
    SOURCE_EVENT_WORKFLOW_EDITED,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Alert,
)
from app.models.email_template_change_event import (
    TEMPLATE_EVENT_ARCHIVED,
    TEMPLATE_EVENT_EDITED,
    TEMPLATE_EVENT_UNARCHIVED,
    EmailTemplateChangeEvent,
)
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.models.list_change_event import (
    LIST_EVENT_ARCHIVED,
    LIST_EVENT_CRITERIA_CHANGED,
    LIST_EVENT_UNARCHIVED,
    ListChangeEvent,
)
from app.models.list_snapshot import ListSnapshot
from app.models.owner_change_event import (
    OWNER_EVENT_DEACTIVATED,
    OWNER_EVENT_DELETED,
    OWNER_EVENT_REACTIVATED,
    OwnerChangeEvent,
)
from app.models.owner_snapshot import OwnerSnapshot
from app.models.monitoring_exclusion import (
    EXCLUSION_TYPE_LIST,
    EXCLUSION_TYPE_PROPERTY,
    EXCLUSION_TYPE_TEMPLATE,
    EXCLUSION_TYPE_WORKFLOW,
    MonitoringExclusion,
)
from app.models.portal_setting import PortalSetting
from app.models.property_change_event import (
    PROPERTY_EVENT_ARCHIVED,
    PROPERTY_EVENT_CREATED,
    PROPERTY_EVENT_DELETED,
    PROPERTY_EVENT_RENAMED,
    PROPERTY_EVENT_TYPE_CHANGED,
    PROPERTY_EVENT_UNARCHIVED,
    PropertyChangeEvent,
)
from app.models.property_snapshot import PropertySnapshot
from app.models.workflow_change_event import (
    EVENT_TYPE_CREATED as WORKFLOW_EVENT_CREATED,
    EVENT_TYPE_DELETED as WORKFLOW_EVENT_DELETED,
    EVENT_TYPE_DISABLED as WORKFLOW_EVENT_DISABLED,
    EVENT_TYPE_EDITED as WORKFLOW_EVENT_EDITED,
    EVENT_TYPE_ENABLED as WORKFLOW_EVENT_ENABLED,
    WorkflowChangeEvent,
)
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services.alert_correlation import (
    correlate_email_template_change_event,
    correlate_list_change_event,
    correlate_owner_change_event,
    correlate_property_change_event,
    correlate_unprocessed_events,
    correlate_workflow_change_event,
)
from app.services.monitoring_config import (
    MONITORING_CATEGORY_LIST_ARCHIVED,
    MONITORING_CATEGORY_OWNER_DEACTIVATED,
    MONITORING_CATEGORY_TEMPLATE_ARCHIVED,
    MONITORING_CATEGORY_PROPERTY_ARCHIVED,
    MONITORING_CATEGORY_PROPERTY_TYPE_CHANGED,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _BaseDbCase(unittest.TestCase):
    """SQLite-backed test harness — fresh DB per test method."""

    PORTAL_ID = "1234567"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'alert-test.sqlite')}"
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

    # ------- Seed helpers ---------------------------------------------------

    def _seed_property_snapshot(
        self,
        session,
        *,
        property_name: str,
        object_type_id: str = "0-1",
        label: str = "",
        archived: bool = False,
        type_: str = "string",
    ) -> None:
        session.add(
            PropertySnapshot(
                portal_id=self.PORTAL_ID,
                object_type_id=object_type_id,
                property_name=property_name,
                label=label or property_name,
                type=type_,
                field_type="text",
                archived=archived,
            )
        )

    def _seed_workflow_snapshot(
        self,
        session,
        *,
        workflow_id: str,
        name: str,
        revision_id: str = "1",
    ) -> None:
        session.add(
            WorkflowSnapshot(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                name=name,
                object_type_id="0-1",
                is_enabled=True,
                revision_id=revision_id,
                definition_json="{}",
            )
        )

    def _seed_list_snapshot(
        self,
        session,
        *,
        list_id: str,
        list_name: str = "VIP Contacts",
        is_archived: bool = False,
    ) -> None:
        session.add(
            ListSnapshot(
                portal_id=self.PORTAL_ID,
                list_id=list_id,
                list_name=list_name,
                list_type="DYNAMIC",
                processing_type="DYNAMIC",
                is_archived=is_archived,
                definition_json="{}",
                definition_hash="hash",
            )
        )

    def _seed_template_snapshot(
        self,
        session,
        *,
        template_id: str,
        template_name: str = "Welcome email",
        is_archived: bool = False,
    ) -> None:
        session.add(
            EmailTemplateSnapshot(
                portal_id=self.PORTAL_ID,
                template_id=template_id,
                template_name=template_name,
                template_type="AUTOMATED_EMAIL",
                subject="Welcome",
                is_archived=is_archived,
                definition_json="{}",
                definition_hash="hash",
            )
        )

    def _seed_owner_snapshot(
        self,
        session,
        *,
        owner_id: str,
        email: str = "owner@example.com",
        is_active: bool = True,
    ) -> None:
        session.add(
            OwnerSnapshot(
                portal_id=self.PORTAL_ID,
                owner_id=owner_id,
                email=email,
                is_active=is_active,
            )
        )

    def _seed_dependency(
        self,
        session,
        *,
        workflow_id: str,
        property_name: str,
        object_type_id: str = "0-1",
        location: str = "",
    ) -> None:
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                dependency_type="property",
                dependency_id=property_name,
                dependency_object_type=object_type_id,
                location=location or f"actions[0].fields.property_name",
                revision_id="1",
            )
        )

    def _seed_list_dependency(
        self,
        session,
        *,
        workflow_id: str,
        list_id: str,
        location: str = "",
    ) -> None:
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                dependency_type="list",
                dependency_id=list_id,
                location=location or "enrollmentCriteria.listFilterBranches[0]",
                revision_id="1",
            )
        )

    def _seed_template_dependency(
        self,
        session,
        *,
        workflow_id: str,
        template_id: str,
        location: str = "",
    ) -> None:
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                dependency_type="email_template",
                dependency_id=template_id,
                location=location or "actions[0].fields.email_id",
                revision_id="1",
            )
        )

    def _seed_owner_dependency(
        self,
        session,
        *,
        workflow_id: str,
        owner_id: str,
        location: str = "",
    ) -> None:
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                dependency_type="owner",
                dependency_id=owner_id,
                location=location or "actions[0].fields.owner_id",
                revision_id="1",
            )
        )

    def _seed_property_event(
        self,
        session,
        *,
        property_name: str,
        event_type: str,
        object_type_id: str = "0-1",
        previous_archived: bool | None = None,
        new_archived: bool | None = None,
        previous_type: str | None = None,
        new_type: str | None = None,
        previous_label: str | None = None,
        new_label: str | None = None,
    ) -> PropertyChangeEvent:
        event = PropertyChangeEvent(
            portal_id=self.PORTAL_ID,
            object_type_id=object_type_id,
            property_name=property_name,
            event_type=event_type,
            previous_archived=previous_archived,
            new_archived=new_archived,
            previous_type=previous_type,
            new_type=new_type,
            previous_label=previous_label,
            new_label=new_label,
        )
        session.add(event)
        session.flush()
        return event

    def _seed_workflow_event(
        self,
        session,
        *,
        workflow_id: str,
        event_type: str,
        previous_revision_id: str | None = None,
        new_revision_id: str | None = None,
        previous_is_enabled: bool | None = None,
        new_is_enabled: bool | None = None,
    ) -> WorkflowChangeEvent:
        event = WorkflowChangeEvent(
            portal_id=self.PORTAL_ID,
            workflow_id=workflow_id,
            event_type=event_type,
            previous_revision_id=previous_revision_id,
            new_revision_id=new_revision_id,
            previous_is_enabled=previous_is_enabled,
            new_is_enabled=new_is_enabled,
        )
        session.add(event)
        session.flush()
        return event

    def _seed_list_event(
        self,
        session,
        *,
        list_id: str,
        event_type: str,
        payload: dict | None = None,
    ) -> ListChangeEvent:
        event = ListChangeEvent(
            portal_id=self.PORTAL_ID,
            list_id=list_id,
            event_type=event_type,
            payload_json=json.dumps(payload or {"list_id": list_id}),
        )
        session.add(event)
        session.flush()
        return event

    def _seed_template_event(
        self,
        session,
        *,
        template_id: str,
        event_type: str,
        payload: dict | None = None,
    ) -> EmailTemplateChangeEvent:
        event = EmailTemplateChangeEvent(
            portal_id=self.PORTAL_ID,
            template_id=template_id,
            event_type=event_type,
            payload_json=json.dumps(payload or {"template_id": template_id}),
        )
        session.add(event)
        session.flush()
        return event

    def _seed_owner_event(
        self,
        session,
        *,
        owner_id: str,
        event_type: str,
        payload: dict | None = None,
    ) -> OwnerChangeEvent:
        event = OwnerChangeEvent(
            portal_id=self.PORTAL_ID,
            owner_id=owner_id,
            event_type=event_type,
            payload_json=json.dumps(payload or {"owner_id": owner_id}),
        )
        session.add(event)
        session.flush()
        return event

    def _seed_monitoring_coverage(self, session, coverage: dict) -> None:
        row = session.get(PortalSetting, self.PORTAL_ID)
        if row is None:
            row = PortalSetting(portal_id=self.PORTAL_ID)
            session.add(row)
        row.monitoring_coverage = coverage

    def _seed_monitoring_exclusion(
        self,
        session,
        *,
        exclusion_type: str,
        exclusion_id: str,
        object_type_id: str | None = None,
    ) -> None:
        session.add(
            MonitoringExclusion(
                portal_id=self.PORTAL_ID,
                exclusion_type=exclusion_type,
                exclusion_id=exclusion_id,
                object_type_id=object_type_id,
            )
        )

    def _all_alerts(self, session) -> list[Alert]:
        return session.query(Alert).order_by(Alert.id.asc()).all()


# ===========================================================================
# Property correlation
# ===========================================================================


class PropertyCorrelationTests(_BaseDbCase):
    def test_property_archived_emits_alert_per_impacted_workflow(self) -> None:
        session = self._session()
        try:
            self._seed_property_snapshot(
                session, property_name="lifecyclestage", label="Lifecycle Stage", archived=True,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_workflow_snapshot(session, workflow_id="200", name="Onboarding")
            self._seed_dependency(
                session, workflow_id="100", property_name="lifecyclestage",
                location="actions[3].fields.property_name",
            )
            self._seed_dependency(
                session, workflow_id="200", property_name="lifecyclestage",
                location="enrollmentCriteria.listFilterBranches[0].filters[0].property",
            )
            event = self._seed_property_event(
                session, property_name="lifecyclestage", event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(2, len(alerts))
            for alert in alerts:
                self.assertEqual(SEVERITY_HIGH, alert.severity)
                self.assertEqual(SOURCE_EVENT_PROPERTY_ARCHIVED, alert.source_event_type)
                self.assertEqual("property", alert.source_dependency_type)
                self.assertEqual("lifecyclestage", alert.source_dependency_id)
                self.assertEqual("0-1", alert.source_object_type_id)
                self.assertEqual(STATUS_OPEN, alert.status)
                self.assertIn("archived", alert.title)

            workflow_ids = sorted(a.impacted_workflow_id for a in alerts)
            self.assertEqual(["100", "200"], workflow_ids)

            # The summary should be parseable JSON with the documented shape.
            summary_obj = json.loads(alerts[0].summary)
            self.assertEqual("property_archived", summary_obj["kind"])
            self.assertIn("change", summary_obj)
            self.assertIn("impact", summary_obj)
            self.assertIn("dependency_locations", summary_obj["impact"])
        finally:
            session.close()

    def test_property_archived_with_no_impacted_workflows_emits_no_alerts(self) -> None:
        session = self._session()
        try:
            self._seed_property_snapshot(
                session, property_name="orphan_property", archived=True,
            )
            event = self._seed_property_event(
                session, property_name="orphan_property",
                event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
        finally:
            session.close()

    def test_property_archived_with_category_disabled_marks_processed_no_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_coverage(
                session,
                {
                    MONITORING_CATEGORY_PROPERTY_ARCHIVED: {
                        "enabled": False,
                        "severityOverride": None,
                    }
                },
            )
            self._seed_property_snapshot(
                session, property_name="lifecyclestage", archived=True,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_dependency(
                session, workflow_id="100", property_name="lifecyclestage",
            )
            event = self._seed_property_event(
                session, property_name="lifecyclestage",
                event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(PropertyChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_property_archived_for_excluded_property_marks_processed_no_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_exclusion(
                session,
                exclusion_type=EXCLUSION_TYPE_PROPERTY,
                exclusion_id="lifecyclestage",
                object_type_id="0-1",
            )
            self._seed_property_snapshot(
                session, property_name="lifecyclestage", archived=True,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_dependency(
                session, workflow_id="100", property_name="lifecyclestage",
            )
            event = self._seed_property_event(
                session, property_name="lifecyclestage",
                event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(PropertyChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_property_archived_exclusion_requires_matching_object_type(self) -> None:
        session = self._session()
        try:
            self._seed_monitoring_exclusion(
                session,
                exclusion_type=EXCLUSION_TYPE_PROPERTY,
                exclusion_id="lifecyclestage",
                object_type_id="0-1",
            )
            self._seed_property_snapshot(
                session,
                property_name="lifecyclestage",
                object_type_id="0-2",
                archived=True,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Deal Nurture")
            self._seed_dependency(
                session,
                workflow_id="100",
                property_name="lifecyclestage",
                object_type_id="0-2",
            )
            event = self._seed_property_event(
                session,
                property_name="lifecyclestage",
                object_type_id="0-2",
                event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False,
                new_archived=True,
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_HIGH, alerts[0].severity)
            self.assertEqual("0-2", alerts[0].source_object_type_id)
        finally:
            session.close()

    def test_property_type_change_emits_medium_severity_alert(self) -> None:
        session = self._session()
        try:
            self._seed_property_snapshot(
                session, property_name="score", label="Lead Score", type_="number",
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Score-driven")
            self._seed_dependency(
                session, workflow_id="100", property_name="score",
            )
            event = self._seed_property_event(
                session, property_name="score",
                event_type=PROPERTY_EVENT_TYPE_CHANGED,
                previous_type="number", new_type="string",
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_MEDIUM, alerts[0].severity)
            self.assertEqual(SOURCE_EVENT_PROPERTY_TYPE_CHANGED, alerts[0].source_event_type)
            summary_obj = json.loads(alerts[0].summary)
            self.assertEqual("number", summary_obj["change"]["previous_type"])
            self.assertEqual("string", summary_obj["change"]["new_type"])
        finally:
            session.close()

    def test_property_type_changed_severity_override_can_promote_to_critical(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_coverage(
                session,
                {
                    MONITORING_CATEGORY_PROPERTY_TYPE_CHANGED: {
                        "enabled": True,
                        "severityOverride": SEVERITY_CRITICAL,
                    }
                },
            )
            self._seed_property_snapshot(
                session, property_name="score", label="Lead Score", type_="number",
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Score-driven")
            self._seed_dependency(session, workflow_id="100", property_name="score")
            event = self._seed_property_event(
                session, property_name="score",
                event_type=PROPERTY_EVENT_TYPE_CHANGED,
                previous_type="number", new_type="string",
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_CRITICAL, alerts[0].severity)
        finally:
            session.close()

    def test_default_behavior_unchanged_when_no_monitoring_config_set(self) -> None:
        session = self._session()
        try:
            self._seed_property_snapshot(
                session, property_name="email", label="Email", archived=True,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Mailer")
            self._seed_dependency(session, workflow_id="100", property_name="email")
            event = self._seed_property_event(
                session, property_name="email",
                event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_HIGH, alerts[0].severity)
            self.assertEqual(SOURCE_EVENT_PROPERTY_ARCHIVED, alerts[0].source_event_type)
        finally:
            session.close()

    def test_property_renamed_emits_low_severity_alert(self) -> None:
        session = self._session()
        try:
            self._seed_property_snapshot(
                session, property_name="score", label="Engagement Score",
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Uses score")
            self._seed_dependency(
                session, workflow_id="100", property_name="score",
            )
            event = self._seed_property_event(
                session, property_name="score",
                event_type=PROPERTY_EVENT_RENAMED,
                previous_label="Lead Score", new_label="Engagement Score",
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_LOW, alerts[0].severity)
            self.assertEqual(SOURCE_EVENT_PROPERTY_RENAMED, alerts[0].source_event_type)
            self.assertIn("renamed", alerts[0].title)
        finally:
            session.close()

    def test_property_deleted_emits_high_severity_alert(self) -> None:
        session = self._session()
        try:
            self._seed_property_snapshot(session, property_name="legacy_prop")
            self._seed_workflow_snapshot(session, workflow_id="100", name="Old workflow")
            self._seed_dependency(session, workflow_id="100", property_name="legacy_prop")
            event = self._seed_property_event(
                session, property_name="legacy_prop",
                event_type=PROPERTY_EVENT_DELETED,
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_HIGH, alerts[0].severity)
            self.assertEqual(SOURCE_EVENT_PROPERTY_DELETED, alerts[0].source_event_type)
        finally:
            session.close()

    def test_property_created_emits_no_alert(self) -> None:
        session = self._session()
        try:
            event = self._seed_property_event(
                session, property_name="new_prop",
                event_type=PROPERTY_EVENT_CREATED,
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
        finally:
            session.close()

    def test_property_unarchived_emits_no_alert(self) -> None:
        session = self._session()
        try:
            event = self._seed_property_event(
                session, property_name="recovered",
                event_type=PROPERTY_EVENT_UNARCHIVED,
                previous_archived=True, new_archived=False,
            )
            session.commit()

            alerts = correlate_property_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
        finally:
            session.close()


# ===========================================================================
# List correlation
# ===========================================================================


class ListCorrelationTests(_BaseDbCase):
    def test_list_archived_emits_alert_per_impacted_workflow(self) -> None:
        session = self._session()
        try:
            self._seed_list_snapshot(
                session,
                list_id="77",
                list_name="Lifecycle segment",
                is_archived=True,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_workflow_snapshot(session, workflow_id="200", name="Onboarding")
            self._seed_list_dependency(
                session,
                workflow_id="100",
                list_id="77",
                location="enrollmentCriteria.listFilterBranches[0]",
            )
            self._seed_list_dependency(
                session,
                workflow_id="200",
                list_id="77",
                location="actions[1].fields.static_list_id",
            )
            event = self._seed_list_event(
                session,
                list_id="77",
                event_type=LIST_EVENT_ARCHIVED,
                payload={"list_id": "77", "list_name": "Lifecycle segment"},
            )
            session.commit()

            alerts = correlate_list_change_event(session, event)
            session.commit()

            self.assertEqual(2, len(alerts))
            for alert in alerts:
                self.assertEqual(SEVERITY_HIGH, alert.severity)
                self.assertEqual(SOURCE_EVENT_LIST_ARCHIVED, alert.source_event_type)
                self.assertEqual("list", alert.source_dependency_type)
                self.assertEqual("77", alert.source_dependency_id)
                self.assertEqual(STATUS_OPEN, alert.status)
                self.assertIn("archived", alert.title)

            self.assertEqual(
                ["100", "200"],
                sorted(alert.impacted_workflow_id for alert in alerts),
            )
            summary_obj = json.loads(alerts[0].summary)
            self.assertEqual("list_archived", summary_obj["kind"])
            self.assertIn("dependency_locations", summary_obj["impact"])
        finally:
            session.close()

    def test_list_archived_with_no_impacted_workflows_emits_no_alert(self) -> None:
        session = self._session()
        try:
            self._seed_list_snapshot(session, list_id="77", is_archived=True)
            event = self._seed_list_event(
                session,
                list_id="77",
                event_type=LIST_EVENT_ARCHIVED,
            )
            session.commit()

            alerts = correlate_list_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
        finally:
            session.close()

    def test_list_archived_with_category_disabled_marks_processed_no_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_coverage(
                session,
                {
                    MONITORING_CATEGORY_LIST_ARCHIVED: {
                        "enabled": False,
                        "severityOverride": None,
                    }
                },
            )
            self._seed_list_snapshot(session, list_id="77", is_archived=True)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_list_dependency(session, workflow_id="100", list_id="77")
            event = self._seed_list_event(
                session,
                list_id="77",
                event_type=LIST_EVENT_ARCHIVED,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_list_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(ListChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_list_archived_for_excluded_list_marks_processed_no_alert(self) -> None:
        session = self._session()
        try:
            self._seed_monitoring_exclusion(
                session,
                exclusion_type=EXCLUSION_TYPE_LIST,
                exclusion_id="77",
            )
            self._seed_list_snapshot(session, list_id="77", is_archived=True)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_list_dependency(session, workflow_id="100", list_id="77")
            event = self._seed_list_event(
                session,
                list_id="77",
                event_type=LIST_EVENT_ARCHIVED,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_list_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(ListChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_list_criteria_changed_emits_medium_severity_alert(self) -> None:
        session = self._session()
        try:
            self._seed_list_snapshot(session, list_id="77", list_name="Subscribers")
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_list_dependency(session, workflow_id="100", list_id="77")
            event = self._seed_list_event(
                session,
                list_id="77",
                event_type=LIST_EVENT_CRITERIA_CHANGED,
                payload={
                    "list_id": "77",
                    "previous_definition_hash": "old",
                    "new_definition_hash": "new",
                },
            )
            session.commit()

            alerts = correlate_list_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_MEDIUM, alerts[0].severity)
            self.assertEqual(
                SOURCE_EVENT_LIST_CRITERIA_CHANGED,
                alerts[0].source_event_type,
            )
        finally:
            session.close()

    def test_list_unarchived_emits_no_alert(self) -> None:
        session = self._session()
        try:
            event = self._seed_list_event(
                session,
                list_id="77",
                event_type=LIST_EVENT_UNARCHIVED,
            )
            session.commit()

            alerts = correlate_list_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
        finally:
            session.close()


# ===========================================================================
# Email template correlation
# ===========================================================================


class EmailTemplateCorrelationTests(_BaseDbCase):
    def test_template_archived_emits_alert_per_impacted_workflow(self) -> None:
        session = self._session()
        try:
            self._seed_template_snapshot(
                session,
                template_id="9001",
                template_name="Welcome automation",
                is_archived=True,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_workflow_snapshot(session, workflow_id="200", name="Onboarding")
            self._seed_template_dependency(
                session,
                workflow_id="100",
                template_id="9001",
                location="actions[1].fields.email_id",
            )
            self._seed_template_dependency(
                session,
                workflow_id="200",
                template_id="9001",
                location="actions[3].fields.email_content_id",
            )
            event = self._seed_template_event(
                session,
                template_id="9001",
                event_type=TEMPLATE_EVENT_ARCHIVED,
                payload={"template_id": "9001", "template_name": "Welcome automation"},
            )
            session.commit()

            alerts = correlate_email_template_change_event(session, event)
            session.commit()

            self.assertEqual(2, len(alerts))
            for alert in alerts:
                self.assertEqual(SEVERITY_HIGH, alert.severity)
                self.assertEqual(SOURCE_EVENT_TEMPLATE_ARCHIVED, alert.source_event_type)
                self.assertEqual("email_template", alert.source_dependency_type)
                self.assertEqual("9001", alert.source_dependency_id)
                self.assertEqual(STATUS_OPEN, alert.status)
                self.assertIn("archived", alert.title)

            self.assertEqual(
                ["100", "200"],
                sorted(alert.impacted_workflow_id for alert in alerts),
            )
            summary_obj = json.loads(alerts[0].summary)
            self.assertEqual("template_archived", summary_obj["kind"])
            self.assertIn("dependency_locations", summary_obj["impact"])
        finally:
            session.close()

    def test_template_archived_with_no_impacted_workflows_emits_no_alert(self) -> None:
        session = self._session()
        try:
            self._seed_template_snapshot(session, template_id="9001", is_archived=True)
            event = self._seed_template_event(
                session,
                template_id="9001",
                event_type=TEMPLATE_EVENT_ARCHIVED,
            )
            session.commit()

            alerts = correlate_email_template_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
        finally:
            session.close()

    def test_template_archived_with_category_disabled_marks_processed_no_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_coverage(
                session,
                {
                    MONITORING_CATEGORY_TEMPLATE_ARCHIVED: {
                        "enabled": False,
                        "severityOverride": None,
                    }
                },
            )
            self._seed_template_snapshot(session, template_id="9001", is_archived=True)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_template_dependency(session, workflow_id="100", template_id="9001")
            event = self._seed_template_event(
                session,
                template_id="9001",
                event_type=TEMPLATE_EVENT_ARCHIVED,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_email_template_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(EmailTemplateChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_template_archived_for_excluded_template_marks_processed_no_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_exclusion(
                session,
                exclusion_type=EXCLUSION_TYPE_TEMPLATE,
                exclusion_id="9001",
            )
            self._seed_template_snapshot(session, template_id="9001", is_archived=True)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_template_dependency(session, workflow_id="100", template_id="9001")
            event = self._seed_template_event(
                session,
                template_id="9001",
                event_type=TEMPLATE_EVENT_ARCHIVED,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_email_template_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(EmailTemplateChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_template_edited_emits_medium_severity_alert(self) -> None:
        session = self._session()
        try:
            self._seed_template_snapshot(
                session,
                template_id="9001",
                template_name="Renewal notice",
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Renewal")
            self._seed_template_dependency(session, workflow_id="100", template_id="9001")
            event = self._seed_template_event(
                session,
                template_id="9001",
                event_type=TEMPLATE_EVENT_EDITED,
            )
            session.commit()

            alerts = correlate_email_template_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_MEDIUM, alerts[0].severity)
            self.assertEqual(SOURCE_EVENT_TEMPLATE_EDITED, alerts[0].source_event_type)
            self.assertIn("edited", alerts[0].title)
        finally:
            session.close()

    def test_template_unarchived_emits_no_alert(self) -> None:
        session = self._session()
        try:
            self._seed_template_snapshot(session, template_id="9001", is_archived=False)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_template_dependency(session, workflow_id="100", template_id="9001")
            event = self._seed_template_event(
                session,
                template_id="9001",
                event_type=TEMPLATE_EVENT_UNARCHIVED,
            )
            session.commit()

            summary = correlate_unprocessed_events(session)
            session.commit()

            self.assertEqual(1, summary["events_processed"])
            self.assertEqual(0, summary["alerts_created"])
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(EmailTemplateChangeEvent, event.id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()


# ===========================================================================
# Owner correlation
# ===========================================================================


class OwnerCorrelationTests(_BaseDbCase):
    def test_owner_deactivated_emits_high_alert_per_impacted_workflow(self) -> None:
        session = self._session()
        try:
            self._seed_owner_snapshot(
                session,
                owner_id="501",
                email="inactive.owner@example.com",
                is_active=False,
            )
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_workflow_snapshot(session, workflow_id="200", name="Onboarding")
            self._seed_owner_dependency(
                session,
                workflow_id="100",
                owner_id="501",
                location="actions[0].fields.owner_id",
            )
            self._seed_owner_dependency(
                session,
                workflow_id="200",
                owner_id="501",
                location="actions[2].fields.assignedOwnerId",
            )
            event = self._seed_owner_event(
                session,
                owner_id="501",
                event_type=OWNER_EVENT_DEACTIVATED,
                payload={"owner_id": "501", "email": "inactive.owner@example.com"},
            )
            session.commit()

            alerts = correlate_owner_change_event(session, event)
            session.commit()

            self.assertEqual(2, len(alerts))
            for alert in alerts:
                self.assertEqual(SEVERITY_HIGH, alert.severity)
                self.assertEqual(SOURCE_EVENT_OWNER_DEACTIVATED, alert.source_event_type)
                self.assertEqual("owner", alert.source_dependency_type)
                self.assertEqual("501", alert.source_dependency_id)
                self.assertEqual(STATUS_OPEN, alert.status)
                self.assertIn("deactivated", alert.title)

            self.assertEqual(
                ["100", "200"],
                sorted(alert.impacted_workflow_id for alert in alerts),
            )
            summary_obj = json.loads(alerts[0].summary)
            self.assertEqual("owner_deactivated", summary_obj["kind"])
            self.assertIn("dependency_locations", summary_obj["impact"])
        finally:
            session.close()

    def test_owner_deactivated_without_impacted_workflows_emits_medium_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_owner_snapshot(
                session,
                owner_id="501",
                email="inactive.owner@example.com",
                is_active=False,
            )
            event = self._seed_owner_event(
                session,
                owner_id="501",
                event_type=OWNER_EVENT_DEACTIVATED,
            )
            session.commit()

            alerts = correlate_owner_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_MEDIUM, alerts[0].severity)
            self.assertIsNone(alerts[0].impacted_workflow_id)
        finally:
            session.close()

    def test_owner_deleted_emits_high_alert_even_without_impacted_workflows(self) -> None:
        session = self._session()
        try:
            self._seed_owner_snapshot(
                session,
                owner_id="501",
                email="deleted.owner@example.com",
                is_active=False,
            )
            event = self._seed_owner_event(
                session,
                owner_id="501",
                event_type=OWNER_EVENT_DELETED,
            )
            session.commit()

            alerts = correlate_owner_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_HIGH, alerts[0].severity)
            self.assertEqual(SOURCE_EVENT_OWNER_DELETED, alerts[0].source_event_type)
            self.assertIsNone(alerts[0].impacted_workflow_id)
        finally:
            session.close()

    def test_owner_deactivated_with_category_disabled_marks_processed_no_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_coverage(
                session,
                {
                    MONITORING_CATEGORY_OWNER_DEACTIVATED: {
                        "enabled": False,
                        "severityOverride": None,
                    }
                },
            )
            self._seed_owner_snapshot(session, owner_id="501", is_active=False)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_owner_dependency(session, workflow_id="100", owner_id="501")
            event = self._seed_owner_event(
                session,
                owner_id="501",
                event_type=OWNER_EVENT_DEACTIVATED,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_owner_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(OwnerChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_owner_reactivated_emits_no_alert(self) -> None:
        session = self._session()
        try:
            self._seed_owner_snapshot(session, owner_id="501", is_active=True)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Lead Nurture")
            self._seed_owner_dependency(session, workflow_id="100", owner_id="501")
            event = self._seed_owner_event(
                session,
                owner_id="501",
                event_type=OWNER_EVENT_REACTIVATED,
            )
            session.commit()

            summary = correlate_unprocessed_events(session)
            session.commit()

            self.assertEqual(1, summary["events_processed"])
            self.assertEqual(0, summary["alerts_created"])
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(OwnerChangeEvent, event.id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()


# ===========================================================================
# Workflow correlation
# ===========================================================================


class WorkflowCorrelationTests(_BaseDbCase):
    def test_workflow_disabled_emits_high_severity_alert(self) -> None:
        session = self._session()
        try:
            self._seed_workflow_snapshot(
                session, workflow_id="500", name="Critical routing",
            )
            event = self._seed_workflow_event(
                session, workflow_id="500",
                event_type=WORKFLOW_EVENT_DISABLED,
                previous_is_enabled=True, new_is_enabled=False,
            )
            session.commit()

            alerts = correlate_workflow_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            self.assertEqual(SEVERITY_HIGH, alert.severity)
            self.assertEqual(SOURCE_EVENT_WORKFLOW_DISABLED, alert.source_event_type)
            self.assertEqual("500", alert.impacted_workflow_id)
            self.assertEqual("Critical routing", alert.impacted_workflow_name)
            self.assertIn("disabled", alert.title)
        finally:
            session.close()

    def test_workflow_disabled_for_excluded_workflow_marks_processed_no_alert(
        self,
    ) -> None:
        session = self._session()
        try:
            self._seed_monitoring_exclusion(
                session,
                exclusion_type=EXCLUSION_TYPE_WORKFLOW,
                exclusion_id="500",
            )
            self._seed_workflow_snapshot(
                session, workflow_id="500", name="Critical routing",
            )
            event = self._seed_workflow_event(
                session, workflow_id="500",
                event_type=WORKFLOW_EVENT_DISABLED,
                previous_is_enabled=True, new_is_enabled=False,
            )
            event_id = event.id
            session.commit()

            alerts = correlate_workflow_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
            self.assertEqual(0, len(self._all_alerts(session)))
            refreshed = session.get(WorkflowChangeEvent, event_id)
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_workflow_edited_emits_medium_severity_alert_with_revision_delta(self) -> None:
        session = self._session()
        try:
            self._seed_workflow_snapshot(
                session, workflow_id="500", name="Routing",
            )
            event = self._seed_workflow_event(
                session, workflow_id="500",
                event_type=WORKFLOW_EVENT_EDITED,
                previous_revision_id="5", new_revision_id="6",
            )
            session.commit()

            alerts = correlate_workflow_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            alert = alerts[0]
            self.assertEqual(SEVERITY_MEDIUM, alert.severity)
            self.assertEqual(SOURCE_EVENT_WORKFLOW_EDITED, alert.source_event_type)
            summary_obj = json.loads(alert.summary)
            self.assertEqual("5", summary_obj["change"]["previous_revision_id"])
            self.assertEqual("6", summary_obj["change"]["new_revision_id"])
            self.assertIn("5", alert.title)
            self.assertIn("6", alert.title)
        finally:
            session.close()

    def test_workflow_deleted_emits_high_severity_alert(self) -> None:
        session = self._session()
        try:
            self._seed_workflow_snapshot(session, workflow_id="500", name="Removed")
            event = self._seed_workflow_event(
                session, workflow_id="500", event_type=WORKFLOW_EVENT_DELETED,
            )
            session.commit()

            alerts = correlate_workflow_change_event(session, event)
            session.commit()

            self.assertEqual(1, len(alerts))
            self.assertEqual(SEVERITY_HIGH, alerts[0].severity)
            self.assertEqual(SOURCE_EVENT_WORKFLOW_DELETED, alerts[0].source_event_type)
        finally:
            session.close()

    def test_workflow_created_emits_no_alert(self) -> None:
        session = self._session()
        try:
            self._seed_workflow_snapshot(session, workflow_id="500", name="Brand new")
            event = self._seed_workflow_event(
                session, workflow_id="500", event_type=WORKFLOW_EVENT_CREATED,
            )
            session.commit()

            alerts = correlate_workflow_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
        finally:
            session.close()

    def test_workflow_enabled_emits_no_alert(self) -> None:
        session = self._session()
        try:
            self._seed_workflow_snapshot(session, workflow_id="500", name="Recovered")
            event = self._seed_workflow_event(
                session, workflow_id="500", event_type=WORKFLOW_EVENT_ENABLED,
                previous_is_enabled=False, new_is_enabled=True,
            )
            session.commit()

            alerts = correlate_workflow_change_event(session, event)
            session.commit()

            self.assertEqual(0, len(alerts))
        finally:
            session.close()


# ===========================================================================
# Dedup
# ===========================================================================


class DedupTests(_BaseDbCase):
    def _seed_environment(self, session) -> None:
        self._seed_property_snapshot(
            session, property_name="email", archived=True,
        )
        self._seed_workflow_snapshot(session, workflow_id="100", name="Mailer")
        self._seed_dependency(session, workflow_id="100", property_name="email")

    def test_repeat_within_7_days_increments_repeat_count(self) -> None:
        session = self._session()
        try:
            self._seed_environment(session)
            event_a = self._seed_property_event(
                session, property_name="email", event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            session.commit()

            first = correlate_property_change_event(session, event_a)
            session.commit()
            self.assertEqual(1, len(first))
            self.assertEqual(1, first[0].repeat_count)

            event_b = self._seed_property_event(
                session, property_name="email", event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            session.commit()

            second = correlate_property_change_event(session, event_b)
            session.commit()

            self.assertEqual(1, len(second))
            self.assertEqual(first[0].id, second[0].id)
            self.assertEqual(2, second[0].repeat_count)
            self.assertIsNotNone(second[0].last_repeated_at)

            # Only one alert row in the DB total.
            self.assertEqual(1, len(self._all_alerts(session)))
        finally:
            session.close()

    def test_repeat_after_resolution_creates_new_row(self) -> None:
        session = self._session()
        try:
            self._seed_environment(session)
            event_a = self._seed_property_event(
                session, property_name="email", event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            session.commit()

            first = correlate_property_change_event(session, event_a)
            session.commit()
            self.assertEqual(1, len(first))

            # Resolve the alert, then fire again.
            first[0].status = STATUS_RESOLVED
            first[0].resolved_at = _utc_now()
            session.commit()

            event_b = self._seed_property_event(
                session, property_name="email", event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            session.commit()

            second = correlate_property_change_event(session, event_b)
            session.commit()

            self.assertEqual(1, len(second))
            self.assertNotEqual(first[0].id, second[0].id)
            self.assertEqual(STATUS_OPEN, second[0].status)
            self.assertEqual(2, len(self._all_alerts(session)))
        finally:
            session.close()


# ===========================================================================
# Batch processor — processed_at marking
# ===========================================================================


class BatchProcessorTests(_BaseDbCase):
    def test_correlate_unprocessed_marks_no_alert_events_processed(self) -> None:
        session = self._session()
        try:
            # A `created` event has no alert but should still be marked processed.
            event = self._seed_property_event(
                session, property_name="new_prop", event_type=PROPERTY_EVENT_CREATED,
            )
            session.commit()

            summary = correlate_unprocessed_events(session)

            self.assertEqual(1, summary["events_processed"])
            self.assertEqual(0, summary["alerts_created"])

            # Fetch fresh; processed_at should be set.
            refreshed = (
                session.query(PropertyChangeEvent)
                .filter(PropertyChangeEvent.id == event.id)
                .one()
            )
            self.assertIsNotNone(refreshed.processed_at)
        finally:
            session.close()

    def test_correlate_unprocessed_handles_mixed_event_types(self) -> None:
        session = self._session()
        try:
            self._seed_property_snapshot(session, property_name="email", archived=True)
            self._seed_workflow_snapshot(session, workflow_id="100", name="Mailer")
            self._seed_workflow_snapshot(session, workflow_id="200", name="Disabled one")
            self._seed_dependency(session, workflow_id="100", property_name="email")

            # Property archive (alert) + property created (no alert) +
            # workflow disabled (alert) + workflow enabled (no alert).
            self._seed_property_event(
                session, property_name="email", event_type=PROPERTY_EVENT_ARCHIVED,
                previous_archived=False, new_archived=True,
            )
            self._seed_property_event(
                session, property_name="brand_new", event_type=PROPERTY_EVENT_CREATED,
            )
            self._seed_workflow_event(
                session, workflow_id="200", event_type=WORKFLOW_EVENT_DISABLED,
            )
            self._seed_workflow_event(
                session, workflow_id="200", event_type=WORKFLOW_EVENT_ENABLED,
            )
            session.commit()

            summary = correlate_unprocessed_events(session)

            self.assertEqual(4, summary["events_processed"])
            # 1 alert for archive (1 impacted workflow), 1 alert for disable.
            self.assertEqual(2, summary["alerts_created"])
            self.assertEqual(0, summary["alerts_updated_repeat"])

            # Re-running picks up nothing — every event is now processed.
            second_summary = correlate_unprocessed_events(session)
            self.assertEqual(0, second_summary["events_processed"])
            self.assertEqual(0, second_summary["alerts_created"])
        finally:
            session.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
