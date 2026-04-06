from pathlib import Path
import json
import textwrap

ROOT = Path(r"C:\OpsLens AI")
BACKEND = ROOT / "backend"
PROJECT = ROOT / "opslens-ai"

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

write_file(BACKEND / "app" / "api" / "v1" / "routes" / "alerts_feed.py", """
from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/recent")
def recent_alerts(request: Request, limit: int = 10):
    safe_limit = max(1, min(limit, 25))
    portal_id = request.query_params.get("portalId")

    if not init_db():
        return {
            "status": "ok",
            "dbConfigured": False,
            "alerts": [],
        }

    session = get_session()
    if session is None:
        return {
            "status": "ok",
            "dbConfigured": False,
            "alerts": [],
        }

    try:
        stmt = select(AlertEvent)

        if portal_id:
            stmt = stmt.where(AlertEvent.portal_id == str(portal_id))

        stmt = stmt.order_by(desc(AlertEvent.received_at_utc)).limit(safe_limit)
        rows = session.execute(stmt).scalars().all()

        alerts = []
        for row in rows:
            alerts.append(
                {
                    "id": row.id,
                    "receivedAtUtc": row.received_at_utc.isoformat() if row.received_at_utc else None,
                    "callbackId": row.callback_id,
                    "portalId": row.portal_id,
                    "workflowId": row.workflow_id,
                    "objectType": row.object_type,
                    "objectId": row.object_id,
                    "severityOverride": row.severity_override,
                    "analystNote": row.analyst_note,
                    "result": row.result,
                    "reason": row.reason,
                }
            )

        return {
            "status": "ok",
            "dbConfigured": True,
            "count": len(alerts),
            "alerts": alerts,
        }
    finally:
        session.close()
""")

write_file(BACKEND / "app" / "api" / "v1" / "router.py", """
from fastapi import APIRouter

from app.api.v1.routes.alerts_feed import router as alerts_feed_router
from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.record_risk import router as record_risk_router
from app.api.v1.routes.settings_store import router as settings_store_router
from app.api.v1.routes.webhooks import router as webhook_router
from app.api.v1.routes.workflow_actions import router as workflow_actions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhook_router)
api_router.include_router(dashboard_router)
api_router.include_router(settings_store_router)
api_router.include_router(record_risk_router)
api_router.include_router(workflow_actions_router)
api_router.include_router(alerts_feed_router)
""")

app_hsmeta_path = PROJECT / "src" / "app" / "app-hsmeta.json"
app_meta = json.loads(app_hsmeta_path.read_text(encoding="utf-8-sig"))
config = app_meta.setdefault("config", {})
permitted_urls = config.setdefault("permittedUrls", {})
fetch_urls = permitted_urls.setdefault("fetch", [])

if "https://api.app-sync.com" not in fetch_urls:
    fetch_urls.append("https://api.app-sync.com")

app_hsmeta_path.write_text(json.dumps(app_meta, indent=2), encoding="utf-8")

