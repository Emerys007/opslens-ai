from pathlib import Path
import textwrap

PROJECT_ROOT = Path.cwd()
WORKSPACE_ROOT = PROJECT_ROOT.parent

files = {
    WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "record_risk.py": """
from fastapi import APIRouter, Request

router = APIRouter(prefix="/records", tags=["records"])


@router.get("/contact-risk")
async def contact_risk(request: Request):
    query = dict(request.query_params)

    record_id = query.get("recordId", "unknown")
    object_type = query.get("objectTypeId", "0-1")

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

    return {
        "status": "ok",
        "record": {
            "recordId": record_id,
            "objectTypeId": object_type,
        },
        "risk": {
            "level": risk_level,
            "incidentTitle": incident_title,
            "affectedWorkflows": affected_workflows,
            "recommendation": recommendation,
        },
        "debug": {
            "portalId": query.get("portalId", "not-provided"),
            "userId": query.get("userId", "not-provided"),
            "userEmail": query.get("userEmail", "not-provided"),
            "appId": query.get("appId", "not-provided"),
        },
    }
""",
    WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "router.py": """
from fastapi import APIRouter

from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.record_risk import router as record_risk_router
from app.api.v1.routes.settings_store import router as settings_store_router
from app.api.v1.routes.webhooks import router as webhook_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhook_router)
api_router.include_router(dashboard_router)
api_router.include_router(settings_store_router)
api_router.include_router(record_risk_router)
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
      <Text>Risk level: {String(payload?.risk?.level ?? "-").toUpperCase()}</Text>
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

print("OpsLens step 7 scaffold created successfully.")
print(f"Project root: {PROJECT_ROOT}")
print(f"Workspace root: {WORKSPACE_ROOT}")
print()
print("Updated / created files:")
for path in files:
    print(f" - {path}")
