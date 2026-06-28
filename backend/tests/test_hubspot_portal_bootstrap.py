import unittest
from unittest.mock import patch

from app.services import hubspot_oauth
from app.services.hubspot_portal_bootstrap import (
    CONTACT_PROPERTIES,
    TICKET_PROPERTIES,
    ensure_portal_bootstrap,
)
from app.services.hubspot_ticket_auto_resolve import auto_resolve_waiting_tickets
from app.services.hubspot_ticket_pipeline import (
    PIPELINE_MODE_DEDICATED,
    PIPELINE_MODE_SHARED,
    PortalProvisioningRequiredError,
    SHARED_STAGE_LABEL_PREFIX,
    STAGE_LABEL_INVESTIGATING,
    STAGE_LABEL_NEW_ALERT,
    STAGE_LABEL_RESOLVED,
    load_portal_ticket_pipeline_config,
)


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


class FakeBootstrapApiWithLimit(FakeBootstrapApi):
    """Bootstrap fake that simulates HubSpot's per-portal ticket pipeline
    cap (1 pipeline on Free / Starter tiers). Pre-seeds an existing
    pipeline named "Support Pipeline" and rejects subsequent POSTs to
    create another pipeline with an API_LIMIT 400."""

    def __init__(self) -> None:
        super().__init__()
        # Pre-seed an existing pipeline so the bootstrap has something
        # to fall back onto. The label is intentionally NOT "OpsLens
        # Alerts" so select_ticket_pipeline returns None and the
        # bootstrap attempts a create.
        self.pipeline = {
            "id": "EXISTING-PIPELINE",
            "label": "Support Pipeline",
            "stages": [
                self._stage(label="Open", ticket_state="OPEN", display_order=0),
                self._stage(label="Closed", ticket_state="CLOSED", display_order=1),
            ],
        }
        self.pipeline_create_attempts = 0

    def request_json(self, token: str, method: str, path: str, payload: dict | None = None):
        # Intercept the create-pipeline POST and return the API_LIMIT 400
        # that HubSpot returns for portals that have hit the cap.
        if method == "POST" and path == "/crm/pipelines/2026-03/tickets":
            self.pipeline_create_attempts += 1
            self.calls.append((method, path))
            return 400, {
                "category": "API_LIMIT",
                "message": "You have reached your limit of 1 ticket pipelines.",
                "context": {"maximum pipelines": ["1"]},
            }
        return super().request_json(token, method, path, payload)


class _StubPortalSettingsRow:
    """Mimics PortalSetting just enough for the test session.get() seam.

    The bootstrap writes resolved pipeline + stage IDs onto this object
    and the assertions read them back."""

    def __init__(self, portal_id: str) -> None:
        self.portal_id = portal_id
        self.opslens_pipeline_mode = ""
        self.opslens_ticket_pipeline_id = ""
        self.opslens_stage_new_alert_id = ""
        self.opslens_stage_investigating_id = ""
        self.opslens_stage_waiting_id = ""
        self.opslens_stage_resolved_id = ""
        self.opslens_stage_duplicate_id = ""


class _StubSession:
    """Tiny in-memory stand-in for a SQLAlchemy session — enough for
    bootstrap.persist_pipeline_settings to round-trip."""

    def __init__(self) -> None:
        self.rows: dict[tuple[type, str], _StubPortalSettingsRow] = {}
        self.commit_count = 0

    def get(self, model, key):
        return self.rows.get((model, key))

    def add(self, row) -> None:
        # We only ever add PortalSetting in this codepath.
        from app.models.portal_setting import PortalSetting
        self.rows[(PortalSetting, row.portal_id)] = row

    def commit(self) -> None:
        self.commit_count += 1


