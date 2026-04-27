import * as React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  EmptyState,
  Flex,
  Heading,
  Link,
  StatusTag,
  Text,
  Tile,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

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

function propertySettingsUrl(portalId: string, sourceObjectTypeId?: string | null) {
  const type = encodeURIComponent(String(sourceObjectTypeId || "0-1"));
  return `https://app.hubspot.com/property-settings/${portalId}/properties?type=${type}`;
}

function workflowUrl(portalId: string, workflowId?: string | null) {
  return `https://app.hubspot.com/workflows/${portalId}/platform/flow/${workflowId}/edit`;
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

function ActionAlertCard({
  alert,
  portalId,
  resolving,
  onResolve,
}: {
  alert: DashboardAlert;
  portalId: string;
  resolving: boolean;
  onResolve: (alertId: string) => void;
}) {
  const alertId = String(alert.id || "");
  const severity = String(alert.severity || "unknown").toUpperCase();

  return (
    <Tile>
      <Flex direction="column" gap="small">
        <Flex justify="between" align="start" gap="small" wrap>
          <Box flex={1}>
            <Flex direction="column" gap="extra-small">
              <StatusTag variant={severityVariant(alert.severity)}>
                {severity}
              </StatusTag>
              <Text format={{ fontWeight: "bold" }}>
                {String(alert.title || "Untitled alert")}
              </Text>
              <Text>{formatTimeAgo(alert.createdAtUtc)}</Text>
            </Flex>
          </Box>
        </Flex>

        <Flex justify="between" align="center" gap="small" wrap>
          <HubSpotLinks alert={alert} portalId={portalId} />
          <Button
            type="button"
            variant="secondary"
            disabled={!alertId || resolving}
            onClick={() => onResolve(alertId)}
          >
            {resolving ? "Resolving..." : "Mark resolved"}
          </Button>
        </Flex>
      </Flex>
    </Tile>
  );
}

function HomePage({ context }: HomePageProps) {
  const [loading, setLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [overviewData, setOverviewData] = useState<OverviewResponse | null>(null);
  const [resolvingAlertId, setResolvingAlertId] = useState("");

  const portalId = String(context?.portal?.id ?? "");
  const userId = String(context?.user?.id ?? "");
  const userEmail = String(context?.user?.email ?? "");
  const appId = String(context?.app?.id ?? context?.appId ?? "");
  const userName = String(context?.user?.firstName ?? "").trim() || "there";

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

  const greeting = greetingForHour(new Date().getHours());
  const subtitle =
    actionRequiredCount > 0
      ? `${actionRequiredCount} ${
          actionRequiredCount === 1 ? "thing needs" : "things need"
        } your attention this morning`
      : "Nothing needs action right now";

  const loadOverview = async () => {
    const response = await hubspot.fetch(
      buildUrl("/api/v1/dashboard/overview", {
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
      throw new Error(`Overview request failed with status ${response.status}`);
    }

    const data = (await response.json()) as OverviewResponse;
    setOverviewData(data);
  };

  const refresh = async () => {
    setLoading(true);
    setOverviewError("");
    try {
      await loadOverview();
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
      await loadOverview();
    } catch (error) {
      setOverviewData(previous);
      setOverviewError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setResolvingAlertId("");
    }
  };

  useEffect(() => {
    refresh().catch((error) => {
      setOverviewError(error instanceof Error ? error.message : "Unknown error");
      setLoading(false);
    });
  }, [portalId, userId, userEmail, appId]);

  return (
    <Flex direction="column" gap="medium">
      <Tile>
        <Flex direction="row" justify="between" align="center" gap="small" wrap>
          <Box flex={1}>
            <Flex direction="column" gap="extra-small">
              <Heading>
                {greeting}, {userName}
              </Heading>
              <Text>
                Portal {portalId || "unknown"} - {subtitle}
              </Text>
              {overviewError ? <Text>Overview issue: {overviewError}</Text> : null}
            </Flex>
          </Box>
          <Button
            type="button"
            variant="secondary"
            disabled={loading}
            onClick={() => refresh()}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        </Flex>
      </Tile>

      <Flex direction="row" gap="small">
        <Box flex={1}>
          <StatusMetric
            label="Needs action"
            value={actionRequiredCount}
            detail="Open critical and high alerts"
          />
        </Box>
        <Box flex={1}>
          <StatusMetric
            label="Watching"
            value={watchingCount}
            detail="Open medium alerts"
          />
        </Box>
        <Box flex={1}>
          <StatusMetric
            label="Resolved this week"
            value={resolvedThisWeekCount}
            detail="Closed in the last 7 days"
          />
        </Box>
      </Flex>

      <Tile>
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
              {sortedActionRequired.slice(0, 5).map((alert) => (
                <ActionAlertCard
                  key={String(alert.id)}
                  alert={alert}
                  portalId={portalId}
                  resolving={resolvingAlertId === String(alert.id)}
                  onResolve={markResolved}
                />
              ))}
            </Flex>
          )}
        </Flex>
      </Tile>

      <Flex direction="row" gap="small">
        <Box flex={1}>
          <Tile>
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
                    <Text key={String(alert.id)}>
                      {String(alert.title || "Untitled alert")} ·{" "}
                      {formatTimeAgo(alert.createdAtUtc)}
                    </Text>
                  ))}
                  {watchingCount > watchingPreview.length ? (
                    <Text>
                      + {watchingCount - watchingPreview.length} more
                    </Text>
                  ) : null}
                </Flex>
              )}
            </Flex>
          </Tile>
        </Box>

        <Box flex={1}>
          <Tile>
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
          </Tile>
        </Box>
      </Flex>
    </Flex>
  );
}

export default HomePage;
