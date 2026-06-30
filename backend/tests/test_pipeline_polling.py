from __future__ import annotations

import io
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

from app import db as db_module
from app.models.pipeline_change_event import (
    PIPELINE_EVENT_ARCHIVED,
    PIPELINE_EVENT_DELETED,
    PIPELINE_EVENT_RENAMED,
    PIPELINE_EVENT_STAGE_ADDED,
    PIPELINE_EVENT_STAGE_REMOVED,
    PIPELINE_EVENT_STAGE_RENAMED,
    PIPELINE_EVENT_STAGE_REORDERED,
    PipelineChangeEvent,
)
from app.models.pipeline_snapshot import PipelineSnapshot
from app.services import pipeline_polling


_STUB_ACCESS_TOKEN = "test-access-token"


def _stage(stage_id: str, label: str, order: int) -> dict:
    return {
        "id": stage_id,
        "label": label,
        "displayOrder": order,
        "archived": False,
        "metadata": {"isClosed": "false", "probability": "0.2"},
    }


def _pipeline_payload(
    pipeline_id: str,
    *,
    label: str | None = None,
    archived: bool = False,
    stages: list[dict] | None = None,
) -> dict:
    return {
        "id": pipeline_id,
        "label": label or f"Pipeline {pipeline_id}",
        "displayOrder": 0,
        "archived": archived,
        "stages": stages
        if stages is not None
        else [_stage("s1", "Appointment", 0), _stage("s2", "Closed Won", 1)],
    }


