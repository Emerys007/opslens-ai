"""DB-backed tests for the dependency map.

Covers persistence, rebuild on revision change, deletion-on-workflow-
removal, and the reverse-index queries
(`find_workflows_affected_by_property`, `_by_list`,
`_by_email_template`).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlsplit

from app import db as db_module
from app.models.hubspot_installation import HubSpotInstallation
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_snapshot import WorkflowSnapshot
from app.services import workflow_polling
from app.services.dependency_mapping import (
    find_workflows_affected_by_email_template,
    find_workflows_affected_by_list,
    find_workflows_affected_by_property,
    list_workflow_dependencies,
    rebuild_workflow_dependencies,
)


_STUB_ACCESS_TOKEN = "test-access-token"

LIST_PATH = "/automation/v4/flows"
DETAIL_PATH_PREFIX = "/automation/v4/flows/"


def _classify_url(url: str) -> tuple[str, str]:
    path = urlsplit(url).path
    if path == LIST_PATH:
        return "list", ""
    if path.startswith(DETAIL_PATH_PREFIX):
        flow_id = path[len(DETAIL_PATH_PREFIX):]
        if flow_id and "/" not in flow_id:
            return "detail", flow_id
    raise AssertionError(f"unexpected URL in test: {url}")


def _flow_summary(flow_id: str, *, name: str = "", revision_id: str = "1", is_enabled: bool = True) -> dict:
    return {
        "id": flow_id,
        "name": name or f"Workflow {flow_id}",
        "flowType": "WORKFLOW",
        "isEnabled": is_enabled,
        "revisionId": revision_id,
        "objectTypeId": "0-1",
        "createdAt": "2026-04-01T12:00:00.000Z",
        "updatedAt": "2026-04-10T12:00:00.000Z",
    }


def _detail_with_property(flow_id: str, property_name: str, *, revision_id: str = "1") -> dict:
    return {
        "id": flow_id,
        "revisionId": revision_id,
        "objectTypeId": "0-1",
        "actions": [
            {
                "actionId": "1",
                "actionTypeId": "0-13",
                "fields": {"property_name": property_name, "value": "lead"},
            },
        ],
    }


class DependencyMappingPollingTests(unittest.TestCase):
    """Exercise dependency rebuild via the polling cycle."""

    PORTAL_ID = "12345"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'dep-mapping-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        session = db_module.get_session()
        assert session is not None
        try:
            session.add(
                HubSpotInstallation(
                    portal_id=self.PORTAL_ID,
                    access_token="seeded-access-token",
                    refresh_token="seeded-refresh-token",
                    is_active=True,
                )
            )
            session.commit()
        finally:
            session.close()

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

    def _all_dependencies(self, session) -> list[WorkflowDependency]:
        return (
            session.query(WorkflowDependency)
            .filter(WorkflowDependency.portal_id == self.PORTAL_ID)
            .order_by(WorkflowDependency.id.asc())
            .all()
        )

    def _make_fake_http(self, list_state: dict, detail_state: dict):
        def fake(url: str, _token: str) -> dict:
            kind, flow_id = _classify_url(url)
            if kind == "list":
                return {"results": list_state["flows"]}
            return detail_state.get(flow_id, {"id": flow_id, "actions": []})
        return fake

    def test_fresh_poll_persists_dependencies(self) -> None:
        list_state = {"flows": [_flow_summary("100", revision_id="1")]}
        detail_state = {"100": _detail_with_property("100", "lifecyclestage")}

        with patch.object(
            workflow_polling, "_http_get_json",
            side_effect=self._make_fake_http(list_state, detail_state),
        ):
            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["createdEvents"])
        self.assertEqual(1, summary["dependenciesRebuilt"])

        session = self._session()
        try:
            deps = self._all_dependencies(session)
            self.assertEqual(1, len(deps))
            self.assertEqual("property", deps[0].dependency_type)
            self.assertEqual("lifecyclestage", deps[0].dependency_id)
            self.assertEqual("100", deps[0].workflow_id)
        finally:
            session.close()

    def test_revision_change_rebuilds_dependencies(self) -> None:
        list_state = {"flows": [_flow_summary("100", revision_id="1")]}
        detail_state = {"100": _detail_with_property("100", "lifecyclestage", revision_id="1")}

        with patch.object(
            workflow_polling, "_http_get_json",
            side_effect=self._make_fake_http(list_state, detail_state),
        ):
            session = self._session()
            try:
                workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        session = self._session()
        try:
            initial_deps = self._all_dependencies(session)
            self.assertEqual(1, len(initial_deps))
            self.assertEqual("lifecyclestage", initial_deps[0].dependency_id)
        finally:
            session.close()

        # Revision advances; new definition references a different property.
        list_state["flows"] = [_flow_summary("100", revision_id="2")]
        detail_state["100"] = _detail_with_property("100", "industry", revision_id="2")

        with patch.object(
            workflow_polling, "_http_get_json",
            side_effect=self._make_fake_http(list_state, detail_state),
        ):
            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["editedEvents"])
        self.assertEqual(1, summary["dependenciesRebuilt"])

        session = self._session()
        try:
            new_deps = self._all_dependencies(session)
            # Old `lifecyclestage` dep is gone; new `industry` dep is present.
            self.assertEqual(1, len(new_deps))
            self.assertEqual("industry", new_deps[0].dependency_id)
            self.assertEqual("2", new_deps[0].revision_id)
        finally:
            session.close()

    def test_workflow_deletion_removes_dependency_rows(self) -> None:
        list_state = {
            "flows": [
                _flow_summary("100", revision_id="1"),
                _flow_summary("200", revision_id="1"),
            ],
        }
        detail_state = {
            "100": _detail_with_property("100", "lifecyclestage"),
            "200": _detail_with_property("200", "industry"),
        }

        with patch.object(
            workflow_polling, "_http_get_json",
            side_effect=self._make_fake_http(list_state, detail_state),
        ):
            session = self._session()
            try:
                workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        session = self._session()
        try:
            self.assertEqual(2, len(self._all_dependencies(session)))
        finally:
            session.close()

        # Workflow 200 disappears in next poll.
        list_state["flows"] = [_flow_summary("100", revision_id="1")]

        with patch.object(
            workflow_polling, "_http_get_json",
            side_effect=self._make_fake_http(list_state, detail_state),
        ):
            session = self._session()
            try:
                summary = workflow_polling.poll_portal_workflows(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["deletedEvents"])

        session = self._session()
        try:
            remaining = self._all_dependencies(session)
            self.assertEqual(1, len(remaining))
            self.assertEqual("100", remaining[0].workflow_id)
        finally:
            session.close()


class ReverseQueryTests(unittest.TestCase):
    """Direct tests of the reverse-index queries against seeded rows."""

    PORTAL_ID = "99999"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'dep-reverse-test.sqlite')}"
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

    def _seed_snapshot(
        self,
        session,
        workflow_id: str,
        *,
        name: str,
        deleted: bool = False,
    ) -> None:
        snap = WorkflowSnapshot(
            portal_id=self.PORTAL_ID,
            workflow_id=workflow_id,
            name=name,
            object_type_id="0-1",
            is_enabled=True,
            revision_id="1",
            definition_json="{}",
        )
        session.add(snap)
        if deleted:
            snap.deleted_at = datetime.now(timezone.utc)

    def _seed_dependency(
        self,
        session,
        *,
        workflow_id: str,
        dependency_type: str,
        dependency_id: str,
        dependency_object_type: str | None = None,
        location: str = "",
    ) -> None:
        session.add(
            WorkflowDependency(
                portal_id=self.PORTAL_ID,
                workflow_id=workflow_id,
                dependency_type=dependency_type,
                dependency_id=dependency_id,
                dependency_object_type=dependency_object_type,
                location=location or f"actions[0].fields.{dependency_type}",
                revision_id="1",
            )
        )

    def test_find_workflows_affected_by_property_returns_matching_workflows(self) -> None:
        session = self._session()
        try:
            self._seed_snapshot(session, "100", name="Lead Nurture")
            self._seed_snapshot(session, "200", name="Onboarding")
            self._seed_snapshot(session, "300", name="Reactivation")
            self._seed_dependency(
                session, workflow_id="100",
                dependency_type="property", dependency_id="lifecyclestage",
                dependency_object_type="0-1",
            )
            self._seed_dependency(
                session, workflow_id="200",
                dependency_type="property", dependency_id="lifecyclestage",
                dependency_object_type="0-1",
            )
            self._seed_dependency(
                session, workflow_id="300",
                dependency_type="property", dependency_id="industry",
                dependency_object_type="0-1",
            )
            session.commit()

            results = find_workflows_affected_by_property(
                session, self.PORTAL_ID, "lifecyclestage",
            )
            workflow_ids = sorted(r["workflow_id"] for r in results)
            self.assertEqual(["100", "200"], workflow_ids)
            names = {r["workflow_id"]: r["workflow_name"] for r in results}
            self.assertEqual("Lead Nurture", names["100"])
            self.assertEqual("Onboarding", names["200"])
        finally:
            session.close()

    def test_object_type_filter_scopes_property_lookup(self) -> None:
        session = self._session()
        try:
            self._seed_snapshot(session, "100", name="Contact-side")
            self._seed_snapshot(session, "200", name="Company-side")
            self._seed_dependency(
                session, workflow_id="100",
                dependency_type="property", dependency_id="email",
                dependency_object_type="0-1",
            )
            self._seed_dependency(
                session, workflow_id="200",
                dependency_type="property", dependency_id="email",
                dependency_object_type="0-2",
            )
            session.commit()

            contact_only = find_workflows_affected_by_property(
                session, self.PORTAL_ID, "email", object_type_id="0-1",
            )
            self.assertEqual(["100"], [r["workflow_id"] for r in contact_only])

            company_only = find_workflows_affected_by_property(
                session, self.PORTAL_ID, "email", object_type_id="0-2",
            )
            self.assertEqual(["200"], [r["workflow_id"] for r in company_only])

            unscoped = find_workflows_affected_by_property(
                session, self.PORTAL_ID, "email",
            )
            self.assertEqual({"100", "200"}, {r["workflow_id"] for r in unscoped})
        finally:
            session.close()

    def test_deleted_workflow_excluded_from_reverse_query(self) -> None:
        session = self._session()
        try:
            self._seed_snapshot(session, "100", name="Active")
            self._seed_snapshot(session, "200", name="Removed", deleted=True)
            self._seed_dependency(
                session, workflow_id="100",
                dependency_type="property", dependency_id="email",
            )
            self._seed_dependency(
                session, workflow_id="200",
                dependency_type="property", dependency_id="email",
            )
            session.commit()

            results = find_workflows_affected_by_property(
                session, self.PORTAL_ID, "email",
            )
            self.assertEqual(["100"], [r["workflow_id"] for r in results])
        finally:
            session.close()

    def test_find_workflows_affected_by_list(self) -> None:
        session = self._session()
        try:
            self._seed_snapshot(session, "100", name="ListUser")
            self._seed_dependency(
                session, workflow_id="100",
                dependency_type="list", dependency_id="42",
            )
            session.commit()

            results = find_workflows_affected_by_list(session, self.PORTAL_ID, "42")
            self.assertEqual(1, len(results))
            self.assertEqual("100", results[0]["workflow_id"])
        finally:
            session.close()

    def test_find_workflows_affected_by_email_template(self) -> None:
        session = self._session()
        try:
            self._seed_snapshot(session, "100", name="Sender")
            self._seed_dependency(
                session, workflow_id="100",
                dependency_type="email_template", dependency_id="9001",
            )
            session.commit()

            results = find_workflows_affected_by_email_template(
                session, self.PORTAL_ID, "9001",
            )
            self.assertEqual(["100"], [r["workflow_id"] for r in results])
        finally:
            session.close()

    def test_rebuild_uses_snapshot_definition_json(self) -> None:
        session = self._session()
        try:
            snap = WorkflowSnapshot(
                portal_id=self.PORTAL_ID,
                workflow_id="500",
                name="Direct rebuild",
                object_type_id="0-1",
                is_enabled=True,
                revision_id="3",
                definition_json=json.dumps(
                    {
                        "objectTypeId": "0-1",
                        "actions": [
                            {
                                "actionTypeId": "0-13",
                                "fields": {"property_name": "industry"},
                            }
                        ],
                    }
                ),
            )
            session.add(snap)
            session.commit()

            summary = rebuild_workflow_dependencies(session, self.PORTAL_ID, "500")
            self.assertEqual(1, summary["dependencies_extracted"])
            self.assertEqual({"property": 1}, summary["by_type"])

            forward = list_workflow_dependencies(session, self.PORTAL_ID, "500")
            self.assertEqual(1, len(forward))
            self.assertEqual("industry", forward[0]["dependency_id"])
            self.assertEqual("3", forward[0]["revision_id"])
        finally:
            session.close()

    def test_rebuild_with_invalid_json_clears_existing_rows(self) -> None:
        session = self._session()
        try:
            snap = WorkflowSnapshot(
                portal_id=self.PORTAL_ID,
                workflow_id="600",
                name="Bad JSON",
                object_type_id="0-1",
                is_enabled=True,
                revision_id="1",
                definition_json="this is not json",
            )
            session.add(snap)
            self._seed_dependency(
                session, workflow_id="600",
                dependency_type="property", dependency_id="stale",
            )
            session.commit()

            summary = rebuild_workflow_dependencies(session, self.PORTAL_ID, "600")
            self.assertEqual("invalid_definition_json", summary["status"])

            remaining = list_workflow_dependencies(session, self.PORTAL_ID, "600")
            self.assertEqual([], remaining)
        finally:
            session.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
