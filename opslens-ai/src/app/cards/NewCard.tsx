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
      <Text>Alert threshold: {String(payload?.appliedSettings?.alertThreshold ?? "-").toUpperCase()}</Text>
      <Text>Risk level: {String(payload?.risk?.level ?? "-").toUpperCase()}</Text>
      <Text>Visible at threshold: {String(payload?.risk?.visibleAtCurrentThreshold ?? false)}</Text>
      <Text>Active incident: {String(payload?.risk?.incidentTitle ?? "-")}</Text>
      <Text>Affected workflows: {String(payload?.risk?.affectedWorkflows ?? "-")}</Text>
      <Text>Recommendation: {String(payload?.risk?.recommendation ?? "-")}</Text>

      <Button onClick={() => loadRisk()}>
        Refresh record risk
      </Button>
    </Flex>
  );
};
