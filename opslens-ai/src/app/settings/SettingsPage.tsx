import React, { useEffect, useMemo, useState } from "react";
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
  const [saving, setSaving] = useState(false);
  const [hasLoadedSettings, setHasLoadedSettings] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");
  const [alertThreshold, setAlertThreshold] = useState("high");
  const [criticalWorkflows, setCriticalWorkflows] = useState("");

  const portalId = String(context?.portal?.id ?? "unknown");
  const userId = String(context?.user?.id ?? "unknown");
  const userEmail = String(context?.user?.email ?? "unknown");

  const settingsUrl = useMemo(() => {
    return `${BACKEND_BASE_URL}/api/v1/settings-store`;
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    setErrorMessage("");
    setSaveMessage("");

    try {
      const response = await hubspot.fetch(settingsUrl, {
        method: "GET",
        timeout: 8000,
      });

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      const settings = data?.settings ?? {};

      const nextSlackWebhookUrl = String(settings?.slackWebhookUrl ?? "");
      const nextAlertThreshold = String(settings?.alertThreshold ?? "high");
      const nextCriticalWorkflows = String(settings?.criticalWorkflows ?? "");

      setSlackWebhookUrl(nextSlackWebhookUrl);
      setAlertThreshold(nextAlertThreshold);
      setCriticalWorkflows(nextCriticalWorkflows);
      setHasLoadedSettings(true);

      const lastSavedAt =
        data?.savedAtUtc ??
        settings?.updatedAtUtc ??
        settings?.loadedAtUtc ??
        "";

      const hasLoadedValues =
        nextSlackWebhookUrl.trim() !== "" ||
        nextCriticalWorkflows.trim() !== "" ||
        nextAlertThreshold.trim() !== "";

      if (lastSavedAt) {
        setSaveMessage(`Last saved at ${lastSavedAt}`);
      } else if (hasLoadedValues) {
        setSaveMessage("Settings loaded from hosted backend.");
      } else {
        setSaveMessage("");
      }
    } catch (err) {
      console.error("Failed to load settings", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setErrorMessage("");
    setSaveMessage("");

    try {
      const response = await hubspot.fetch(settingsUrl, {
        method: "POST",
        timeout: 8000,
        body: {
          slackWebhookUrl,
          alertThreshold,
          criticalWorkflows,
        },
      });

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      const savedAt =
        data?.savedAtUtc ??
        data?.settings?.updatedAtUtc ??
        data?.settings?.loadedAtUtc ??
        "";

      setSaveMessage(savedAt ? `Saved at ${savedAt}` : "Settings saved.");
    } catch (err) {
      console.error("Failed to save settings", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    loadSettings().catch((err) =>
      console.error("Unexpected settings load error", err)
    );
  }, [settingsUrl]);

  const formLocked = loading || saving || !hasLoadedSettings;

  return (
    <Flex direction="column" gap="medium">
      <EmptyState title="OpsLens AI settings" layout="vertical">
        <Text>
          This page now loads and saves portal-level OpsLens settings through
          the hosted Python backend.
        </Text>
      </EmptyState>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Backend status</Text>
        <Text>{loading ? "Loading settings..." : saving ? "Saving..." : "Ready"}</Text>
        <Text>
          {errorMessage
            ? `Error: ${errorMessage}`
            : "No settings fetch error detected."}
        </Text>
        {!hasLoadedSettings ? (
          <Text>Settings must load successfully before you can edit or save them.</Text>
        ) : null}
        <Text>{saveMessage ? saveMessage : "No settings save event yet."}</Text>
        {errorMessage ? (
          <Button
            onClick={() => {
              loadSettings().catch((err) =>
                console.error("Unexpected settings retry error", err)
              );
            }}
            disabled={loading || saving}
          >
            Retry loading settings
          </Button>
        ) : null}
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
            onChange={(value) => setSlackWebhookUrl(String(value))}
            placeholder="https://hooks.slack.com/services/..."
            readOnly={formLocked}
          />

          <Select
            label="Alert threshold"
            name="alertThreshold"
            value={alertThreshold}
            onChange={(value) => setAlertThreshold(String(value))}
            readOnly={formLocked}
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
            onChange={(value) => setCriticalWorkflows(String(value))}
            placeholder={"Quote Sync\nOwner Routing\nImport Cleanup"}
            description="One workflow name per line."
            readOnly={formLocked}
          />

          <Button type="submit" disabled={formLocked}>
            {saving ? "Saving..." : "Save settings"}
          </Button>
        </Flex>
      </Form>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Debug context</Text>
        <Text>Portal ID: {portalId}</Text>
        <Text>User ID: {userId}</Text>
        <Text>User Email: {userEmail}</Text>
        <Text>Settings URL: {settingsUrl}</Text>
      </Box>
    </Flex>
  );
};

export default SettingsPage;
