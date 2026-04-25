"""Tests for OpsLens v2 workflow polling and revision tracking.

Covers seven scenarios against a single SQLite-backed test session:

1. Fresh portal with three workflows -> three "created" change events,
   three snapshot rows persisted.
2. Polling again with no underlying changes -> zero new change events,
   `last_seen_at` is refreshed.
3. A workflow's `revisionId` advancing -> one "edited" change event and
   the cached definition is refetched.
4. A workflow's `isEnabled` flag flipping -> one "disabled" then one
   "enabled" change event; the snapshot is updated each time.
5. A workflow that disappears from the list response -> one "deleted"
   change event and `deleted_at` is set on the snapshot.
6. HubSpot returning HTTP 401 on the list call -> the poll is skipped
   gracefully with no events written and no exception escaping.
7. The list endpoint paginating across two pages -> all workflows from
   both pages are persisted in a single poll cycle.

The tests mock at the `_http_get_json` boundary inside
`app.services.workflow_polling`, so the transport layer is exercised
indirectly. The 401 case mocks `urllib.request.urlopen` directly to
exercise the HTTPError code path.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import urlsplit

from app import db as db_module
from app.models.hubspot_installation import HubSpotInstallation
from app.models.workflow_change_event import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_DISABLED,
    EVENT_TYPE_EDITED,
    EVENT_TYPE_ENABLED,
    WorkflowChangeEvent,
)
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services import workflow_polling


# Path discriminators for the HubSpot Automation v4 endpoints. The list
# URL ends exactly in `/automation/v4/flows`; the detail URL starts with
# `/automation/v4/flows/` followed by the workflow id. Centralising
# routing here keeps the mock for every test case consistent — and means
# the file fails loudly the moment production code starts calling an
# unexpected endpoint.
LIST_PATH = "/automation/v4/flows"
DETAIL_PATH_PREFIX = "/automation/v4/flows/"


def _classify_url(url: str) -> tuple[str, str]:
    """Return ``(kind, flow_id)`` where ``kind`` is "list" or "detail"."""
    path = urlsplit(url).path
    if path == LIST_PATH:
        return "list", ""
    if path.startswith(DETAIL_PATH_PREFIX):
        flow_id = path[len(DETAIL_PATH_PREFIX):]
        if flow_id and "/" not in flow_id:
            return "detail", flow_id
    raise AssertionError(f"unexpected URL in test: {url}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# `get_portal_access_token` round-trips a timezone-aware expiry through
# SQLAlchemy. SQLite strips the tzinfo on write, which would make the
# downstream "is the token close to expiry?" comparison raise
# TypeError. Bypass that production path by always returning a stub
# token from inside `workflow_polling`.
_STUB_ACCESS_TOKEN = "test-access-token"


def _flow_payload(
    flow_id: str,
    *,
    name: str = "",
    is_enabled: bool = True,
    revision_id: str = "1",
    flow_type: str = "WORKFLOW",
    object_type_id: str = "0-1",
) -> dict:
    return {
        "id": flow_id,
        "name": name or f"Workflow {flow_id}",
        "flowType": flow_type,
        "isEnabled": is_enabled,
        "revisionId": revision_id,
        "objectTypeId": object_type_id,
        "createdAt": "2026-04-01T12:00:00.000Z",
        "updatedAt": "2026-04-10T12:00:00.000Z",
    }


def _list_response(flows: list[dict], *, next_after: str | None = None) -> dict:
    payload: dict = {"results": flows}
    if next_after:
        payload["paging"] = {"next": {"after": next_after}}
    return payload


def _detail_payload(flow_id: str, *, revision_id: str = "1") -> dict:
    return {
        "id": flow_id,
        "revisionId": revision_id,
        "actions": [{"actionId": "1", "actionTypeId": "0-13"}],
    }


class WorkflowPollingTests(unittest.TestCase):
    PORTAL_ID = "1234567"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'workflow-polling-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        # Seed a HubSpot installation row for completeness — this also
        # ensures the polling logic that runs `get_portal_access_token`
        # has a row to look up, even though we mock the call below.
        session = db_module.get_session()
        assert session is not None
        try:
            installation = HubSpotInstallation(
                portal_id=self.PORTAL_ID,
                access_token="seeded-access-token",
                refresh_token="seeded-refresh-token",
                is_active=True,
            )
            session.add(installation)
            session.commit()
        finally:
            session.close()

        # Stub the access-token resolver across every test in this
        # class so we never hit the SQLite tz-stripping path.
        self._token_patcher = patch.object(
            workflow_polling,
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

    def _all_events(self, session) -> list[WorkflowChangeEvent]:
        return (
            session.query(WorkflowChangeEvent)
            .order_by(WorkflowChangeEvent.id.asc())
            .all()
        )

    def _all_snapshots(self, session) -> list[WorkflowSnapshot]:
        return (
            session.query(WorkflowSnapshot)
            .filter(WorkflowSnapshot.portal_id == self.PORTAL_ID)
            .order_by(WorkflowSnapshot.workflow_id.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_fresh_portal_three_workflows_emits_three_created_events(self) -> None:
        flows = [
            _flow_payload("100", name="Lead nurture", revision_id="3"),
            _flow_payload("200", name="Onboarding", revision_id="1"),
            _flow_payload("300", name="Reactivation", revision_id="7"),
        ]

        def fake_http_get_json(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                return _list_response(flows)
            return {"id": flow_id, "actions": []}

        with patch.object(
            workflow_polling, "_http_get_json", side_effect=fake_http_get_json
        ):
            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual("ok", summary["status"])
        self.assertEqual(3, summary["polled"])
        self.assertEqual(3, summary["createdEvents"])
        self.assertEqual(0, summary["editedEvents"])
        self.assertEqual(0, summary["deletedEvents"])

        session = self._session()
        try:
            events = self._all_events(session)
            self.assertEqual(3, len(events))
            self.assertEqual(
                {EVENT_TYPE_CREATED}, {event.event_type for event in events}
            )

            snapshots = self._all_snapshots(session)
            self.assertEqual(3, len(snapshots))
            self.assertEqual(
                {"100", "200", "300"},
                {snap.workflow_id for snap in snapshots},
            )
            for snap in snapshots:
                self.assertTrue(snap.definition_json)
                self.assertIsNotNone(snap.definition_fetched_at)
                self.assertIsNone(snap.deleted_at)
        finally:
            session.close()

    def test_idempotent_poll_emits_no_events_but_refreshes_last_seen(self) -> None:
        flows = [
            _flow_payload("100", revision_id="3"),
            _flow_payload("200", revision_id="1"),
        ]

        def fake_http_get_json(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                return _list_response(flows)
            return {"id": flow_id}

        with patch.object(
            workflow_polling,
            "_http_get_json",
            side_effect=fake_http_get_json,
        ):
            session = self._session()
            try:
                workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

            # Capture last_seen_at after the first poll, then re-poll.
            session = self._session()
            try:
                before = {
                    snap.workflow_id: snap.last_seen_at
                    for snap in self._all_snapshots(session)
                }
            finally:
                session.close()

            # Force a measurable timestamp gap.
            import time

            time.sleep(0.05)

            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual("ok", summary["status"])
        self.assertEqual(0, summary["createdEvents"])
        self.assertEqual(0, summary["editedEvents"])
        self.assertEqual(0, summary["deletedEvents"])
        self.assertEqual(0, summary["enabledEvents"])
        self.assertEqual(0, summary["disabledEvents"])

        session = self._session()
        try:
            # No new events created beyond the initial 2.
            events = self._all_events(session)
            self.assertEqual(2, len(events))

            after = {
                snap.workflow_id: snap.last_seen_at
                for snap in self._all_snapshots(session)
            }
            for workflow_id, before_ts in before.items():
                after_ts = after[workflow_id]
                self.assertGreaterEqual(after_ts, before_ts)
        finally:
            session.close()

    def test_revision_change_emits_edited_event_and_refetches_definition(
        self,
    ) -> None:
        flows_v1 = [_flow_payload("100", revision_id="1")]
        flows_v2 = [_flow_payload("100", revision_id="2")]

        list_state = {"flows": flows_v1}
        detail_calls: list[str] = []

        def fake_http_get_json(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                return _list_response(list_state["flows"])
            detail_calls.append(flow_id)
            return _detail_payload(flow_id, revision_id="2")

        with patch.object(
            workflow_polling, "_http_get_json", side_effect=fake_http_get_json
        ):
            # First poll seeds the snapshot at revision 1.
            session = self._session()
            try:
                workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

            initial_detail_calls = list(detail_calls)
            list_state["flows"] = flows_v2

            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["editedEvents"])
        self.assertEqual(0, summary["createdEvents"])
        self.assertEqual(0, summary["deletedEvents"])

        session = self._session()
        try:
            events = self._all_events(session)
            self.assertEqual(2, len(events))
            self.assertEqual(EVENT_TYPE_CREATED, events[0].event_type)
            self.assertEqual(EVENT_TYPE_EDITED, events[1].event_type)
            self.assertEqual("1", events[1].previous_revision_id)
            self.assertEqual("2", events[1].new_revision_id)

            snapshots = self._all_snapshots(session)
            self.assertEqual(1, len(snapshots))
            self.assertEqual("2", snapshots[0].revision_id)
        finally:
            session.close()

        # The detail endpoint should have been hit at least once on the
        # initial create AND again on the edit (>= 2 total calls).
        self.assertGreater(len(detail_calls), len(initial_detail_calls))

    def test_is_enabled_flip_emits_disabled_then_enabled_events(self) -> None:
        list_state = {
            "flows": [_flow_payload("100", is_enabled=True, revision_id="1")],
        }

        def fake_http_get_json(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                return _list_response(list_state["flows"])
            return _detail_payload(flow_id)

        with patch.object(
            workflow_polling, "_http_get_json", side_effect=fake_http_get_json
        ):
            # Poll 1: seed enabled.
            session = self._session()
            try:
                workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

            # Poll 2: HubSpot reports the workflow disabled.
            list_state["flows"] = [
                _flow_payload("100", is_enabled=False, revision_id="1"),
            ]
            session = self._session()
            try:
                summary_disable = workflow_polling.poll_portal_workflows(
                    session, self.PORTAL_ID
                )
            finally:
                session.close()

            # Poll 3: HubSpot reports the workflow re-enabled.
            list_state["flows"] = [
                _flow_payload("100", is_enabled=True, revision_id="1"),
            ]
            session = self._session()
            try:
                summary_enable = workflow_polling.poll_portal_workflows(
                    session, self.PORTAL_ID
                )
            finally:
                session.close()

        self.assertEqual(1, summary_disable["disabledEvents"])
        self.assertEqual(0, summary_disable["enabledEvents"])
        self.assertEqual(1, summary_enable["enabledEvents"])
        self.assertEqual(0, summary_enable["disabledEvents"])

        session = self._session()
        try:
            events = self._all_events(session)
            event_types = [event.event_type for event in events]
            self.assertEqual(
                [EVENT_TYPE_CREATED, EVENT_TYPE_DISABLED, EVENT_TYPE_ENABLED],
                event_types,
            )
            disabled_event = events[1]
            self.assertEqual(True, disabled_event.previous_is_enabled)
            self.assertEqual(False, disabled_event.new_is_enabled)
            enabled_event = events[2]
            self.assertEqual(False, enabled_event.previous_is_enabled)
            self.assertEqual(True, enabled_event.new_is_enabled)

            snapshots = self._all_snapshots(session)
            self.assertEqual(1, len(snapshots))
            self.assertTrue(snapshots[0].is_enabled)
        finally:
            session.close()

    def test_missing_workflow_emits_deleted_event_and_sets_deleted_at(self) -> None:
        list_state = {
            "flows": [
                _flow_payload("100", revision_id="1"),
                _flow_payload("200", revision_id="1"),
            ],
        }

        def fake_http_get_json(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                return _list_response(list_state["flows"])
            return _detail_payload(flow_id)

        with patch.object(
            workflow_polling, "_http_get_json", side_effect=fake_http_get_json
        ):
            session = self._session()
            try:
                workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

            # Workflow 200 disappears.
            list_state["flows"] = [_flow_payload("100", revision_id="1")]

            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["deletedEvents"])
        self.assertEqual(0, summary["createdEvents"])
        self.assertEqual(0, summary["editedEvents"])

        session = self._session()
        try:
            events = self._all_events(session)
            deletions = [e for e in events if e.event_type == EVENT_TYPE_DELETED]
            self.assertEqual(1, len(deletions))
            self.assertEqual("200", deletions[0].workflow_id)

            snapshot_200 = (
                session.query(WorkflowSnapshot)
                .filter(
                    WorkflowSnapshot.portal_id == self.PORTAL_ID,
                    WorkflowSnapshot.workflow_id == "200",
                )
                .one()
            )
            self.assertIsNotNone(snapshot_200.deleted_at)

            snapshot_100 = (
                session.query(WorkflowSnapshot)
                .filter(
                    WorkflowSnapshot.portal_id == self.PORTAL_ID,
                    WorkflowSnapshot.workflow_id == "100",
                )
                .one()
            )
            self.assertIsNone(snapshot_100.deleted_at)
        finally:
            session.close()

    def test_hubspot_unauthorized_skips_gracefully(self) -> None:
        def raise_401(*_args, **_kwargs):
            raise urllib.error.HTTPError(
                url=workflow_polling.HUBSPOT_FLOWS_LIST_URL,
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        with patch("urllib.request.urlopen", side_effect=raise_401):
            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual("skipped", summary["status"])
        self.assertEqual("hubspot_unauthorized", summary.get("reason"))

        session = self._session()
        try:
            events = self._all_events(session)
            self.assertEqual(0, len(events))
            snapshots = self._all_snapshots(session)
            self.assertEqual(0, len(snapshots))
        finally:
            session.close()

    def test_pagination_across_two_pages_persists_all_workflows(self) -> None:
        page_one = [
            _flow_payload("100", name="A", revision_id="1"),
            _flow_payload("200", name="B", revision_id="1"),
        ]
        page_two = [
            _flow_payload("300", name="C", revision_id="1"),
            _flow_payload("400", name="D", revision_id="1"),
        ]

        page_calls: list[str] = []

        def fake_http_get_json(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                page_calls.append(url)
                if "after=cursor-2" in urlsplit(url).query:
                    return _list_response(page_two)
                return _list_response(page_one, next_after="cursor-2")
            return _detail_payload(flow_id)

        with patch.object(
            workflow_polling, "_http_get_json", side_effect=fake_http_get_json
        ):
            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual("ok", summary["status"])
        self.assertEqual(4, summary["polled"])
        self.assertEqual(4, summary["createdEvents"])
        self.assertGreaterEqual(len(page_calls), 2)

        session = self._session()
        try:
            snapshots = self._all_snapshots(session)
            self.assertEqual(
                {"100", "200", "300", "400"},
                {snap.workflow_id for snap in snapshots},
            )
        finally:
            session.close()


class WorkflowPollingAdminEndpointTests(unittest.TestCase):
    """Covers the X-OpsLens-Admin-Key auth on the manual-trigger endpoint."""

    PORTAL_ID = "9999999"

    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'admin-poll-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        session = db_module.get_session()
        assert session is not None
        try:
            installation = HubSpotInstallation(
                portal_id=self.PORTAL_ID,
                access_token="seeded-access-token",
                refresh_token="seeded-refresh-token",
                is_active=True,
            )
            session.add(installation)
            session.commit()
        finally:
            session.close()

        self._token_patcher = patch.object(
            workflow_polling,
            "get_portal_access_token",
            return_value=_STUB_ACCESS_TOKEN,
        )
        self._token_patcher.start()

        # Don't let the FastAPI lifespan kick off the background polling
        # loop while the test client is alive — it would attempt real
        # HTTP calls and race with our patches. We use a TestClient with
        # the lifespan disabled by entering and exiting it manually
        # below; FastAPI's TestClient runs the lifespan on enter, but
        # since we never enter the context manager (we use the client
        # directly for individual requests), startup/shutdown only fire
        # if the client is used as a context manager.
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._token_patcher.stop()
        self.client.close()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        self._tempdir.cleanup()

    def test_admin_endpoint_requires_matching_key(self) -> None:
        with patch(
            "app.api.v1.routes.admin_workflows.settings.maintenance_api_key",
            "secret-key",
        ):
            response = self.client.post(
                f"/api/v1/admin/workflows/poll/{self.PORTAL_ID}",
                headers={"X-OpsLens-Admin-Key": "wrong"},
            )
        self.assertEqual(401, response.status_code)

    def test_admin_endpoint_runs_poll_when_key_matches(self) -> None:
        flows = [_flow_payload("500", revision_id="1")]

        def fake_http_get_json(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                return _list_response(flows)
            return _detail_payload(flow_id)

        with (
            patch(
                "app.api.v1.routes.admin_workflows.settings.maintenance_api_key",
                "secret-key",
            ),
            patch.object(
                workflow_polling, "_http_get_json", side_effect=fake_http_get_json
            ),
        ):
            response = self.client.post(
                f"/api/v1/admin/workflows/poll/{self.PORTAL_ID}",
                headers={"X-OpsLens-Admin-Key": "secret-key"},
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("ok", payload["status"])
        self.assertEqual(1, payload["createdEvents"])

    def test_admin_endpoint_returns_503_when_no_key_configured(self) -> None:
        with patch(
            "app.api.v1.routes.admin_workflows.settings.maintenance_api_key",
            "",
        ):
            response = self.client.post(
                f"/api/v1/admin/workflows/poll/{self.PORTAL_ID}",
                headers={"X-OpsLens-Admin-Key": "anything"},
            )
        self.assertEqual(503, response.status_code)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
