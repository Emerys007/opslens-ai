"""Tests for `app.services.ticket_delivery`.

Mocks the seam at `load_portal_ticket_pipeline_config` and at
`urllib.request.urlopen` for the POST. Real HubSpot is never hit.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch

from app import db as db_module
from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_KIND_PROPERTY,
    STATUS_OPEN,
    Alert,
)
from app.models.portal_setting import PortalSetting
from app.services import ticket_delivery
from app.services.hubspot_ticket_pipeline import (
    PortalProvisioningRequiredError,
    TicketPipelineConfig,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_PIPELINE_CONFIG = TicketPipelineConfig(
    portal_id="12345",
    pipeline_id="pipeline-opslens",
    pipeline_label="OpsLens Alerts",
    stage_new_alert="stage-new",
    stage_investigating="stage-investigating",
    stage_waiting="stage-waiting",
    stage_resolved="stage-resolved",
    stage_duplicate="stage-duplicate",
)


class _FakeResponse:
    def __init__(self, *, status: int = 201, body: bytes = b'{"id":"ticket-9999"}'):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _BaseTicketCase(unittest.TestCase):
    PORTAL_ID = "12345"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'ticket-delivery-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        # Default: stub the portal access token resolver across every test.
        self._token_patcher = patch.object(
            ticket_delivery,
            "get_portal_access_token",
            return_value="seeded-access-token",
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

    def _seed_settings(
        self,
        session,
        *,
        threshold: str = "medium",
        ticket_enabled: bool = True,
    ) -> None:
        session.add(
            PortalSetting(
                portal_id=self.PORTAL_ID,
                slack_webhook_url="",
                alert_threshold=threshold,
                slack_delivery_enabled=True,
                ticket_delivery_enabled=ticket_enabled,
            )
        )
        session.commit()

    def _seed_alert(
        self,
        session,
        *,
        severity: str = SEVERITY_HIGH,
        title: str = "Property archived",
        hubspot_ticket_id: str | None = None,
    ) -> Alert:
        alert = Alert(
            portal_id=self.PORTAL_ID,
            alert_signature=f"sig-{title}-{severity}",
            severity=severity,
            status=STATUS_OPEN,
            source_event_type=SOURCE_EVENT_PROPERTY_ARCHIVED,
            source_event_kind=SOURCE_KIND_PROPERTY,
            source_dependency_type="property",
            source_dependency_id="lifecyclestage",
            source_object_type_id="0-1",
            impacted_workflow_id="67890",
            impacted_workflow_name="Lead Nurture",
            title=title,
            summary='{"kind":"property_archived"}',
            hubspot_ticket_id=hubspot_ticket_id,
            repeat_count=1,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert


# ---------------------------------------------------------------------------
# deliver_alert_to_ticket
# ---------------------------------------------------------------------------


class DeliverAlertToTicketTests(_BaseTicketCase):
    def test_happy_path_creates_ticket_and_stamps_id(self) -> None:
        captured: dict = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = request.data.decode("utf-8")
            captured["headers"] = dict(request.header_items())
            return _FakeResponse(status=201, body=b'{"id":"ticket-42"}')

        session = self._session()
        try:
            self._seed_settings(session)
            alert = self._seed_alert(session)

            with (
                patch.object(
                    ticket_delivery, "load_portal_ticket_pipeline_config",
                    return_value=_PIPELINE_CONFIG,
                ),
                patch("urllib.request.urlopen", side_effect=fake_urlopen),
            ):
                ticket_id = ticket_delivery.deliver_alert_to_ticket(session, alert)
            session.commit()
            session.refresh(alert)
        finally:
            session.close()

        self.assertEqual("ticket-42", ticket_id)
        self.assertEqual("ticket-42", alert.hubspot_ticket_id)
        # Properties payload should carry the OpsLens custom keys.
        body = json.loads(captured["body"])
        props = body["properties"]
        self.assertEqual("pipeline-opslens", props["hs_pipeline"])
        self.assertEqual("stage-new", props["hs_pipeline_stage"])
        self.assertEqual(str(alert.id), props["opslens_alert_id"])
        self.assertEqual("high", props["opslens_severity"])
        self.assertTrue(props["opslens_signature"])

    def test_alert_with_existing_ticket_id_is_skipped(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session)
            alert = self._seed_alert(session, hubspot_ticket_id="existing-7")

            with (
                patch.object(
                    ticket_delivery, "load_portal_ticket_pipeline_config",
                ) as mock_pipeline,
                patch("urllib.request.urlopen") as mock_urlopen,
            ):
                ticket_id = ticket_delivery.deliver_alert_to_ticket(session, alert)
                mock_pipeline.assert_not_called()
                mock_urlopen.assert_not_called()
        finally:
            session.close()

        # The function returns the existing id unchanged.
        self.assertEqual("existing-7", ticket_id)

    def test_pipeline_lookup_failure_returns_none(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session)
            alert = self._seed_alert(session)

            with (
                patch.object(
                    ticket_delivery, "load_portal_ticket_pipeline_config",
                    side_effect=PortalProvisioningRequiredError("pipeline missing"),
                ),
                patch("urllib.request.urlopen") as mock_urlopen,
            ):
                ticket_id = ticket_delivery.deliver_alert_to_ticket(session, alert)
                mock_urlopen.assert_not_called()
        finally:
            session.close()

        self.assertIsNone(ticket_id)
        self.assertIsNone(alert.hubspot_ticket_id)

    def test_4xx_on_create_returns_none_and_does_not_stamp(self) -> None:
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                url=request.full_url, code=400, msg="Bad Request",
                hdrs=None, fp=io.BytesIO(b'{"message":"invalid property"}'),
            )

        session = self._session()
        try:
            self._seed_settings(session)
            alert = self._seed_alert(session)

            with (
                patch.object(
                    ticket_delivery, "load_portal_ticket_pipeline_config",
                    return_value=_PIPELINE_CONFIG,
                ),
                patch("urllib.request.urlopen", side_effect=fake_urlopen),
            ):
                ticket_id = ticket_delivery.deliver_alert_to_ticket(session, alert)
        finally:
            session.close()

        self.assertIsNone(ticket_id)
        self.assertIsNone(alert.hubspot_ticket_id)


# ---------------------------------------------------------------------------
# deliver_pending_tickets (batch)
# ---------------------------------------------------------------------------


class DeliverPendingTicketsTests(_BaseTicketCase):
    def test_below_threshold_alerts_are_skipped(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session, threshold=SEVERITY_HIGH)
            self._seed_alert(session, severity=SEVERITY_LOW, title="low")
            self._seed_alert(session, severity=SEVERITY_HIGH, title="high")

            with (
                patch.object(
                    ticket_delivery, "load_portal_ticket_pipeline_config",
                    return_value=_PIPELINE_CONFIG,
                ),
                patch("urllib.request.urlopen", return_value=_FakeResponse()),
            ):
                summary = ticket_delivery.deliver_pending_tickets(session)
        finally:
            session.close()

        self.assertEqual(1, summary["attempted"])
        self.assertEqual(1, summary["succeeded"])
        self.assertEqual(1, summary["skipped_below_threshold"])

    def test_portal_level_disable_skips_entire_portal(self) -> None:
        session = self._session()
        try:
            self._seed_settings(session, ticket_enabled=False)
            self._seed_alert(session, severity=SEVERITY_HIGH, title="suppressed")

            with (
                patch.object(ticket_delivery, "load_portal_ticket_pipeline_config") as mock_pipeline,
                patch("urllib.request.urlopen") as mock_urlopen,
            ):
                summary = ticket_delivery.deliver_pending_tickets(session)
                mock_pipeline.assert_not_called()
                mock_urlopen.assert_not_called()
        finally:
            session.close()

        self.assertEqual(0, summary["attempted"])
        self.assertGreaterEqual(summary["skipped_disabled_or_unconfigured"], 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
