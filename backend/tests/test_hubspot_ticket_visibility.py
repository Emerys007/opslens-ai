import unittest
from unittest.mock import patch

from app.services.hubspot_ticket_pipeline import PortalProvisioningRequiredError, TicketPipelineConfig
from app.services.hubspot_ticket_visibility import load_ticket_visibility


PIPELINE_CONFIG = TicketPipelineConfig(
    portal_id="8886743",
    pipeline_id="892158537",
    pipeline_label="OpsLens Alerts",
    stage_new_alert="1344597295",
    stage_investigating="1344597296",
    stage_waiting="1344597297",
    stage_resolved="1344597298",
    stage_duplicate="1344597299",
)


class HubSpotTicketVisibilityTests(unittest.TestCase):
    def test_load_ticket_visibility_uses_portal_token_backed_search(self) -> None:
        with (
            patch("app.services.hubspot_ticket_visibility._resolve_token_for_portal", return_value="oauth-token") as resolve_token,
            patch(
                "app.services.hubspot_ticket_visibility.load_portal_ticket_pipeline_config",
                return_value=PIPELINE_CONFIG,
            ) as load_pipeline,
            patch(
                "app.services.hubspot_ticket_visibility._request_json",
                return_value=(
                    200,
                    {
                        "total": 1,
                        "results": [
                            {
                                "id": "44567632273",
                                "properties": {
                                    "subject": "OpsLens critical alert | Workflow 123 | Contact 456",
                                    "hs_pipeline_stage": "1344597297",
                                    "opslens_ticket_contact_id": "456",
                                },
                            }
                        ],
                    },
                ),
            ) as request_json,
        ):
            payload = load_ticket_visibility(portal_id="8886743", limit=4)

        resolve_token.assert_called_once_with("8886743")
        load_pipeline.assert_called_once_with(token="oauth-token", portal_id="8886743")
        request_json.assert_called_once()
        called_token, called_method, called_path, called_body = request_json.call_args.args
        self.assertEqual("oauth-token", called_token)
        self.assertEqual("POST", called_method)
        self.assertEqual("/crm/v3/objects/tickets/search", called_path)
        self.assertEqual("892158537", called_body["filterGroups"][0]["filters"][0]["value"])
        self.assertEqual("HAS_PROPERTY", called_body["filterGroups"][0]["filters"][1]["operator"])
        self.assertEqual("ok", payload["status"])
        self.assertTrue(payload["provisioned"])
        self.assertEqual("8886743", payload["portalId"])
        self.assertEqual(1, payload["total"])

    def test_load_ticket_visibility_returns_empty_for_unprovisioned_portal(self) -> None:
        with (
            patch("app.services.hubspot_ticket_visibility._resolve_token_for_portal", return_value="oauth-token"),
            patch(
                "app.services.hubspot_ticket_visibility.load_portal_ticket_pipeline_config",
                side_effect=PortalProvisioningRequiredError("OpsLens Alerts ticket pipeline was not found for portal 8886743."),
            ),
            patch("app.services.hubspot_ticket_visibility._request_json") as request_json,
        ):
            payload = load_ticket_visibility(portal_id="8886743", limit=4)

        request_json.assert_not_called()
        self.assertEqual("ok", payload["status"])
        self.assertFalse(payload["provisioned"])
        self.assertEqual([], payload["results"])
        self.assertEqual(0, payload["total"])


if __name__ == "__main__":
    unittest.main()
