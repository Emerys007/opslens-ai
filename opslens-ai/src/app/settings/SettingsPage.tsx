import React, { useEffect, useMemo, useState } from "react";
import {
  Accordion,
  AutoGrid,
  Box,
  Button,
  Flex,
  Form,
  Heading,
  Input,
  Select,
  StatusTag,
  Text,
  TextArea,
  Tile,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

hubspot.extend(({ context }) => {
  return <SettingsPage context={context} />;
});

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

type StatusVariant = "danger" | "warning" | "info" | "success" | "default";

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
  const settingsStatus: { label: string; variant: StatusVariant } = loading
    ? { label: "Loading settings", variant: "info" }
    : saving
      ? { label: "Saving changes", variant: "warning" }
      : errorMessage
        ? { label: "Needs attention", variant: "warning" }
        : !hasLoadedSettings
          ? { label: "Protected", variant: "default" }
          : { label: "Ready", variant: "success" };
  const statusMessage = errorMessage
    ? `Error: ${errorMessage}`
    : !hasLoadedSettings
      ? "Settings stay locked until the current portal configuration loads successfully."
      : saveMessage || "Portal settings are ready to edit.";

  return (
    <Flex direction="column" gap="small">
      <Tile compact>
        <Flex direction="column" gap="small">
          <Flex justify="between" align="center" wrap gap="small">
            <Box flex="auto">
              <Heading>OpsLens settings</Heading>
              <Text>
                Compact portal controls for alert routing and workflow monitoring.
              </Text>
            </Box>
            <StatusTag variant={settingsStatus.variant}>
              {settingsStatus.label}
            </StatusTag>
          </Flex>
          <Text>{statusMessage}</Text>
        </Flex>
      </Tile>

      <Form
        preventDefault={true}
        onSubmit={() => {
          saveSettings().catch((err) =>
            console.error("Unexpected settings save error", err)
          );
        }}
      >
        <Flex direction="column" gap="small">
          <AutoGrid columnWidth={280} flexible={true} gap="small">
            <Tile compact>
              <Flex direction="column" gap="small">
                <Heading inline={true}>Alert routing</Heading>
                <Text>
                  Manage where OpsLens alert activity is sent and when it becomes visible.
                </Text>
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
              </Flex>
            </Tile>

            <Tile compact>
              <Flex direction="column" gap="small">
                <Heading inline={true}>Workflow monitoring</Heading>
                <Text>
                  Keep the workflow list tight so operators can focus on the highest-value flows.
                </Text>
                <TextArea
                  label="Critical workflows"
                  name="criticalWorkflows"
                  value={criticalWorkflows}
                  onChange={(value) => setCriticalWorkflows(String(value))}
                  placeholder={"Quote Sync\nOwner Routing\nImport Cleanup"}
                  description="One workflow name per line."
                  readOnly={formLocked}
                  rows={7}
                />
              </Flex>
            </Tile>
          </AutoGrid>

          <Tile compact>
            <Flex justify="between" align="center" wrap gap="small">
              <Box flex="auto">
                <Text format={{ fontWeight: "bold" }}>Save state</Text>
                <Text>
                  {!hasLoadedSettings
                    ? "Settings must load successfully before you can edit or save them."
                    : saveMessage || "Changes save to the hosted portal settings store."}
                </Text>
                {errorMessage ? <Text>Error: {errorMessage}</Text> : null}
              </Box>
              <Flex align="center" gap="small" wrap>
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
                <Button type="submit" disabled={formLocked}>
                  {saving ? "Saving..." : "Save settings"}
                </Button>
              </Flex>
            </Flex>
          </Tile>
        </Flex>
      </Form>

      <Accordion title="Technical details" size="small">
        <Tile compact>
          <AutoGrid columnWidth={220} flexible={true} gap="small">
            <DetailField label="Portal ID" value={portalId} />
            <DetailField label="User ID" value={userId} />
            <DetailField label="User email" value={userEmail} />
            <DetailField label="Settings URL" value={settingsUrl} />
          </AutoGrid>
        </Tile>
      </Accordion>
    </Flex>
  );
};

export default SettingsPage;
