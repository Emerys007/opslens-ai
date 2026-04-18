import React, { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Divider,
  Flex,
  Text,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

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

  const refreshAll = async () => {
    if (!recordId) {
      setErrorMessage("No recordId was provided by HubSpot context.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setErrorMessage("");

    try {
      await Promise.all([loadRecordRisk(), loadRecentWebhooks()]);
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

  return (
    <Flex direction="column" gap="medium">
      <Box>
        <Text format={{ fontWeight: "bold" }}>OpsLens AI</Text>
        <Text>
          This record card now reads the latest saved alert and the most recent webhook history for this record.
        </Text>
      </Box>

      <Button
        onClick={() => {
          refreshAll().catch((err) =>
            console.error("Unexpected New Card refresh error", err)
          );
        }}
      >
        Refresh record risk
      </Button>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Card status</Text>
        <Text>{loading ? "Loading..." : "Ready"}</Text>
        <Text>{errorMessage ? `Error: ${errorMessage}` : "No card fetch error detected."}</Text>
        <Text>Database configured: {String(debug?.dbConfigured ?? "-")}</Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Latest saved alert</Text>
        <Text>Alert threshold: {String(visibility?.threshold ?? settings?.alertThreshold ?? "-")}</Text>
        <Text>Risk level: {String(recordRisk?.risk?.level ?? "-").toUpperCase()}</Text>
        <Text>Incident title: {String(recordRisk?.risk?.incidentTitle ?? "-")}</Text>
        <Text>Visible at threshold: {String(visibility?.visible ?? "-")}</Text>
        <Text>Latest event at: {formatDate(latestAlert?.receivedAtUtc)}</Text>
        <Text>Workflow ID: {String(latestAlert?.workflowId ?? "-")}</Text>
        <Text>Callback ID: {String(latestAlert?.callbackId ?? "-")}</Text>
        <Text>Result: {String(latestAlert?.result ?? "-")}</Text>
        <Text>Reason: {String(latestAlert?.reason ?? "-")}</Text>
        <Text>Analyst note: {String(latestAlert?.analystNote ?? "-")}</Text>
        <Text>Recommendation: {String(recordRisk?.risk?.recommendation ?? "-")}</Text>
        <Text>
          Object: {String(latestAlert?.objectType ?? "-")} / {String(latestAlert?.objectId ?? "-")}
        </Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Recent webhook activity for this record</Text>
        {webhookDbConfigured === false ? (
          <Text>Webhook database is not configured.</Text>
        ) : recentWebhookActivity.length === 0 ? (
          <Text>No recent webhook events found for this record.</Text>
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
        <Text>Record ID: {recordId || "unknown"}</Text>
        <Text>Object type ID: {objectTypeId || "unknown"}</Text>
        <Text>Portal ID: {portalId || "unknown"}</Text>
        <Text>User ID: {userId || "unknown"}</Text>
        <Text>User Email: {userEmail || "unknown"}</Text>
        <Text>App ID: {appId || "unknown"}</Text>
      </Box>
    </Flex>
  );
};

export default NewCard;
