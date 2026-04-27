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

type ExclusionType = "workflow" | "property" | "list" | "template";

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

type WorkflowPickerOption = {
  id: string;
  name: string;
  isEnabled: boolean;
};

type PropertyPickerOption = {
  name: string;
  label: string;
  type: string;
};

type ListPickerOption = {
  id: string;
  name: string;
  isArchived: boolean;
};

type TemplatePickerOption = {
  id: string;
  name: string;
  subject?: string;
  isArchived: boolean;
};

const CATEGORY_LABELS: Record<string, string> = {
  property_archived: "Archived properties",
  property_deleted: "Deleted properties",
  property_renamed: "Renamed properties",
  property_type_changed: "Property type changes",
  workflow_disabled: "Disabled workflows",
  workflow_edited: "Edited workflows",
  list_archived: "Archived lists",
  list_deleted: "Deleted lists",
  list_criteria_changed: "List criteria changes",
  template_archived: "Archived email templates",
  template_deleted: "Deleted email templates",
  template_edited: "Edited email templates",
  owner_deactivated: "Deactivated owners",
  owner_deleted: "Deleted owners",
};

const COVERAGE_CATEGORY_GROUPS: Array<{ label: string; names: string[] }> = [
  {
    label: "Property changes",
    names: [
      "property_archived",
      "property_deleted",
      "property_renamed",
      "property_type_changed",
    ],
  },
  {
    label: "Workflow changes",
    names: ["workflow_disabled", "workflow_edited"],
  },
  {
    label: "List changes",
    names: ["list_archived", "list_deleted", "list_criteria_changed"],
  },
  {
    label: "Email template changes",
    names: ["template_archived", "template_deleted", "template_edited"],
  },
  {
    label: "Owner changes",
    names: ["owner_deactivated", "owner_deleted"],
  },
];

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

function workflowOptionLabel(workflow: WorkflowPickerOption) {
  const name = String(workflow.name || workflow.id).trim();
  const status = workflow.isEnabled ? "active" : "disabled";
  return `${name} (${workflow.id}, ${status})`;
}

function propertyOptionLabel(property: PropertyPickerOption) {
  const label = String(property.label || property.name).trim();
  const type = property.type ? `, ${property.type}` : "";
  return `${label} (${property.name}${type})`;
}

function listOptionLabel(list: ListPickerOption) {
  const name = String(list.name || list.id).trim();
  const status = list.isArchived ? "archived" : "active";
  return `${name} (${list.id}, ${status})`;
}

