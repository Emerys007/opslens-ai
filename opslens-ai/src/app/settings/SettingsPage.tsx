import * as React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Accordion,
  Box,
  Button,
  Divider,
  Flex,
  Form,
  Heading,
  Input,
  Select,
  StatusTag,
  Text,
  Tile,
  Toggle,
  hubspot,
} from "@hubspot/ui-extensions";

hubspot.extend(({ context }) => <SettingsPage context={context} />);

type PortalSettings = {
  slackWebhookUrl?: string;
  alertThreshold?: string;
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
const DASHBOARD_API_BASE = "https://api.app-sync.com/api/v1/dashboard";
const DEFAULT_SEVERITY_VALUE = "__default__";

type MonitoringCategory = {
  name: string;
  defaultSeverity: string;
  enabled: boolean;
  severityOverride?: string | null;
};

type MonitoringCoverageResponse = {
  status?: string;
  portalId?: string;
  coverage?: Record<string, { enabled?: boolean; severityOverride?: string | null }>;
  categories?: MonitoringCategory[];
};

type ExclusionType = "workflow" | "property";

type MonitoringExclusion = {
  id: number;
  portalId?: string;
  type: ExclusionType;
  exclusionId: string;
  objectTypeId?: string | null;
  reason?: string | null;
  createdAtUtc?: string | null;
  createdByUserId?: string | null;
};

const CATEGORY_LABELS: Record<string, string> = {
  property_archived: "Archived properties",
  property_deleted: "Deleted properties",
  property_renamed: "Renamed properties",
  property_type_changed: "Property type changes",
  workflow_disabled: "Disabled workflows",
  workflow_edited: "Edited workflows",
};

const OBJECT_TYPE_OPTIONS = [
  { label: "Contact", value: "0-1" },
  { label: "Company", value: "0-2" },
  { label: "Deal", value: "0-3" },
  { label: "Ticket", value: "0-5" },
];

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

function severityLabel(value?: string | null) {
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) {
    return "";
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function categoryLabel(name: string) {
  return CATEGORY_LABELS[name] || name;
}

function objectTypeLabel(objectTypeId?: string | null) {
  const match = OBJECT_TYPE_OPTIONS.find((option) => option.value === objectTypeId);
  return match?.label ?? String(objectTypeId || "Unknown object");
}

function normalizeCategories(categories?: MonitoringCategory[]) {
  return (Array.isArray(categories) ? categories : []).map((category) => ({
    name: String(category.name ?? ""),
    defaultSeverity: String(category.defaultSeverity ?? "medium").toLowerCase(),
    enabled: category.enabled !== false,
    severityOverride: category.severityOverride
      ? String(category.severityOverride).toLowerCase()
      : null,
  })).filter((category) => category.name);
}

function coverageFingerprint(categories: MonitoringCategory[]) {
  const payload = categories
    .map((category) => ({
      name: category.name,
      enabled: category.enabled !== false,
      severityOverride: category.severityOverride || null,
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
  return JSON.stringify(payload);
}

function coveragePayload(categories: MonitoringCategory[]) {
  return categories.reduce<Record<string, { enabled: boolean; severityOverride: string | null }>>(
    (payload, category) => {
      payload[category.name] = {
        enabled: category.enabled !== false,
        severityOverride: category.severityOverride || null,
      };
      return payload;
    },
    {}
  );
}

function exclusionKey(exclusion: MonitoringExclusion) {
  return `${exclusion.type}-${exclusion.id}`;
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

function SettingsPage({ context }: { context: any }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasLoadedSettings, setHasLoadedSettings] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");
  const [alertThreshold, setAlertThreshold] = useState("medium");
  const [slackDeliveryEnabled, setSlackDeliveryEnabled] = useState(true);
  const [ticketDeliveryEnabled, setTicketDeliveryEnabled] = useState(true);
  const [lastSavedAt, setLastSavedAt] = useState("");
  const [settingsStorage, setSettingsStorage] = useState("");
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [coverageSaving, setCoverageSaving] = useState(false);
  const [coverageError, setCoverageError] = useState("");
  const [coverageMessage, setCoverageMessage] = useState("");
  const [coverageCategories, setCoverageCategories] = useState<MonitoringCategory[]>([]);
  const [loadedCoverageFingerprint, setLoadedCoverageFingerprint] = useState(
    coverageFingerprint([])
  );
  const [exclusionsLoading, setExclusionsLoading] = useState(false);
  const [exclusionsSaving, setExclusionsSaving] = useState(false);
  const [exclusionsError, setExclusionsError] = useState("");
  const [workflowExclusions, setWorkflowExclusions] = useState<MonitoringExclusion[]>([]);
  const [propertyExclusions, setPropertyExclusions] = useState<MonitoringExclusion[]>([]);
  const [workflowExclusionId, setWorkflowExclusionId] = useState("");
  const [workflowExclusionReason, setWorkflowExclusionReason] = useState("");
  const [propertyExclusionId, setPropertyExclusionId] = useState("");
  const [propertyExclusionObjectTypeId, setPropertyExclusionObjectTypeId] = useState("0-1");
  const [propertyExclusionReason, setPropertyExclusionReason] = useState("");

  const portalId = String(context?.portal?.id ?? "");
  const userId = String(context?.user?.id ?? "unknown");
  const userEmail = String(context?.user?.email ?? "unknown");
  const portalLabel = portalId || "Portal pending";

  const settingsUrl = useMemo(
    () => buildUrl(SETTINGS_API_BASE, { portalId }),
    [portalId]
  );
  const coverageUrl = useMemo(
    () => buildUrl(`${DASHBOARD_API_BASE}/monitoring-coverage`, { portalId }),
    [portalId]
  );

  const formLocked = loading || saving || !hasLoadedSettings || !portalId;
  const coverageDirty =
    coverageCategories.length > 0 &&
    coverageFingerprint(coverageCategories) !== loadedCoverageFingerprint;
  const coverageLocked = coverageLoading || coverageSaving || !portalId;
  const enabledCategoryCount = coverageCategories.filter(
    (category) => category.enabled !== false
  ).length;
  const coverageCategoryCount = coverageCategories.length || 6;
  const monitoringCoverageTitle = `Monitoring coverage (${enabledCategoryCount} enabled / ${coverageCategoryCount})`;
  const excludedWorkflowsTitle = `Excluded workflows (${workflowExclusions.length})`;
  const excludedPropertiesTitle = `Excluded properties (${propertyExclusions.length})`;
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

  useEffect(() => {
    if (!portalId) {
      return;
    }

    loadMonitoringCoverage();
    loadExclusions();
  }, [coverageUrl, portalId]);

  async function loadMonitoringCoverage() {
    if (!portalId) {
      return;
    }

    setCoverageLoading(true);
    setCoverageError("");
    setCoverageMessage("");

    try {
      const response = await hubspot.fetch(coverageUrl, {
        method: "GET",
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = (await response.json()) as MonitoringCoverageResponse;
      const categories = normalizeCategories(data.categories);
      setCoverageCategories(categories);
      setLoadedCoverageFingerprint(coverageFingerprint(categories));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setCoverageError(message);
    } finally {
      setCoverageLoading(false);
    }
  }

  async function saveMonitoringCoverage() {
    setCoverageSaving(true);
    setCoverageError("");
    setCoverageMessage("");

    try {
      const response = await hubspot.fetch(coverageUrl, {
        method: "PUT",
        body: coveragePayload(coverageCategories),
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = (await response.json()) as MonitoringCoverageResponse;
      const categories = normalizeCategories(data.categories);
      setCoverageCategories(categories);
      setLoadedCoverageFingerprint(coverageFingerprint(categories));
      setCoverageMessage("Saved.");
      setTimeout(() => setCoverageMessage(""), 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setCoverageError(message);
    } finally {
      setCoverageSaving(false);
    }
  }

  function setCategoryEnabled(categoryName: string, enabled: boolean) {
    setCoverageCategories((categories) =>
      categories.map((category) =>
        category.name === categoryName ? { ...category, enabled } : category
      )
    );
  }

  function setCategorySeverity(categoryName: string, value: string) {
    const severityOverride =
      value === DEFAULT_SEVERITY_VALUE ? null : value.toLowerCase();

    setCoverageCategories((categories) =>
      categories.map((category) =>
        category.name === categoryName
          ? { ...category, severityOverride }
          : category
      )
    );
  }

  function exclusionsUrl(type?: ExclusionType) {
    return buildUrl(`${DASHBOARD_API_BASE}/exclusions`, {
      portalId,
      type: type ?? "",
    });
  }

  async function loadExclusions() {
    if (!portalId) {
      return;
    }

    setExclusionsLoading(true);
    setExclusionsError("");

    try {
      const [workflowResponse, propertyResponse] = await Promise.all([
        hubspot.fetch(exclusionsUrl("workflow"), {
          method: "GET",
          timeout: 15000,
        }),
        hubspot.fetch(exclusionsUrl("property"), {
          method: "GET",
          timeout: 15000,
        }),
      ]);

      if (!workflowResponse.ok) {
        throw new Error(
          `Workflow exclusions returned status ${workflowResponse.status}`
        );
      }
      if (!propertyResponse.ok) {
        throw new Error(
          `Property exclusions returned status ${propertyResponse.status}`
        );
      }

      setWorkflowExclusions(
        ((await workflowResponse.json()) as MonitoringExclusion[]) ?? []
      );
      setPropertyExclusions(
        ((await propertyResponse.json()) as MonitoringExclusion[]) ?? []
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setExclusionsError(message);
    } finally {
      setExclusionsLoading(false);
    }
  }

  async function addWorkflowExclusion() {
    const id = workflowExclusionId.trim();
    if (!id) {
      return;
    }

    setExclusionsSaving(true);
    setExclusionsError("");

    try {
      const response = await hubspot.fetch(exclusionsUrl(), {
        method: "POST",
        body: {
          type: "workflow",
          id,
          reason: workflowExclusionReason.trim() || undefined,
        },
        timeout: 15000,
      });
      if (response.status === 409) {
        throw new Error("This workflow is already excluded.");
      }
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      setWorkflowExclusionId("");
      setWorkflowExclusionReason("");
      await loadExclusions();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setExclusionsError(message);
    } finally {
      setExclusionsSaving(false);
    }
  }

  async function addPropertyExclusion() {
    const id = propertyExclusionId.trim();
    if (!id) {
      return;
    }

    setExclusionsSaving(true);
    setExclusionsError("");

    try {
      const response = await hubspot.fetch(exclusionsUrl(), {
        method: "POST",
        body: {
          type: "property",
          id,
          objectTypeId: propertyExclusionObjectTypeId,
          reason: propertyExclusionReason.trim() || undefined,
        },
        timeout: 15000,
      });
      if (response.status === 409) {
        throw new Error("This property is already excluded.");
      }
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      setPropertyExclusionId("");
      setPropertyExclusionReason("");
      await loadExclusions();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setExclusionsError(message);
    } finally {
      setExclusionsSaving(false);
    }
  }

  async function removeExclusion(exclusion: MonitoringExclusion) {
    const previousWorkflows = workflowExclusions;
    const previousProperties = propertyExclusions;
    const url = buildUrl(
      `${DASHBOARD_API_BASE}/exclusions/${exclusion.id}`,
      { portalId }
    );

    if (exclusion.type === "workflow") {
      setWorkflowExclusions((rows) =>
        rows.filter((row) => row.id !== exclusion.id)
      );
    } else {
      setPropertyExclusions((rows) =>
        rows.filter((row) => row.id !== exclusion.id)
      );
    }

    setExclusionsSaving(true);
    setExclusionsError("");

    try {
      const response = await hubspot.fetch(url, {
        method: "DELETE",
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      await loadExclusions();
    } catch (error) {
      setWorkflowExclusions(previousWorkflows);
      setPropertyExclusions(previousProperties);
      const message = error instanceof Error ? error.message : String(error);
      setExclusionsError(message);
    } finally {
      setExclusionsSaving(false);
    }
  }

  async function saveSettings() {
    setSaving(true);
    setSaveMessage("");
    setErrorMessage("");
    setTestMessage("");

    try {
      const payload = {
        slackWebhookUrl,
        alertThreshold,
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

      <Accordion title="Alert routing" defaultOpen size="md">
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

              </Flex>
            </Box>
            </Flex>
          </Flex>
        </Form>
      </Accordion>

      <Accordion title={monitoringCoverageTitle} size="md">
        <Tile>
          <Flex direction="column" gap="medium">
          <SectionHeader
            eyebrow="Monitoring coverage"
            title="Choose what OpsLens watches"
            body="Turn alert categories on or off for this portal, and override severity only where this client's operating model needs it."
          />
          <Divider />

          {coverageLoading ? <Text>Loading monitoring coverage...</Text> : null}
          {coverageError ? (
            <Flex align="center" gap="small" wrap>
              <StatusTag variant="danger">Error</StatusTag>
              <Text>{coverageError}</Text>
            </Flex>
          ) : null}

          <Flex direction="column" gap="small">
            {coverageCategories.map((category) => (
              <Flex
                key={category.name}
                direction="row"
                justify="between"
                align="center"
                gap="small"
                wrap
              >
                <Box flex={1}>
                  <Flex direction="column" gap="extra-small">
                    <Text format={{ fontWeight: "bold" }}>
                      {categoryLabel(category.name)}
                    </Text>
                    <Text>
                      Default severity: {severityLabel(category.defaultSeverity)}
                    </Text>
                  </Flex>
                </Box>
                <Flex direction="row" align="center" gap="small" wrap>
                  <Toggle
                    label={category.enabled ? "On" : "Off"}
                    checked={category.enabled}
                    readonly={coverageLocked}
                    onChange={(value) =>
                      setCategoryEnabled(category.name, Boolean(value))
                    }
                  />
                  <Select
                    label="Severity override"
                    name={`severity-${category.name}`}
                    value={
                      category.severityOverride || DEFAULT_SEVERITY_VALUE
                    }
                    onChange={(value) =>
                      setCategorySeverity(
                        category.name,
                        String(value ?? DEFAULT_SEVERITY_VALUE)
                      )
                    }
                    readOnly={coverageLocked || !category.enabled}
                    options={[
                      {
                        label: `Default (${severityLabel(
                          category.defaultSeverity
                        )})`,
                        value: DEFAULT_SEVERITY_VALUE,
                      },
                      { label: "Low", value: "low" },
                      { label: "Medium", value: "medium" },
                      { label: "High", value: "high" },
                      { label: "Critical", value: "critical" },
                    ]}
                  />
                </Flex>
              </Flex>
            ))}
          </Flex>

          {!coverageLoading && coverageCategories.length === 0 ? (
            <Text>
              Monitoring coverage could not be loaded yet. The rest of this
              settings page remains available.
            </Text>
          ) : null}

          <Flex direction="row" justify="end" gap="small">
            <Button
              type="button"
              variant="primary"
              disabled={coverageLocked || !coverageDirty}
              onClick={saveMonitoringCoverage}
            >
              {coverageSaving ? "Saving..." : "Save monitoring coverage"}
            </Button>
          </Flex>

          {coverageMessage ? (
            <Flex align="center" gap="small" wrap>
              <StatusTag variant="success">Saved</StatusTag>
              <Text>{coverageMessage}</Text>
            </Flex>
          ) : null}
          </Flex>
        </Tile>
      </Accordion>

      <Accordion title={excludedWorkflowsTitle} size="md">
        <Tile>
          <Flex direction="column" gap="medium">
            <SectionHeader
              eyebrow="Exclusions"
              title="Excluded workflows"
              body="Workflows in this list will not generate alerts when disabled, edited, or deleted."
            />
            <Divider />

            {exclusionsLoading ? <Text>Loading exclusions...</Text> : null}

            <Flex direction="column" gap="small">
              {workflowExclusions.length === 0 ? (
                <Text>No excluded workflows yet.</Text>
              ) : (
                workflowExclusions.map((exclusion) => (
                  <Flex
                    key={exclusionKey(exclusion)}
                    direction="row"
                    justify="between"
                    align="center"
                    gap="small"
                    wrap
                  >
                    <Box flex={1}>
                      <Flex direction="column" gap="extra-small">
                        <Text format={{ fontWeight: "bold" }}>
                          {exclusion.exclusionId}
                        </Text>
                        {exclusion.reason ? (
                          <Text>{exclusion.reason}</Text>
                        ) : null}
                      </Flex>
                    </Box>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={exclusionsSaving}
                      onClick={() => removeExclusion(exclusion)}
                    >
                      Remove
                    </Button>
                  </Flex>
                ))
              )}
            </Flex>

            <Divider />

            <Flex direction="row" gap="small" align="center" wrap>
              <Box flex={1}>
                <Input
                  label="Workflow ID"
                  name="workflowExclusionId"
                  value={workflowExclusionId}
                  type="text"
                  onChange={(value) =>
                    setWorkflowExclusionId(String(value ?? ""))
                  }
                  readOnly={exclusionsSaving || !portalId}
                  description="Paste the HubSpot workflow ID to exclude from monitoring."
                />
              </Box>
              <Box flex={1}>
                <Input
                  label="Reason"
                  name="workflowExclusionReason"
                  value={workflowExclusionReason}
                  type="text"
                  onChange={(value) =>
                    setWorkflowExclusionReason(String(value ?? ""))
                  }
                  readOnly={exclusionsSaving || !portalId}
                  description="Optional note for future admins."
                />
              </Box>
              <Button
                type="button"
                variant="primary"
                disabled={
                  exclusionsSaving || !portalId || !workflowExclusionId.trim()
                }
                onClick={addWorkflowExclusion}
              >
                Add exclusion
              </Button>
            </Flex>
          </Flex>
        </Tile>
      </Accordion>

      <Accordion title={excludedPropertiesTitle} size="md">
        <Tile>
          <Flex direction="column" gap="medium">
            <SectionHeader
              eyebrow="Exclusions"
              title="Excluded properties"
              body="Properties in this list will not generate alerts when archived, deleted, renamed, or type-changed."
            />
            <Divider />

            <Flex direction="column" gap="small">
              {propertyExclusions.length === 0 ? (
                <Text>No excluded properties yet.</Text>
              ) : (
                propertyExclusions.map((exclusion) => (
                  <Flex
                    key={exclusionKey(exclusion)}
                    direction="row"
                    justify="between"
                    align="center"
                    gap="small"
                    wrap
                  >
                    <Box flex={1}>
                      <Flex direction="column" gap="extra-small">
                        <Text format={{ fontWeight: "bold" }}>
                          {exclusion.exclusionId}
                        </Text>
                        <Text>{objectTypeLabel(exclusion.objectTypeId)}</Text>
                        {exclusion.reason ? (
                          <Text>{exclusion.reason}</Text>
                        ) : null}
                      </Flex>
                    </Box>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={exclusionsSaving}
                      onClick={() => removeExclusion(exclusion)}
                    >
                      Remove
                    </Button>
                  </Flex>
                ))
              )}
            </Flex>

            <Divider />

            <Flex direction="row" gap="small" align="center" wrap>
              <Box flex={1}>
                <Input
                  label="Property name"
                  name="propertyExclusionId"
                  value={propertyExclusionId}
                  type="text"
                  onChange={(value) =>
                    setPropertyExclusionId(String(value ?? ""))
                  }
                  readOnly={exclusionsSaving || !portalId}
                  description="Use the internal HubSpot property name, not the display label."
                />
              </Box>
              <Box flex={1}>
                <Select
                  label="Object type"
                  name="propertyExclusionObjectTypeId"
                  value={propertyExclusionObjectTypeId}
                  onChange={(value) =>
                    setPropertyExclusionObjectTypeId(String(value ?? "0-1"))
                  }
                  readOnly={exclusionsSaving || !portalId}
                  options={OBJECT_TYPE_OPTIONS}
                />
              </Box>
              <Box flex={1}>
                <Input
                  label="Reason"
                  name="propertyExclusionReason"
                  value={propertyExclusionReason}
                  type="text"
                  onChange={(value) =>
                    setPropertyExclusionReason(String(value ?? ""))
                  }
                  readOnly={exclusionsSaving || !portalId}
                  description="Optional note for future admins."
                />
              </Box>
              <Button
                type="button"
                variant="primary"
                disabled={
                  exclusionsSaving || !portalId || !propertyExclusionId.trim()
                }
                onClick={addPropertyExclusion}
              >
                Add exclusion
              </Button>
            </Flex>

            {exclusionsError ? (
              <Flex align="center" gap="small" wrap>
                <StatusTag variant="danger">Error</StatusTag>
                <Text>{exclusionsError}</Text>
              </Flex>
            ) : null}
          </Flex>
        </Tile>
      </Accordion>
    </Flex>
  );
}

export default SettingsPage;
