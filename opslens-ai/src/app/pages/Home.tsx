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

const TICKET_STAGE_LABELS: Record<string, string> = {
  "1341759033": "New Alert",
  "1341759034": "Investigating",
  "1341759035": "Waiting / Monitoring",
  "1341759036": "Resolved",
  "1341759037": "Closed as Duplicate",
};

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

type TicketProperties = {
  subject?: string;
  hs_pipeline_stage?: string;
  hs_lastmodifieddate?: string;
  opslens_ticket_callback_id?: string;
  opslens_ticket_workflow_id?: string;
  opslens_ticket_contact_id?: string;
  opslens_ticket_severity?: string;
  opslens_ticket_delivery_status?: string;
  opslens_ticket_reason?: string;
  opslens_ticket_first_alert_at?: string;
  opslens_ticket_last_alert_at?: string;
  opslens_ticket_repeat_count?: string;
  opslens_ticket_resolved_at?: string;
  opslens_ticket_resolution_reason?: string;
};

type TicketAutomationTicket = {
  id?: string;
  properties?: TicketProperties;
  createdAt?: string;
  updatedAt?: string;
  archived?: boolean;
  url?: string;
};

type TicketAutomationResponse = {
  status?: string;
  portalId?: string;
  provisioned?: boolean;
  pipelineId?: string;
  total?: number;
  results?: TicketAutomationTicket[];
};

type MetricTileProps = {
  label: string;
  value: string | number;
  note?: string;
};

