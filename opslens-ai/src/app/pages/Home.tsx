import * as React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  ButtonRow,
  Card,
  Divider,
  EmptyState,
  Flex,
  Heading,
  Link,
  Statistics,
  StatisticsItem,
  StatusTag,
  Tag,
  Text,
  Tile,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";
const ACTION_PAGE_SIZE_OPTIONS = [3, 5, 10, 25, 50];

hubspot.extend(({ context }) => <HomePage context={context} />);

type HomePageProps = {
  context: any;
};

type DashboardAlert = {
  id?: string;
  severity?: string;
  title?: string;
  sourceEventType?: string;
  impactedWorkflowId?: string | null;
  impactedWorkflowName?: string | null;
  recommendedAction?: string | null;
  fixGuidance?: {
    summary?: string;
    steps?: string[];
    restorable?: boolean;
  } | null;
  dependencyLocations?: string[] | null;
  sourceDependencyId?: string | null;
  sourceObjectTypeId?: string | null;
  createdAtUtc?: string | null;
};

type OverviewResponse = {
  status?: string;
  app?: string;
  connectedBackend?: boolean;
  settings?: {
    portalId?: string;
    slackWebhookUrl?: string;
    alertThreshold?: string;
    criticalWorkflows?: string;
    updatedAtUtc?: string;
    storage?: string;
  };
  summary?: {
    openIncidents?: number;
    criticalIssues?: number;
    monitoredWorkflows?: number;
    lastCheckedUtc?: string | null;
    activeIncidents?: unknown[];
    actionRequired?: DashboardAlert[];
    watching?: DashboardAlert[];
    resolvedThisWeekCount?: number;
    actionRequiredCount?: number;
    watchingCount?: number;
    lastPollUtc?: string | null;
    slackConnected?: boolean;
  };
};

type PollNowResponse = {
  status?: string;
  eventsDetected?: number;
  alertsCreated?: number;
};

type InstallDiagnosticSummary = {
  status?: string;
  issuesFound?: number;
};

type InstallDiagnosticResponse = {
  status?: string;
  portalId?: string;
  summary?: InstallDiagnosticSummary;
};

type StatusVariant = "danger" | "warning" | "info" | "success" | "default";

function buildUrl(path: string, params: Record<string, string>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      query.set(key, value);
    }
  });
  const queryString = query.toString();
  return `${BACKEND_BASE_URL}${path}${queryString ? `?${queryString}` : ""}`;
}

function greetingForHour(hour: number) {
  if (hour >= 5 && hour < 12) {
    return "Good morning";
  }
  if (hour >= 12 && hour < 17) {
    return "Good afternoon";
  }
  if (hour >= 17 && hour < 22) {
    return "Good evening";
  }
  return "Hello";
}

function formatTimeAgo(value?: string | null) {
  if (!value) {
    return "Not available";
  }

  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return "Not available";
  }

  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) {
    return "just now";
  }

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hr ago`;
  }

  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }

  return new Date(timestamp).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function severityRank(severity?: string | null) {
  const level = String(severity || "").toLowerCase();
  if (level === "critical") {
    return 2;
  }
  if (level === "high") {
    return 1;
  }
  return 0;
}

function severityVariant(severity?: string | null): StatusVariant {
  const level = String(severity || "").toLowerCase();
  if (level === "critical") {
    return "danger";
  }
  if (level === "high") {
    return "warning";
  }
  if (level === "medium") {
    return "info";
  }
  return "default";
}

type AlertVariant = "info" | "warning" | "success" | "error" | "danger" | "tip";

function alertVariantForStatus(status: StatusVariant): AlertVariant {
  if (status === "danger") {
    return "danger";
  }
  if (status === "warning") {
    return "warning";
  }
  if (status === "success") {
    return "success";
  }
  // "info" and "default" both map to the neutral informational banner.
  return "info";
}

function severityTagVariant(
  severity?: string | null
): "default" | "warning" | "success" | "error" | "info" {
  const level = String(severity || "").toLowerCase();
  if (level === "critical") {
    return "error";
  }
  if (level === "high") {
    return "warning";
  }
  if (level === "medium") {
    return "info";
  }
  return "default";
}

function isPropertyAlert(sourceEventType?: string | null) {
  return (
    sourceEventType === "property_archived" ||
    sourceEventType === "property_deleted" ||
    sourceEventType === "property_renamed" ||
    sourceEventType === "property_type_changed"
  );
}

function isWorkflowAlert(sourceEventType?: string | null) {
  return (
    sourceEventType === "workflow_disabled" ||
    sourceEventType === "workflow_edited" ||
    sourceEventType === "workflow_deleted"
  );
}

function isListAlert(sourceEventType?: string | null) {
  return (
    sourceEventType === "list_archived" ||
    sourceEventType === "list_deleted" ||
    sourceEventType === "list_criteria_changed"
  );
}

function isTemplateAlert(sourceEventType?: string | null) {
  return (
    sourceEventType === "template_archived" ||
    sourceEventType === "template_deleted" ||
    sourceEventType === "template_edited"
  );
}

function isOwnerAlert(sourceEventType?: string | null) {
  return (
    sourceEventType === "owner_deactivated" ||
    sourceEventType === "owner_deleted"
  );
}

function propertySettingsUrl(portalId: string, sourceObjectTypeId?: string | null) {
  const type = encodeURIComponent(String(sourceObjectTypeId || "0-1"));
  return `https://app.hubspot.com/property-settings/${portalId}/properties?type=${type}`;
}

