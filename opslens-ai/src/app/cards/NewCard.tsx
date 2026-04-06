import React, { useEffect, useState } from "react";
import { Button, Divider, Flex, Text, hubspot } from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

type CardPayload = {
  status?: string;
  settings?: {
    alertThreshold?: string;
    criticalWorkflows?: string;
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
  } | null;
};

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

hubspot.extend(({ context }) => <NewCard context={context} />);

const NewCard = ({ context }: { context: any }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState<CardPayload | null>(null);

  const recordId = String(context?.crm?.objectId ?? "");
  const objectTypeId = String(context?.crm?.objectTypeId ?? "0-1");

  const loadRisk = async () => {
    if (!recordId) {
      setError("Record ID is missing from HubSpot context.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await hubspot.fetch(
        `${BACKEND_BASE_URL}/api/v1/records/contact-risk?recordId=${encodeURIComponent(recordId)}&objectTypeId=${encodeURIComponent(objectTypeId)}`
      );

      if (!response.ok) {
        throw new Error(`Record risk request failed with status ${response.status}`);
      }

      const json: CardPayload = await response.json();
      setPayload(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRisk();
  }, [recordId, objectTypeId]);

  const latest = payload?.latestAlert;

  return (
    <Flex direction="column">
      <Text>OpsLens AI</Text>
      <Text>This record card now reads the latest saved alert for this contact from Postgres.</Text>

      <Button onClick={loadRisk}>Refresh record risk</Button>

      <Divider />

      {loading ? (
        <Text>Loading...</Text>
      ) : error ? (
        <Text>Error: {error}</Text>
      ) : latest ? (
        <>
          <Text>Alert threshold: {safeText(payload?.visibility?.threshold).toUpperCase()}</Text>
          <Text>Risk level: {safeText(payload?.risk?.level).toUpperCase()}</Text>
          <Text>Visible at threshold: {String(Boolean(payload?.visibility?.visible))}</Text>
          <Text>Latest event at: {formatDateTime(latest.receivedAtUtc)}</Text>
          <Text>Workflow ID: {safeText(latest.workflowId)}</Text>
          <Text>Callback ID: {safeText(latest.callbackId)}</Text>
          <Text>Result: {safeText(latest.result)}</Text>
          <Text>Reason: {safeText(latest.reason, "No rejection reason")}</Text>
          <Text>Analyst note: {safeText(latest.analystNote, "No analyst note")}</Text>
          <Text>Object: {safeText(latest.objectType)} / {safeText(latest.objectId)}</Text>
        </>
      ) : (
        <>
          <Text>Alert threshold: {safeText(payload?.visibility?.threshold).toUpperCase()}</Text>
          <Text>Risk level: {safeText(payload?.risk?.level).toUpperCase()}</Text>
          <Text>{safeText(payload?.risk?.incidentTitle, "No saved alert")}</Text>
          <Text>{safeText(payload?.risk?.recommendation, "Run the workflow and refresh this card.")}</Text>
        </>
      )}
    </Flex>
  );
};

export default NewCard;