class SharedPipelineFallbackTests(unittest.TestCase):
    def test_bootstrap_reuses_existing_opslens_alerts_pipeline(self) -> None:
        """If a pipeline labeled 'OpsLens Alerts' already exists, the
        bootstrap reuses it without attempting a create POST. This is
        the idempotency contract used by the retry endpoint."""
        fake_api = FakeBootstrapApi()
        # Pre-seed a fully-stocked OpsLens Alerts pipeline so the
        # bootstrap finds it and skips creation entirely.
        fake_api.pipeline = {
            "id": "EXISTING-OPSLENS",
            "label": "OpsLens Alerts",
            "stages": [
                fake_api._stage(label="New Alert", ticket_state="OPEN", display_order=0),
                fake_api._stage(label="Investigating", ticket_state="OPEN", display_order=1),
                fake_api._stage(label="Waiting / Monitoring", ticket_state="OPEN", display_order=2),
                fake_api._stage(label="Resolved", ticket_state="CLOSED", display_order=3),
                fake_api._stage(label="Closed as Duplicate", ticket_state="CLOSED", display_order=4),
            ],
        }
        stub_session = _StubSession()
        from app.models.portal_setting import PortalSetting
        stub_session.rows[(PortalSetting, "8886743")] = _StubPortalSettingsRow("8886743")

        with (
            patch("app.services.hubspot_portal_bootstrap._request_json", side_effect=fake_api.request_json),
            patch("app.services.hubspot_portal_bootstrap.fetch_ticket_pipelines", side_effect=fake_api.fetch_ticket_pipelines),
        ):
            summary = ensure_portal_bootstrap(token="token", portal_id="8886743", session=stub_session)

        self.assertFalse(summary["pipelineCreated"])
        self.assertEqual(PIPELINE_MODE_DEDICATED, summary["pipelineMode"])
        self.assertEqual("EXISTING-OPSLENS", summary["pipelineId"])
        # No POST to create a new pipeline.
        self.assertNotIn(("POST", "/crm/pipelines/2026-03/tickets"), fake_api.calls)
        # Settings row was populated with the reused pipeline id.
        row = stub_session.rows[(PortalSetting, "8886743")]
        self.assertEqual("EXISTING-OPSLENS", row.opslens_ticket_pipeline_id)
        self.assertEqual(PIPELINE_MODE_DEDICATED, row.opslens_pipeline_mode)
        self.assertTrue(row.opslens_stage_new_alert_id)
        self.assertTrue(row.opslens_stage_resolved_id)

    def test_bootstrap_falls_back_to_shared_pipeline_on_api_limit(self) -> None:
        """When create-pipeline returns category=API_LIMIT the bootstrap
        attaches OpsLens-prefixed stages to the existing pipeline,
        persists pipeline_mode=shared + all five stage IDs, and reports
        success."""
        fake_api = FakeBootstrapApiWithLimit()
        stub_session = _StubSession()

        with (
            patch("app.services.hubspot_portal_bootstrap._request_json", side_effect=fake_api.request_json),
            patch("app.services.hubspot_portal_bootstrap.fetch_ticket_pipelines", side_effect=fake_api.fetch_ticket_pipelines),
        ):
            summary = ensure_portal_bootstrap(token="token", portal_id="50634496", session=stub_session)

        # The bootstrap attempted a create exactly once (then fell back).
        self.assertEqual(1, fake_api.pipeline_create_attempts)
        # Reports shared mode and the existing pipeline id.
        self.assertEqual(PIPELINE_MODE_SHARED, summary["pipelineMode"])
        self.assertEqual("EXISTING-PIPELINE", summary["pipelineId"])
        # All five OpsLens-prefixed stages were created on the existing
        # pipeline (the customer's "Open" / "Closed" stages were left
        # untouched).
        prefixed_stages = [
            stage["label"]
            for stage in fake_api.pipeline["stages"]
            if str(stage.get("label", "")).startswith(SHARED_STAGE_LABEL_PREFIX)
        ]
        self.assertEqual(5, len(prefixed_stages))
        for canonical_label in (
            STAGE_LABEL_NEW_ALERT,
            STAGE_LABEL_INVESTIGATING,
            STAGE_LABEL_RESOLVED,
        ):
            self.assertIn(f"{SHARED_STAGE_LABEL_PREFIX}{canonical_label}", prefixed_stages)
        # The customer's pre-existing stages survived the run.
        existing_labels = {str(stage.get("label", "")) for stage in fake_api.pipeline["stages"]}
        self.assertIn("Open", existing_labels)
        self.assertIn("Closed", existing_labels)
        # All five stage IDs were persisted to portal_settings.
        from app.models.portal_setting import PortalSetting
        row = stub_session.rows[(PortalSetting, "50634496")]
        self.assertEqual(PIPELINE_MODE_SHARED, row.opslens_pipeline_mode)
        self.assertEqual("EXISTING-PIPELINE", row.opslens_ticket_pipeline_id)
        for stage_id in (
            row.opslens_stage_new_alert_id,
            row.opslens_stage_investigating_id,
            row.opslens_stage_waiting_id,
            row.opslens_stage_resolved_id,
            row.opslens_stage_duplicate_id,
        ):
            self.assertTrue(stage_id, "shared-mode bootstrap should persist a non-empty stage id")

    def test_shared_pipeline_bootstrap_is_idempotent(self) -> None:
        """A second bootstrap on a shared-pipeline portal must not
        duplicate the OpsLens-prefixed stages."""
        fake_api = FakeBootstrapApiWithLimit()
        stub_session = _StubSession()

        with (
            patch("app.services.hubspot_portal_bootstrap._request_json", side_effect=fake_api.request_json),
            patch("app.services.hubspot_portal_bootstrap.fetch_ticket_pipelines", side_effect=fake_api.fetch_ticket_pipelines),
        ):
            first = ensure_portal_bootstrap(token="token", portal_id="50634496", session=stub_session)
            second = ensure_portal_bootstrap(token="token", portal_id="50634496", session=stub_session)

        # First run created all 5 prefixed stages, second run created none.
        self.assertEqual(5, len(first["stagesCreated"]))
        self.assertEqual([], second["stagesCreated"])
        # Both runs report shared mode and the same pipeline id.
        self.assertEqual(PIPELINE_MODE_SHARED, first["pipelineMode"])
        self.assertEqual(PIPELINE_MODE_SHARED, second["pipelineMode"])
        self.assertEqual(first["pipelineId"], second["pipelineId"])
        # Pipeline still has exactly 5 OpsLens-prefixed stages (no dupes)
        # plus the original 2 pre-existing.
        prefixed_stages = [
            stage["label"]
            for stage in fake_api.pipeline["stages"]
            if str(stage.get("label", "")).startswith(SHARED_STAGE_LABEL_PREFIX)
        ]
        self.assertEqual(5, len(prefixed_stages))
        self.assertEqual(7, len(fake_api.pipeline["stages"]))
        # Stage IDs in portal_settings stayed stable across the second run.
        from app.models.portal_setting import PortalSetting
        row = stub_session.rows[(PortalSetting, "50634496")]
        self.assertEqual(first["stageIds"][STAGE_LABEL_NEW_ALERT], row.opslens_stage_new_alert_id)


