from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app import db as db_module
from app.main import app
from app.models.portal_setting import PortalSetting
from app.services.slack_oauth import (
    SlackOAuthError,
    build_slack_authorize_url,
    exchange_slack_code,
    parse_slack_state,
    sign_slack_state,
)

_SECRET = "app.services.slack_oauth.settings.oauth_state_secret"
_CLIENT_ID = "app.services.slack_oauth.settings.slack_client_id"
_CLIENT_SECRET = "app.services.slack_oauth.settings.slack_client_secret"


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> bytes:
        return self._text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SlackStateTests(unittest.TestCase):
    def test_sign_and_parse_round_trip(self) -> None:
        with patch(_SECRET, "test-secret"):
            state = sign_slack_state("8886743")
            self.assertEqual("8886743", parse_slack_state(state))

    def test_tampered_state_is_rejected(self) -> None:
        with patch(_SECRET, "test-secret"):
            state = sign_slack_state("8886743")
        with patch(_SECRET, "different-secret"):
            with self.assertRaises(SlackOAuthError):
                parse_slack_state(state)

    def test_missing_state_is_rejected(self) -> None:
        with patch(_SECRET, "test-secret"):
            with self.assertRaises(SlackOAuthError):
                parse_slack_state("")


class SlackAuthorizeUrlTests(unittest.TestCase):
    def test_authorize_url_has_scope_and_state(self) -> None:
        with patch(_CLIENT_ID, "client-123"), patch(_SECRET, "test-secret"):
            url = build_slack_authorize_url("8886743")
        self.assertIn("https://slack.com/oauth/v2/authorize", url)
        self.assertIn("client_id=client-123", url)
        self.assertIn("scope=incoming-webhook", url)
        self.assertIn("state=", url)
        self.assertIn("slack%2Foauth-callback", url)

    def test_authorize_url_requires_client_id(self) -> None:
        with patch(_CLIENT_ID, ""):
            with self.assertRaises(SlackOAuthError):
                build_slack_authorize_url("8886743")


class SlackExchangeTests(unittest.TestCase):
    def test_exchange_returns_webhook_channel_team(self) -> None:
        body = json.dumps(
            {
                "ok": True,
                "team": {"name": "Acme"},
                "incoming_webhook": {
                    "url": "https://hooks.slack.com/services/T/B/x",
                    "channel": "#ops-alerts",
                },
            }
        )
        with patch(_CLIENT_ID, "c"), patch(_CLIENT_SECRET, "s"), patch(
            "app.services.slack_oauth.urllib.request.urlopen",
            return_value=_FakeResponse(body),
        ):
            result = exchange_slack_code("code")
        self.assertEqual("https://hooks.slack.com/services/T/B/x", result["webhook_url"])
        self.assertEqual("#ops-alerts", result["channel"])
        self.assertEqual("Acme", result["team_name"])

    def test_exchange_raises_on_not_ok(self) -> None:
        with patch(_CLIENT_ID, "c"), patch(_CLIENT_SECRET, "s"), patch(
            "app.services.slack_oauth.urllib.request.urlopen",
            return_value=_FakeResponse(json.dumps({"ok": False, "error": "bad_code"})),
        ):
            with self.assertRaises(SlackOAuthError):
                exchange_slack_code("code")

    def test_exchange_raises_when_no_webhook(self) -> None:
        with patch(_CLIENT_ID, "c"), patch(_CLIENT_SECRET, "s"), patch(
            "app.services.slack_oauth.urllib.request.urlopen",
            return_value=_FakeResponse(json.dumps({"ok": True, "team": {"name": "Acme"}})),
        ):
            with self.assertRaises(SlackOAuthError):
                exchange_slack_code("code")


class SlackCallbackTests(unittest.TestCase):
    PORTAL_ID = "8886743"

    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'slack-test.sqlite')}"
        )
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

    def test_callback_stores_webhook_and_redirects(self) -> None:
        with patch(_SECRET, "test-secret"):
            state = sign_slack_state(self.PORTAL_ID)

        with patch(_SECRET, "test-secret"), patch(
            "app.routes.slack_oauth.exchange_slack_code",
            return_value={
                "webhook_url": "https://hooks.slack.com/services/T/B/x",
                "channel": "#ops-alerts",
                "team_name": "Acme",
            },
        ):
            response = self.client.get(
                f"/slack/oauth-callback?code=auth-code&state={state}",
                follow_redirects=False,
            )

        self.assertEqual(302, response.status_code)
        self.assertTrue(
            response.headers["location"].startswith("https://app.hubspot.com/connected-apps/")
        )

        session = db_module.get_session()
        try:
            row = session.get(PortalSetting, self.PORTAL_ID)
            self.assertIsNotNone(row)
            self.assertEqual("https://hooks.slack.com/services/T/B/x", row.slack_webhook_url)
            self.assertEqual("#ops-alerts", row.slack_channel_name)
            self.assertEqual("Acme", row.slack_team_name)
            self.assertTrue(row.slack_delivery_enabled)
        finally:
            session.close()

    def test_callback_with_bad_state_does_not_crash(self) -> None:
        with patch(_SECRET, "test-secret"):
            response = self.client.get(
                "/slack/oauth-callback?code=auth-code&state=garbage",
                follow_redirects=False,
            )
        self.assertEqual(302, response.status_code)