type DetailFieldProps = {
  label: string;
  value: string;
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

const DetailField = ({ label, value }: DetailFieldProps) => {
  return (
    <Box>
      <Text format={{ fontWeight: "bold" }}>{label}</Text>
      <Text>{value}</Text>
    </Box>
  );
};

const getErrorMessage = (error: unknown) => {
  return error instanceof Error ? error.message : "Unknown error";
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

const getTicketStageLabel = (stageId?: string | null) => {
  const value = String(stageId || "").trim();
  return TICKET_STAGE_LABELS[value] || value || "Unknown";
};

const getTicketStageVariant = (stageId?: string | null): StatusVariant => {
  const value = String(stageId || "").trim();

  if (value === "1341759033") return "danger";
  if (value === "1341759034") return "warning";
  if (value === "1341759035") return "info";
  if (value === "1341759036") return "success";

  return "default";
};

const HomePage = ({ context }: HomePageProps) => {
  const [loading, setLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [webhookError, setWebhookError] = useState("");
  const [ticketError, setTicketError] = useState("");
  const [overviewData, setOverviewData] = useState<OverviewResponse | null>(null);
  const [recentWebhookActivity, setRecentWebhookActivity] = useState<WebhookEvent[]>([]);
  const [webhookDbConfigured, setWebhookDbConfigured] = useState<boolean | null>(null);
  const [webhookEventCount, setWebhookEventCount] = useState(0);
  const [ticketLoading, setTicketLoading] = useState(false);
  const [ticketActivity, setTicketActivity] = useState<TicketAutomationTicket[]>([]);
  const [ticketActivityTotal, setTicketActivityTotal] = useState(0);
  const [ticketAutomationProvisioned, setTicketAutomationProvisioned] = useState<boolean | null>(null);
  const [ticketPipelineId, setTicketPipelineId] = useState("");

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
    const response = await hubspot.fetch(
      buildUrl("/api/v1/dashboard/overview", {
        portalId,
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
    const nextEvents = Array.isArray(data?.events) ? data.events : [];

    setWebhookDbConfigured(
      typeof data?.dbConfigured === "boolean" ? data.dbConfigured : null
    );
    setWebhookEventCount(
      typeof data?.count === "number" ? data.count : nextEvents.length
    );
    setRecentWebhookActivity(nextEvents);
  };

  const loadTicketAutomation = async () => {
    setTicketLoading(true);
    setTicketActivity([]);
    setTicketActivityTotal(0);
    setTicketAutomationProvisioned(null);
    setTicketPipelineId("");

    try {
      const response = await hubspot.fetch(
        buildUrl("/api/v1/dashboard/ticket-automation", {
          portalId,
          limit: "4",
        }),
        {
          method: "GET",
          timeout: 5000,
        }
      );

      if (!response.ok) {
        throw new Error(
          `Ticket automation request failed with status ${response.status}`
        );
      }

      const data = (await response.json()) as TicketAutomationResponse;
      const results = Array.isArray(data?.results) ? data.results : [];

      setTicketActivity(results);
      setTicketActivityTotal(
        typeof data?.total === "number" ? data.total : results.length
      );
      setTicketAutomationProvisioned(
        typeof data?.provisioned === "boolean" ? data.provisioned : null
      );
      setTicketPipelineId(String(data?.pipelineId ?? ""));
    } finally {
      setTicketLoading(false);
    }
  };

  const refreshAll = async () => {
    setLoading(true);
    setOverviewError("");
    setWebhookError("");
    setTicketError("");

    const results = await Promise.allSettled([
      loadOverview(),
      loadRecentWebhookActivity(),
      loadTicketAutomation(),
    ]);

    if (results[0].status === "rejected") {
      setOverviewError(getErrorMessage(results[0].reason));
    }

    if (results[1].status === "rejected") {
      setWebhookError(getErrorMessage(results[1].reason));
    }

    if (results[2].status === "rejected") {
      setTicketError(getErrorMessage(results[2].reason));
    }

    setLoading(false);
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
  const monitoredWorkflows = String(settings?.criticalWorkflows ?? "")
    .split("\n")
    .map((value) => value.trim())
    .filter(Boolean);
  const criticalWorkflowCount = monitoredWorkflows.length;
  const incidentPreview = activeIncidents.slice(0, 3);
  const webhookPreview = recentWebhookActivity.slice(0, 3);
  const ticketPreview = ticketActivity.slice(0, 3);
  const recentActiveTickets = ticketPreview.filter(
    (ticket) => !ticket?.properties?.opslens_ticket_resolved_at
  ).length;
  const recentResolvedTickets = ticketPreview.filter(
    (ticket) => Boolean(ticket?.properties?.opslens_ticket_resolved_at)
  ).length;
  const pageStatus: { label: string; variant: StatusVariant } = loading
    ? { label: "Refreshing", variant: getStatusVariant("loading") }
    : overviewError || webhookError || ticketError
      ? { label: "Needs attention", variant: getStatusVariant("error") }
      : { label: "Live", variant: getStatusVariant("success") };
  const incidentStatus: { label: string; variant: StatusVariant } = overviewError
    ? { label: "Overview issue", variant: "warning" }
    : Number(summary?.openIncidents ?? 0) > 0
      ? { label: `${String(summary?.openIncidents ?? 0)} open`, variant: "warning" }
      : { label: "Stable", variant: "success" };
  const savedAlertStatus: { label: string; variant: StatusVariant } = overviewError
    ? { label: "Unavailable", variant: "warning" }
    : Number(debug?.visibleRowsAtThreshold ?? 0) > 0
      ? { label: `${String(debug?.visibleRowsAtThreshold ?? 0)} visible`, variant: "info" }
      : { label: "Quiet", variant: "default" };
  const ticketStatus: { label: string; variant: StatusVariant } = ticketLoading
    ? { label: "Refreshing", variant: "info" }
    : ticketError
      ? { label: "Visibility issue", variant: "warning" }
      : ticketAutomationProvisioned === false
        ? { label: "Not provisioned", variant: "default" }
      : ticketActivityTotal === 0
        ? { label: "No tickets", variant: "default" }
        : recentActiveTickets > 0
          ? { label: `${recentActiveTickets} active`, variant: "warning" }
          : { label: "Resolved recently", variant: "success" };
  const webhookStatus: { label: string; variant: StatusVariant } = webhookError
    ? { label: "Feed issue", variant: "warning" }
    : webhookDbConfigured === false
      ? { label: "Database unavailable", variant: "warning" }
      : webhookPreview.length > 0
        ? { label: `${webhookPreview.length} recent`, variant: "info" }
        : { label: "Quiet", variant: "default" };

  const ticketAutomationUrl = buildUrl("/api/v1/dashboard/ticket-automation", {
    portalId,
    limit: "4",
  });

  return (
    <Flex direction="column" gap="small">
      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Box flex="auto">
              <Heading>OpsLens control center</Heading>
              <Text>
                Compact portal view for incidents, saved alerts, ticket automation,
                and webhook activity.
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

          {overviewError || webhookError || ticketError ? (
            <Flex direction="column" gap="flush">
              {overviewError ? <Text>Overview: {overviewError}</Text> : null}
              {ticketError ? <Text>Ticket automation: {ticketError}</Text> : null}
              {webhookError ? <Text>Webhooks: {webhookError}</Text> : null}
            </Flex>
          ) : (
            <Text>
              Last backend check {formatDate(summary?.lastCheckedUtc)}. Threshold{" "}
              {String(settings?.alertThreshold ?? "-").toUpperCase()} for portal{" "}
              {portalId || "unknown"}.
            </Text>
          )}
        </Flex>
      </Tile>

      <AutoGrid columnWidth={160} flexible={true} gap="small">
        <MetricTile
          label="Open incidents"
          value={String(summary?.openIncidents ?? "-")}
          note="Above the current threshold"
        />
        <MetricTile
          label="Critical issues"
          value={String(summary?.criticalIssues ?? "-")}
          note="Highest-severity incident count"
        />
        <MetricTile
          label="Saved alerts"
          value={String(debug?.visibleRowsAtThreshold ?? "-")}
          note={`${String(debug?.savedAlertRows ?? "-")} rows stored`}
        />
        <MetricTile
          label="Tracked tickets"
          value={String(ticketActivityTotal)}
          note="OpsLens tickets in this portal"
        />
        <MetricTile
          label="Webhook events"
          value={String(webhookEventCount)}
          note="Most recent activity sample"
        />
      </AutoGrid>

      <AutoGrid columnWidth={320} flexible={true} gap="small">
        <Tile compact>
          <Flex direction="column" gap="small">
            <Flex justify="between" align="center" wrap gap="small">
              <Box flex="auto">
                <Heading inline={true}>Incidents</Heading>
                <Text>Current operator queue above the saved threshold.</Text>
              </Box>
              <StatusTag variant={incidentStatus.variant}>{incidentStatus.label}</StatusTag>
            </Flex>

            {overviewError ? (
              <Text>Incident summary is unavailable until overview data reloads.</Text>
            ) : incidentPreview.length === 0 ? (
              <Text>No incidents are currently above the alert threshold.</Text>
            ) : (
              <Flex direction="column" gap="small">
                {incidentPreview.map((incident, idx) => (
                  <Tile compact key={incident?.id ?? idx}>
                    <Flex direction="column" gap="flush">
                      <Flex justify="between" align="center" wrap gap="small">
                        <Text format={{ fontWeight: "bold" }}>
                          {String(incident?.title ?? "Untitled incident")}
                        </Text>
                        <StatusTag variant={getSeverityVariant(incident?.severity)}>
                          {String(incident?.severity ?? "unknown").toUpperCase()}
                        </StatusTag>
                      </Flex>
                      <Text>ID {String(incident?.id ?? "-")}</Text>
                      <Text>
                        Affected records {String(incident?.affectedRecords ?? "-")}
                      </Text>
                      <Text>
                        Recommendation {String(incident?.recommendation ?? "-")}
                      </Text>
                    </Flex>
                  </Tile>
                ))}
              </Flex>
            )}
          </Flex>
        </Tile>

        <Tile compact>
          <Flex direction="column" gap="small">
            <Flex justify="between" align="center" wrap gap="small">
              <Box flex="auto">
                <Heading inline={true}>Saved alerts</Heading>
                <Text>Portal-level visibility, thresholds, and monitored workflows.</Text>
              </Box>
              <StatusTag variant={savedAlertStatus.variant}>{savedAlertStatus.label}</StatusTag>
            </Flex>

            {overviewError ? (
              <Text>Saved-alert context is unavailable until overview data reloads.</Text>
            ) : (
              <AutoGrid columnWidth={170} flexible={true} gap="small">
                <DetailField
                  label="Alert threshold"
                  value={String(settings?.alertThreshold ?? "-").toUpperCase()}
                />
                <DetailField
                  label="Critical workflows"
                  value={
                    criticalWorkflowCount > 0
                      ? String(criticalWorkflowCount)
                      : "None configured"
                  }
                />
                <DetailField
                  label="Saved alert rows"
                  value={String(debug?.savedAlertRows ?? "-")}
                />
                <DetailField
                  label="Settings storage"
                  value={String(settings?.storage ?? debug?.settingsStorage ?? "-")}
                />
                <DetailField
                  label="Workflow list"
                  value={
                    monitoredWorkflows.length > 0
                      ? monitoredWorkflows.slice(0, 3).join(", ")
                      : "No workflow names saved"
                  }
                />
                <DetailField
                  label="Settings updated"
                  value={formatDate(settings?.updatedAtUtc)}
                />
              </AutoGrid>
            )}
          </Flex>
        </Tile>

        <Tile compact>
          <Flex direction="column" gap="small">
            <Flex justify="between" align="center" wrap gap="small">
              <Box flex="auto">
                <Heading inline={true}>Ticket automation</Heading>
                <Text>Recent OpsLens ticket sync and auto-resolve visibility.</Text>
              </Box>
              <StatusTag variant={ticketStatus.variant}>{ticketStatus.label}</StatusTag>
            </Flex>

            {ticketError ? (
              <Text>Ticket visibility is limited right now: {ticketError}</Text>
            ) : ticketAutomationProvisioned === false ? (
              <Text>OpsLens ticket automation is not provisioned for this portal yet.</Text>
            ) : ticketActivityTotal === 0 ? (
              <Text>No OpsLens tickets have been found for this portal yet.</Text>
            ) : (
              <Flex direction="column" gap="small">
                <AutoGrid columnWidth={170} flexible={true} gap="small">
                  <DetailField
                    label="Tracked tickets"
                    value={String(ticketActivityTotal)}
                  />
                  <DetailField
                    label="Active in preview"
                    value={String(recentActiveTickets)}
                  />
                  <DetailField
                    label="Resolved in preview"
                    value={String(recentResolvedTickets)}
                  />
                  <DetailField
                    label="Latest ticket update"
                    value={formatDate(
                      ticketPreview[0]?.properties?.hs_lastmodifieddate ??
                        ticketPreview[0]?.updatedAt
                    )}
                  />
                  <DetailField
                    label="Pipeline ID"
                    value={ticketPipelineId || "Not returned"}
                  />
                </AutoGrid>

                <Flex direction="column" gap="small">
                  {ticketPreview.map((ticket, idx) => {
                    const properties = ticket?.properties ?? {};

                    return (
                      <Tile compact key={ticket?.id ?? idx}>
                        <Flex direction="column" gap="flush">
                          <Flex justify="between" align="center" wrap gap="small">
                            <Text format={{ fontWeight: "bold" }}>
                              {String(
                                properties?.subject ||
                                  `Ticket ${String(ticket?.id ?? idx + 1)}`
                              )}
                            </Text>
                            <StatusTag
                              variant={getTicketStageVariant(
                                properties?.hs_pipeline_stage
                              )}
                            >
                              {getTicketStageLabel(properties?.hs_pipeline_stage)}
                            </StatusTag>
                          </Flex>
                          <Text>
                            Contact {String(properties?.opslens_ticket_contact_id ?? "-")} •
                            Workflow {String(properties?.opslens_ticket_workflow_id ?? "-")}
                          </Text>
                          <Text>
                            Delivery {String(
                              properties?.opslens_ticket_delivery_status ?? "-"
                            )} • Last alert{" "}
                            {formatDate(properties?.opslens_ticket_last_alert_at)}
                          </Text>
                        </Flex>
                      </Tile>
                    );
                  })}
                </Flex>
              </Flex>
            )}
          </Flex>
        </Tile>

        <Tile compact>
          <Flex direction="column" gap="small">
            <Flex justify="between" align="center" wrap gap="small">
              <Box flex="auto">
                <Heading inline={true}>Webhook activity</Heading>
                <Text>Recent delivery and property-change activity for this portal.</Text>
              </Box>
              <StatusTag variant={webhookStatus.variant}>{webhookStatus.label}</StatusTag>
            </Flex>

            {webhookError ? (
              <Text>Webhook activity is unavailable right now: {webhookError}</Text>
            ) : webhookDbConfigured === false ? (
              <Text>Webhook storage is not configured for this environment.</Text>
            ) : webhookPreview.length === 0 ? (
              <Text>No recent webhook events were found for this portal.</Text>
            ) : (
              <Flex direction="column" gap="small">
                {webhookPreview.map((event, idx) => (
                  <Tile compact key={event?.eventId ?? `${event?.subscriptionType ?? "event"}-${idx}`}>
                    <Flex direction="column" gap="flush">
                      <Text format={{ fontWeight: "bold" }}>
                        {String(event?.subscriptionType ?? "-")}
                      </Text>
                      <Text>
                        Object {String(event?.objectId ?? "-")} •{" "}
                        {String(event?.propertyName ?? "-")}
                      </Text>
                      <Text>
                        Received {formatDate(event?.receivedAtUtc)} • Occurred{" "}
                        {formatDate(event?.occurredAtUtc)}
                      </Text>
                      <Text>
                        Source {String(event?.changeSource ?? "-")} • Value{" "}
                        {String(event?.propertyValue ?? "-")}
                      </Text>
                    </Flex>
                  </Tile>
                ))}
              </Flex>
            )}
          </Flex>
        </Tile>
      </AutoGrid>

      <Accordion title="Advanced context" size="small">
        <Flex direction="column" gap="small">
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
                })}
              />
              <DetailField
                label="Webhook URL"
                value={buildUrl("/api/v1/webhooks/recent", { portalId })}
              />
              <DetailField
                label="Ticket automation route"
                value={ticketAutomationUrl}
              />
              <DetailField
                label="Ticket pipeline"
                value={ticketPipelineId || "Not returned"}
              />
            </AutoGrid>
          </Tile>

          <Tile compact>
            <Flex direction="column" gap="flush">
              <Text format={{ fontWeight: "bold" }}>Recent refresh notes</Text>
              <Text>
                Overview status {overviewError ? `issue: ${overviewError}` : "ok"}
              </Text>
              <Text>
                Ticket automation status {ticketError ? `issue: ${ticketError}` : "ok"}
              </Text>
              <Text>
                Webhook status {webhookError ? `issue: ${webhookError}` : "ok"}
              </Text>
            </Flex>
          </Tile>
        </Flex>
      </Accordion>
    </Flex>
  );
};

export default HomePage;