function workflowUrl(portalId: string, workflowId?: string | null) {
  return `https://app.hubspot.com/workflows/${portalId}/platform/flow/${workflowId}/edit`;
}

function listUrl(portalId: string, listId?: string | null) {
  return `https://app.hubspot.com/contacts/${portalId}/objectLists/${listId}/filters`;
}

function templateUrl(portalId: string, templateId?: string | null) {
  return `https://app.hubspot.com/email/${portalId}/edit/${templateId}/content`;
}

function usersSettingsUrl(portalId: string) {
  return `https://app.hubspot.com/settings/${portalId}/users`;
}

function appSettingsUrl(portalId: string) {
  // Generic "installed apps" landing page — works without an appId
  // because HubSpot routes the user to the right OpsLens settings panel
  // from there. Avoids the previous breakage where context?.app?.id was
  // undefined at render time.
  return `https://app.hubspot.com/integrations-settings/${portalId}/installed`;
}

function StatusMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <Tile compact>
      <Flex direction="column" gap="small">
        <Text format={{ fontWeight: "bold" }}>{label}</Text>
        <Heading>{String(value)}</Heading>
        <Text>{detail}</Text>
      </Flex>
    </Tile>
  );
}

function HealthRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Flex justify="between" align="center" gap="small" wrap>
      <Text format={{ fontWeight: "bold" }}>{label}</Text>
      <Box>{children}</Box>
    </Flex>
  );
}

function HubSpotLinks({
  alert,
  portalId,
}: {
  alert: DashboardAlert;
  portalId: string;
}) {
  const links = [];

  if (isPropertyAlert(alert.sourceEventType)) {
    links.push({
      label: "Open property settings",
      url: propertySettingsUrl(portalId, alert.sourceObjectTypeId),
    });
    if (alert.impactedWorkflowId) {
      links.push({
        label: "Open workflow",
        url: workflowUrl(portalId, alert.impactedWorkflowId),
      });
    }
  } else if (isWorkflowAlert(alert.sourceEventType) && alert.impactedWorkflowId) {
    links.push({
      label: "Open workflow",
      url: workflowUrl(portalId, alert.impactedWorkflowId),
    });
  } else if (isListAlert(alert.sourceEventType)) {
    if (alert.sourceDependencyId) {
      links.push({
        label: "Open list",
        url: listUrl(portalId, alert.sourceDependencyId),
      });
    }
    if (alert.impactedWorkflowId) {
      links.push({
        label: "Open workflow",
        url: workflowUrl(portalId, alert.impactedWorkflowId),
      });
    }
  } else if (isTemplateAlert(alert.sourceEventType)) {
    if (alert.sourceDependencyId) {
      links.push({
        label: "Open template",
        url: templateUrl(portalId, alert.sourceDependencyId),
      });
    }
    if (alert.impactedWorkflowId) {
      links.push({
        label: "Open workflow",
        url: workflowUrl(portalId, alert.impactedWorkflowId),
      });
    }
  } else if (isOwnerAlert(alert.sourceEventType)) {
    links.push({
      label: "Open user settings",
      url: usersSettingsUrl(portalId),
    });
    if (alert.impactedWorkflowId) {
      links.push({
        label: "Open workflow",
        url: workflowUrl(portalId, alert.impactedWorkflowId),
      });
    }
  }

  if (links.length === 0) {
    return null;
  }

  return (
    <Flex direction="row" gap="small" wrap>
      {links.map((link) => (
        <Link
          key={`${link.label}-${link.url}`}
          href={{ url: link.url, external: true }}
        >
          {link.label}
        </Link>
      ))}
    </Flex>
  );
}

