from pathlib import Path
import textwrap

PROJECT_ROOT = Path.cwd()
WORKSPACE_ROOT = PROJECT_ROOT.parent

files = {
    WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "dashboard.py": """
from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def dashboard_overview(request: Request):
    query = dict(request.query_params)

    return {
        "status": "ok",
        "app": "OpsLens AI",
        "connectedBackend": True,
        "summary": {
            "openIncidents": 3,
            "criticalIssues": 1,
            "monitoredWorkflows": 12,
            "lastCheckedUtc": datetime.now(timezone.utc).isoformat(),
        },
        "activeIncidents": [
            {
                "id": "INC-1001",
                "severity": "critical",
                "title": "Quote Sync workflow failures",
                "recommendation": "Review latest workflow revision and test 3 sample records.",
                "affectedRecords": 42,
            },
            {
                "id": "INC-1002",
                "severity": "high",
                "title": "Owner routing mismatch after property update",
                "recommendation": "Validate owner mapping and confirm fallback logic.",
                "affectedRecords": 17,
            },
            {
                "id": "INC-1003",
                "severity": "medium",
                "title": "Duplicate contacts spike after import",
                "recommendation": "Review import source and run duplicate cleanup queue.",
                "affectedRecords": 9,
            },
        ],
        "debug": {
            "portalId": query.get("portalId", "not-provided"),
            "userId": query.get("userId", "not-provided"),
            "userEmail": query.get("userEmail", "not-provided"),
            "appId": query.get("appId", "not-provided"),
        },
    }
""",
    WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "settings_store.py": """
from pathlib import Path
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/settings-store", tags=["settings-store"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "portal_settings.json"

DEFAULT_SETTINGS = {
    "slackWebhookUrl": "",
    "alertThreshold": "high",
    "criticalWorkflows": "",
}


def _read_all_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


def _write_all_settings(data: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@router.get("")
async def get_settings(request: Request):
    query = dict(request.query_params)
    portal_id = query.get("portalId")
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required")

    all_settings = _read_all_settings()
    current = all_settings.get(portal_id, DEFAULT_SETTINGS.copy())

    return {
        "status": "ok",
        "portalId": portal_id,
        "settings": current,
        "loadedAtUtc": datetime.now(timezone.utc).isoformat(),
    }


@router.post("")
async def save_settings(request: Request):
    query = dict(request.query_params)
    portal_id = query.get("portalId")
    if not portal_id:
        raise HTTPException(status_code=400, detail="portalId is required")

    body = await request.json()

    settings = {
        "slackWebhookUrl": str(body.get("slackWebhookUrl", "")).strip(),
        "alertThreshold": str(body.get("alertThreshold", "high")).strip() or "high",
        "criticalWorkflows": str(body.get("criticalWorkflows", "")).strip(),
    }

    all_settings = _read_all_settings()
    all_settings[portal_id] = settings
    _write_all_settings(all_settings)

    return {
        "status": "ok",
        "portalId": portal_id,
        "settings": settings,
        "savedAtUtc": datetime.now(timezone.utc).isoformat(),
    }
""",
    WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "router.py": """
from fastapi import APIRouter

from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.settings_store import router as settings_store_router
from app.api.v1.routes.webhooks import router as webhook_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhook_router)
api_router.include_router(dashboard_router)
api_router.include_router(settings_store_router)
""",
    PROJECT_ROOT / "src" / "app" / "pages" / "Home.tsx": """
import React, { useEffect, useState } from "react";
import {
  Box,
  Divider,
  EmptyState,
  Flex,
  Text,
  hubspot,
} from "@hubspot/ui-extensions";
import {
  HeaderActions,
  PrimaryHeaderActionButton,
  SecondaryHeaderActionButton,
} from "@hubspot/ui-extensions/pages/home";

const BACKEND_BASE_URL = "https://opslens.local";

hubspot.extend(({ context }) => {
  return <Home context={context} />;
});

const Home = ({ context }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState(null);

  const loadOverview = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await hubspot.fetch(
        `${BACKEND_BASE_URL}/api/v1/dashboard/overview`,
        {
          method: "GET",
          timeout: 3000,
        }
      );

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      setOverview(data);
    } catch (err) {
      console.error("Failed to load dashboard overview", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOverview().catch((err) =>
      console.error("Unexpected dashboard load error", err)
    );
  }, []);

  const incidents = overview?.activeIncidents ?? [];

  return (
    <>
      <HeaderActions>
        <PrimaryHeaderActionButton onClick={() => loadOverview()}>
          Refresh queue
        </PrimaryHeaderActionButton>
        <SecondaryHeaderActionButton onClick={() => console.log("open-settings")}>
          Settings
        </SecondaryHeaderActionButton>
      </HeaderActions>

      <Flex direction="column" gap="medium">
        <EmptyState title="OpsLens AI is connected" layout="vertical">
          <Text>
            This page is now loading live summary and incident data from the local Python backend.
          </Text>
        </EmptyState>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Backend status</Text>
          <Text>{loading ? "Loading..." : overview?.status ?? "No response yet"}</Text>
          <Text>{error ? `Error: ${error}` : "No fetch error detected."}</Text>
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Ops summary</Text>
          <Text>Open incidents: {String(overview?.summary?.openIncidents ?? "-")}</Text>
          <Text>Critical issues: {String(overview?.summary?.criticalIssues ?? "-")}</Text>
          <Text>Monitored workflows: {String(overview?.summary?.monitoredWorkflows ?? "-")}</Text>
          <Text>Last checked: {String(overview?.summary?.lastCheckedUtc ?? "-")}</Text>
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Active incidents</Text>
          {incidents.length === 0 ? (
            <Text>No incidents returned.</Text>
          ) : (
            <Flex direction="column" gap="small">
              {incidents.map((incident) => (
                <Box key={incident.id}>
                  <Text format={{ fontWeight: "bold" }}>
                    [{String(incident.severity).toUpperCase()}] {incident.title}
                  </Text>
                  <Text>ID: {incident.id}</Text>
                  <Text>Affected records: {String(incident.affectedRecords ?? "-")}</Text>
                  <Text>Recommended next step: {incident.recommendation}</Text>
                </Box>
              ))}
            </Flex>
          )}
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Debug context</Text>
          <Text>Portal ID from HubSpot context: {String(context?.portal?.id ?? "unknown")}</Text>
          <Text>User ID from HubSpot context: {String(context?.user?.id ?? "unknown")}</Text>
          <Text>Portal ID seen by backend: {String(overview?.debug?.portalId ?? "unknown")}</Text>
          <Text>User ID seen by backend: {String(overview?.debug?.userId ?? "unknown")}</Text>
        </Box>
      </Flex>
    </>
  );
};
""",
    PROJECT_ROOT / "src" / "app" / "settings" / "SettingsPage.tsx": """
import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  Divider,
  EmptyState,
  Flex,
  Form,
  Input,
  Select,
  Text,
  TextArea,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://opslens.local";

hubspot.extend(({ context }) => {
  return <SettingsPage context={context} />;
});

const SettingsPage = ({ context }) => {
  const [loading, setLoading] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");
  const [alertThreshold, setAlertThreshold] = useState("high");
  const [criticalWorkflows, setCriticalWorkflows] = useState("");

  const loadSettings = async () => {
    setLoading(true);
    setErrorMessage("");
    setSaveMessage("");

    try {
      const response = await hubspot.fetch(
        `${BACKEND_BASE_URL}/api/v1/settings-store`,
        {
          method: "GET",
          timeout: 3000,
        }
      );

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      setSlackWebhookUrl(data?.settings?.slackWebhookUrl ?? "");
      setAlertThreshold(data?.settings?.alertThreshold ?? "high");
      setCriticalWorkflows(data?.settings?.criticalWorkflows ?? "");
    } catch (err) {
      console.error("Failed to load settings", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setErrorMessage("");
    setSaveMessage("");

    try {
      const response = await hubspot.fetch(
        `${BACKEND_BASE_URL}/api/v1/settings-store`,
        {
          method: "POST",
          timeout: 3000,
          body: JSON.stringify({
            slackWebhookUrl,
            alertThreshold,
            criticalWorkflows,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      setSaveMessage(`Saved at ${data.savedAtUtc}`);
    } catch (err) {
      console.error("Failed to save settings", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    }
  };

  useEffect(() => {
    loadSettings().catch((err) =>
      console.error("Unexpected settings load error", err)
    );
  }, []);

  return (
    <Flex direction="column" gap="medium">
      <EmptyState title="OpsLens AI settings" layout="vertical">
        <Text>
          This page now loads and saves portal-level OpsLens settings through the local Python backend.
        </Text>
      </EmptyState>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Backend status</Text>
        <Text>{loading ? "Loading settings..." : "Ready"}</Text>
        <Text>{errorMessage ? `Error: ${errorMessage}` : "No settings fetch error detected."}</Text>
        <Text>{saveMessage ? saveMessage : "No settings save event yet."}</Text>
      </Box>

      <Divider />

      <Form
        preventDefault={true}
        onSubmit={() => {
          saveSettings().catch((err) =>
            console.error("Unexpected settings save error", err)
          );
        }}
      >
        <Flex direction="column" gap="medium">
          <Input
            label="Slack webhook URL"
            name="slackWebhookUrl"
            value={slackWebhookUrl}
            onChange={(value) => setSlackWebhookUrl(value)}
            placeholder="https://hooks.slack.com/services/..."
          />

          <Select
            label="Alert threshold"
            name="alertThreshold"
            value={alertThreshold}
            onChange={(value) => setAlertThreshold(String(value))}
            options={[
              { label: "Critical", value: "critical" },
              { label: "High", value: "high" },
              { label: "Medium", value: "medium" },
            ]}
          />

          <TextArea
            label="Critical workflows"
            name="criticalWorkflows"
            value={criticalWorkflows}
            onChange={(value) => setCriticalWorkflows(value)}
            placeholder={"Quote Sync\\nOwner Routing\\nImport Cleanup"}
            description="One workflow name per line."
          />

          <Button type="submit">Save settings</Button>
        </Flex>
      </Form>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Debug context</Text>
        <Text>Portal ID: {String(context?.portal?.id ?? "unknown")}</Text>
        <Text>User ID: {String(context?.user?.id ?? "unknown")}</Text>
      </Box>
    </Flex>
  );
};
""",
}

for path, content in files.items():
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\\n"), encoding="utf-8")

print("OpsLens step 6B scaffold created successfully.")
print(f"Project root: {PROJECT_ROOT}")
print(f"Workspace root: {WORKSPACE_ROOT}")
print()
print("Updated / created files:")
for path in files:
    print(f" - {path}")