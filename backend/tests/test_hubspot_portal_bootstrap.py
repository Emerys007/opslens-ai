import unittest
from unittest.mock import patch

from app.services import hubspot_oauth
from app.services.hubspot_portal_bootstrap import (
    CONTACT_PROPERTIES,
    TICKET_PROPERTIES,
    ensure_portal_bootstrap,
)
from app.services.hubspot_ticket_auto_resolve import auto_resolve_waiting_tickets
from app.services.hubspot_ticket_pipeline import PortalProvisioningRequiredError


class FakeBootstrapApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.groups = {
            "contacts": set(),
            "tickets": set(),
        }
        self.properties = {
            "contacts": set(),
            "tickets": set(),
        }
        self.pipeline = None
        self._next_stage_id = 1000

    def _stage(self, label: str, ticket_state: str, display_order: int) -> dict:
        stage = {
            "id": str(self._next_stage_id),
            "label": label,
            "displayOrder": display_order,
            "metadata": {"ticketState": ticket_state},
        }
        self._next_stage_id += 1
        return stage

    def request_json(self, token: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        self.calls.append((method, path))

        if method == "GET" and "/crm/v3/properties/" in path and "/groups/" in path:
            parts = path.strip("/").split("/")
            object_type = parts[3]
            group_name = parts[5]
            if group_name in self.groups[object_type]:
                return 200, {"name": group_name}
            return 404, {"message": "group missing"}

        if method == "POST" and path.endswith("/groups"):
            object_type = path.strip("/").split("/")[3]
            group_name = str(payload.get("name") or "").strip()
            if group_name in self.groups[object_type]:
                return 409, {"message": "already exists"}
            self.groups[object_type].add(group_name)
            return 201, {"name": group_name}

        if method == "POST" and "/crm/v3/properties/" in path and not path.endswith("/groups"):
            object_type = path.strip("/").split("/")[3]
            property_name = str(payload.get("name") or "").strip()
            if property_name in self.properties[object_type]:
                return 409, {"message": "already exists"}
            self.properties[object_type].add(property_name)
            return 201, {"name": property_name}

        if method == "POST" and path == "/crm/pipelines/2026-03/tickets":
            self.pipeline = {
                "id": "9001",
                "label": str(payload.get("label") or ""),
                "stages": [
                    self._stage(
                        label=str(stage.get("label") or ""),
                        ticket_state=str((stage.get("metadata") or {}).get("ticketState") or ""),
                        display_order=int(stage.get("displayOrder") or 0),
                    )
                    for stage in (payload.get("stages") or [])
                ],
            }
            return 201, self.pipeline

        if method == "POST" and "/crm/pipelines/2026-03/tickets/" in path and path.endswith("/stages"):
            if self.pipeline is None:
                return 404, {"message": "pipeline missing"}
            stage = self._stage(
                label=str(payload.get("label") or ""),
                ticket_state=str((payload.get("metadata") or {}).get("ticketState") or ""),
                display_order=int(payload.get("displayOrder") or 0),
            )
            self.pipeline["stages"].append(stage)
            return 201, stage

        if method == "PATCH" and "/crm/pipelines/2026-03/tickets/" in path and "/stages/" in path:
            if self.pipeline is None:
                return 404, {"message": "pipeline missing"}
            stage_id = path.rsplit("/", 1)[-1]
            for stage in self.pipeline.get("stages", []):
                if str(stage.get("id") or "") == stage_id:
                    stage["label"] = str(payload.get("label") or stage.get("label") or "")
                    stage["displayOrder"] = int(payload.get("displayOrder") or stage.get("displayOrder") or 0)
                    stage["metadata"] = payload.get("metadata") or {}
                    return 200, stage
            return 404, {"message": "stage missing"}

        raise AssertionError(f"Unexpected HubSpot call: {method} {path}")

    def fetch_ticket_pipelines(self, token: str) -> list[dict]:
        if self.pipeline is None:
            return []
        return [self.pipeline]


class HubSpotPortalBootstrapTests(unittest.TestCase):
    def test_bootstrap_creates_missing_schema(self) -> None:
        fake_api = FakeBootstrapApi()

        with (
            patch("app.services.hubspot_portal_bootstrap._request_json", side_effect=fake_api.request_json),
            patch("app.services.hubspot_portal_bootstrap.fetch_ticket_pipelines", side_effect=fake_api.fetch_ticket_pipelines),
        ):
            summary = ensure_portal_bootstrap(token="token", portal_id="8886743")

        self.assertTrue(summary["contactPropertyGroupCreated"])
        self.assertTrue(summary["ticketPropertyGroupCreated"])
        self.assertEqual(sorted(prop.name for prop in CONTACT_PROPERTIES), sorted(summary["contactPropertiesCreated"]))
        self.assertEqual(sorted(prop.name for prop in TICKET_PROPERTIES), sorted(summary["ticketPropertiesCreated"]))
        self.assertTrue(summary["pipelineCreated"])
        self.assertEqual([], summary["stagesCreated"])
        self.assertEqual([], summary["stagesUpdated"])
        self.assertEqual("9001", summary["pipelineId"])
        self.assertIn(("GET", "/crm/v3/properties/contacts/groups/opslens_ai"), fake_api.calls)
        self.assertIn(("POST", "/crm/v3/properties/contacts/groups"), fake_api.calls)
        self.assertIn(("POST", "/crm/v3/properties/contacts"), fake_api.calls)
        self.assertIn(("GET", "/crm/v3/properties/tickets/groups/opslens_ai_tickets"), fake_api.calls)
        self.assertIn(("POST", "/crm/v3/properties/tickets/groups"), fake_api.calls)
        self.assertIn(("POST", "/crm/v3/properties/tickets"), fake_api.calls)

    def test_bootstrap_is_idempotent(self) -> None:
        fake_api = FakeBootstrapApi()

        with (
            patch("app.services.hubspot_portal_bootstrap._request_json", side_effect=fake_api.request_json),
            patch("app.services.hubspot_portal_bootstrap.fetch_ticket_pipelines", side_effect=fake_api.fetch_ticket_pipelines),
        ):
            first = ensure_portal_bootstrap(token="token", portal_id="8886743")
            second = ensure_portal_bootstrap(token="token", portal_id="8886743")

        self.assertTrue(first["pipelineCreated"])
        self.assertFalse(second["contactPropertyGroupCreated"])
        self.assertFalse(second["ticketPropertyGroupCreated"])
        self.assertEqual([], second["contactPropertiesCreated"])
        self.assertEqual([], second["ticketPropertiesCreated"])
        self.assertFalse(second["pipelineCreated"])
        self.assertEqual([], second["stagesCreated"])
        self.assertEqual([], second["stagesUpdated"])
        self.assertEqual("9001", second["pipelineId"])
        self.assertEqual(1, fake_api.calls.count(("POST", "/crm/v3/properties/contacts/groups")))
        self.assertEqual(1, fake_api.calls.count(("POST", "/crm/v3/properties/tickets/groups")))

    def test_bootstrap_provisions_v2_alert_ticket_properties_idempotently(self) -> None:
        """Explicit coverage for the three custom ticket properties the
        v2 alert correlation engine relies on: ``opslens_alert_id``,
        ``opslens_severity``, ``opslens_signature``. They should be
        created on the first bootstrap run and skipped on the second.
        """
        fake_api = FakeBootstrapApi()
        v2_property_names = {"opslens_alert_id", "opslens_severity", "opslens_signature"}

        with (
            patch("app.services.hubspot_portal_bootstrap._request_json", side_effect=fake_api.request_json),
            patch(
                "app.services.hubspot_portal_bootstrap.fetch_ticket_pipelines",
                side_effect=fake_api.fetch_ticket_pipelines,
            ),
        ):
            first = ensure_portal_bootstrap(token="token", portal_id="8886743")
            second = ensure_portal_bootstrap(token="token", portal_id="8886743")

        # All three v2 properties were declared in TICKET_PROPERTIES.
        registered_names = {prop.name for prop in TICKET_PROPERTIES}
        for name in v2_property_names:
            self.assertIn(name, registered_names, f"{name} missing from TICKET_PROPERTIES")

        # First run actually created them.
        first_created = set(first["ticketPropertiesCreated"])
        for name in v2_property_names:
            self.assertIn(name, first_created, f"{name} not created on first bootstrap")

        # Second run treated them as already-provisioned (no recreation).
        self.assertEqual([], second["ticketPropertiesCreated"])

        # And the underlying fake HubSpot has the rows persisted exactly once.
        for name in v2_property_names:
            self.assertIn(name, fake_api.properties["tickets"])

    def test_bootstrap_treats_group_conflicts_as_success(self) -> None:
        fake_api = FakeBootstrapApi()

        def request_json(token: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
            if method == "POST" and path in {
                "/crm/v3/properties/contacts/groups",
                "/crm/v3/properties/tickets/groups",
            }:
                fake_api.calls.append((method, path))
                return 409, {"message": "already exists"}
            return fake_api.request_json(token, method, path, payload)

        with (
            patch("app.services.hubspot_portal_bootstrap._request_json", side_effect=request_json),
            patch("app.services.hubspot_portal_bootstrap.fetch_ticket_pipelines", side_effect=fake_api.fetch_ticket_pipelines),
        ):
            summary = ensure_portal_bootstrap(token="token", portal_id="8886743")

        self.assertFalse(summary["contactPropertyGroupCreated"])
        self.assertFalse(summary["ticketPropertyGroupCreated"])
        self.assertTrue(summary["pipelineCreated"])


class HubSpotBootstrapScopeTests(unittest.TestCase):
    def test_required_scopes_always_include_contact_schema_write(self) -> None:
        with patch.object(hubspot_oauth.settings, "hubspot_scopes", "oauth crm.objects.contacts.read crm.objects.contacts.write tickets"):
            scopes = hubspot_oauth._required_scopes().split()

        for required_scope in (
            "crm.schemas.contacts.write",
            "automation",
            "crm.schemas.contacts.read",
            "crm.schemas.companies.read",
            "crm.schemas.deals.read",
            "crm.schemas.tickets.read",
        ):
            self.assertIn(required_scope, scopes)


class AutoResolveProvisioningSkipTests(unittest.TestCase):
    def test_auto_resolve_skips_non_provisioned_portals_without_errors(self) -> None:
        with (
            patch("app.services.hubspot_ticket_auto_resolve._installed_portal_ids", return_value=["8886743"]),
            patch("app.services.hubspot_ticket_auto_resolve._resolve_token_for_portal", return_value="token"),
            patch(
                "app.services.hubspot_ticket_auto_resolve.load_portal_ticket_pipeline_config",
                side_effect=PortalProvisioningRequiredError("OpsLens Alerts ticket pipeline was not found for portal 8886743."),
            ),
            patch("app.services.hubspot_ticket_auto_resolve._search_waiting_tickets") as search_tickets,
        ):
            summary = auto_resolve_waiting_tickets(quiet_hours=24, max_records=10)

        search_tickets.assert_not_called()
        self.assertEqual("ok", summary["status"])
        self.assertEqual([], summary["errors"])
        self.assertEqual(0, summary["searched"])
        self.assertEqual(
            [
                {
                    "portalId": "8886743",
                    "reason": "OpsLens Alerts ticket pipeline was not found for portal 8886743.",
                }
            ],
            summary["skippedPortals"],
        )


if __name__ == "__main__":
    unittest.main()
