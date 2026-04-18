
import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  Divider,
  EmptyState,
  Flex,
  Form,
  Input,
  Select,
  Text,
  TextArea,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

hubspot.extend(({ context }) => {
  return <SettingsPage context={context} />;
});

const SettingsPage = ({ context }) => {
  const [loading, setLoading] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");
  const [alertThreshold, setAlertThreshold] = useState("high");
  const [criticalWorkflows, setCriticalWorkflows] = useState("");

  const loadSettings = async () => {
    setLoading(true);
    setErrorMessage("");
    setSaveMessage("");

    try {
      const response = await hubspot.fetch(
  `${BACKEND_BASE_URL}/api/v1/settings-store`,
  {
    method: "GET",
    timeout: 3000,
  }
);

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      setSlackWebhookUrl(data?.settings?.slackWebhookUrl ?? "");
      setAlertThreshold(data?.settings?.alertThreshold ?? "high");
      setCriticalWorkflows(data?.settings?.criticalWorkflows ?? "");
    } catch (err) {
      console.error("Failed to load settings", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setErrorMessage("");
    setSaveMessage("");

    try {
      const response = await hubspot.fetch(
  `${BACKEND_BASE_URL}/api/v1/settings-store`,
  {
    method: "POST",
    timeout: 3000,
    body: {
      slackWebhookUrl,
      alertThreshold,
      criticalWorkflows,
    },
  }
);

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      setSaveMessage(`Saved at ${data.savedAtUtc}`);
    } catch (err) {
      console.error("Failed to save settings", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    }
  };

  useEffect(() => {
    loadSettings().catch((err) =>
      console.error("Unexpected settings load error", err)
    );
  }, []);

  return (
    <Flex direction="column" gap="medium">
      <EmptyState title="OpsLens AI settings" layout="vertical">
        <Text>
          This page now loads and saves portal-level OpsLens settings through the local Python backend.
        </Text>
      </EmptyState>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Backend status</Text>
        <Text>{loading ? "Loading settings..." : "Ready"}</Text>
        <Text>{errorMessage ? `Error: ${errorMessage}` : "No settings fetch error detected."}</Text>
        <Text>{saveMessage ? saveMessage : "No settings save event yet."}</Text>
      </Box>

      <Divider />

      <Form
        preventDefault={true}
        onSubmit={() => {
          saveSettings().catch((err) =>
            console.error("Unexpected settings save error", err)
          );
        }}
      >
        <Flex direction="column" gap="medium">
          <Input
            label="Slack webhook URL"
            name="slackWebhookUrl"
            value={slackWebhookUrl}
            onChange={(value) => setSlackWebhookUrl(value)}
            placeholder="https://hooks.slack.com/services/..."
          />

          <Select
            label="Alert threshold"
            name="alertThreshold"
            value={alertThreshold}
            onChange={(value) => setAlertThreshold(String(value))}
            options={[
              { label: "Critical", value: "critical" },
              { label: "High", value: "high" },
              { label: "Medium", value: "medium" },
            ]}
          />

          <TextArea
            label="Critical workflows"
            name="criticalWorkflows"
            value={criticalWorkflows}
            onChange={(value) => setCriticalWorkflows(value)}
            placeholder={"Quote Sync\nOwner Routing\nImport Cleanup"}
            description="One workflow name per line."
          />

          <Button type="submit">Save settings</Button>
        </Flex>
      </Form>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Debug context</Text>
        <Text>Portal ID: {String(context?.portal?.id ?? "unknown")}</Text>
        <Text>User ID: {String(context?.user?.id ?? "unknown")}</Text>
      </Box>
    </Flex>
  );
};

