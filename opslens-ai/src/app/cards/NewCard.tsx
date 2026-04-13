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
  alertThreshold?: string;
  visibleAtThreshold?: boolean;
  risk?: {
    level?: string;
    incidentTitle?: string;
    affectedWorkflows?: number;
    recommendation?: string;
  };
  latestSavedAlert?: {
    receivedAtUtc?: string;
    workflowId?: string;
    callbackId?: string;
    result?: string;
    reason?: string;
    analystNote?: string;
    objectType?: string;
    objectId?: string;
    severity?: string;
    deliveryStatus?: string;
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

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [recordRisk, setRecordRisk] = useState<RecordRiskResponse | null>(null);
  const [recentWebhookActivity, setRecentWebhookActivity] = useState<WebhookEvent[]>([]);

  const formatDate = (value?: string | null) => {
    if (!value) return "-";
    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  };

  const loadRecordRisk = async () => {
    const response = await hubspot.fetch(
      `${BACKEND_BASE_URL}/api/v1/records/contact-risk?recordId=${encodeURIComponent(recordId)}&objectTypeId=${encodeURIComponent(objectTypeId)}`,
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Record risk request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecordRiskResponse;
    setRecordRisk(data);
  };

  const loadRecentWebhooks = async () => {
    const response = await hubspot.fetch(
      `${BACKEND_BASE_URL}/api/v1/webhooks/recent?objectId=${encodeURIComponent(recordId)}&limit=5`,
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Webhook history request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecentWebhooksResponse;
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
  }, [recordId, objectTypeId]);

  const latestSavedAlert = recordRisk?.latestSavedAlert;

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
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Latest saved alert</Text>
        <Text>Alert threshold: {String(recordRisk?.alertThreshold ?? "-")}</Text>
        <Text>Risk level: {String(recordRisk?.risk?.level ?? "-").toUpperCase()}</Text>
        <Text>Visible at threshold: {String(recordRisk?.visibleAtThreshold ?? "-")}</Text>
        <Text>Latest event at: {formatDate(latestSavedAlert?.receivedAtUtc)}</Text>
        <Text>Workflow ID: {String(latestSavedAlert?.workflowId ?? "-")}</Text>
        <Text>Callback ID: {String(latestSavedAlert?.callbackId ?? "-")}</Text>
        <Text>Result: {String(latestSavedAlert?.result ?? "-")}</Text>
        <Text>Reason: {String(latestSavedAlert?.reason ?? "-")}</Text>
        <Text>Analyst note: {String(latestSavedAlert?.analystNote ?? "-")}</Text>
        <Text>
          Object: {String(latestSavedAlert?.objectType ?? "-")} / {String(latestSavedAlert?.objectId ?? "-")}
        </Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Recent webhook activity for this record</Text>
        {recentWebhookActivity.length === 0 ? (
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
        <Text>Portal ID: {String(context?.portal?.id ?? "unknown")}</Text>
        <Text>User ID: {String(context?.user?.id ?? "unknown")}</Text>
        <Text>User Email: {String(context?.user?.email ?? "unknown")}</Text>
      </Box>
    </Flex>
  );
};

export default NewCard;
