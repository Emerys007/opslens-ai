from pathlib import Path

path = Path(r"C:\OpsLens AI\opslens-ai\src\app\pages\Home.tsx")
path.parent.mkdir(parents=True, exist_ok=True)

content = r'''import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  Divider,
  EmptyState,
  Flex,
  Text,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

hubspot.extend(({ context }) => {
  return <HomePage context={context} />;
});

type HomePageProps = {
  context: any;
};

type OverviewResponse = {
  status?: string;
  app?: string;
  connectedBackend?: boolean;
  settings?: {
    portalId?: string;
    slackWebhookUrl?: string;
    alertThreshold?: string;
    criticalWorkflows?: string;
    updatedAtUtc?: string;
    storage?: string;
  };
  summary?: {
    openIncidents?: number;
    criticalIssues?: number;
    monitoredWorkflows?: number;
    lastCheckedUtc?: string;
    activeIncidents?: Array<{
      id?: string;
      severity?: string;
      title?: string;
      affectedRecords?: number;
      recommendation?: string;
    }>;
    settingsStorage?: string;
    savedAlertRows?: number;
    visibleRowsAtThreshold?: number;
    dbConfigured?: boolean;
  };
  recentAlerts?: Array<{
    severity?: string;
    result?: string;
    receivedAtUtc?: string;
    objectType?: string;
    objectId?: string;
    workflowId?: string;
    callbackId?: string;
    analystNote?: string;
  }>;
};

type WebhookEvent = {
  receivedAtUtc?: string;
  portalId?: string;
  appId?: string;
  subscriptionType?: string;
  objectTypeId?: string | null;
  objectId?: string;
  propertyName?: string | null;
  propertyValue?: string | null;
  changeSource?: string | null;
  changeFlag?: string | null;
  sourceId?: string | null;
  eventId?: string | null;
  subscriptionId?: string | null;
  attemptNumber?: number | null;
  occurredAtUtc?: string | null;
};

type RecentWebhooksResponse = {
  status?: string;
  dbConfigured?: boolean;
  count?: number;
  events?: WebhookEvent[];
};

const HomePage = ({ context }: HomePageProps) => {
  const [loading, setLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [webhookError, setWebhookError] = useState("");
  const [overviewData, setOverviewData] = useState<OverviewResponse | null>(null);
  const [recentWebhookActivity, setRecentWebhookActivity] = useState<WebhookEvent[]>([]);

  const formatDate = (value?: string | null) => {
    if (!value) return "-";
    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  };

  const loadOverview = async () => {
    setOverviewError("");

    const response = await hubspot.fetch(
      `${BACKEND_BASE_URL}/api/v1/dashboard/overview`,
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Overview request failed with status ${response.status}`);
    }

    const data = (await response.json()) as OverviewResponse;
    setOverviewData(data);
  };

  const loadRecentWebhookActivity = async () => {
    setWebhookError("");

    const response = await hubspot.fetch(
      `${BACKEND_BASE_URL}/api/v1/webhooks/recent`,
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Recent webhooks request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecentWebhooksResponse;
    setRecentWebhookActivity(Array.isArray(data?.events) ? data.events : []);
  };

  const refreshAll = async () => {
    setLoading(true);
    setOverviewError("");
    setWebhookError("");

    try {
      await Promise.all([
        loadOverview(),
        loadRecentWebhookActivity(),
      ]);
    } catch (err) {
      console.error("App Home refresh failed", err);
      const message = err instanceof Error ? err.message : "Unknown refresh error";

      if (message.toLowerCase().includes("webhook")) {
        setWebhookError(message);
      } else if (message.toLowerCase().includes("overview")) {
        setOverviewError(message);
      } else {
        setOverviewError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll().catch((err) => console.error("Unexpected Home load error", err));
  }, []);

  const settings = overviewData?.settings ?? {};
  const summary = overviewData?.summary ?? {};
  const activeIncidents = Array.isArray(summary?.activeIncidents) ? summary.activeIncidents : [];
  const recentAlerts = Array.isArray(overviewData?.recentAlerts) ? overviewData.recentAlerts : [];

  return (
    <Flex direction="column" gap="medium">
      <EmptyState title="OpsLens AI is connected" layout="vertical">
        <Text>
          This page is now loading live summary, recent alerts, and recent webhook activity from the hosted backend.
        </Text>
      </EmptyState>

      <Button
        onClick={() => {
          refreshAll().catch((err) =>
            console.error("Unexpected Home refresh error", err)
          );
        }}
      >
        Refresh
      </Button>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Backend status</Text>
        <Text>{loading ? "Loading..." : "ok"}</Text>
        <Text>{overviewError ? `Overview error: ${overviewError}` : "No fetch error detected."}</Text>
        <Text>{webhookError ? `Webhook feed error: ${webhookError}` : "No webhook feed error detected."}</Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Applied settings</Text>
        <Text>Alert threshold: {String(settings?.alertThreshold ?? "-")}</Text>
        <Text>Critical workflows: {String(settings?.criticalWorkflows ?? "-")}</Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Ops summary</Text>
        <Text>Open incidents: {String(summary?.openIncidents ?? "-")}</Text>
        <Text>Critical issues: {String(summary?.criticalIssues ?? "-")}</Text>
        <Text>Monitored workflows: {String(summary?.monitoredWorkflows ?? "-")}</Text>
        <Text>Last checked: {formatDate(summary?.lastCheckedUtc)}</Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Active incidents</Text>
        {activeIncidents.length === 0 ? (
          <Text>No active incidents returned.</Text>
        ) : (
          <Flex direction="column" gap="small">
            {activeIncidents.map((incident, idx) => (
              <Box key={incident?.id ?? idx}>
                <Text>
                  [{String(incident?.severity ?? "-").toUpperCase()}] {String(incident?.title ?? "Untitled incident")}
                </Text>
                <Text>ID: {String(incident?.id ?? "-")}</Text>
                <Text>Affected records: {String(incident?.affectedRecords ?? "-")}</Text>
                <Text>Recommendation: {String(incident?.recommendation ?? "-")}</Text>
              </Box>
            ))}
          </Flex>
        )}
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Recent captured alerts</Text>
        {recentAlerts.length === 0 ? (
          <Text>No recent alerts found in Postgres for this portal.</Text>
        ) : (
          <Flex direction="column" gap="small">
            {recentAlerts.map((alert, idx) => (
              <Box key={alert?.callbackId ?? idx}>
                <Text>
                  {String(alert?.severity ?? "-").toUpperCase()} - {String(alert?.result ?? "-")}
                </Text>
                <Text>Received: {formatDate(alert?.receivedAtUtc)}</Text>
                <Text>
                  Object: {String(alert?.objectType ?? "-")} / {String(alert?.objectId ?? "-")}
                </Text>
                <Text>Workflow ID: {String(alert?.workflowId ?? "-")}</Text>
                <Text>Callback ID: {String(alert?.callbackId ?? "-")}</Text>
                <Text>Analyst note: {String(alert?.analystNote ?? "-")}</Text>
              </Box>
            ))}
          </Flex>
        )}
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Recent webhook activity</Text>
        {recentWebhookActivity.length === 0 ? (
          <Text>No recent webhook events found for this portal.</Text>
        ) : (
          <Flex direction="column" gap="small">
            {recentWebhookActivity.map((event, idx) => (
              <Box key={event?.eventId ?? `${event?.subscriptionType ?? "event"}-${idx}`}>
                <Text>
                  {String(event?.subscriptionType ?? "-")} on object {String(event?.objectId ?? "-")}
                </Text>
                <Text>Received: {formatDate(event?.receivedAtUtc)}</Text>
                <Text>Occurred: {formatDate(event?.occurredAtUtc)}</Text>
                <Text>Property: {String(event?.propertyName ?? "-")}</Text>
                <Text>Value: {String(event?.propertyValue ?? "-")}</Text>
                <Text>Change source: {String(event?.changeSource ?? "-")}</Text>
                <Text>Source ID: {String(event?.sourceId ?? "-")}</Text>
                <Text>Event ID: {String(event?.eventId ?? "-")}</Text>
              </Box>
            ))}
          </Flex>
        )}
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Debug context</Text>
        <Text>Portal ID: {String(context?.portal?.id ?? "unknown")}</Text>
        <Text>User ID: {String(context?.user?.id ?? "unknown")}</Text>
        <Text>User Email: {String(context?.user?.email ?? "unknown")}</Text>
        <Text>Overview URL: {BACKEND_BASE_URL}/api/v1/dashboard/overview</Text>
        <Text>Webhook URL: {BACKEND_BASE_URL}/api/v1/webhooks/recent</Text>
      </Box>
    </Flex>
  );
};

export default HomePage;
'''
path.write_text(content, encoding="utf-8")
print(f"Updated App Home page: {path}")