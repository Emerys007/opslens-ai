import unittest

from app.services.hubspot_ticket_pipeline import build_ticket_pipeline_config, select_ticket_pipeline


def _portal_8886743_pipeline() -> dict:
    return {
        "id": "892158537",
        "label": "OpsLens Alerts",
        "stages": [
            {"id": "1344597295", "label": "New Alert"},
            {"id": "1344597296", "label": "Investigating"},
            {"id": "1344597297", "label": "Waiting / Monitoring"},
            {"id": "1344597298", "label": "Resolved"},
            {"id": "1344597299", "label": "Closed as Duplicate"},
        ],
    }


class HubSpotTicketPipelineTests(unittest.TestCase):
    def test_select_pipeline_falls_back_to_opslens_label_when_preferred_id_is_missing(self) -> None:
        pipelines = [
            {"id": "123", "label": "Support"},
            _portal_8886743_pipeline(),
        ]

        selected = select_ticket_pipeline(pipelines, preferred_pipeline_id="890820374")

        self.assertIsNotNone(selected)
        self.assertEqual("892158537", selected["id"])

    def test_build_ticket_pipeline_config_uses_stage_ids_from_the_portal_pipeline(self) -> None:
        config = build_ticket_pipeline_config("8886743", _portal_8886743_pipeline())

        self.assertEqual("8886743", config.portal_id)
        self.assertEqual("892158537", config.pipeline_id)
        self.assertEqual("1344597295", config.stage_new_alert)
        self.assertEqual("1344597296", config.stage_investigating)
        self.assertEqual("1344597297", config.stage_waiting)
        self.assertEqual("1344597298", config.stage_resolved)
        self.assertEqual("1344597299", config.stage_duplicate)
        self.assertEqual(
            {"1344597295", "1344597296", "1344597297"},
            config.open_stage_ids,
        )


if __name__ == "__main__":
    unittest.main()
