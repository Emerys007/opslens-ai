from pathlib import Path
import json
import textwrap

PROJECT_ROOT = Path.cwd()
WORKSPACE_ROOT = PROJECT_ROOT.parent

app_hsmeta = PROJECT_ROOT / "src" / "app" / "app-hsmeta.json"
local_json = PROJECT_ROOT / "local.json"
home_tsx = PROJECT_ROOT / "src" / "app" / "pages" / "Home.tsx"

backend_router = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "router.py"
dashboard_route = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "dashboard.py"

if not app_hsmeta.exists():
    raise SystemExit(f"Could not find: {app_hsmeta}")

data = json.loads(app_hsmeta.read_text(encoding="utf-8"))
config = data.setdefault("config", {})
permitted_urls = config.setdefault("permittedUrls", {})
fetch_urls = permitted_urls.setdefault("fetch", [])
if "https://opslens.local" not in fetch_urls:
    fetch_urls.append("https://opslens.local")
permitted_urls.setdefault("img", [])
permitted_urls.setdefault("iframe", [])
app_hsmeta.write_text(json.dumps(data, indent=2), encoding="utf-8")

local_json.write_text(
    json.dumps(
        {
            "proxy": {
                "https://opslens.local": "http://127.0.0.1:8000"
            }
        },
        indent=2
    ),
    encoding="utf-8"
)

dashboard_route.parent.mkdir(parents=True, exist_ok=True)
dashboard_route.write_text(
    textwrap.dedent("""
    from datetime import datetime, timezone

    from fastapi import APIRouter, Request

    router = APIRouter(prefix="/dashboard", tags=["dashboard"])


    @router.get("/summary")
    async def dashboard_summary(request: Request):
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
            "debug": {
                "portalId": query.get("portalId", "not-provided"),
                "userId": query.get("userId", "not-provided"),
                "userEmail": query.get("userEmail", "not-provided"),
                "appId": query.get("appId", "not-provided"),
                "note": "During local proxy development, HubSpot metadata may not be appended unless request-signing is configured for the proxy.",
            },
        }
    """).lstrip("\n"),
    encoding="utf-8"
)

backend_router.write_text(
    textwrap.dedent("""
    from fastapi import APIRouter

    from app.api.v1.routes.dashboard import router as dashboard_router
    from app.api.v1.routes.health import router as health_router
    from app.api.v1.routes.webhooks import router as webhook_router

    api_router = APIRouter()
    api_router.include_router(health_router)
    api_router.include_router(webhook_router)
    api_router.include_router(dashboard_router)
    """).lstrip("\n"),
    encoding="utf-8"
)

home_tsx.write_text(
    textwrap.dedent("""
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
      const [summary, setSummary] = useState(null);

      const loadSummary = async () => {
        setLoading(true);
        setError("");

        try {
          const response = await hubspot.fetch(
            `${BACKEND_BASE_URL}/api/v1/dashboard/summary`,
            {
              method: "GET",
              timeout: 3000,
            }
          );

          if (!response.ok) {
            throw new Error(`Backend returned status ${response.status}`);
          }

          const data = await response.json();
          setSummary(data);
        } catch (err) {
          console.error("Failed to load dashboard summary", err);
          setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
          setLoading(false);
        }
      };

      useEffect(() => {
        loadSummary().catch((err) =>
          console.error("Unexpected dashboard load error", err)
        );
      }, []);

      return (
        <>
          <HeaderActions>
            <PrimaryHeaderActionButton onClick={() => loadSummary()}>
              Refresh queue
            </PrimaryHeaderActionButton>
            <SecondaryHeaderActionButton onClick={() => console.log("open-settings")}>
              Settings
            </SecondaryHeaderActionButton>
          </HeaderActions>

          <Flex direction="column" gap="medium">
            <EmptyState title="OpsLens AI is connected" layout="vertical">
              <Text>
                This page is now attempting to load live data from the local Python backend.
              </Text>
            </EmptyState>

            <Divider />

            <Box>
              <Text format={{ fontWeight: "bold" }}>Backend status</Text>
              <Text>{loading ? "Loading..." : summary?.status ?? "No response yet"}</Text>
              <Text>{error ? `Error: ${error}` : "No fetch error detected."}</Text>
            </Box>

            <Divider />

            <Box>
              <Text format={{ fontWeight: "bold" }}>Ops summary</Text>
              <Text>Open incidents: {String(summary?.summary?.openIncidents ?? "-")}</Text>
              <Text>Critical issues: {String(summary?.summary?.criticalIssues ?? "-")}</Text>
              <Text>Monitored workflows: {String(summary?.summary?.monitoredWorkflows ?? "-")}</Text>
              <Text>Last checked: {String(summary?.summary?.lastCheckedUtc ?? "-")}</Text>
            </Box>

            <Divider />

            <Box>
              <Text format={{ fontWeight: "bold" }}>Debug context</Text>
              <Text>Portal ID from HubSpot context: {String(context?.portal?.id ?? "unknown")}</Text>
              <Text>User ID from HubSpot context: {String(context?.user?.id ?? "unknown")}</Text>
              <Text>Portal ID seen by backend: {String(summary?.debug?.portalId ?? "unknown")}</Text>
              <Text>User ID seen by backend: {String(summary?.debug?.userId ?? "unknown")}</Text>
            </Box>
          </Flex>
        </>
      );
    };
    """).lstrip("\n"),
    encoding="utf-8"
)

print("OpsLens step 5 backend wiring scaffold created successfully.")
print(f"Project root: {PROJECT_ROOT}")
print(f"Workspace root: {WORKSPACE_ROOT}")
print()
print("Updated / created files:")
print(f" - {app_hsmeta}")
print(f" - {local_json}")
print(f" - {home_tsx}")
print(f" - {backend_router}")
print(f" - {dashboard_route}")