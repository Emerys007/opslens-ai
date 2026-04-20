import React, { useEffect, useMemo, useState } from "react";
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
const HUBSPOT_API_BASE_URL = "https://api.hubapi.com";

const TICKET_STAGE_LABELS: Record<string, string> = {
  "1341759033": "New Alert",
  "1341759034": "Investigating",
  "1341759035": "Waiting / Monitoring",
  "1341759036": "Resolved",
  "1341759037": "Closed as Duplicate",
};

const OPSLENS_TICKET_PROPERTIES = [
  "subject",
  "hs_pipeline_stage",
  "hs_lastmodifieddate",
  "opslens_ticket_callback_id",
  "opslens_ticket_workflow_id",
  "opslens_ticket_contact_id",
  "opslens_ticket_severity",
  "opslens_ticket_delivery_status",
  "opslens_ticket_reason",
  "opslens_ticket_first_alert_at",
  "opslens_ticket_last_alert_at",
  "opslens_ticket_repeat_count",
  "opslens_ticket_resolved_at",
  "opslens_ticket_resolution_reason",
];

hubspot.extend(({ context }) => {
  return <NewCard context={context} />;
});

type RecordRiskResponse = {
  status?: string;
  message?: string;
  record?: {
    recordId?: string;
    objectTypeId?: string;
  };
  settings?: {
    portalId?: string;
    slackWebhookUrl?: string;
    alertThreshold?: string;
    criticalWorkflows?: string;
    updatedAtUtc?: string | null;
    storage?: string;
  };
  risk?: {
    level?: string;
    incidentTitle?: string;
    recommendation?: string;
  };
  visibility?: {
    threshold?: string;
    visible?: boolean;
  };
  latestAlert?: {
    id?: string | number;
    receivedAtUtc?: string;
    portalId?: string;
    workflowId?: string;
    callbackId?: string;
    result?: string;
    reason?: string;
    severityOverride?: string | null;
    analystNote?: string;
    objectType?: string;
    objectId?: string;
  };
  debug?: {
    portalId?: string;
    userId?: string;
    userEmail?: string;
    appId?: string;
    dbConfigured?: boolean;
    settingsStorage?: string;
  };
};

