import * as React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Divider,
  Flex,
  Form,
  Heading,
  Input,
  Select,
  StatusTag,
  Tag,
  Text,
  TextArea,
  Tile,
  Toggle,
  hubspot,
} from "@hubspot/ui-extensions";

hubspot.extend(({ context }) => <SettingsPage context={context} />);

type PortalSettings = {
  slackWebhookUrl?: string;
  alertThreshold?: string;
  criticalWorkflows?: string;
  slackDeliveryEnabled?: boolean;
  ticketDeliveryEnabled?: boolean;
  updatedAtUtc?: string | null;
  loadedAtUtc?: string | null;
  lastPolledAt?: string | null;
  lastPolledAtUtc?: string | null;
  storage?: string;
};

type SettingsResponse = {
  status?: string;
  message?: string;
  settings?: PortalSettings;
  savedAtUtc?: string;
  dbConfigured?: boolean;
};

type StatusVariant = "success" | "warning" | "danger";

const SETTINGS_API_BASE = "https://api.app-sync.com/api/v1/settings-store";

function buildUrl(baseUrl: string, params: Record<string, string>) {
  const url = new URL(baseUrl);
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

function relativeTime(timestamp?: string | null) {
  if (!timestamp) {
    return "Waiting for the first saved configuration";
  }

  const value = Date.parse(timestamp);
  if (Number.isNaN(value)) {
    return "Recently updated";
  }

  const seconds = Math.max(0, Math.floor((Date.now() - value) / 1000));
  if (seconds < 60) {
    return "Updated just now";
  }

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `Updated ${minutes} min ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `Updated ${hours} hr ago`;
  }

  const days = Math.floor(hours / 24);
  return `Updated ${days} day${days === 1 ? "" : "s"} ago`;
}

function formatTimestamp(timestamp?: string | null) {
  if (!timestamp) {
    return "Not saved yet";
  }

  const value = Date.parse(timestamp);
  if (Number.isNaN(value)) {
    return "Recently updated";
  }

  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function thresholdEmoji(threshold: string) {
  if (threshold === "critical" || threshold === "high") {
    return "🔴";
  }
  if (threshold === "medium") {
    return "🟡";
  }
  return "⚪";
}

function thresholdLabel(threshold: string) {
  if (threshold === "critical") {
    return "Critical alerts only";
  }
  if (threshold === "high") {
    return "High and critical alerts";
  }
  return "Medium, high, and critical alerts";
}

function SectionHeader({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <Flex direction="column" gap="extra-small">
      <Text format={{ fontWeight: "bold" }}>{eyebrow}</Text>
      <Heading>{title}</Heading>
      <Text>{body}</Text>
    </Flex>
  );
}

function StatusMetric({
  label,
  value,
  detail,
  status,
}: {
  label: string;
  value: string;
  detail: string;
  status?: StatusVariant;
}) {
  return (
    <Tile compact>
      <Flex direction="column" gap="small">
        <Flex justify="between" align="center" gap="small" wrap>
          <Text format={{ fontWeight: "bold" }}>{label}</Text>
          {status ? <StatusTag variant={status}>{value}</StatusTag> : null}
        </Flex>
        <Heading>{value}</Heading>
        <Text>{detail}</Text>
      </Flex>
    </Tile>
  );
}

function DeliveryToggle({
  checked,
  label,
  disabled,
  onChange,
}: {
  checked: boolean;
  label: string;
  description: string;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <Flex direction="row" gap="small" align="center">
      <Toggle
        label={label}
        checked={checked}
        readonly={disabled}
        onChange={(value) => onChange(Boolean(value))}
      />
    </Flex>
  );
}

function MonitorItem({
  title,
  severity,
  variant,
}: {
  title: string;
  severity: string;
  variant: "error" | "warning" | "default";
  description: string;
}) {
  return (
    <Flex justify="between" align="center" gap="small" wrap>
      <Text format={{ fontWeight: "bold" }}>{title}</Text>
      <Tag variant={variant}>{severity}</Tag>
    </Flex>
  );
}

function SettingsPage({ context }: { context: any }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasLoadedSettings, setHasLoadedSettings] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");
  const [alertThreshold, setAlertThreshold] = useState("medium");
  const [criticalWorkflows, setCriticalWorkflows] = useState("");
  const [slackDeliveryEnabled, setSlackDeliveryEnabled] = useState(true);
  const [ticketDeliveryEnabled, setTicketDeliveryEnabled] = useState(true);
  const [lastSavedAt, setLastSavedAt] = useState("");
  const [settingsStorage, setSettingsStorage] = useState("");

  const portalId = String(context?.portal?.id ?? "");
  const userId = String(context?.user?.id ?? "unknown");
  const userEmail = String(context?.user?.email ?? "unknown");
  const portalLabel = portalId || "Portal pending";

  const settingsUrl = useMemo(
    () => buildUrl(SETTINGS_API_BASE, { portalId }),
    [portalId]
  );

  const formLocked = loading || saving || !hasLoadedSettings || !portalId;
  const monitoringTimestamp = lastSavedAt || "";
  const statusVariant: StatusVariant = errorMessage ? "warning" : "success";

  useEffect(() => {
    async function loadSettings() {
      setLoading(true);
      setErrorMessage("");
      setSaveMessage("");
      setTestMessage("");

      try {
        const response = await hubspot.fetch(settingsUrl, {
          method: "GET",
          timeout: 15000,
        });
        if (!response.ok) {
          throw new Error(`Backend returned status ${response.status}`);
        }
        const data = (await response.json()) as SettingsResponse;
        if (data?.status === "error") {
          throw new Error(data.message || "Settings could not be loaded.");
        }

        const settings = data?.settings ?? {};
        setSlackWebhookUrl(String(settings.slackWebhookUrl ?? ""));
        setAlertThreshold(String(settings.alertThreshold ?? "medium"));
        setCriticalWorkflows(String(settings.criticalWorkflows ?? ""));
        setSlackDeliveryEnabled(settings.slackDeliveryEnabled !== false);
        setTicketDeliveryEnabled(settings.ticketDeliveryEnabled !== false);
        setLastSavedAt(
          String(
            settings.lastPolledAtUtc ??
              settings.lastPolledAt ??
              settings.updatedAtUtc ??
              data?.savedAtUtc ??
              settings.loadedAtUtc ??
              ""
          )
        );
        setSettingsStorage(String(settings.storage ?? ""));
        setHasLoadedSettings(true);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setErrorMessage(message);
        setHasLoadedSettings(false);
      } finally {
        setLoading(false);
      }
    }

    loadSettings();
  }, [settingsUrl]);

  async function saveSettings() {
    setSaving(true);
    setSaveMessage("");
    setErrorMessage("");
    setTestMessage("");

    try {
      const payload = {
        slackWebhookUrl,
        alertThreshold,
        criticalWorkflows,
        slackDeliveryEnabled,
        ticketDeliveryEnabled,
      };
      const response = await hubspot.fetch(settingsUrl, {
        method: "POST",
        body: payload,
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }
      const data = (await response.json()) as SettingsResponse;
      if (data?.status === "error") {
        throw new Error(data.message || "Settings could not be saved.");
      }

      const settings = data?.settings ?? {};
      setSlackWebhookUrl(String(settings.slackWebhookUrl ?? slackWebhookUrl));
      setAlertThreshold(String(settings.alertThreshold ?? alertThreshold));
      setCriticalWorkflows(
        String(settings.criticalWorkflows ?? criticalWorkflows)
      );
      setSlackDeliveryEnabled(
        settings.slackDeliveryEnabled ?? slackDeliveryEnabled
      );
      setTicketDeliveryEnabled(
        settings.ticketDeliveryEnabled ?? ticketDeliveryEnabled
      );
      setLastSavedAt(
        String(
          settings.updatedAtUtc ??
            data?.savedAtUtc ??
            settings.loadedAtUtc ??
            new Date().toISOString()
        )
      );
      setSettingsStorage(String(settings.storage ?? settingsStorage));
      setSaveMessage(
        "Settings saved. OpsLens will apply them on the next polling cycle."
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message);
    } finally {
      setSaving(false);
    }
  }

  function handleTestAlert() {
    setSaveMessage("");

    if (!slackWebhookUrl.trim()) {
      setTestMessage("Add a Slack webhook URL before sending a test alert.");
      return;
    }

    setTestMessage(
      "Test delivery is not connected from this iframe yet. Save this webhook and OpsLens will post the next matching alert automatically."
    );
  }

  return (
    <Flex direction="column" gap="medium">
      <Tile>
        <Flex direction="column" gap="medium">
          <Flex justify="between" align="center" gap="small" wrap>
            <Box flex={1}>
              <SectionHeader
                eyebrow="System status"
                title="OpsLens is monitoring this HubSpot portal"
                body="Portal settings are loaded through the connected-app session, so the page reflects the configuration OpsLens will use for this account."
              />
            </Box>
            <StatusTag variant="success">Monitoring active</StatusTag>
          </Flex>
        </Flex>
      </Tile>

      <Flex direction="row" gap="small">
        <Box flex={1}>
          <StatusMetric
            label="Monitoring"
            value="Active"
            detail={relativeTime(monitoringTimestamp)}
            status={statusVariant}
          />
        </Box>
        <Box flex={1}>
          <StatusMetric
            label="Last settings sync"
            value={formatTimestamp(monitoringTimestamp)}
            detail="Settings synced from OpsLens backend"
          />
        </Box>
        <Box flex={1}>
          <StatusMetric
            label="Portal"
            value={portalLabel}
            detail="Connected via OAuth"
          />
        </Box>
      </Flex>

      <Form onSubmit={saveSettings}>
        <Flex direction="column" gap="medium">
          <Flex direction="row" gap="small" align="start">
            <Box flex={1}>
              <Tile>
                <Flex direction="column" gap="medium">
                  <SectionHeader
                    eyebrow="Alert routing"
                    title="Send the right alerts to the right place"
                    body="Choose where OpsLens should deliver workflow risk signals and how sensitive Slack should be for this portal."
                  />

                  <Input
                    label="Slack webhook URL"
                    name="slackWebhookUrl"
                    value={slackWebhookUrl}
                    type="text"
                    onChange={(value) =>
                      setSlackWebhookUrl(String(value ?? ""))
                    }
                    readOnly={formLocked}
                    description="OpsLens posts Slack alerts to this incoming webhook when a monitored change meets the selected threshold."
                  />

                  <Select
                    label="Slack alert threshold"
                    name="alertThreshold"
                    value={alertThreshold}
                    onChange={(value) =>
                      setAlertThreshold(String(value ?? "medium"))
                    }
                    readOnly={formLocked}
                    description="Use a higher threshold for quiet client channels, or medium when consultants want earlier warning on schema edits."
                    options={[
                      { label: "Critical only", value: "critical" },
                      { label: "High and critical", value: "high" },
                      { label: "Medium, high, and critical", value: "medium" },
                    ]}
                  />

                  <TextArea
                    label="Critical workflows"
                    name="criticalWorkflows"
                    value={criticalWorkflows}
                    onChange={(value) =>
                      setCriticalWorkflows(String(value ?? ""))
                    }
                    readOnly={formLocked}
                    rows={3}
                    description="Add one workflow identifier per line so OpsLens can escalate changes that touch revenue-critical automation."
                  />

                  <Flex direction="row" gap="medium">
                    <Box flex={1}>
                      <DeliveryToggle
                        label="Send Slack alerts"
                        checked={slackDeliveryEnabled}
                        disabled={formLocked}
                        onChange={setSlackDeliveryEnabled}
                        description="Slack delivery is best for fast triage by the consultant or operations team watching the portal."
                      />
                    </Box>
                    <Box flex={1}>
                      <DeliveryToggle
                        label="Create HubSpot tickets"
                        checked={ticketDeliveryEnabled}
                        disabled={formLocked}
                        onChange={setTicketDeliveryEnabled}
                        description="Ticket delivery keeps a durable HubSpot record for issues that need owner assignment and follow-up."
                      />
                    </Box>
                  </Flex>

                  <Flex direction="row" justify="end" gap="small">
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={formLocked}
                      onClick={handleTestAlert}
                    >
                      Test alert
                    </Button>
                    <Button
                      type="submit"
                      variant="primary"
                      disabled={formLocked}
                    >
                      {saving ? "Saving…" : "Save settings"}
                    </Button>
                  </Flex>

                  {saveMessage ? (
                    <Flex align="center" gap="small" wrap>
                      <StatusTag variant="success">Saved</StatusTag>
                      <Text>{saveMessage}</Text>
                    </Flex>
                  ) : null}
                  {testMessage ? (
                    <Flex align="center" gap="small" wrap>
                      <StatusTag variant="warning">Test unavailable</StatusTag>
                      <Text>{testMessage}</Text>
                    </Flex>
                  ) : null}
                  {errorMessage ? (
                    <Flex align="center" gap="small" wrap>
                      <StatusTag variant="danger">Error</StatusTag>
                      <Text>{errorMessage}</Text>
                    </Flex>
                  ) : null}
                  {!portalId ? (
                    <StatusTag variant="warning">
                      Portal context is still loading from HubSpot.
                    </StatusTag>
                  ) : null}
                </Flex>
              </Tile>
            </Box>

            <Box flex={1}>
              <Flex direction="column" gap="small">
                <Tile>
                  <Flex direction="column" gap="medium">
                    <Text format={{ fontWeight: "bold" }}>
                      Slack preview — {thresholdLabel(alertThreshold)}
                    </Text>
                    <Divider />
                    <Box>
                      <Flex direction="column" gap="small">
                        <Flex align="center" gap="small" wrap>
                          <Text>{thresholdEmoji(alertThreshold)}</Text>
                          <Text format={{ fontWeight: "bold" }}>
                            Property 'Lead Source' archived — 1 workflow(s)
                            affected
                          </Text>
                        </Flex>
                        <Text>
                          Lead Source was archived in HubSpot, but the Lead
                          Nurture workflow still references it in enrollment
                          criteria. New contacts may skip the intended route
                          until the property is restored or the workflow
                          reference is replaced.
                        </Text>
                        <Flex direction="column" gap="small">
                          <Text format={{ fontWeight: "bold" }}>
                            Recommended action
                          </Text>
                          <Text>
                            Open the workflow, replace the archived property
                            reference, then rerun enrollment tests for recent
                            leads.
                          </Text>
                        </Flex>
                        <Divider />
                        <Text>
                          OpsLens • Portal {portalLabel} • Detected just now
                        </Text>
                      </Flex>
                    </Box>
                  </Flex>
                </Tile>

                <Tile>
                  <Flex direction="column" gap="medium">
                    <Text format={{ fontWeight: "bold" }}>
                      Monitoring coverage
                    </Text>
                    <Divider />
                    <Flex direction="column" gap="extra-small">
                      <MonitorItem
                        title="Archived properties"
                        severity="High"
                        variant="error"
                        description="A property archive can break workflow filters, branches, and personalization that still depend on the field."
                      />
                      <MonitorItem
                        title="Deleted properties"
                        severity="High"
                        variant="error"
                        description="Deleted fields remove the source data workflows expect, so OpsLens treats affected automation as urgent."
                      />
                      <MonitorItem
                        title="Renamed properties"
                        severity="Low"
                        variant="default"
                        description="Label changes usually preserve API names, but OpsLens still flags them so consultants can prevent confusion."
                      />
                      <MonitorItem
                        title="Property type changes"
                        severity="Medium"
                        variant="warning"
                        description="Changing field type can alter workflow comparisons, list membership, and downstream reporting logic."
                      />
                      <MonitorItem
                        title="Disabled workflows"
                        severity="High"
                        variant="error"
                        description="A disabled workflow can stop lead routing, lifecycle updates, or customer notifications without a visible failure."
                      />
                      <MonitorItem
                        title="Edited workflows"
                        severity="Medium"
                        variant="warning"
                        description="Workflow edits can change enrollment, branching, and actions, so OpsLens highlights them for review."
                      />
                    </Flex>
                  </Flex>
                </Tile>
              </Flex>
            </Box>
          </Flex>
        </Flex>
      </Form>
    </Flex>
  );
}

export default SettingsPage;
