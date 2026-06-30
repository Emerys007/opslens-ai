from __future__ import annotations

import json
import os
import tempfile
import unittest

from app import db as db_module
from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SOURCE_EVENT_PIPELINE_ARCHIVED,
    SOURCE_EVENT_PIPELINE_DELETED,
    SOURCE_EVENT_PIPELINE_RENAMED,
    SOURCE_EVENT_PIPELINE_STAGE_REMOVED,
    SOURCE_EVENT_PIPELINE_STAGE_RENAMED,
    SOURCE_EVENT_PIPELINE_STAGE_REORDERED,
    STATUS_OPEN,
    Alert,
)
from app.models.pipeline_change_event import (
    PIPELINE_EVENT_ARCHIVED,
    PIPELINE_EVENT_DELETED,
    PIPELINE_EVENT_RENAMED,
    PIPELINE_EVENT_STAGE_ADDED,
    PIPELINE_EVENT_STAGE_REMOVED,
    PIPELINE_EVENT_STAGE_RENAMED,
    PIPELINE_EVENT_STAGE_REORDERED,
    PIPELINE_EVENT_UNARCHIVED,
    PipelineChangeEvent,
)
from app.models.pipeline_snapshot import PipelineSnapshot
from app.models.portal_entitlement import PortalEntitlement
from app.models.portal_setting import PortalSetting
from app.services.alert_correlation import (
    correlate_pipeline_change_event,
    correlate_unprocessed_events,
)
from app.services.monitoring_config import MONITORING_CATEGORY_PIPELINE_STAGE_REMOVED


