from __future__ import annotations

import unittest
import urllib.error
from unittest.mock import patch

from app.services.workflow_remediation import (
    WorkflowRemediationError,
    reenable_workflow,
)

_TOKEN_PATH = "app.services.workflow_remediation.get_portal_access_token"
_REQUEST_PATH = "app.services.workflow_remediation._request_json"


class ReenableWorkflowServiceTests(unittest.TestCase):
    def test_already_enabled_skips_put(self) -> None:
        calls: list[tuple] = []

        def fake_request(url, token, *, method, body=None):
            calls.append((method, url, body))
            return {"id": "100", "isEnabled": True, "revisionId": "5", "type": "FLOW"}

        with patch(_TOKEN_PATH, return_value="tok"), patch(
            _REQUEST_PATH, side_effect=fake_request
        ):
            result = reenable_workflow(None, "P1", "100")

        self.assertTrue(result["alreadyEnabled"])
        self.assertTrue(result["isEnabled"])
        self.assertEqual(1, len(calls))
        self.assertEqual("GET", calls[0][0])

    def test_disabled_flips_and_round_trips_full_body(self) -> None:
        flow = {
            "id": "100",
            "isEnabled": False,
            "revisionId": "5",
            "type": "FLOW",
            "actions": [{"x": 1}],
        }
        calls: list[tuple] = []

        def fake_request(url, token, *, method, body=None):
            calls.append((method, url, body))
            if method == "GET":
                return dict(flow)
            return {"id": "100", "isEnabled": True, "revisionId": "6"}

        with patch(_TOKEN_PATH, return_value="tok"), patch(
            _REQUEST_PATH, side_effect=fake_request
        ):
            result = reenable_workflow(None, "P1", "100")

        self.assertFalse(result["alreadyEnabled"])
        self.assertTrue(result["isEnabled"])
        self.assertEqual(2, len(calls))
        self.assertEqual("PUT", calls[1][0])
        put_body = calls[1][2]
        # The full flow round-trips with only isEnabled flipped on.
        self.assertTrue(put_body["isEnabled"])
        self.assertEqual([{"x": 1}], put_body["actions"])
        self.assertEqual("5", put_body["revisionId"])

    def test_missing_args_raise(self) -> None:
        with self.assertRaises(WorkflowRemediationError):
            reenable_workflow(None, "", "100")
        with self.assertRaises(WorkflowRemediationError):
            reenable_workflow(None, "P1", "")

    def test_get_404_is_user_safe(self) -> None:
        def fake_request(url, token, *, method, body=None):
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

        with patch(_TOKEN_PATH, return_value="tok"), patch(
            _REQUEST_PATH, side_effect=fake_request
        ):
            with self.assertRaises(WorkflowRemediationError) as ctx:
                reenable_workflow(None, "P1", "100")
        self.assertIn("no longer exists", str(ctx.exception))

    def test_put_409_is_user_safe(self) -> None:
        def fake_request(url, token, *, method, body=None):
            if method == "GET":
                return {"id": "100", "isEnabled": False, "revisionId": "5"}
            raise urllib.error.HTTPError(url, 409, "Conflict", None, None)

        with patch(_TOKEN_PATH, return_value="tok"), patch(
            _REQUEST_PATH, side_effect=fake_request
        ):
            with self.assertRaises(WorkflowRemediationError) as ctx:
                reenable_workflow(None, "P1", "100")
        self.assertIn("changed in HubSpot", str(ctx.exception))

    def test_token_failure_is_user_safe(self) -> None:
        with patch(_TOKEN_PATH, side_effect=RuntimeError("no token")):
            with self.assertRaises(WorkflowRemediationError) as ctx:
                reenable_workflow(None, "P1", "100")
        self.assertIn("No active HubSpot connection", str(ctx.exception))
