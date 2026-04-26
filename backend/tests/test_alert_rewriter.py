"""Tests for `app.services.alert_rewriter`.

Mocks the HTTP layer at `urllib.request.urlopen` and the kill-switch
config via `patch.object(app.config.settings, ...)`.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from app import db as db_module
from app.config import settings as app_settings
from app.models.alert import (
    SEVERITY_HIGH,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_KIND_PROPERTY,
    STATUS_OPEN,
    Alert,
)
from app.services import alert_rewriter


class _FakeResponse:
    def __init__(self, *, status: int = 200, body: bytes = b""):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _anthropic_response_body(text: str) -> bytes:
    payload = {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5-20251001",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    return json.dumps(payload).encode("utf-8")


class _BaseRewriterCase(unittest.TestCase):
    """SQLite-backed harness with two patcher setups: API key + kill switch."""

    PORTAL_ID = "12345"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'rewriter-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        # Default to "rewriter enabled with a fake key" — individual
        # tests can override either via patch.object below.
        self._key_patcher = patch.object(app_settings, "anthropic_api_key", "sk-test-key")
        self._enabled_patcher = patch.object(app_settings, "alert_rewriter_enabled", True)
        self._key_patcher.start()
        self._enabled_patcher.start()

    def tearDown(self) -> None:
        self._enabled_patcher.stop()
        self._key_patcher.stop()
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

    def _seed_alert(
        self,
        session,
        *,
        title: str = "Property archived",
        plain_english_explanation: str | None = None,
        recommended_action: str | None = None,
    ) -> Alert:
        alert = Alert(
            portal_id=self.PORTAL_ID,
            alert_signature=f"sig-{title}",
            severity=SEVERITY_HIGH,
            status=STATUS_OPEN,
            source_event_type=SOURCE_EVENT_PROPERTY_ARCHIVED,
            source_event_kind=SOURCE_KIND_PROPERTY,
            source_dependency_type="property",
            source_dependency_id="lifecyclestage",
            source_object_type_id="0-1",
            impacted_workflow_id="67890",
            impacted_workflow_name="Lead Nurture",
            title=title,
            summary=json.dumps(
                {
                    "kind": "property_archived",
                    "change": {
                        "property_label": "Lifecycle Stage",
                        "property_name": "lifecyclestage",
                    },
                    "impact": {
                        "workflow_id": "67890",
                        "workflow_name": "Lead Nurture",
                        "dependency_locations": ["actions[3].fields.property_name"],
                    },
                }
            ),
            plain_english_explanation=plain_english_explanation,
            recommended_action=recommended_action,
            repeat_count=1,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert


# ---------------------------------------------------------------------------
# rewrite_alert
# ---------------------------------------------------------------------------


class RewriteAlertTests(_BaseRewriterCase):
    def test_happy_path_calls_api_and_writes_explanation_and_action(self) -> None:
        captured: dict = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return _FakeResponse(
                status=200,
                body=_anthropic_response_body(
                    "EXPLANATION: The lifecyclestage property was archived; the Lead Nurture workflow's set-property action will fail at the next enrollment.\n\n"
                    "ACTION: Restore lifecyclestage or rewire the action to a replacement property."
                ),
            )

        session = self._session()
        try:
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok = alert_rewriter.rewrite_alert(session, alert)
            session.commit()
            session.refresh(alert)
        finally:
            session.close()

        self.assertTrue(ok)
        self.assertEqual(alert_rewriter.ANTHROPIC_URL, captured["url"])
        # Header lookups in urllib normalize key case to title-case.
        normalized_headers = {k.lower(): v for k, v in captured["headers"].items()}
        self.assertEqual("sk-test-key", normalized_headers["x-api-key"])
        self.assertEqual(alert_rewriter.ANTHROPIC_VERSION, normalized_headers["anthropic-version"])
        self.assertEqual(alert_rewriter.ANTHROPIC_MODEL, captured["body"]["model"])
        self.assertEqual(alert_rewriter.SYSTEM_PROMPT, captured["body"]["system"])
        self.assertEqual(1, len(captured["body"]["messages"]))
        self.assertEqual("user", captured["body"]["messages"][0]["role"])

        self.assertIn("Lead Nurture", alert.plain_english_explanation)
        self.assertIn("lifecyclestage", alert.plain_english_explanation)
        self.assertIn("Restore", alert.recommended_action)

    def test_already_rewritten_alert_is_skipped_silently(self) -> None:
        session = self._session()
        try:
            alert = self._seed_alert(
                session,
                plain_english_explanation="prior text",
                recommended_action="prior action",
            )

            with patch("urllib.request.urlopen") as mock_urlopen:
                ok = alert_rewriter.rewrite_alert(session, alert)
                mock_urlopen.assert_not_called()
        finally:
            session.close()

        self.assertFalse(ok)
        self.assertEqual("prior text", alert.plain_english_explanation)
        self.assertEqual("prior action", alert.recommended_action)

    def test_4xx_returns_false_and_leaves_fields_null(self) -> None:
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                url=request.full_url, code=429, msg="Too Many Requests",
                hdrs=None, fp=io.BytesIO(b'{"error":{"type":"rate_limit"}}'),
            )

        session = self._session()
        try:
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok = alert_rewriter.rewrite_alert(session, alert)
        finally:
            session.close()

        self.assertFalse(ok)
        self.assertIsNone(alert.plain_english_explanation)
        self.assertIsNone(alert.recommended_action)

    def test_malformed_response_missing_markers_returns_false(self) -> None:
        def fake_urlopen(request, timeout):
            return _FakeResponse(
                status=200,
                body=_anthropic_response_body(
                    "I will tell you about this alert. The property was archived."
                ),
            )

        session = self._session()
        try:
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok = alert_rewriter.rewrite_alert(session, alert)
        finally:
            session.close()

        self.assertFalse(ok)
        self.assertIsNone(alert.plain_english_explanation)
        self.assertIsNone(alert.recommended_action)

    def test_200_with_valid_response_populates_fields_correctly(self) -> None:
        def fake_urlopen(request, timeout):
            return _FakeResponse(
                status=200,
                body=_anthropic_response_body(
                    "EXPLANATION: Workflow 'Onboarding' was disabled; new contacts will not enter the sequence.\n\n"
                    "ACTION: Re-enable Onboarding in the workflow editor and verify enrollment criteria."
                ),
            )

        session = self._session()
        try:
            alert = self._seed_alert(session)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ok = alert_rewriter.rewrite_alert(session, alert)
        finally:
            session.close()

        self.assertTrue(ok)
        self.assertEqual(
            "Workflow 'Onboarding' was disabled; new contacts will not enter the sequence.",
            alert.plain_english_explanation,
        )
        self.assertEqual(
            "Re-enable Onboarding in the workflow editor and verify enrollment criteria.",
            alert.recommended_action,
        )


# ---------------------------------------------------------------------------
# Kill switch / no key
# ---------------------------------------------------------------------------


class RewriterDisabledTests(_BaseRewriterCase):
    def test_kill_switch_off_skips_all_alerts_without_calling_api(self) -> None:
        session = self._session()
        try:
            self._seed_alert(session, title="A")
            self._seed_alert(session, title="B")

            with (
                patch.object(app_settings, "alert_rewriter_enabled", False),
                patch("urllib.request.urlopen") as mock_urlopen,
            ):
                summary = alert_rewriter.rewrite_pending_alerts(session)
                mock_urlopen.assert_not_called()
        finally:
            session.close()

        self.assertEqual(0, summary["attempted"])
        self.assertEqual(0, summary["succeeded"])
        self.assertEqual(0, summary["failed"])
        self.assertEqual(2, summary["skipped_disabled"])

    def test_empty_api_key_skips_all_alerts(self) -> None:
        session = self._session()
        try:
            self._seed_alert(session, title="A")

            with (
                patch.object(app_settings, "anthropic_api_key", ""),
                patch("urllib.request.urlopen") as mock_urlopen,
            ):
                summary = alert_rewriter.rewrite_pending_alerts(session)
                mock_urlopen.assert_not_called()
        finally:
            session.close()

        self.assertEqual(0, summary["attempted"])
        self.assertEqual(1, summary["skipped_disabled"])


# ---------------------------------------------------------------------------
# rewrite_pending_alerts (batch)
# ---------------------------------------------------------------------------


class RewritePendingAlertsBatchTests(_BaseRewriterCase):
    def test_processes_multiple_pending_alerts(self) -> None:
        body = _anthropic_response_body(
            "EXPLANATION: Property archived will break workflow.\n\n"
            "ACTION: Restore the property or unwire the workflow."
        )

        def fake_urlopen(request, timeout):
            return _FakeResponse(status=200, body=body)

        session = self._session()
        try:
            for i in range(3):
                self._seed_alert(session, title=f"Alert {i}")

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                summary = alert_rewriter.rewrite_pending_alerts(session)
        finally:
            session.close()

        self.assertEqual(3, summary["attempted"])
        self.assertEqual(3, summary["succeeded"])
        self.assertEqual(0, summary["failed"])
        self.assertEqual(0, summary["skipped_disabled"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