class PipelinePollingTests(unittest.TestCase):
    PORTAL_ID = "8675309"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'pipeline-polling-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        self._token_patcher = patch.object(
            pipeline_polling,
            "get_portal_access_token",
            return_value=_STUB_ACCESS_TOKEN,
        )
        self._token_patcher.start()

    def tearDown(self) -> None:
        self._token_patcher.stop()
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

    def _all_events(self, session) -> list[PipelineChangeEvent]:
        return (
            session.query(PipelineChangeEvent)
            .filter(PipelineChangeEvent.portal_id == self.PORTAL_ID)
            .order_by(PipelineChangeEvent.id.asc())
            .all()
        )

    def _all_snapshots(self, session) -> list[PipelineSnapshot]:
        return (
            session.query(PipelineSnapshot)
            .filter(PipelineSnapshot.portal_id == self.PORTAL_ID)
            .order_by(PipelineSnapshot.pipeline_id.asc())
            .all()
        )

    def _make_fake_http(self, active_state, archived_state=None):
        archived_state = archived_state or []

        def fake(url: str, _token: str) -> dict:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            archived = params.get("archived", ["false"])[0] == "true"
            return {"results": list(archived_state if archived else active_state)}

        return fake

    def _poll(self, session, active, archived=None):
        return pipeline_polling.poll_portal_pipelines(
            session, self.PORTAL_ID, self._make_fake_http(active, archived)
        )

    def test_fresh_portal_emits_no_change_events_for_baseline(self) -> None:
        session = self._session()
        try:
            summary = self._poll(session, [_pipeline_payload("default"), _pipeline_payload("p2")])
            self.assertEqual("ok", summary["status"])
            self.assertEqual(2, summary["polled"])
            self.assertEqual(0, summary["events_emitted"])
            self.assertEqual([], self._all_events(session))
            self.assertEqual(2, len(self._all_snapshots(session)))
        finally:
            session.close()

    def test_stage_renamed_emits_event(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("default")])
            renamed = _pipeline_payload(
                "default",
                stages=[_stage("s1", "First Touch", 0), _stage("s2", "Closed Won", 1)],
            )
            summary = self._poll(session, [renamed])
            self.assertEqual(1, summary["stageRenamedEvents"])
            self.assertEqual(
                [PIPELINE_EVENT_STAGE_RENAMED],
                [e.event_type for e in self._all_events(session)],
            )
        finally:
            session.close()

    def test_stage_removed_emits_event(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("default")])
            shrunk = _pipeline_payload("default", stages=[_stage("s1", "Appointment", 0)])
            summary = self._poll(session, [shrunk])
            self.assertEqual(1, summary["stageRemovedEvents"])
            self.assertEqual(
                [PIPELINE_EVENT_STAGE_REMOVED],
                [e.event_type for e in self._all_events(session)],
            )
        finally:
            session.close()

    def test_stage_added_emits_event(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("default")])
            grown = _pipeline_payload(
                "default",
                stages=[
                    _stage("s1", "Appointment", 0),
                    _stage("s2", "Closed Won", 1),
                    _stage("s3", "Negotiation", 2),
                ],
            )
            summary = self._poll(session, [grown])
            self.assertEqual(1, summary["stageAddedEvents"])
            self.assertEqual(
                [PIPELINE_EVENT_STAGE_ADDED],
                [e.event_type for e in self._all_events(session)],
            )
        finally:
            session.close()

    def test_stage_reordered_emits_event(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("default")])
            swapped = _pipeline_payload(
                "default",
                stages=[_stage("s1", "Appointment", 1), _stage("s2", "Closed Won", 0)],
            )
            summary = self._poll(session, [swapped])
            self.assertEqual(1, summary["stageReorderedEvents"])
            self.assertEqual(
                [PIPELINE_EVENT_STAGE_REORDERED],
                [e.event_type for e in self._all_events(session)],
            )
        finally:
            session.close()

    def test_pipeline_renamed_emits_event(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("p2", label="Sales")])
            summary = self._poll(session, [_pipeline_payload("p2", label="Enterprise Sales")])
            self.assertEqual(1, summary["renamedEvents"])
            self.assertEqual(
                [PIPELINE_EVENT_RENAMED],
                [e.event_type for e in self._all_events(session)],
            )
        finally:
            session.close()

    def test_pipeline_archived_emits_event(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("p2")])
            summary = self._poll(
                session, [], archived=[_pipeline_payload("p2", archived=True)]
            )
            self.assertEqual(1, summary["archivedEvents"])
            self.assertEqual(
                [PIPELINE_EVENT_ARCHIVED],
                [e.event_type for e in self._all_events(session)],
            )
        finally:
            session.close()

    def test_disappeared_pipeline_emits_deleted_event(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("default"), _pipeline_payload("p2")])
            summary = self._poll(session, [_pipeline_payload("default")])
            self.assertEqual(1, summary["deletedEvents"])
            self.assertEqual(
                [PIPELINE_EVENT_DELETED],
                [e.event_type for e in self._all_events(session)],
            )
            gone = (
                session.query(PipelineSnapshot)
                .filter(
                    PipelineSnapshot.portal_id == self.PORTAL_ID,
                    PipelineSnapshot.pipeline_id == "p2",
                )
                .one()
            )
            self.assertIsNotNone(gone.deleted_at)
        finally:
            session.close()

    def test_empty_fetch_does_not_mass_delete(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("default"), _pipeline_payload("p2")])
            # Transient API glitch: both active + archived return nothing.
            summary = self._poll(session, [])
            self.assertEqual(0, summary["deletedEvents"])
            self.assertEqual([], self._all_events(session))
            for snap in self._all_snapshots(session):
                self.assertIsNone(snap.deleted_at)
        finally:
            session.close()

    def test_idempotent_poll_emits_no_events(self) -> None:
        session = self._session()
        try:
            self._poll(session, [_pipeline_payload("default")])
            summary = self._poll(session, [_pipeline_payload("default")])
            self.assertEqual(0, summary["events_emitted"])
            self.assertEqual([], self._all_events(session))
        finally:
            session.close()

    def test_401_skips_portal_gracefully(self) -> None:
        def fake_http(url: str, _token: str) -> dict:
            raise urllib.error.HTTPError(
                url=url, code=401, msg="Unauthorized", hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        session = self._session()
        try:
            summary = pipeline_polling.poll_portal_pipelines(
                session, self.PORTAL_ID, fake_http
            )
            self.assertEqual("skipped", summary["status"])
            self.assertEqual("hubspot_unauthorized", summary["reason"])
            self.assertEqual(0, summary["events_emitted"])
        finally:
            session.close()

    def test_429_aborts_portal_cycle(self) -> None:
        def fake_http(url: str, _token: str) -> dict:
            raise urllib.error.HTTPError(
                url=url, code=429, msg="Too Many Requests", hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        session = self._session()
        try:
            summary = pipeline_polling.poll_portal_pipelines(
                session, self.PORTAL_ID, fake_http
            )
            self.assertEqual("error", summary["status"])
            self.assertEqual("hubspot_rate_limited", summary["reason"])
            self.assertEqual(0, summary["events_emitted"])
        finally:
            session.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