class TicketPipelineConfigFromPortalSettingsTests(unittest.TestCase):
    """load_portal_ticket_pipeline_config should read from portal_settings
    when stage IDs are persisted there — no HubSpot lookup required."""

    def test_load_returns_config_built_from_persisted_stage_ids(self) -> None:
        from app.models.portal_setting import PortalSetting
        stub_session = _StubSession()
        row = _StubPortalSettingsRow("50634496")
        row.opslens_pipeline_mode = PIPELINE_MODE_SHARED
        row.opslens_ticket_pipeline_id = "EXISTING-PIPELINE"
        row.opslens_stage_new_alert_id = "stage-1"
        row.opslens_stage_investigating_id = "stage-2"
        row.opslens_stage_waiting_id = "stage-3"
        row.opslens_stage_resolved_id = "stage-4"
        row.opslens_stage_duplicate_id = "stage-5"
        stub_session.rows[(PortalSetting, "50634496")] = row

        # If load_portal_ticket_pipeline_config consulted HubSpot we'd
        # see this side_effect raise; the test passes only when the
        # lookup is satisfied entirely from the session row.
        with patch(
            "app.services.hubspot_ticket_pipeline.fetch_ticket_pipelines",
            side_effect=AssertionError("HubSpot should not be called when settings has the IDs"),
        ):
            config = load_portal_ticket_pipeline_config(
                token="token",
                portal_id="50634496",
                session=stub_session,
            )

        self.assertEqual("EXISTING-PIPELINE", config.pipeline_id)
        self.assertEqual(PIPELINE_MODE_SHARED, config.pipeline_mode)
        self.assertEqual("stage-1", config.stage_new_alert)
        self.assertEqual("stage-4", config.stage_resolved)
        # The mode-aware open/closed sets still work on the persisted IDs.
        self.assertIn("stage-1", config.open_stage_ids)
        self.assertIn("stage-4", config.closed_stage_ids)


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
            "crm.lists.read",
            "content",
            "crm.objects.owners.read",
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
