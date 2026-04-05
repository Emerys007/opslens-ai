from pathlib import Path
import textwrap

PROJECT_ROOT = Path.cwd()
WORKSPACE_ROOT = PROJECT_ROOT.parent

files = {
    WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "dashboard.py": """
from datetime import datetime, timezone
from pathlib import Path
import json

from fastapi import APIRouter, Request

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "portal_settings.json"

SEVERITY_ORDER = {
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def _read_all_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


@router.get("/overview")
async def dashboard_overview(request: Request):
    query = dict(request.query_params)
    portal_id = query.get("portalId", "not-provided")

    all_settings = _read_all_settings()
    portal_settings = all_settings.get(
        portal_id,
        {
            "slackWebhookUrl": "",
            "alertThreshold": "high",
            "criticalWorkflows": "",
        },
    )

    threshold = str(portal_settings.get("alertThreshold", "high")).lower()
    threshold_rank = SEVERITY_ORDER.get(threshold, 2)

    all_incidents = [
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
    ]

    filtered_incidents = [
        incident
        for incident in all_incidents
        if SEVERITY_ORDER.get(incident["severity"], 0) >= threshold_rank
    ]

    critical_count = len(
        [incident for incident in filtered_incidents if incident["severity"] == "critical"]
    )

    return {
        "status": "ok",
        "app": "OpsLens AI",
        "connectedBackend": True,
        "appliedSettings": portal_settings,
        "summary": {
            "openIncidents": len(filtered_incidents),
            "criticalIssues": critical_count,
            "monitoredWorkflows": 12,
            "lastCheckedUtc": datetime.now(timezone.utc).isoformat(),
        },
        "activeIncidents": filtered_incidents,
        "debug": {
            "portalId": portal_id,
            "userId": query.get("userId", "not-provided"),
            "userEmail": query.get("userEmail", "not-provided"),
            "appId": query.get("appId", "not-provided"),
        },
    }
""",
    WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "record_risk.py": """
from pathlib import Path
import json

from fastapi import APIRouter, Request

router = APIRouter(prefix="/records", tags=["records"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "portal_settings.json"

SEVERITY_ORDER = {
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def _read_all_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


@router.get("/contact-risk")
async def contact_risk(request: Request):
    query = dict(request.query_params)

    record_id = query.get("recordId", "unknown")
    object_type = query.get("objectTypeId", "0-1")
    portal_id = query.get("portalId", "not-provided")

    all_settings = _read_all_settings()
    portal_settings = all_settings.get(
        portal_id,
        {
            "slackWebhookUrl": "",
            "alertThreshold": "high",
            "criticalWorkflows": "",
        },
    )

    threshold = str(portal_settings.get("alertThreshold", "high")).lower()
    threshold_rank = SEVERITY_ORDER.get(threshold, 2)

    if str(record_id).endswith("2"):
        risk_level = "critical"
        incident_title = "Quote Sync workflow failures"
        affected_workflows = 3
        recommendation = "Review latest workflow revision and test this contact through the sync path."
    elif str(record_id).endswith("5"):
        risk_level = "high"
        incident_title = "Owner routing mismatch after property update"
        affected_workflows = 2
        recommendation = "Validate owner mapping and confirm fallback routing logic."
    else:
        risk_level = "medium"
        incident_title = "Duplicate contacts spike after import"
        affected_workflows = 1
        recommendation = "Review duplicate cleanup queue and confirm this record's merge status."

    visible = SEVERITY_ORDER.get(risk_level, 0) >= threshold_rank

    return {
        "status": "ok",
        "record": {
            "recordId": record_id,
            "objectTypeId": object_type,
        },
        "appliedSettings": portal_settings,
        "risk": {
            "level": risk_level,
            "incidentTitle": incident_title if visible else "Below current alert threshold",
            "affectedWorkflows": affected_workflows if visible else 0,
            "recommendation": recommendation if visible else "No action required at the current alert threshold.",
            "visibleAtCurrentThreshold": visible,
        },
        "debug": {
            "portalId": portal_id,
            "userId": query.get("userId", "not-provided"),
            "userEmail": query.get("userEmail", "not-provided"),
            "appId": query.get("appId", "not-provided"),
        },
    }
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
          <Text format={{ fontWeight: "bold" }}>Applied settings</Text>
          <Text>Alert threshold: {String(overview?.appliedSettings?.alertThreshold ?? "-").toUpperCase()}</Text>
          <Text>Critical workflows: {String(overview?.appliedSettings?.criticalWorkflows ?? "-")}</Text>
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
            <Text>No incidents returned at the current threshold.</Text>
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
    PROJECT_ROOT / "src" / "app" / "cards" / "NewCard.tsx": """
import React, { useEffect, useState } from "react";
import { Button, Divider, Flex, Text, hubspot } from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://opslens.local";

hubspot.extend(({ context }) => {
  return <NewCard context={context} />;
});

const NewCard = ({ context }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);

  const recordId = String(context?.crm?.objectId ?? "unknown");
  const objectTypeId = String(context?.crm?.objectTypeId ?? "0-1");

  const loadRisk = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await hubspot.fetch(
        `${BACKEND_BASE_URL}/api/v1/records/contact-risk?recordId=${encodeURIComponent(recordId)}&objectTypeId=${encodeURIComponent(objectTypeId)}`,
        {
          method: "GET",
          timeout: 3000,
        }
      );

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      setPayload(data);
    } catch (err) {
      console.error("Failed to load record risk", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRisk().catch((err) =>
      console.error("Unexpected record risk load error", err)
    );
  }, [recordId, objectTypeId]);

  return (
    <Flex direction="column" gap="small">
      <Text format={{ fontWeight: "bold" }}>OpsLens AI</Text>
      <Text>
        {loading
          ? "Loading record risk..."
          : error
            ? `Error: ${error}`
            : "Live record risk loaded from the local Python backend."}
      </Text>

      <Divider />

      <Text>CRM object type: {objectTypeId}</Text>
      <Text>Record ID: {recordId}</Text>
      <Text>Alert threshold: {String(payload?.appliedSettings?.alertThreshold ?? "-").toUpperCase()}</Text>
      <Text>Risk level: {String(payload?.risk?.level ?? "-").toUpperCase()}</Text>
      <Text>Visible at threshold: {String(payload?.risk?.visibleAtCurrentThreshold ?? false)}</Text>
      <Text>Active incident: {String(payload?.risk?.incidentTitle ?? "-")}</Text>
      <Text>Affected workflows: {String(payload?.risk?.affectedWorkflows ?? "-")}</Text>
      <Text>Recommendation: {String(payload?.risk?.recommendation ?? "-")}</Text>

      <Button onClick={() => loadRisk()}>
        Refresh record risk
      </Button>
    </Flex>
  );
};
""",
}

for path, content in files.items():
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")

print("OpsLens step 8 scaffold created successfully.")
print(f"Project root: {PROJECT_ROOT}")
print(f"Workspace root: {WORKSPACE_ROOT}")
print()
print("Updated / created files:")
for path in files:
    print(f" - {path}")
