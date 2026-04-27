from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app
from app.models.monitoring_exclusion import (
    EXCLUSION_TYPE_PROPERTY,
    EXCLUSION_TYPE_WORKFLOW,
    MonitoringExclusion,
)
from app.services.monitoring_config import (
    MONITORING_CATEGORIES,
    MONITORING_CATEGORY_PROPERTY_ARCHIVED,
    MONITORING_CATEGORY_PROPERTY_DELETED,
    MONITORING_CATEGORY_WORKFLOW_EDITED,
)


class MonitoringConfigEndpointTests(unittest.TestCase):
    PORTAL_ID = "51300126"
    OTHER_PORTAL_ID = "99999999"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'monitoring-test.sqlite')}"
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

    def _seed_exclusion(
        self,
        session,
        *,
        portal_id: str | None = None,
        exclusion_type: str = EXCLUSION_TYPE_WORKFLOW,
        exclusion_id: str = "12345",
        object_type_id: str | None = None,
    ) -> MonitoringExclusion:
        row = MonitoringExclusion(
            portal_id=portal_id or self.PORTAL_ID,
            exclusion_type=exclusion_type,
            exclusion_id=exclusion_id,
            object_type_id=object_type_id,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def test_default_config_returned_when_no_override_set(self) -> None:
        response = self.client.get(
            f"/api/v1/dashboard/monitoring-coverage?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        coverage = payload["coverage"]

        self.assertEqual(set(MONITORING_CATEGORIES), set(coverage.keys()))
        for category in MONITORING_CATEGORIES:
            self.assertTrue(coverage[category]["enabled"])
            self.assertIsNone(coverage[category]["severityOverride"])

        defaults = {row["name"]: row["defaultSeverity"] for row in payload["categories"]}
        self.assertEqual("high", defaults[MONITORING_CATEGORY_PROPERTY_ARCHIVED])

    def test_put_updates_only_specified_categories_and_leaves_others_default(
        self,
    ) -> None:
        response = self.client.put(
            f"/api/v1/dashboard/monitoring-coverage?portalId={self.PORTAL_ID}",
            json={
                MONITORING_CATEGORY_PROPERTY_DELETED: {
                    "enabled": True,
                    "severityOverride": "critical",
                },
                MONITORING_CATEGORY_WORKFLOW_EDITED: {
                    "enabled": False,
                    "severityOverride": None,
                },
            },
        )
        self.assertEqual(200, response.status_code)
        coverage = response.json()["coverage"]

        self.assertTrue(coverage[MONITORING_CATEGORY_PROPERTY_ARCHIVED]["enabled"])
        self.assertIsNone(
            coverage[MONITORING_CATEGORY_PROPERTY_ARCHIVED]["severityOverride"]
        )
        self.assertEqual(
            "critical",
            coverage[MONITORING_CATEGORY_PROPERTY_DELETED]["severityOverride"],
        )
        self.assertFalse(coverage[MONITORING_CATEGORY_WORKFLOW_EDITED]["enabled"])

    def test_put_with_invalid_category_name_returns_400(self) -> None:
        response = self.client.put(
            f"/api/v1/dashboard/monitoring-coverage?portalId={self.PORTAL_ID}",
            json={"workflow_deleted": {"enabled": False, "severityOverride": None}},
        )
        self.assertEqual(400, response.status_code)

    def test_put_with_invalid_severity_returns_400(self) -> None:
        response = self.client.put(
            f"/api/v1/dashboard/monitoring-coverage?portalId={self.PORTAL_ID}",
            json={
                MONITORING_CATEGORY_PROPERTY_ARCHIVED: {
                    "enabled": True,
                    "severityOverride": "urgent",
                }
            },
        )
        self.assertEqual(400, response.status_code)

    def test_post_exclusion_creates_row(self) -> None:
        response = self.client.post(
            f"/api/v1/dashboard/exclusions?portalId={self.PORTAL_ID}&userId=user-123",
            json={
                "type": "workflow",
                "id": "12345",
                "reason": "deprecated",
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()

        self.assertEqual(EXCLUSION_TYPE_WORKFLOW, payload["type"])
        self.assertEqual("12345", payload["exclusionId"])
        self.assertIsNone(payload["objectTypeId"])
        self.assertEqual("deprecated", payload["reason"])
        self.assertEqual("user-123", payload["createdByUserId"])

    def test_post_duplicate_exclusion_returns_409(self) -> None:
        first = self.client.post(
            f"/api/v1/dashboard/exclusions?portalId={self.PORTAL_ID}",
            json={"type": "workflow", "id": "12345"},
        )
        second = self.client.post(
            f"/api/v1/dashboard/exclusions?portalId={self.PORTAL_ID}",
            json={"type": "workflow", "id": "12345"},
        )

        self.assertEqual(200, first.status_code)
        self.assertEqual(409, second.status_code)

    def test_delete_exclusion_of_another_portal_returns_404(self) -> None:
        session = self._session()
        try:
            row = self._seed_exclusion(session, portal_id=self.OTHER_PORTAL_ID)
            exclusion_id = row.id
        finally:
            session.close()

        response = self.client.delete(
            f"/api/v1/dashboard/exclusions/{exclusion_id}?portalId={self.PORTAL_ID}"
        )
        self.assertEqual(404, response.status_code)

    def test_get_exclusions_filtered_by_type_returns_only_matching_rows(self) -> None:
        session = self._session()
        try:
            self._seed_exclusion(
                session,
                exclusion_type=EXCLUSION_TYPE_WORKFLOW,
                exclusion_id="workflow-1",
            )
            self._seed_exclusion(
                session,
                exclusion_type=EXCLUSION_TYPE_PROPERTY,
                exclusion_id="lead_source",
                object_type_id="0-1",
            )
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/dashboard/exclusions?portalId={self.PORTAL_ID}&type=property"
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()

        self.assertEqual(1, len(payload))
        self.assertEqual(EXCLUSION_TYPE_PROPERTY, payload[0]["type"])
        self.assertEqual("lead_source", payload[0]["exclusionId"])
        self.assertEqual("0-1", payload[0]["objectTypeId"])


if __name__ == "__main__":
    unittest.main()