function BlastRadius({ alert }: { alert: DashboardAlert }) {
  const isAssetChange =
    isPropertyAlert(alert.sourceEventType) ||
    isListAlert(alert.sourceEventType) ||
    isTemplateAlert(alert.sourceEventType) ||
    isOwnerAlert(alert.sourceEventType);
  const workflowName = String(alert.impactedWorkflowName || "").trim();

  if (!isAssetChange || !workflowName) {
    return null;
  }

  const verb = isOwnerAlert(alert.sourceEventType)
    ? "Still referenced in"
    : "Affects";
  const locations = Array.isArray(alert.dependencyLocations)
    ? alert.dependencyLocations.filter((loc) => String(loc).trim())
    : [];
  const where =
    locations.length > 0 ? ` — used as ${locations.join(", ")}` : "";

  return (
    <Box>
      <Text format={{ fontWeight: "bold" }}>Blast radius</Text>
      <Text variant="microcopy">
        {`${verb} workflow “${workflowName}”${where}`}
      </Text>
    </Box>
  );
}

function RecommendedAction({ alert }: { alert: DashboardAlert }) {
  const action = String(alert.recommendedAction || "").trim();
  if (!action) {
    return null;
  }
  return (
    <Box>
      <Text format={{ fontWeight: "bold" }}>Recommended action</Text>
      <Text variant="microcopy">{action}</Text>
    </Box>
  );
}

function FixGuidance({ alert }: { alert: DashboardAlert }) {
  const guidance = alert.fixGuidance;
  const summary = String(guidance?.summary || "").trim();
  const steps = Array.isArray(guidance?.steps)
    ? guidance!.steps.filter((step) => String(step).trim())
    : [];
  if (!summary && steps.length === 0) {
    return null;
  }
  return (
    <Box>
      <Text format={{ fontWeight: "bold" }}>How to fix</Text>
      {summary ? <Text variant="microcopy">{summary}</Text> : null}
      {steps.map((step, index) => (
        <Text key={index} variant="microcopy">{`${index + 1}. ${step}`}</Text>
      ))}
    </Box>
  );
}

function ActionAlertCard({
  alert,
  portalId,
  resolving,
  reenabling,
  onResolve,
  onReenable,
}: {
  alert: DashboardAlert;
  portalId: string;
  resolving: boolean;
  reenabling: boolean;
  onResolve: (alertId: string) => void;
  onReenable: (alertId: string, workflowId: string) => void;
}) {
  const alertId = String(alert.id || "");
  const severity = String(alert.severity || "unknown").toUpperCase();
  const isReenableCandidate =
    alert.sourceEventType === "workflow_disabled" &&
    Boolean(alert.impactedWorkflowId);
  const [confirmingReenable, setConfirmingReenable] = useState(false);

  return (
    <Card>
      <Flex direction="column" gap="small">
        <Flex justify="between" align="start" gap="small" wrap>
          <Box flex={1}>
            <Flex direction="column" gap="extra-small">
              <Box>
                <Tag variant={severityTagVariant(alert.severity)} inline>
                  {severity}
                </Tag>
              </Box>
              <Heading>{String(alert.title || "Untitled alert")}</Heading>
              <Text variant="microcopy">{formatTimeAgo(alert.createdAtUtc)}</Text>
            </Flex>
          </Box>
        </Flex>

        <Divider />

        <BlastRadius alert={alert} />
        <RecommendedAction alert={alert} />
        <FixGuidance alert={alert} />

        <Flex justify="between" align="center" gap="small" wrap>
          <HubSpotLinks alert={alert} portalId={portalId} />
          <Flex direction="row" gap="small" align="center" wrap>
            {isReenableCandidate ? (
              confirmingReenable ? (
                <Flex direction="row" gap="small" align="center" wrap>
                  <Text variant="microcopy">Turn this workflow back on?</Text>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={reenabling}
                    onClick={() => {
                      setConfirmingReenable(false);
                      onReenable(alertId, String(alert.impactedWorkflowId || ""));
                    }}
                  >
                    {reenabling ? "Re-enabling..." : "Confirm"}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={reenabling}
                    onClick={() => setConfirmingReenable(false)}
                  >
                    Cancel
                  </Button>
                </Flex>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={reenabling || resolving}
                  onClick={() => setConfirmingReenable(true)}
                >
                  Re-enable workflow
                </Button>
              )
            ) : null}
            <Button
              type="button"
              variant="secondary"
              disabled={!alertId || resolving || reenabling}
              onClick={() => onResolve(alertId)}
            >
              {resolving ? "Resolving..." : "Mark resolved"}
            </Button>
          </Flex>
        </Flex>
      </Flex>
    </Card>
  );
}

