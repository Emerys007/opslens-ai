import React, { useEffect, useState } from "react";
import {
  Accordion,
  AutoGrid,
  Box,
  Button,
  Flex,
  Heading,
  StatusTag,
  Text,
  Tile,
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
  };
  debug?: {
    portalId?: string;
    userId?: string;
    userEmail?: string;
    appId?: string;
    dbConfigured?: boolean;
    savedAlertRows?: number;
    visibleRowsAtThreshold?: number;
    settingsStorage?: string;
  };
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

type MetricTileProps = {
  label: string;
  value: string | number;
  note?: string;
};

type StatusVariant = "danger" | "warning" | "info" | "success" | "default";

const MetricTile = ({ label, value, note }: MetricTileProps) => {
  return (
    <Tile compact>
      <Flex direction="column" gap="flush">
        <Text format={{ fontWeight: "bold" }}>{label}</Text>
        <Heading>{String(value)}</Heading>
        {note ? <Text>{note}</Text> : null}
      </Flex>
    </Tile>
  );
};

type DetailFieldProps = {
  label: string;
  value: string;
};

const DetailField = ({ label, value }: DetailFieldProps) => {
  return (
    <Box>
      <Text format={{ fontWeight: "bold" }}>{label}</Text>
      <Text>{value}</Text>
    </Box>
  );
};

const getStatusVariant = (
  variant: "loading" | "error" | "success" | "default"
): StatusVariant => {
  if (variant === "loading") return "info";
  if (variant === "error") return "warning";
  if (variant === "success") return "success";
  return "default";
};

const getSeverityVariant = (severity?: string | null): StatusVariant => {
  const level = String(severity || "").toLowerCase();

  if (level === "critical") return "danger";
  if (level === "high") return "warning";
  if (level === "medium") return "info";

  return "default";
};