type WebhookEvent = {
  receivedAtUtc?: string;
  portalId?: string;
  subscriptionType?: string;
  objectTypeId?: string | null;
  objectId?: string;
  propertyName?: string | null;
  propertyValue?: string | null;
  changeSource?: string | null;
  sourceId?: string | null;
  eventId?: string | null;
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

type TicketSearchResult = {
  id?: string;
  properties?: TicketProperties;
};

type TicketSearchResponse = {
  total?: number;
  results?: TicketSearchResult[];
};

type DetailFieldProps = {
  label: string;
  value: string;
};

type StatusVariant = "danger" | "warning" | "info" | "success" | "default";

const DetailField = ({ label, value }: DetailFieldProps) => {
  return (
    <Box>
      <Text format={{ fontWeight: "bold" }}>{label}</Text>
      <Text>{value}</Text>
    </Box>
  );
};

const getRiskVariant = (level?: string | null): StatusVariant => {
  const text = String(level || "").toLowerCase();

  if (text === "critical") return "danger";
  if (text === "high") return "warning";
  if (text === "medium") return "info";
  if (text === "none") return "success";

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

const NewCard = ({ context }: { context: any }) => {
  const recordId = useMemo(
    () => String(context?.crm?.objectId ?? context?.objectId ?? ""),
    [context]
  );
  const objectTypeId = useMemo(
    () => String(context?.crm?.objectTypeId ?? context?.objectTypeId ?? ""),
    [context]
  );
  const portalId = String(context?.portal?.id ?? "");
  const userId = String(context?.user?.id ?? "");
  const userEmail = String(context?.user?.email ?? "");
  const appId = String(context?.app?.id ?? context?.appId ?? "");

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [recordRisk, setRecordRisk] = useState<RecordRiskResponse | null>(null);
  const [recentWebhookActivity, setRecentWebhookActivity] = useState<WebhookEvent[]>([]);
  const [webhookDbConfigured, setWebhookDbConfigured] = useState<boolean | null>(null);
  const [ticketRecord, setTicketRecord] = useState<TicketSearchResult | null>(null);
  const [ticketError, setTicketError] = useState("");
  const [ticketLoading, setTicketLoading] = useState(false);

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

  const searchTickets = async (filters: Array<Record<string, string>>) => {
    const response = await hubspot.fetch(
      `${HUBSPOT_API_BASE_URL}/crm/v3/objects/tickets/search`,
      {
        method: "POST",
        timeout: 5000,
        body: {
          filterGroups: [
            {
              filters,
            },
          ],
          properties: OPSLENS_TICKET_PROPERTIES,
          sorts: ["-hs_lastmodifieddate"],
          limit: 1,
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Ticket search failed with status ${response.status}`);
    }

    const data = (await response.json()) as TicketSearchResponse;
    const results = Array.isArray(data?.results) ? data.results : [];
    return results[0] ?? null;
  };

  const loadRecordRisk = async () => {
    const response = await hubspot.fetch(
      buildUrl("/api/v1/records/contact-risk", {
        recordId,
        objectTypeId,
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
      throw new Error(`Record risk request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecordRiskResponse;
    if (data?.status === "error") {
      throw new Error(data?.message || "Record risk request failed.");
    }

    setRecordRisk(data);
    return data;
  };

  const loadRecentWebhooks = async () => {
    const response = await hubspot.fetch(
      buildUrl("/api/v1/webhooks/recent", {
        portalId,
        objectId: recordId,
        limit: "5",
      }),
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Webhook history request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecentWebhooksResponse;
    setWebhookDbConfigured(
      typeof data?.dbConfigured === "boolean" ? data.dbConfigured : null
    );
    setRecentWebhookActivity(Array.isArray(data?.events) ? data.events : []);
  };

  const loadTicketRecord = async (workflowId?: string | null) => {
    if (!recordId) {
      setTicketRecord(null);
      setTicketError("");
      return;
    }

    setTicketLoading(true);
    setTicketError("");

    try {
      const baseFilters = [
        {
          propertyName: "opslens_ticket_contact_id",
          operator: "EQ",
          value: String(recordId),
        },
      ];
      const workflowFilters =
        workflowId && String(workflowId).trim()
          ? [
              ...baseFilters,
              {
                propertyName: "opslens_ticket_workflow_id",
                operator: "EQ",
                value: String(workflowId).trim(),
              },
            ]
          : baseFilters;

      let nextTicket = await searchTickets(workflowFilters);

      if (!nextTicket && workflowFilters.length !== baseFilters.length) {
        nextTicket = await searchTickets(baseFilters);
      }

      setTicketRecord(nextTicket);
    } catch (err) {
      console.error("Ticket visibility load failed", err);
      setTicketRecord(null);
      setTicketError(err instanceof Error ? err.message : "Unknown ticket error");
    } finally {
      setTicketLoading(false);
    }
  };

  const refreshAll = async () => {
    if (!recordId) {
      setErrorMessage("No recordId was provided by HubSpot context.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setErrorMessage("");

    try {
      const riskData = await loadRecordRisk();

      await Promise.all([
        loadRecentWebhooks(),
        loadTicketRecord(riskData?.latestAlert?.workflowId),
      ]);
    } catch (err) {
      console.error("New Card refresh failed", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll().catch((err) =>
      console.error("Unexpected New Card load error", err)
    );
  }, [recordId, objectTypeId, portalId, userId, userEmail, appId]);

  const latestAlert = recordRisk?.latestAlert;
  const visibility = recordRisk?.visibility ?? {};
  const settings = recordRisk?.settings ?? {};
  const debug = recordRisk?.debug ?? {};
  const ticketProperties = ticketRecord?.properties ?? {};
  const webhookPreview = recentWebhookActivity.slice(0, 3);
  const cardStatus: { label: string; variant: StatusVariant } = loading
    ? { label: "Refreshing", variant: "info" }
    : errorMessage
      ? { label: "Needs attention", variant: "warning" }
      : { label: "Ready", variant: "success" };
  const ticketStatus: { label: string; variant: StatusVariant } = ticketLoading
    ? { label: "Loading", variant: "info" }
    : ticketError
      ? { label: "Visibility issue", variant: "warning" }
      : ticketRecord
        ? {
            label: getTicketStageLabel(ticketProperties?.hs_pipeline_stage),
            variant: getTicketStageVariant(ticketProperties?.hs_pipeline_stage),
          }
        : { label: "Not found", variant: "default" };
  const autoResolveStatus: { label: string; variant: StatusVariant } =
    ticketProperties?.opslens_ticket_resolved_at
      ? { label: "Resolved", variant: "success" }
      : ticketRecord
        ? { label: "Active", variant: "info" }
        : { label: "Unavailable", variant: "default" };

  return (
    <Flex direction="column" gap="small">
      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Box flex="auto">
              <Heading>OpsLens AI</Heading>
              <Text>
                Compact record view for alert status, ticket automation, and recent activity.
              </Text>
            </Box>
            <Flex align="center" gap="small" wrap>
              <StatusTag variant={cardStatus.variant}>{cardStatus.label}</StatusTag>
              <StatusTag variant={getRiskVariant(recordRisk?.risk?.level)}>
                {String(recordRisk?.risk?.level ?? "unknown").toUpperCase()}
              </StatusTag>
              <Button
                onClick={() => {
                  refreshAll().catch((err) =>
                    console.error("Unexpected New Card refresh error", err)
                  );
                }}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh"}
              </Button>
            </Flex>
          </Flex>

          {errorMessage ? (
            <Text>Error: {errorMessage}</Text>
          ) : (
            <Text>
              Latest event {formatDate(latestAlert?.receivedAtUtc)}. Threshold{" "}
              {String(visibility?.threshold ?? settings?.alertThreshold ?? "-").toUpperCase()}.
            </Text>
          )}
        </Flex>
      </Tile>

      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Heading inline={true}>Latest alert</Heading>
            <StatusTag variant={visibility?.visible ? "success" : "default"}>
              {visibility?.visible ? "Visible at threshold" : "Below threshold"}
            </StatusTag>
          </Flex>

          <AutoGrid columnWidth={190} flexible={true} gap="small">
            <DetailField
              label="Incident title"
              value={String(recordRisk?.risk?.incidentTitle ?? "-")}
            />
            <DetailField
              label="Risk level"
              value={String(recordRisk?.risk?.level ?? "-").toUpperCase()}
            />
            <DetailField
              label="Workflow ID"
              value={String(latestAlert?.workflowId ?? "-")}
            />
            <DetailField
              label="Callback ID"
              value={String(latestAlert?.callbackId ?? "-")}
            />
            <DetailField
              label="Latest event"
              value={formatDate(latestAlert?.receivedAtUtc)}
            />
            <DetailField
              label="Reason"
              value={String(latestAlert?.reason ?? "-")}
            />
            <DetailField
              label="Analyst note"
              value={String(latestAlert?.analystNote ?? "-")}
            />
            <DetailField
              label="Object"
              value={`${String(latestAlert?.objectType ?? "-")} / ${String(
                latestAlert?.objectId ?? "-"
              )}`}
            />
          </AutoGrid>

          <Text>
            Recommendation: {String(recordRisk?.risk?.recommendation ?? "-")}
          </Text>
        </Flex>
      </Tile>

      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Heading inline={true}>Ticket sync</Heading>
            <StatusTag variant={ticketStatus.variant}>{ticketStatus.label}</StatusTag>
          </Flex>

          {ticketError ? (
            <Text>Ticket visibility error: {ticketError}</Text>
          ) : !ticketRecord ? (
            <Text>No OpsLens ticket was found for this contact.</Text>
          ) : (
            <AutoGrid columnWidth={180} flexible={true} gap="small">
              <DetailField label="Ticket ID" value={String(ticketRecord?.id ?? "-")} />
              <DetailField
                label="Ticket stage"
                value={getTicketStageLabel(ticketProperties?.hs_pipeline_stage)}
              />
              <DetailField
                label="Severity"
                value={String(ticketProperties?.opslens_ticket_severity ?? "-")}
              />
              <DetailField
                label="Delivery status"
                value={String(ticketProperties?.opslens_ticket_delivery_status ?? "-")}
              />
              <DetailField
                label="Repeat count"
                value={String(ticketProperties?.opslens_ticket_repeat_count ?? "-")}
              />
              <DetailField
                label="Last alert at"
                value={formatDate(ticketProperties?.opslens_ticket_last_alert_at)}
              />
              <DetailField
                label="Workflow ID"
                value={String(ticketProperties?.opslens_ticket_workflow_id ?? "-")}
              />
              <DetailField
                label="Ticket reason"
                value={String(ticketProperties?.opslens_ticket_reason ?? "-")}
              />
            </AutoGrid>
          )}
        </Flex>
      </Tile>

      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Heading inline={true}>Auto-resolve</Heading>
            <StatusTag variant={autoResolveStatus.variant}>
              {autoResolveStatus.label}
            </StatusTag>
          </Flex>

          {ticketError ? (
            <Text>Auto-resolve details depend on ticket visibility.</Text>
          ) : !ticketRecord ? (
            <Text>Auto-resolve details appear after an OpsLens ticket exists for this contact.</Text>
          ) : ticketProperties?.opslens_ticket_resolved_at ? (
            <AutoGrid columnWidth={180} flexible={true} gap="small">
              <DetailField
                label="Resolved at"
                value={formatDate(ticketProperties?.opslens_ticket_resolved_at)}
              />
              <DetailField
                label="Resolution reason"
                value={String(ticketProperties?.opslens_ticket_resolution_reason ?? "-")}
              />
              <DetailField
                label="First alert at"
                value={formatDate(ticketProperties?.opslens_ticket_first_alert_at)}
              />
              <DetailField
                label="Last updated"
                value={formatDate(ticketProperties?.hs_lastmodifieddate)}
              />
            </AutoGrid>
          ) : (
            <Text>This ticket is active and has not been auto-resolved.</Text>
          )}
        </Flex>
      </Tile>

      <Accordion title="Activity & technical details" size="small">
        <Flex direction="column" gap="small">
          <Tile compact>
            <Flex direction="column" gap="small">
              <Heading inline={true}>Recent webhook activity</Heading>
              {webhookDbConfigured === false ? (
                <Text>Webhook database is not configured.</Text>
              ) : webhookPreview.length === 0 ? (
                <Text>No recent webhook events were found for this record.</Text>
              ) : (
                <AutoGrid columnWidth={220} flexible={true} gap="small">
                  {webhookPreview.map((event, idx) => (
                    <Tile compact key={event?.eventId ?? `${event?.subscriptionType ?? "event"}-${idx}`}>
                      <Flex direction="column" gap="flush">
                        <Text format={{ fontWeight: "bold" }}>
                          {String(event?.subscriptionType ?? "-")}
                        </Text>
                        <Text>Object {String(event?.objectId ?? "-")}</Text>
                        <Text>Received {formatDate(event?.receivedAtUtc)}</Text>
                        <Text>Property {String(event?.propertyName ?? "-")}</Text>
                      </Flex>
                    </Tile>
                  ))}
                </AutoGrid>
              )}
            </Flex>
          </Tile>

          <Tile compact>
            <AutoGrid columnWidth={200} flexible={true} gap="small">
              <DetailField label="Record ID" value={recordId || "unknown"} />
              <DetailField label="Object type ID" value={objectTypeId || "unknown"} />
              <DetailField label="Portal ID" value={portalId || "unknown"} />
              <DetailField label="User ID" value={userId || "unknown"} />
              <DetailField label="User email" value={userEmail || "unknown"} />
              <DetailField label="App ID" value={appId || "unknown"} />
              <DetailField
                label="Database configured"
                value={String(debug?.dbConfigured ?? "-")}
              />
              <DetailField
                label="Ticket stage ID"
                value={String(ticketProperties?.hs_pipeline_stage ?? "-")}
              />
            </AutoGrid>
          </Tile>
        </Flex>
      </Accordion>
    </Flex>
  );
};

export default NewCard;
