"""HTTP-level tests for the admin endpoints in
`app.api.v1.routes.admin_workflows`. Auth, payload shape, and the
forward/reverse dependency lookups.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app
from app.models.hubspot_installation import HubSpotInstallation
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_snapshot import WorkflowSnapshot


class AdminWorkflowEndpointTests(unittest.TestCase):
    PORTAL_ID = "55555"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'admin-workflows-test.sqlite')}"
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
            # Two workflows with overlapping property dependencies for
            # reverse-query coverage.
            session.add(
                WorkflowSnapshot(
                    portal_id=self.PORTAL_ID,
                    workflow_id="100",
                    name="Lead Nurture",
                    object_type_id="0-1",
                    is_enabled=True,
                    revision_id="1",
                    definition_json="{}",
                )
            )
            session.add(
                WorkflowSnapshot(
                    portal_id=self.PORTAL_ID,
                    workflow_id="200",
                    name="Onboarding",
                    object_type_id="0-1",
                    is_enabled=True,
                    revision_id="1",
                    definition_json="{}",
                )
            )
            for workflow_id in ("100", "200"):
                session.add(
                    WorkflowDependency(
                        portal_id=self.PORTAL_ID,
                        workflow_id=workflow_id,
                        dependency_type="property",
                        dependency_id="lifecyclestage",
                        dependency_object_type="0-1",
                        location=f"actions[0].fields.property_name",
                        revision_id="1",
                    )
                )
            # A list dependency on workflow 100 only.
            session.add(
                WorkflowDependency(
                    portal_id=self.PORTAL_ID,
                    workflow_id="100",
                    dependency_type="list",
                    dependency_id="42",
                    location="actions[1].fields.list_id",
                    revision_id="1",
                )
            )
            # An email-template dependency on workflow 200.
            session.add(
                WorkflowDependency(
                    portal_id=self.PORTAL_ID,
                    workflow_id="200",
                    dependency_type="email_template",
                    dependency_id="9001",
                    location="actions[2].fields.email_id",
                    revision_id="1",
                )
            )
            # A company-scoped property dependency for object-type filtering.
            session.add(
                WorkflowDependency(
                    portal_id=self.PORTAL_ID,
                    workflow_id="200",
                    dependency_type="property",
                    dependency_id="industry",
                    dependency_object_type="0-2",
                    location="actions[3].fields.property_name",
                    revision_id="1",
                )
            )
            session.commit()
        finally:
            session.close()

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        self._tempdir.cleanup()

    def _patched_admin_key(self):
        return patch(
            "app.api.v1.routes.admin_workflows.settings.maintenance_api_key",
            "secret-key",
        )

    # ------------------------------------------------------------------
    # Forward query: a single workflow's dependencies
    # ------------------------------------------------------------------

    def test_list_dependencies_for_workflow_returns_persisted_rows(self) -> None:
        with self._patched_admin_key():
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/100/dependencies",
                headers={"X-OpsLens-Admin-Key": "secret-key"},
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(self.PORTAL_ID, payload["portalId"])
        self.assertEqual("100", payload["workflowId"])
        self.assertEqual(2, payload["count"])
        types = sorted(d["dependency_type"] for d in payload["dependencies"])
        self.assertEqual(["list", "property"], types)

    def test_list_dependencies_requires_admin_key(self) -> None:
        with self._patched_admin_key():
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/100/dependencies",
                headers={"X-OpsLens-Admin-Key": "wrong"},
            )
        self.assertEqual(401, response.status_code)

    # ------------------------------------------------------------------
    # Reverse query: workflows affected by a property
    # ------------------------------------------------------------------

    def test_reverse_property_query_returns_affected_workflows(self) -> None:
        with self._patched_admin_key():
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/dependencies/property/lifecyclestage",
                headers={"X-OpsLens-Admin-Key": "secret-key"},
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("lifecyclestage", payload["propertyName"])
        self.assertEqual(2, payload["count"])
        ids = sorted(w["workflow_id"] for w in payload["workflows"])
        self.assertEqual(["100", "200"], ids)

    def test_reverse_property_query_with_object_type_scopes_results(self) -> None:
        with self._patched_admin_key():
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/dependencies/property/industry",
                params={"objectTypeId": "0-2"},
                headers={"X-OpsLens-Admin-Key": "secret-key"},
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("0-2", payload["objectTypeId"])
        ids = [w["workflow_id"] for w in payload["workflows"]]
        self.assertEqual(["200"], ids)

    def test_reverse_property_query_requires_admin_key(self) -> None:
        with self._patched_admin_key():
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/dependencies/property/lifecyclestage",
                headers={"X-OpsLens-Admin-Key": "wrong"},
            )
        self.assertEqual(401, response.status_code)

    # ------------------------------------------------------------------
    # Reverse query: workflows affected by a list / email template
    # ------------------------------------------------------------------

    def test_reverse_list_query(self) -> None:
        with self._patched_admin_key():
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/dependencies/list/42",
                headers={"X-OpsLens-Admin-Key": "secret-key"},
            )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("42", payload["listId"])
        self.assertEqual(["100"], [w["workflow_id"] for w in payload["workflows"]])

    def test_reverse_email_template_query(self) -> None:
        with self._patched_admin_key():
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/dependencies/email-template/9001",
                headers={"X-OpsLens-Admin-Key": "secret-key"},
            )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("9001", payload["templateId"])
        self.assertEqual(["200"], [w["workflow_id"] for w in payload["workflows"]])

    def test_no_admin_key_configured_returns_503(self) -> None:
        with patch(
            "app.api.v1.routes.admin_workflows.settings.maintenance_api_key",
            "",
        ):
            response = self.client.get(
                f"/api/v1/admin/workflows/{self.PORTAL_ID}/100/dependencies",
                headers={"X-OpsLens-Admin-Key": "anything"},
            )
        self.assertEqual(503, response.status_code)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