function templateOptionLabel(template: TemplatePickerOption) {
  const name = String(template.name || template.id).trim();
  const subject = String(template.subject || "").trim();
  const status = template.isArchived ? "archived" : "active";
  const detail = subject ? `${template.id}, ${subject}, ${status}` : `${template.id}, ${status}`;
  return `${name} (${detail})`;
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
  const [listExclusions, setListExclusions] = useState<MonitoringExclusion[]>([]);
  const [templateExclusions, setTemplateExclusions] = useState<MonitoringExclusion[]>([]);
  const [propertyExclusions, setPropertyExclusions] = useState<MonitoringExclusion[]>([]);
  const [workflowPickerOptions, setWorkflowPickerOptions] = useState<WorkflowPickerOption[]>([]);
  const [workflowPickerLoading, setWorkflowPickerLoading] = useState(false);
  const [workflowPickerError, setWorkflowPickerError] = useState("");
  const [listPickerOptions, setListPickerOptions] = useState<ListPickerOption[]>([]);
  const [listPickerLoading, setListPickerLoading] = useState(false);
  const [listPickerError, setListPickerError] = useState("");
  const [templatePickerOptions, setTemplatePickerOptions] = useState<TemplatePickerOption[]>([]);
  const [templatePickerLoading, setTemplatePickerLoading] = useState(false);
  const [templatePickerError, setTemplatePickerError] = useState("");
  const [propertyPickerOptions, setPropertyPickerOptions] = useState<PropertyPickerOption[]>([]);
  const [propertyPickerLoading, setPropertyPickerLoading] = useState(false);
  const [propertyPickerError, setPropertyPickerError] = useState("");
  const [workflowExclusionId, setWorkflowExclusionId] = useState("");
  const [workflowExclusionReason, setWorkflowExclusionReason] = useState("");
  const [listExclusionId, setListExclusionId] = useState("");
  const [listExclusionReason, setListExclusionReason] = useState("");
  const [templateExclusionId, setTemplateExclusionId] = useState("");
  const [templateExclusionReason, setTemplateExclusionReason] = useState("");
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
  const workflowsUrl = useMemo(
    () => buildUrl(`${DASHBOARD_API_BASE}/workflows`, { portalId }),
    [portalId]
  );
  const listsUrl = useMemo(
    () => buildUrl(`${DASHBOARD_API_BASE}/lists`, { portalId }),
    [portalId]
  );
  const templatesUrl = useMemo(
    () => buildUrl(`${DASHBOARD_API_BASE}/templates`, { portalId }),
    [portalId]
  );
  const propertiesUrl = useMemo(
    () =>
      buildUrl(`${DASHBOARD_API_BASE}/properties`, {
        portalId,
        objectTypeId: propertyExclusionObjectTypeId,
      }),
    [portalId, propertyExclusionObjectTypeId]
  );

  const formLocked = loading || saving || !hasLoadedSettings || !portalId;
  const coverageDirty =
    coverageCategories.length > 0 &&
    coverageFingerprint(coverageCategories) !== loadedCoverageFingerprint;
  const coverageLocked = coverageLoading || coverageSaving || !portalId;
  const enabledCategoryCount = coverageCategories.filter(
    (category) => category.enabled !== false
  ).length;
  const coverageCategoryCount =
    coverageCategories.length ||
    COVERAGE_CATEGORY_GROUPS.reduce(
      (total, group) => total + group.names.length,
      0
    );
  const monitoringCoverageTitle = `Monitoring coverage (${enabledCategoryCount} enabled / ${coverageCategoryCount})`;
  const excludedWorkflowsTitle = `Excluded workflows (${workflowExclusions.length})`;
  const excludedListsTitle = `Excluded lists (${listExclusions.length})`;
  const excludedTemplatesTitle = `Excluded templates (${templateExclusions.length})`;
  const excludedPropertiesTitle = `Excluded properties (${propertyExclusions.length})`;
  const workflowSelectOptions = [
    {
      label: workflowPickerLoading
        ? "Loading monitored workflows..."
        : "Select a monitored workflow",
      value: "",
    },
    ...workflowPickerOptions.map((workflow) => ({
      label: workflowOptionLabel(workflow),
      value: workflow.id,
    })),
  ];
  const listSelectOptions = [
    {
      label: listPickerLoading ? "Loading monitored lists..." : "Select a list",
      value: "",
    },
    ...listPickerOptions.map((list) => ({
      label: listOptionLabel(list),
      value: list.id,
    })),
  ];
  const templateSelectOptions = [
    {
      label: templatePickerLoading
        ? "Loading monitored email templates..."
        : "Select an email template",
      value: "",
    },
    ...templatePickerOptions.map((template) => ({
      label: templateOptionLabel(template),
      value: template.id,
    })),
  ];
  const propertySelectOptions = [
    {
      label: propertyPickerLoading
        ? "Loading properties..."
        : "Select a property",
      value: "",
    },
    ...propertyPickerOptions.map((property) => ({
      label: propertyOptionLabel(property),
      value: property.name,
    })),
  ];
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
    loadWorkflowPickerOptions();
    loadListPickerOptions();
    loadTemplatePickerOptions();
  }, [coverageUrl, listsUrl, portalId, templatesUrl, workflowsUrl]);

  useEffect(() => {
    if (!portalId || !propertyExclusionObjectTypeId) {
      return;
    }

    loadPropertyPickerOptions();
  }, [portalId, propertiesUrl, propertyExclusionObjectTypeId]);

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
      const [workflowResponse, listResponse, templateResponse, propertyResponse] =
        await Promise.all([
          hubspot.fetch(exclusionsUrl("workflow"), {
            method: "GET",
            timeout: 15000,
          }),
          hubspot.fetch(exclusionsUrl("list"), {
            method: "GET",
            timeout: 15000,
          }),
          hubspot.fetch(exclusionsUrl("template"), {
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
      if (!listResponse.ok) {
        throw new Error(`List exclusions returned status ${listResponse.status}`);
      }
      if (!templateResponse.ok) {
        throw new Error(
          `Template exclusions returned status ${templateResponse.status}`
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
      setListExclusions(
        ((await listResponse.json()) as MonitoringExclusion[]) ?? []
      );
      setTemplateExclusions(
        ((await templateResponse.json()) as MonitoringExclusion[]) ?? []
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

  async function loadWorkflowPickerOptions() {
    if (!portalId) {
      return;
    }

    setWorkflowPickerLoading(true);
    setWorkflowPickerError("");

    try {
      const response = await hubspot.fetch(workflowsUrl, {
        method: "GET",
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const rows = ((await response.json()) as WorkflowPickerOption[]) ?? [];
      setWorkflowPickerOptions(
        rows
          .map((row) => ({
            id: String(row.id ?? "").trim(),
            name: String(row.name ?? "").trim(),
            isEnabled: row.isEnabled !== false,
          }))
          .filter((row) => row.id)
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setWorkflowPickerError(message);
    } finally {
      setWorkflowPickerLoading(false);
    }
  }

  async function loadListPickerOptions() {
    if (!portalId) {
      return;
    }

    setListPickerLoading(true);
    setListPickerError("");

    try {
      const response = await hubspot.fetch(listsUrl, {
        method: "GET",
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const rows = ((await response.json()) as ListPickerOption[]) ?? [];
      setListPickerOptions(
        rows
          .map((row) => ({
            id: String(row.id ?? "").trim(),
            name: String(row.name ?? "").trim(),
            isArchived: row.isArchived === true,
          }))
          .filter((row) => row.id)
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setListPickerError(message);
    } finally {
      setListPickerLoading(false);
    }
  }

  async function loadTemplatePickerOptions() {
    if (!portalId) {
      return;
    }

    setTemplatePickerLoading(true);
    setTemplatePickerError("");

    try {
      const response = await hubspot.fetch(templatesUrl, {
        method: "GET",
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const rows = ((await response.json()) as TemplatePickerOption[]) ?? [];
      setTemplatePickerOptions(
        rows
          .map((row) => ({
            id: String(row.id ?? "").trim(),
            name: String(row.name ?? "").trim(),
            subject: String(row.subject ?? "").trim(),
            isArchived: row.isArchived === true,
          }))
          .filter((row) => row.id)
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setTemplatePickerError(message);
    } finally {
      setTemplatePickerLoading(false);
    }
  }

  async function loadPropertyPickerOptions() {
    if (!portalId || !propertyExclusionObjectTypeId) {
      return;
    }

    setPropertyPickerLoading(true);
    setPropertyPickerError("");

    try {
      const response = await hubspot.fetch(propertiesUrl, {
        method: "GET",
        timeout: 15000,
      });
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const rows = ((await response.json()) as PropertyPickerOption[]) ?? [];
      setPropertyPickerOptions(
        rows
          .map((row) => ({
            name: String(row.name ?? "").trim(),
            label: String(row.label ?? "").trim(),
            type: String(row.type ?? "").trim(),
          }))
          .filter((row) => row.name)
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setPropertyPickerError(message);
      setPropertyPickerOptions([]);
    } finally {
      setPropertyPickerLoading(false);
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

  async function addListExclusion() {
    const id = listExclusionId.trim();
    if (!id) {
      return;
    }

    setExclusionsSaving(true);
    setExclusionsError("");

    try {
      const response = await hubspot.fetch(exclusionsUrl(), {
        method: "POST",
        body: {
          type: "list",
          id,
          reason: listExclusionReason.trim() || undefined,
        },
        timeout: 15000,
      });
      if (response.status === 409) {
        throw new Error("This list is already excluded.");
      }
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      setListExclusionId("");
      setListExclusionReason("");
      await loadExclusions();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setExclusionsError(message);
    } finally {
      setExclusionsSaving(false);
    }
  }

  async function addTemplateExclusion() {
    const id = templateExclusionId.trim();
    if (!id) {
      return;
    }

    setExclusionsSaving(true);
    setExclusionsError("");

    try {
      const response = await hubspot.fetch(exclusionsUrl(), {
        method: "POST",
        body: {
          type: "template",
          id,
          reason: templateExclusionReason.trim() || undefined,
        },
        timeout: 15000,
      });
      if (response.status === 409) {
        throw new Error("This email template is already excluded.");
      }
      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      setTemplateExclusionId("");
      setTemplateExclusionReason("");
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
    const previousLists = listExclusions;
    const previousTemplates = templateExclusions;
    const previousProperties = propertyExclusions;
    const url = buildUrl(
      `${DASHBOARD_API_BASE}/exclusions/${exclusion.id}`,
      { portalId }
    );

    if (exclusion.type === "workflow") {
      setWorkflowExclusions((rows) =>
        rows.filter((row) => row.id !== exclusion.id)
      );
    } else if (exclusion.type === "list") {
      setListExclusions((rows) =>
        rows.filter((row) => row.id !== exclusion.id)
      );
    } else if (exclusion.type === "template") {
      setTemplateExclusions((rows) =>
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
      setListExclusions(previousLists);
      setTemplateExclusions(previousTemplates);
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
              body="OpsLens alerts you when something changes in your portal that can break an active automation."
            />

            {coverageLoading ? <Text>Loading monitoring coverage...</Text> : null}
            {coverageError ? (
              <Flex align="center" gap="small" wrap>
                <StatusTag variant="danger">Error</StatusTag>
                <Text>{coverageError}</Text>
              </Flex>
            ) : null}

            <Flex direction="column" gap="medium">
              {COVERAGE_CATEGORY_GROUPS.map((group) => {
                const groupCategories = coverageCategories.filter((category) =>
                  group.names.includes(category.name)
                );
                if (groupCategories.length === 0) {
                  return null;
                }

                return (
                  <Flex key={group.label} direction="column" gap="small">
                    <Divider />
                    <Text
                      variant="microcopy"
                      format={{
                        fontWeight: "demibold",
                        textTransform: "uppercase",
                      }}
                    >
                      {group.label}
                    </Text>
                    {groupCategories.map((category) => (
                      <Flex
                        key={category.name}
                        direction="row"
                        align="center"
                        gap="medium"
                        wrap
                      >
                        <Box flex={2}>
                          <Flex direction="column" gap="extra-small">
                            <Text format={{ fontWeight: "bold" }}>
                              {categoryLabel(category.name)}
                            </Text>
                            <Text>
                              Default severity:{" "}
                              {severityLabel(category.defaultSeverity)}
                            </Text>
                          </Flex>
                        </Box>
                        <Box flex={1}>
                          <Toggle
                            label="Enabled"
                            checked={category.enabled}
                            readonly={coverageLocked}
                            onChange={(value) =>
                              setCategoryEnabled(category.name, Boolean(value))
                            }
                          />
                        </Box>
                        <Box flex={2}>
                          <Select
                            label="Severity override"
                            name={`severity-${category.name}`}
                            value={
                              category.severityOverride ||
                              DEFAULT_SEVERITY_VALUE
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
                        </Box>
                      </Flex>
                    ))}
                  </Flex>
                );
              })}
            </Flex>

            {!coverageLoading && coverageCategories.length === 0 ? (
              <Text>
                Monitoring coverage could not be loaded yet. The rest of this
                settings page remains available.
              </Text>
            ) : null}

            {coverageCategories.length > 0 ? (
              <Text variant="microcopy">
                Tip: To stop alerts for a specific workflow, list, email
                template, or property, use the Excluded sections below.
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
                <Flex direction="column" gap="extra-small" align="center">
                  <Text variant="microcopy">
                    No excluded workflows yet.
                  </Text>
                  <Text variant="microcopy">
                    Pick a monitored workflow below to suppress future workflow alerts.
                  </Text>
                </Flex>
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

            <Flex direction="column" gap="small">
              <Flex direction="row" gap="small" align="start" wrap>
                <Box flex={2}>
                  <Select
                    label="Workflow"
                    name="workflowExclusionId"
                    value={workflowExclusionId}
                    onChange={(value) =>
                      setWorkflowExclusionId(String(value ?? ""))
                    }
                    readOnly={
                      exclusionsSaving ||
                      workflowPickerLoading ||
                      workflowPickerOptions.length === 0 ||
                      !portalId
                    }
                    description="Choose from workflows OpsLens has already observed; the workflow ID is shown in the option text."
                    error={Boolean(workflowPickerError)}
                    validationMessage={workflowPickerError || undefined}
                    options={workflowSelectOptions}
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
              </Flex>
              <Flex direction="row" justify="end" gap="small">
                <Button
                  type="button"
                  variant="primary"
                  disabled={
                    exclusionsSaving ||
                    workflowPickerLoading ||
                    !portalId ||
                    !workflowExclusionId.trim()
                  }
                  onClick={addWorkflowExclusion}
                >
                  Add exclusion
                </Button>
              </Flex>
            </Flex>
          </Flex>
        </Tile>
      </Accordion>

      <Accordion title={excludedListsTitle} size="md">
        <Tile>
          <Flex direction="column" gap="medium">
            <SectionHeader
              eyebrow="Exclusions"
              title="Excluded lists"
              body="Lists in this list will not generate alerts when archived, deleted, or criteria-changed."
            />
            <Divider />

            {exclusionsLoading ? <Text>Loading exclusions...</Text> : null}

            <Flex direction="column" gap="small">
              {listExclusions.length === 0 ? (
                <Flex direction="column" gap="extra-small" align="center">
                  <Text variant="microcopy">
                    No excluded lists yet.
                  </Text>
                  <Text variant="microcopy">
                    Pick a monitored list below to suppress future list alerts.
                  </Text>
                </Flex>
              ) : (
                listExclusions.map((exclusion) => (
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

            <Flex direction="column" gap="small">
              <Flex direction="row" gap="small" align="start" wrap>
                <Box flex={2}>
                  <Select
                    label="List"
                    name="listExclusionId"
                    value={listExclusionId}
                    onChange={(value) =>
                      setListExclusionId(String(value ?? ""))
                    }
                    readOnly={
                      exclusionsSaving ||
                      listPickerLoading ||
                      listPickerOptions.length === 0 ||
                      !portalId
                    }
                    description="Choose from lists OpsLens has already observed; the list ID is shown in the option text."
                    error={Boolean(listPickerError)}
                    validationMessage={listPickerError || undefined}
                    options={listSelectOptions}
                  />
                </Box>
                <Box flex={1}>
                  <Input
                    label="Reason"
                    name="listExclusionReason"
                    value={listExclusionReason}
                    type="text"
                    onChange={(value) =>
                      setListExclusionReason(String(value ?? ""))
                    }
                    readOnly={exclusionsSaving || !portalId}
                    description="Optional note for future admins."
                  />
                </Box>
              </Flex>
              <Flex direction="row" justify="end" gap="small">
                <Button
                  type="button"
                  variant="primary"
                  disabled={
                    exclusionsSaving ||
                    listPickerLoading ||
                    !portalId ||
                    !listExclusionId.trim()
                  }
                  onClick={addListExclusion}
                >
                  Add exclusion
                </Button>
              </Flex>
            </Flex>
          </Flex>
        </Tile>
      </Accordion>

      <Accordion title={excludedTemplatesTitle} size="md">
        <Tile>
          <Flex direction="column" gap="medium">
            <SectionHeader
              eyebrow="Exclusions"
              title="Excluded email templates"
              body="Email templates in this list will not generate alerts when archived, deleted, or edited."
            />
            <Divider />

            {exclusionsLoading ? <Text>Loading exclusions...</Text> : null}

            <Flex direction="column" gap="small">
              {templateExclusions.length === 0 ? (
                <Flex direction="column" gap="extra-small" align="center">
                  <Text variant="microcopy">
                    No excluded email templates yet.
                  </Text>
                  <Text variant="microcopy">
                    Pick a monitored template below to suppress future template alerts.
                  </Text>
                </Flex>
              ) : (
                templateExclusions.map((exclusion) => (
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

            <Flex direction="column" gap="small">
              <Flex direction="row" gap="small" align="start" wrap>
                <Box flex={2}>
                  <Select
                    label="Email template"
                    name="templateExclusionId"
                    value={templateExclusionId}
                    onChange={(value) =>
                      setTemplateExclusionId(String(value ?? ""))
                    }
                    readOnly={
                      exclusionsSaving ||
                      templatePickerLoading ||
                      templatePickerOptions.length === 0 ||
                      !portalId
                    }
                    description="Choose from automated marketing emails OpsLens has already observed."
                    error={Boolean(templatePickerError)}
                    validationMessage={templatePickerError || undefined}
                    options={templateSelectOptions}
                  />
                </Box>
                <Box flex={1}>
                  <Input
                    label="Reason"
                    name="templateExclusionReason"
                    value={templateExclusionReason}
                    type="text"
                    onChange={(value) =>
                      setTemplateExclusionReason(String(value ?? ""))
                    }
                    readOnly={exclusionsSaving || !portalId}
                    description="Optional note for future admins."
                  />
                </Box>
              </Flex>
              <Flex direction="row" justify="end" gap="small">
                <Button
                  type="button"
                  variant="primary"
                  disabled={
                    exclusionsSaving ||
                    templatePickerLoading ||
                    !portalId ||
                    !templateExclusionId.trim()
                  }
                  onClick={addTemplateExclusion}
                >
                  Add exclusion
                </Button>
              </Flex>
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
                <Flex direction="column" gap="extra-small" align="center">
                  <Text variant="microcopy">
                    No excluded properties yet.
                  </Text>
                  <Text variant="microcopy">
                    Choose an object type, then pick the HubSpot property to exclude.
                  </Text>
                </Flex>
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

            <Flex direction="column" gap="small">
              <Flex direction="row" gap="small" align="start" wrap>
                <Box flex={1}>
                  <Select
                    label="Object type"
                    name="propertyExclusionObjectTypeId"
                    value={propertyExclusionObjectTypeId}
                    onChange={(value) => {
                      setPropertyExclusionObjectTypeId(String(value ?? "0-1"));
                      setPropertyExclusionId("");
                      setPropertyPickerOptions([]);
                    }}
                    readOnly={exclusionsSaving || propertyPickerLoading || !portalId}
                    description="Pick the HubSpot object before choosing a property."
                    options={OBJECT_TYPE_OPTIONS}
                  />
                </Box>
                <Box flex={2}>
                  <Select
                    label="Property"
                    name="propertyExclusionId"
                    value={propertyExclusionId}
                    onChange={(value) =>
                      setPropertyExclusionId(String(value ?? ""))
                    }
                    readOnly={
                      exclusionsSaving ||
                      propertyPickerLoading ||
                      propertyPickerOptions.length === 0 ||
                      !portalId
                    }
                    description="Choose by HubSpot label; the internal name is shown in the option text."
                    error={Boolean(propertyPickerError)}
                    validationMessage={propertyPickerError || undefined}
                    options={propertySelectOptions}
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
              </Flex>
              <Flex direction="row" justify="end" gap="small">
                <Button
                  type="button"
                  variant="primary"
                  disabled={
                    exclusionsSaving ||
                    propertyPickerLoading ||
                    !portalId ||
                    !propertyExclusionId.trim()
                  }
                  onClick={addPropertyExclusion}
                >
                  Add exclusion
                </Button>
              </Flex>
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