write_file(PROJECT / "src" / "app" / "pages" / "Home.tsx", """
import React, { useEffect, useState } from "react";
import { Button, Divider, Flex, Text, hubspot } from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

type OverviewIncident = {
  id?: string;
  severity?: string;
  title?: string;
  affectedRecords?: number;
  recommendation?: string;
};

type OverviewResponse = {
  status?: string;
  settings?: {
    alertThreshold?: string;
    criticalWorkflows?: string;
  };
  summary?: {
    openIncidents?: number;
    criticalIssues?: number;
    monitoredWorkflows?: number;
    lastCheckedUtc?: string;
    activeIncidents?: OverviewIncident[];
  };
};

type AlertRow = {
  id?: number;
  receivedAtUtc?: string;
  callbackId?: string;
  portalId?: string;
  workflowId?: string;
  objectType?: string;
  objectId?: string;
  severityOverride?: string;
  analystNote?: string;
  result?: string;
  reason?: string;
};

type RecentAlertsResponse = {
  status?: string;
  dbConfigured?: boolean;
  count?: number;
  alerts?: AlertRow[];
};

hubspot.extend(() => <Home />);

function safeText(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

function formatDateTime(value: unknown): string {
  if (!value) return "-";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

const Home = () => {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [overviewError, setOverviewError] = useState("");
  const [alertsError, setAlertsError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadAll = async () => {
    setLoading(true);
    setOverviewError("");
    setAlertsError("");

    try {
      const overviewResponse = await hubspot.fetch(`${BACKEND_BASE_URL}/api/v1/dashboard/overview`);
      if (!overviewResponse.ok) {
        throw new Error(`Overview request failed with status ${overviewResponse.status}`);
      }
      const overviewJson: OverviewResponse = await overviewResponse.json();
      setOverview(overviewJson);
    } catch (error) {
      setOverviewError(error instanceof Error ? error.message : "Unknown overview error");
    }

    try {
      const alertsResponse = await hubspot.fetch(`${BACKEND_BASE_URL}/api/v1/alerts/recent?limit=8`);
      if (!alertsResponse.ok) {
        throw new Error(`Recent alerts request failed with status ${alertsResponse.status}`);
      }
      const alertsJson: RecentAlertsResponse = await alertsResponse.json();
      setAlerts(Array.isArray(alertsJson.alerts) ? alertsJson.alerts : []);
    } catch (error) {
      setAlertsError(error instanceof Error ? error.message : "Unknown alerts error");
    }

    setLoading(false);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const activeIncidents = overview?.summary?.activeIncidents || [];

  return (
    <Flex direction="column">
      <Text>OpsLens AI is connected</Text>
      <Text>This page is now loading live summary and recent alerts from the hosted backend.</Text>
      <Button onClick={loadAll}>Refresh</Button>

      <Divider />

      <Text>Backend status</Text>
      <Text>
        {loading
          ? "Loading..."
          : overviewError
          ? `Overview error: ${overviewError}`
          : "ok"}
      </Text>
      <Text>
        {alertsError ? `Recent alerts error: ${alertsError}` : "No fetch error detected."}
      </Text>

      <Divider />

      <Text>Applied settings</Text>
      <Text>Alert threshold: {safeText(overview?.settings?.alertThreshold)}</Text>
      <Text>Critical workflows: {safeText(overview?.settings?.criticalWorkflows)}</Text>

      <Divider />

      <Text>Ops summary</Text>
      <Text>Open incidents: {safeText(overview?.summary?.openIncidents)}</Text>
      <Text>Critical issues: {safeText(overview?.summary?.criticalIssues)}</Text>
      <Text>Monitored workflows: {safeText(overview?.summary?.monitoredWorkflows)}</Text>
      <Text>Last checked: {formatDateTime(overview?.summary?.lastCheckedUtc)}</Text>

      <Divider />

      <Text>Active incidents</Text>
      {activeIncidents.length === 0 ? (
        <Text>No active incidents returned.</Text>
      ) : (
        activeIncidents.map((incident, index) => (
          <React.Fragment key={`incident-${index}`}>
            <Text>
              [{safeText(incident.severity, "unknown").toUpperCase()}] {safeText(incident.title)}
            </Text>
            <Text>ID: {safeText(incident.id)}</Text>
            <Text>Affected records: {safeText(incident.affectedRecords)}</Text>
            <Text>Recommendation: {safeText(incident.recommendation)}</Text>
            <Divider />
          </React.Fragment>
        ))
      )}

      <Text>Recent captured alerts</Text>
      {alerts.length === 0 ? (
        <Text>No recent alerts found in Postgres for this portal.</Text>
      ) : (
        alerts.map((alert, index) => (
          <React.Fragment key={`alert-${alert.id ?? index}`}>
            <Text>
              {safeText(alert.severityOverride, "use_settings").toUpperCase()} · {safeText(alert.result)}
            </Text>
            <Text>Received: {formatDateTime(alert.receivedAtUtc)}</Text>
            <Text>Object: {safeText(alert.objectType)} / {safeText(alert.objectId)}</Text>
            <Text>Workflow ID: {safeText(alert.workflowId)}</Text>
            <Text>Callback ID: {safeText(alert.callbackId)}</Text>
            <Text>Analyst note: {safeText(alert.analystNote, "No analyst note")}</Text>
            <Divider />
          </React.Fragment>
        ))
      )}
    </Flex>
  );
};

export default Home;
""")

print("OpsLens step 13 scaffold created successfully.")
print("Updated files:")
print(" - backend/app/api/v1/routes/alerts_feed.py")
print(" - backend/app/api/v1/router.py")
print(" - src/app/app-hsmeta.json")
print(" - src/app/pages/Home.tsx")