class PipelineCorrelationTests(unittest.TestCase):
    PORTAL_ID = "51300126"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'pipeline-corr.sqlite')}"
        )
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()
        self.session = self._open_session()

    def tearDown(self) -> None:
        self.session.close()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        self._tempdir.cleanup()

    def _open_session(self):
        s = db_module.get_session()
        self.assertIsNotNone(s)
        return s

    def _seed_snapshot(self, *, pipeline_id="default", label="Sales Pipeline"):
        self.session.add(
            PipelineSnapshot(
                portal_id=self.PORTAL_ID,
                pipeline_id=pipeline_id,
                label=label,
                is_active=True,
                stages_json="[]",
            )
        )
        self.session.commit()

    def _seed_event(self, *, event_type, pipeline_id="default", payload=None):
        ev = PipelineChangeEvent(
            portal_id=self.PORTAL_ID,
            pipeline_id=pipeline_id,
            event_type=event_type,
            payload_json=json.dumps(payload or {}),
        )
        self.session.add(ev)
        self.session.commit()
        self.session.refresh(ev)
        return ev

    def _seed_entitlement(self, plan):
        self.session.add(
            PortalEntitlement(
                portal_id=self.PORTAL_ID,
                plan=plan,
                billing_interval="monthly",
                subscription_status="active",
                trial_approved=False,
            )
        )
        self.session.commit()

    def _seed_coverage(self, coverage):
        row = self.session.get(PortalSetting, self.PORTAL_ID)
        if row is None:
            row = PortalSetting(portal_id=self.PORTAL_ID)
            self.session.add(row)
        row.monitoring_coverage = coverage
        self.session.commit()

    def _correlate(self, event):
        alerts = correlate_pipeline_change_event(self.session, event)
        self.session.commit()
        return alerts

    # -- severity / mapping ------------------------------------------------

    def test_stage_removed_emits_high_alert(self) -> None:
        self._seed_snapshot()
        event = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_REMOVED,
            payload={"pipeline_id": "default", "stage_id": "s2", "stage_label": "Closed Won"},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        alert = alerts[0]
        self.assertEqual(SEVERITY_HIGH, alert.severity)
        self.assertEqual(SOURCE_EVENT_PIPELINE_STAGE_REMOVED, alert.source_event_type)
        self.assertEqual("pipeline", alert.source_dependency_type)
        self.assertEqual("default:s2", alert.source_dependency_id)
        self.assertEqual(STATUS_OPEN, alert.status)
        self.assertIsNone(alert.impacted_workflow_id)
        self.assertIn("removed", alert.title.lower())
        self.assertIn("Closed Won", alert.title)
        summary_obj = json.loads(alert.summary)
        self.assertEqual(SOURCE_EVENT_PIPELINE_STAGE_REMOVED, summary_obj["kind"])
        self.assertIsNone(summary_obj["impact"])

    def test_pipeline_archived_emits_high_alert(self) -> None:
        self._seed_snapshot()
        event = self._seed_event(
            event_type=PIPELINE_EVENT_ARCHIVED,
            payload={"pipeline_id": "default", "label": "Sales Pipeline"},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        self.assertEqual(SEVERITY_HIGH, alerts[0].severity)
        self.assertEqual(SOURCE_EVENT_PIPELINE_ARCHIVED, alerts[0].source_event_type)
        self.assertEqual("default", alerts[0].source_dependency_id)
        self.assertIn("archived", alerts[0].title.lower())

    def test_pipeline_deleted_emits_high_alert(self) -> None:
        self._seed_snapshot()
        event = self._seed_event(
            event_type=PIPELINE_EVENT_DELETED,
            payload={"pipeline_id": "default", "label": "Sales Pipeline"},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        self.assertEqual(SEVERITY_HIGH, alerts[0].severity)
        self.assertEqual(SOURCE_EVENT_PIPELINE_DELETED, alerts[0].source_event_type)

    def test_stage_renamed_emits_low_alert(self) -> None:
        self._seed_snapshot()
        event = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_RENAMED,
            payload={
                "pipeline_id": "default",
                "stage_id": "s1",
                "previous_label": "Appointment",
                "new_label": "First Touch",
            },
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        self.assertEqual(SEVERITY_LOW, alerts[0].severity)
        self.assertEqual(SOURCE_EVENT_PIPELINE_STAGE_RENAMED, alerts[0].source_event_type)
        self.assertIn("renamed", alerts[0].title.lower())

    def test_stage_reordered_emits_medium_alert(self) -> None:
        self._seed_snapshot()
        event = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_REORDERED,
            payload={"pipeline_id": "default", "previous_order": ["s1", "s2"], "new_order": ["s2", "s1"]},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        self.assertEqual(SEVERITY_MEDIUM, alerts[0].severity)
        self.assertEqual(SOURCE_EVENT_PIPELINE_STAGE_REORDERED, alerts[0].source_event_type)

    def test_pipeline_renamed_emits_low_alert(self) -> None:
        self._seed_snapshot(label="Enterprise Sales")
        event = self._seed_event(
            event_type=PIPELINE_EVENT_RENAMED,
            payload={"pipeline_id": "default", "previous_label": "Sales", "new_label": "Enterprise Sales"},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        self.assertEqual(SEVERITY_LOW, alerts[0].severity)
        self.assertEqual(SOURCE_EVENT_PIPELINE_RENAMED, alerts[0].source_event_type)

    # -- gating ------------------------------------------------------------

    def test_category_disabled_marks_processed_no_alert(self) -> None:
        self._seed_snapshot()
        self._seed_coverage(
            {MONITORING_CATEGORY_PIPELINE_STAGE_REMOVED: {"enabled": False, "severityOverride": None}}
        )
        event = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_REMOVED,
            payload={"pipeline_id": "default", "stage_id": "s2"},
        )
        alerts = self._correlate(event)
        refreshed = self.session.get(PipelineChangeEvent, event.id)
        self.assertEqual([], alerts)
        self.assertIsNotNone(refreshed.processed_at)

    def test_gated_out_below_agency_plan(self) -> None:
        self._seed_snapshot()
        self._seed_entitlement("professional")  # pipeline is Agency-only
        event = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_REMOVED,
            payload={"pipeline_id": "default", "stage_id": "s2"},
        )
        self.assertEqual([], self._correlate(event))

    def test_emitted_for_agency_plan(self) -> None:
        self._seed_snapshot()
        self._seed_entitlement("agency")
        event = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_REMOVED,
            payload={"pipeline_id": "default", "stage_id": "s2"},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        self.assertEqual(SEVERITY_HIGH, alerts[0].severity)

    def test_unarchived_event_emits_no_alert(self) -> None:
        self._seed_snapshot()
        event = self._seed_event(
            event_type=PIPELINE_EVENT_UNARCHIVED,
            payload={"pipeline_id": "default", "label": "Sales Pipeline"},
        )
        self.assertEqual([], correlate_pipeline_change_event(self.session, event))
        counters = correlate_unprocessed_events(self.session)
        refreshed = self.session.get(PipelineChangeEvent, event.id)
        self.assertIsNotNone(refreshed.processed_at)
        self.assertEqual(0, int(counters.get("alerts_created") or 0))

    def test_stage_removals_dedup_independently_per_stage(self) -> None:
        self._seed_snapshot()
        e1 = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_REMOVED,
            payload={"pipeline_id": "default", "stage_id": "s2", "stage_label": "Closed Won"},
        )
        e2 = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_REMOVED,
            payload={"pipeline_id": "default", "stage_id": "s3", "stage_label": "Negotiation"},
        )
        correlate_pipeline_change_event(self.session, e1)
        correlate_pipeline_change_event(self.session, e2)
        self.session.commit()
        count = self.session.query(Alert).filter(Alert.portal_id == self.PORTAL_ID).count()
        # Two different stages -> two distinct alerts (different dependency id).
        self.assertEqual(2, count)

    def test_stage_added_emits_low_alert(self) -> None:
        self._seed_snapshot()
        event = self._seed_event(
            event_type=PIPELINE_EVENT_STAGE_ADDED,
            payload={"pipeline_id": "default", "stage_id": "s9", "stage_label": "Discovery"},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        self.assertEqual(SEVERITY_LOW, alerts[0].severity)
        self.assertIn("added", alerts[0].title.lower())

    def test_same_stage_repeat_dedups(self) -> None:
        self._seed_snapshot()
        payload = {"pipeline_id": "default", "stage_id": "s2", "stage_label": "Closed Won"}
        correlate_pipeline_change_event(
            self.session, self._seed_event(event_type=PIPELINE_EVENT_STAGE_REMOVED, payload=payload)
        )
        correlate_pipeline_change_event(
            self.session, self._seed_event(event_type=PIPELINE_EVENT_STAGE_REMOVED, payload=payload)
        )
        self.session.commit()
        rows = self.session.query(Alert).filter(Alert.portal_id == self.PORTAL_ID).all()
        # Same stage repeats -> one row, repeat_count bumped (not a new alert).
        self.assertEqual(1, len(rows))
        self.assertEqual(2, rows[0].repeat_count)

    def test_severity_override_is_honored(self) -> None:
        self._seed_snapshot()
        self._seed_coverage(
            {SOURCE_EVENT_PIPELINE_RENAMED: {"enabled": True, "severityOverride": "high"}}
        )
        event = self._seed_event(
            event_type=PIPELINE_EVENT_RENAMED,
            payload={"pipeline_id": "default", "new_label": "X"},
        )
        alerts = self._correlate(event)
        self.assertEqual(1, len(alerts))
        # Default for rename is LOW; the per-portal override forces HIGH.
        self.assertEqual(SEVERITY_HIGH, alerts[0].severity)


if __name__ == "__main__":
    unittest.main()