const HomePage = ({ context }: HomePageProps) => {
  const [loading, setLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [webhookError, setWebhookError] = useState("");
  const [overviewData, setOverviewData] = useState<OverviewResponse | null>(null);
  const [recentWebhookActivity, setRecentWebhookActivity] = useState<WebhookEvent[]>([]);
  const [webhookDbConfigured, setWebhookDbConfigured] = useState<boolean | null>(null);

  const portalId = String(context?.portal?.id ?? "");
  const userId = String(context?.user?.id ?? "");
  const userEmail = String(context?.user?.email ?? "");
  const appId = String(context?.app?.id ?? context?.appId ?? "");

  const formatDate = (value?: string | null) => {
    if (!value) return "-";

    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  };

  const buildUrl = (path: string, params: Record<string, string>) => {
    const query = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {
      if (value) {
        query.set(key, value);
      }
    });

    const queryString = query.toString();
    return `${BACKEND_BASE_URL}${path}${queryString ? `?${queryString}` : ""}`;
  };

  const loadOverview = async () => {
    setOverviewError("");

    const response = await hubspot.fetch(
      buildUrl("/api/v1/dashboard/overview", {
        portalId,
        userId,
        userEmail,
        appId,
      }),
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
      buildUrl("/api/v1/webhooks/recent", {
        portalId,
      }),
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Recent webhooks request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecentWebhooksResponse;
    setWebhookDbConfigured(
      typeof data?.dbConfigured === "boolean" ? data.dbConfigured : null
    );
    setRecentWebhookActivity(Array.isArray(data?.events) ? data.events : []);
  };

  const refreshAll = async () => {
    setLoading(true);
    setOverviewError("");
    setWebhookError("");

    try {
      await Promise.all([loadOverview(), loadRecentWebhookActivity()]);
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
  }, [portalId, userId, userEmail, appId]);

  const settings = overviewData?.settings ?? {};
  const summary = overviewData?.summary ?? {};
  const debug = overviewData?.debug ?? {};
  const activeIncidents = Array.isArray(summary?.activeIncidents)
    ? summary.activeIncidents
    : [];
  const criticalWorkflowCount = String(settings?.criticalWorkflows ?? "")
    .split("\n")
    .map((value) => value.trim())
    .filter(Boolean).length;
  const webhookPreview = recentWebhookActivity.slice(0, 4);
  const pageStatus: { label: string; variant: StatusVariant } = loading
    ? { label: "Refreshing", variant: getStatusVariant("loading") }
    : overviewError || webhookError
      ? { label: "Needs attention", variant: getStatusVariant("error") }
      : { label: "Live", variant: getStatusVariant("success") };
  const incidentStatus: { label: string; variant: StatusVariant } =
    Number(summary?.openIncidents ?? 0) > 0
      ? { label: `${String(summary?.openIncidents ?? 0)} open`, variant: "warning" }
      : { label: "Stable", variant: "success" };
  const webhookStatus: { label: string; variant: StatusVariant } =
    webhookDbConfigured === false
      ? { label: "Database unavailable", variant: "warning" }
      : webhookPreview.length > 0
        ? { label: `${webhookPreview.length} recent`, variant: "info" }
        : { label: "Quiet", variant: "default" };

  return (
    <Flex direction="column" gap="small">
      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Box flex="auto">
              <Heading>OpsLens AI</Heading>
              <Text>
                Portal operations view for incidents, saved alerts, and webhook health.
              </Text>
            </Box>
            <Flex align="center" gap="small" wrap>
              <StatusTag variant={pageStatus.variant}>{pageStatus.label}</StatusTag>
              <Button
                onClick={() => {
                  refreshAll().catch((err) =>
                    console.error("Unexpected Home refresh error", err)
                  );
                }}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh"}
              </Button>
            </Flex>
          </Flex>

          {overviewError || webhookError ? (
            <Flex direction="column" gap="flush">
              {overviewError ? <Text>Overview: {overviewError}</Text> : null}
              {webhookError ? <Text>Webhooks: {webhookError}</Text> : null}
            </Flex>
          ) : (
            <Text>
              Last backend check {formatDate(summary?.lastCheckedUtc)}. Threshold{" "}
              {String(settings?.alertThreshold ?? "-").toUpperCase()}.
            </Text>
          )}
        </Flex>
      </Tile>

      <AutoGrid columnWidth={170} flexible={true} gap="small">
        <MetricTile
          label="Open incidents"
          value={String(summary?.openIncidents ?? "-")}
          note="Above the current alert threshold"
        />
        <MetricTile
          label="Critical issues"
          value={String(summary?.criticalIssues ?? "-")}
          note="Escalated incident count"
        />
        <MetricTile
          label="Monitored workflows"
          value={String(summary?.monitoredWorkflows ?? "-")}
          note={`${criticalWorkflowCount} marked critical`}
        />
        <MetricTile
          label="Saved alerts"
          value={String(debug?.savedAlertRows ?? "-")}
          note={`${String(debug?.visibleRowsAtThreshold ?? "-")} visible now`}
        />
      </AutoGrid>

      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Heading inline={true}>Incidents</Heading>
            <StatusTag variant={incidentStatus.variant}>{incidentStatus.label}</StatusTag>
          </Flex>

          {activeIncidents.length === 0 ? (
            <Text>No incidents are above the current alert threshold.</Text>
          ) : (
            <AutoGrid columnWidth={260} flexible={true} gap="small">
              {activeIncidents.map((incident, idx) => (
                <Tile compact key={incident?.id ?? idx}>
                  <Flex direction="column" gap="flush">
                    <Flex justify="between" align="center" wrap gap="small">
                      <Text format={{ fontWeight: "bold" }}>
                        {String(incident?.title ?? "Untitled incident")}
                      </Text>
                      <StatusTag
                        variant={getSeverityVariant(incident?.severity)}
                      >
                        {String(incident?.severity ?? "unknown").toUpperCase()}
                      </StatusTag>
                    </Flex>
                    <Text>ID: {String(incident?.id ?? "-")}</Text>
                    <Text>
                      Affected records: {String(incident?.affectedRecords ?? "-")}
                    </Text>
                    <Text>
                      Recommendation: {String(incident?.recommendation ?? "-")}
                    </Text>
                  </Flex>
                </Tile>
              ))}
            </AutoGrid>
          )}
        </Flex>
      </Tile>

      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Heading inline={true}>Saved alerts</Heading>
            <StatusTag variant="info">
              Threshold {String(settings?.alertThreshold ?? "-").toUpperCase()}
            </StatusTag>
          </Flex>

          <AutoGrid columnWidth={220} flexible={true} gap="small">
            <DetailField
              label="Saved alert rows"
              value={String(debug?.savedAlertRows ?? "-")}
            />
            <DetailField
              label="Visible at threshold"
              value={String(debug?.visibleRowsAtThreshold ?? "-")}
            />
            <DetailField
              label="Critical workflows"
              value={criticalWorkflowCount > 0 ? String(criticalWorkflowCount) : "None configured"}
            />
            <DetailField
              label="Settings storage"
              value={String(settings?.storage ?? debug?.settingsStorage ?? "-")}
            />
            <DetailField
              label="Workflow list"
              value={
                criticalWorkflowCount > 0
                  ? String(settings?.criticalWorkflows ?? "")
                      .split("\n")
                      .map((value) => value.trim())
                      .filter(Boolean)
                      .slice(0, 3)
                      .join(", ")
                  : "No critical workflow names saved"
              }
            />
            <DetailField
              label="Settings updated"
              value={formatDate(settings?.updatedAtUtc)}
            />
          </AutoGrid>
        </Flex>
      </Tile>

      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Heading inline={true}>Webhook activity</Heading>
            <StatusTag variant={webhookStatus.variant}>{webhookStatus.label}</StatusTag>
          </Flex>

          {webhookDbConfigured === false ? (
            <Text>Webhook database is not configured.</Text>
          ) : webhookPreview.length === 0 ? (
            <Text>No recent webhook events were found for this portal.</Text>
          ) : (
            <AutoGrid columnWidth={240} flexible={true} gap="small">
              {webhookPreview.map((event, idx) => (
                <Tile compact key={event?.eventId ?? `${event?.subscriptionType ?? "event"}-${idx}`}>
                  <Flex direction="column" gap="flush">
                    <Text format={{ fontWeight: "bold" }}>
                      {String(event?.subscriptionType ?? "-")}
                    </Text>
                    <Text>
                      Object {String(event?.objectId ?? "-")} • {String(event?.propertyName ?? "-")}
                    </Text>
                    <Text>Received {formatDate(event?.receivedAtUtc)}</Text>
                    <Text>Occurred {formatDate(event?.occurredAtUtc)}</Text>
                    <Text>
                      Value {String(event?.propertyValue ?? "-")} from {String(event?.changeSource ?? "-")}
                    </Text>
                  </Flex>
                </Tile>
              ))}
            </AutoGrid>
          )}
        </Flex>
      </Tile>

      <Accordion title="Technical details" size="small">
        <Tile compact>
          <AutoGrid columnWidth={220} flexible={true} gap="small">
            <DetailField label="Portal ID" value={portalId || "unknown"} />
            <DetailField label="User ID" value={userId || "unknown"} />
            <DetailField label="User email" value={userEmail || "unknown"} />
            <DetailField label="App ID" value={appId || "unknown"} />
            <DetailField
              label="Database configured"
              value={String(debug?.dbConfigured ?? "-")}
            />
            <DetailField
              label="Overview URL"
              value={buildUrl("/api/v1/dashboard/overview", {
                portalId,
                userId,
                userEmail,
                appId,
              })}
            />
            <DetailField
              label="Webhook URL"
              value={buildUrl("/api/v1/webhooks/recent", { portalId })}
            />
          </AutoGrid>
        </Tile>
      </Accordion>
    </Flex>
  );
};

export default HomePage;