function HomePage({ context }: HomePageProps) {
  const [loading, setLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [overviewData, setOverviewData] = useState<OverviewResponse | null>(null);
  const [resolvingAlertId, setResolvingAlertId] = useState("");
  const [reenablingAlertId, setReenablingAlertId] = useState("");
  const [actionPageSize, setActionPageSize] = useState(10);
  const [actionPage, setActionPage] = useState(1);
  const [lastUpdatedAt, setLastUpdatedAt] = useState("");
  const [timeTick, setTimeTick] = useState(0);
  const [checkingNow, setCheckingNow] = useState(false);
  const [checkNowMessage, setCheckNowMessage] = useState("");
  const [checkNowLockedUntil, setCheckNowLockedUntil] = useState(0);
  const [diagnosticData, setDiagnosticData] =
    useState<InstallDiagnosticResponse | null>(null);
  const [scanningDiagnostic, setScanningDiagnostic] = useState(false);

  const portalId = String(context?.portal?.id ?? "");
  const userId = String(context?.user?.id ?? "");
  const userEmail = String(context?.user?.email ?? "");
  const appId = String(context?.app?.id ?? context?.appId ?? "");
  const userName = String(context?.user?.firstName ?? "").trim();

  // Diagnostic for the Settings link — logged once per mount so we can
  // confirm context.portal.id resolves at render time (the prior
  // attempt rendered nothing because it ANDed with appId, which is
  // often undefined in this surface).
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.log("[OpsLens] context.portal.id =", context?.portal?.id, "appId =", appId);
  }, []);

  const settingsUrl = portalId ? appSettingsUrl(portalId) : null;

  const summary = overviewData?.summary ?? {};
  const settings = overviewData?.settings ?? {};
  const actionRequired = Array.isArray(summary.actionRequired)
    ? summary.actionRequired
    : [];
  const watching = Array.isArray(summary.watching) ? summary.watching : [];

  const sortedActionRequired = useMemo(() => {
    return [...actionRequired].sort((left, right) => {
      const rankDelta = severityRank(right.severity) - severityRank(left.severity);
      if (rankDelta !== 0) {
        return rankDelta;
      }
      return (
        Date.parse(String(right.createdAtUtc || "")) -
        Date.parse(String(left.createdAtUtc || ""))
      );
    });
  }, [actionRequired]);

  const watchingPreview = useMemo(() => watching.slice(0, 3), [watching]);

  const actionRequiredCount =
    typeof summary.actionRequiredCount === "number"
      ? summary.actionRequiredCount
      : actionRequired.length;
  const watchingCount =
    typeof summary.watchingCount === "number" ? summary.watchingCount : watching.length;
  const resolvedThisWeekCount =
    typeof summary.resolvedThisWeekCount === "number"
      ? summary.resolvedThisWeekCount
      : 0;
  const totalActionPages = Math.max(
    1,
    Math.ceil(actionRequiredCount / actionPageSize)
  );
  const showingStart =
    actionRequiredCount === 0 ? 0 : (actionPage - 1) * actionPageSize + 1;
  const showingEnd = Math.min(actionPage * actionPageSize, actionRequiredCount);
  const showActionPagination = actionRequiredCount > actionPageSize;
  const checkNowLocked = checkNowLockedUntil > Date.now();
  const lastUpdatedLabel =
    timeTick >= 0 && lastUpdatedAt ? formatTimeAgo(lastUpdatedAt) : "Not updated yet";
  const diagnosticSummary = diagnosticData?.summary;
  const diagnosticStatus = String(diagnosticSummary?.status || "");
  const diagnosticIssuesFound =
    typeof diagnosticSummary?.issuesFound === "number"
      ? diagnosticSummary.issuesFound
      : 0;
  let diagnosticBannerText = "";
  let diagnosticBannerVariant: StatusVariant = "default";
  let diagnosticBannerTag = "";
  if (scanningDiagnostic) {
    diagnosticBannerText = "Scanning your portal for broken dependencies...";
    diagnosticBannerVariant = "info";
    diagnosticBannerTag = "Scanning";
  } else if (diagnosticStatus === "completed") {
    if (diagnosticIssuesFound > 0) {
      diagnosticBannerText = `OpsLens found ${diagnosticIssuesFound} potential issue${
        diagnosticIssuesFound === 1 ? "" : "s"
      } in your portal.`;
      diagnosticBannerVariant = "warning";
      diagnosticBannerTag = "Review";
    } else {
      diagnosticBannerText =
        "Good news: OpsLens scanned your portal and found no broken dependencies.";
      diagnosticBannerVariant = "success";
      diagnosticBannerTag = "Clean";
    }
  } else if (diagnosticStatus === "error") {
    diagnosticBannerText = "OpsLens couldn't complete the dependency scan.";
    diagnosticBannerVariant = "danger";
    diagnosticBannerTag = "Failed";
  } else {
    diagnosticBannerText =
      "OpsLens hasn't scanned this portal for broken dependencies yet.";
    diagnosticBannerVariant = "default";
    diagnosticBannerTag = "Not run";
  }
  const scanButtonLabel =
    diagnosticStatus === "completed" ? "Re-run scan" : "Run scan";

  const greeting = greetingForHour(new Date().getHours());
  const greetingLine = userName ? `${greeting}, ${userName}` : greeting;
  const subtitle =
    actionRequiredCount > 0
      ? `${actionRequiredCount} ${
          actionRequiredCount === 1 ? "thing needs" : "things need"
        } your attention`
      : "Nothing needs action right now";

  const loadOverview = async () => {
    const response = await hubspot.fetch(
      buildUrl("/api/v1/dashboard/overview", {
        portalId,
        userId,
        userEmail,
        appId,
        actionPageSize: String(actionPageSize),
        actionPage: String(actionPage),
      }),
      {
        method: "GET",
        timeout: 8000,
      }
    );

    if (!response.ok) {
      throw new Error(`Overview request failed with status ${response.status}`);
    }

    const data = (await response.json()) as OverviewResponse;
    setOverviewData(data);
    setLastUpdatedAt(new Date().toISOString());
    return data;
  };

  const loadInstallDiagnostic = async () => {
    if (!portalId) {
      setDiagnosticData(null);
      return null;
    }

    const response = await hubspot.fetch(
      buildUrl("/api/v1/dashboard/install-diagnostic", {
        portalId,
        userId,
        userEmail,
        appId,
      }),
      {
        method: "GET",
        timeout: 8000,
      }
    );

    if (!response.ok) {
      throw new Error(`Diagnostic request failed with status ${response.status}`);
    }

    const data = (await response.json()) as InstallDiagnosticResponse;
    setDiagnosticData(data);
    return data;
  };

  const refresh = async () => {
    setLoading(true);
    setOverviewError("");
    try {
      await loadOverview();
      await loadInstallDiagnostic().catch(() => {
        setDiagnosticData(null);
      });
    } catch (error) {
      setOverviewError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const markResolved = async (alertId: string) => {
    if (!alertId || !portalId) {
      return;
    }

    const previous = overviewData;
    setResolvingAlertId(alertId);
    setOverviewError("");
    setOverviewData((current) => {
      if (!current?.summary) {
        return current;
      }
      const currentSummary = current.summary;
      const nextActionRequired = Array.isArray(currentSummary.actionRequired)
        ? currentSummary.actionRequired.filter((alert) => String(alert.id) !== alertId)
        : [];
      return {
        ...current,
        summary: {
          ...currentSummary,
          actionRequired: nextActionRequired,
          actionRequiredCount: Math.max(
            0,
            Number(currentSummary.actionRequiredCount ?? nextActionRequired.length) - 1
          ),
          resolvedThisWeekCount:
            Number(currentSummary.resolvedThisWeekCount ?? 0) + 1,
        },
      };
    });

    try {
      const response = await hubspot.fetch(
        buildUrl(`/api/v1/dashboard/alerts/${alertId}/resolve`, { portalId }),
        {
          method: "POST",
          timeout: 8000,
        }
      );
      if (!response.ok) {
        throw new Error(`Resolve request failed with status ${response.status}`);
      }
      const data = await loadOverview();
      const nextSummary = data?.summary ?? {};
      const nextActionRequired = Array.isArray(nextSummary.actionRequired)
        ? nextSummary.actionRequired
        : [];
      const nextActionRequiredCount =
        typeof nextSummary.actionRequiredCount === "number"
          ? nextSummary.actionRequiredCount
          : nextActionRequired.length;
      if (
        nextActionRequired.length === 0 &&
        actionPage > 1 &&
        nextActionRequiredCount > 0
      ) {
        setActionPage(Math.ceil(nextActionRequiredCount / actionPageSize));
      }
    } catch (error) {
      setOverviewData(previous);
      setOverviewError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setResolvingAlertId("");
    }
  };

  const reenableWorkflow = async (alertId: string, workflowId: string) => {
    if (!alertId || !workflowId || !portalId) {
      return;
    }

    setReenablingAlertId(alertId);
    setOverviewError("");
    try {
      const response = await hubspot.fetch(
        buildUrl(`/api/v1/dashboard/alerts/${alertId}/reenable-workflow`, {
          portalId,
        }),
        {
          method: "POST",
          timeout: 20000,
        }
      );
      if (!response.ok) {
        let detail = `Re-enable failed with status ${response.status}`;
        try {
          const body = (await response.json()) as { detail?: string };
          if (body?.detail) {
            detail = String(body.detail);
          }
        } catch (parseError) {
          // Keep the default message if the error body isn't JSON.
        }
        throw new Error(detail);
      }
      await loadOverview();
    } catch (error) {
      setOverviewError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setReenablingAlertId("");
    }
  };

  const runDiagnosticScan = async () => {
    if (!portalId || scanningDiagnostic) {
      return;
    }
    setScanningDiagnostic(true);
    setOverviewError("");
    try {
      const response = await hubspot.fetch(
        buildUrl("/api/v1/dashboard/install-diagnostic/run", { portalId }),
        {
          method: "POST",
          timeout: 60000,
        }
      );
      if (!response.ok) {
        let detail = `Scan failed with status ${response.status}`;
        try {
          const body = (await response.json()) as { detail?: string };
          if (body?.detail) {
            detail = String(body.detail);
          }
        } catch (parseError) {
          // Keep the default message if the error body isn't JSON.
        }
        throw new Error(detail);
      }
      const data = (await response.json()) as InstallDiagnosticResponse;
      setDiagnosticData(data);
    } catch (error) {
      setOverviewError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setScanningDiagnostic(false);
    }
  };

  const clearCheckNowMessageSoon = () => {
    setTimeout(() => {
      setCheckNowMessage("");
    }, 5000);
  };

  const checkNow = async () => {
    if (!portalId || checkingNow || checkNowLocked) {
      return;
    }

    setCheckingNow(true);
    setOverviewError("");
    setCheckNowMessage("Checking your portal...");

    try {
      const response = await hubspot.fetch(
        buildUrl("/api/v1/dashboard/poll-now", { portalId }),
        {
          method: "POST",
          timeout: 30000,
        }
      );
      if (response.status === 429) {
        setCheckNowMessage("Just checked — wait 30s.");
        clearCheckNowMessageSoon();
        return;
      }
      if (!response.ok) {
        throw new Error(`Check-now request failed with status ${response.status}`);
      }

      const payload = (await response.json()) as PollNowResponse;
      await loadOverview();
      await loadInstallDiagnostic().catch(() => null);
      setCheckNowLockedUntil(Date.now() + 30000);
      const eventsDetected = Number(payload.eventsDetected ?? 0);
      setCheckNowMessage(
        eventsDetected > 0 ? `Found ${eventsDetected} event(s)` : "No new changes"
      );
      clearCheckNowMessageSoon();
    } catch (error) {
      setCheckNowMessage(
        error instanceof Error ? error.message : "Check-now request failed."
      );
      clearCheckNowMessageSoon();
    } finally {
      setCheckingNow(false);
    }
  };

  useEffect(() => {
    refresh().catch((error) => {
      setOverviewError(error instanceof Error ? error.message : "Unknown error");
      setLoading(false);
    });
  }, [portalId, userId, userEmail, appId, actionPageSize, actionPage]);

  useEffect(() => {
    const intervalId = setInterval(() => {
      loadOverview().catch((error) => {
        setOverviewError(error instanceof Error ? error.message : "Unknown error");
      });
      loadInstallDiagnostic().catch(() => {
        setDiagnosticData(null);
      });
    }, 60000);
    return () => clearInterval(intervalId);
  }, [portalId, userId, userEmail, appId, actionPageSize, actionPage]);

  useEffect(() => {
    const intervalId = setInterval(() => {
      setTimeTick((value) => value + 1);
    }, 5000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <Flex direction="column" gap="medium">
      <Card>
        <Flex direction="column" gap="medium">
          <Flex direction="row" justify="between" align="start" gap="small" wrap>
            <Box flex={1}>
              <Flex direction="column" gap="extra-small">
                <Heading>{greetingLine}</Heading>
                <Text>{subtitle}</Text>
              </Flex>
            </Box>
            <Flex direction="column" align="end" gap="extra-small">
              <ButtonRow>
                <Button
                  type="button"
                  variant="primary"
                  disabled={checkingNow || checkNowLocked || !portalId}
                  onClick={checkNow}
                >
                  {checkingNow ? "Checking..." : "Check now"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={loading}
                  onClick={() => refresh()}
                >
                  {loading ? "Refreshing..." : "Refresh"}
                </Button>
              </ButtonRow>
              {settingsUrl ? (
                <Link href={{ url: settingsUrl, external: true }} variant="light">
                  Settings
                </Link>
              ) : null}
            </Flex>
          </Flex>

          {overviewError ? (
            <Alert title="Overview issue" variant="error">
              {overviewError}
            </Alert>
          ) : null}

          <Divider />

          <Statistics>
            <StatisticsItem label="Needs action" number={actionRequiredCount}>
              <Text variant="microcopy">Open critical and high</Text>
            </StatisticsItem>
            <StatisticsItem label="Watching" number={watchingCount}>
              <Text variant="microcopy">Open medium alerts</Text>
            </StatisticsItem>
            <StatisticsItem
              label="Resolved this week"
              number={resolvedThisWeekCount}
            >
              <Text variant="microcopy">Closed in last 7 days</Text>
            </StatisticsItem>
            <StatisticsItem label="Last checked" number={lastUpdatedLabel}>
              <Text variant="microcopy">
                {checkNowMessage ? checkNowMessage : "Auto-refreshes"}
              </Text>
            </StatisticsItem>
          </Statistics>
        </Flex>
      </Card>

      <Alert
        title={diagnosticBannerText}
        variant={alertVariantForStatus(diagnosticBannerVariant)}
      >
        <Flex direction="row" justify="between" align="center" gap="small" wrap>
          <StatusTag variant={diagnosticBannerVariant}>
            {diagnosticBannerTag}
          </StatusTag>
          <Button
            type="button"
            variant="secondary"
            disabled={!portalId || scanningDiagnostic}
            onClick={runDiagnosticScan}
          >
            {scanningDiagnostic ? "Scanning..." : scanButtonLabel}
          </Button>
        </Flex>
      </Alert>

      <Card>
        <Flex direction="column" gap="medium">
          <Flex justify="between" align="center" gap="small" wrap>
            <Box flex={1}>
              <Heading>Action queue</Heading>
              <Text>Workflow-impacting changes that need a consultant review.</Text>
            </Box>
            <StatusTag variant={actionRequiredCount > 0 ? "danger" : "success"}>
              {actionRequiredCount > 0 ? "Needs action" : "All clear"}
            </StatusTag>
          </Flex>

          {sortedActionRequired.length === 0 ? (
            <EmptyState
              title="All clear. OpsLens is monitoring your portal."
              layout="horizontal"
              flush
            >
              <Text>
                No critical or high-severity alerts are open right now.
              </Text>
            </EmptyState>
          ) : (
            <Flex direction="column" gap="small">
              {sortedActionRequired.map((alert) => (
                <ActionAlertCard
                  key={String(alert.id)}
                  alert={alert}
                  portalId={portalId}
                  resolving={resolvingAlertId === String(alert.id)}
                  reenabling={reenablingAlertId === String(alert.id)}
                  onResolve={markResolved}
                  onReenable={reenableWorkflow}
                />
              ))}
            </Flex>
          )}

          {showActionPagination ? (
            <Flex direction="row" justify="between" align="center" gap="small" wrap>
              <Text>
                Showing {showingStart}–{showingEnd} of {actionRequiredCount}
              </Text>

              <Flex direction="row" align="center" gap="small" wrap>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={actionPage === 1 || loading}
                  onClick={() => setActionPage((page) => Math.max(1, page - 1))}
                >
                  Previous
                </Button>
                <Text>
                  Page {actionPage} of {totalActionPages}
                </Text>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={actionPage * actionPageSize >= actionRequiredCount || loading}
                  onClick={() => setActionPage((page) => page + 1)}
                >
                  Next
                </Button>
              </Flex>

              <Flex direction="row" align="center" gap="extra-small" wrap>
                <Text>Rows</Text>
                {ACTION_PAGE_SIZE_OPTIONS.map((size) => (
                  <Button
                    key={size}
                    type="button"
                    variant={actionPageSize === size ? "primary" : "secondary"}
                    disabled={loading}
                    onClick={() => {
                      setActionPageSize(size);
                      setActionPage(1);
                    }}
                  >
                    {String(size)}
                  </Button>
                ))}
              </Flex>
            </Flex>
          ) : null}
        </Flex>
      </Card>

      {/*
        Watching + System health share a single Tile so they render at
        identical height by construction — one container, two columns.
        The previous side-by-side Tile-per-Box approach left visible
        height mismatches because Tile clamps its own intrinsic height
        and HubSpot UI Extensions exposes no minHeight / style props on
        Box or Tile to force equality from the outside.
      */}
      <Card>
        <Flex direction="row" gap="medium" align="stretch">
          <Box flex={1} alignSelf="stretch">
            <Flex direction="column" gap="medium">
              <Flex direction="column" gap="extra-small">
                <Heading>Watching</Heading>
                <Text>Medium-severity alerts worth keeping an eye on.</Text>
              </Flex>
              {watchingPreview.length === 0 ? (
                <Text>No medium-severity alerts are open.</Text>
              ) : (
                <Flex direction="column" gap="small">
                  {watchingPreview.map((alert) => (
                    <Flex
                      key={String(alert.id)}
                      direction="row"
                      align="center"
                      gap="small"
                      wrap
                    >
                      <Tag variant="info" inline>
                        MEDIUM
                      </Tag>
                      <Text>
                        {String(alert.title || "Untitled alert")} ·{" "}
                        {formatTimeAgo(alert.createdAtUtc)}
                      </Text>
                    </Flex>
                  ))}
                  {watchingCount > watchingPreview.length ? (
                    <Text>
                      + {watchingCount - watchingPreview.length} more
                    </Text>
                  ) : null}
                </Flex>
              )}
            </Flex>
          </Box>

          {/* No vertical divider — HubSpot's Divider is horizontal-only.
              The gap="medium" on the parent Flex provides separation. */}
          <Box flex={1} alignSelf="stretch">
            <Flex direction="column" gap="medium">
              <Flex direction="column" gap="extra-small">
                <Heading>System health</Heading>
                <Text>Current delivery and polling status for this portal.</Text>
              </Flex>
              <Flex direction="column" gap="small">
                <HealthRow label="Last poll">
                  <Text>{formatTimeAgo(summary.lastPollUtc)}</Text>
                </HealthRow>
                <HealthRow label="Slack delivery">
                  <StatusTag variant={summary.slackConnected ? "success" : "warning"}>
                    {summary.slackConnected ? "Connected" : "Not configured"}
                  </StatusTag>
                </HealthRow>
                <HealthRow label="Threshold">
                  <Text>{String(settings.alertThreshold || "medium").toUpperCase()}</Text>
                </HealthRow>
              </Flex>
            </Flex>
          </Box>
        </Flex>
      </Card>
    </Flex>
  );
}

export default HomePage;
