import React, { useEffect, useState } from "react";
import {
  Box,
  Divider,
  EmptyState,
  Flex,
  Text,
  hubspot,
} from "@hubspot/ui-extensions";
import {
  HeaderActions,
  PrimaryHeaderActionButton,
  SecondaryHeaderActionButton,
} from "@hubspot/ui-extensions/pages/home";

const BACKEND_BASE_URL = "https://opslens.local";

hubspot.extend(({ context }) => {
  return <Home context={context} />;
});

const Home = ({ context }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState(null);

  const loadOverview = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await hubspot.fetch(
        `${BACKEND_BASE_URL}/api/v1/dashboard/overview`,
        {
          method: "GET",
          timeout: 3000,
        }
      );

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();
      setOverview(data);
    } catch (err) {
      console.error("Failed to load dashboard overview", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOverview().catch((err) =>
      console.error("Unexpected dashboard load error", err)
    );
  }, []);

  const incidents = overview?.activeIncidents ?? [];

  return (
    <>
      <HeaderActions>
        <PrimaryHeaderActionButton onClick={() => loadOverview()}>
          Refresh queue
        </PrimaryHeaderActionButton>
        <SecondaryHeaderActionButton onClick={() => console.log("open-settings")}>
          Settings
        </SecondaryHeaderActionButton>
      </HeaderActions>

      <Flex direction="column" gap="medium">
        <EmptyState title="OpsLens AI is connected" layout="vertical">
          <Text>
            This page is now loading live summary and incident data from the local Python backend.
          </Text>
        </EmptyState>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Backend status</Text>
          <Text>{loading ? "Loading..." : overview?.status ?? "No response yet"}</Text>
          <Text>{error ? `Error: ${error}` : "No fetch error detected."}</Text>
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Applied settings</Text>
          <Text>Alert threshold: {String(overview?.appliedSettings?.alertThreshold ?? "-").toUpperCase()}</Text>
          <Text>Critical workflows: {String(overview?.appliedSettings?.criticalWorkflows ?? "-")}</Text>
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Ops summary</Text>
          <Text>Open incidents: {String(overview?.summary?.openIncidents ?? "-")}</Text>
          <Text>Critical issues: {String(overview?.summary?.criticalIssues ?? "-")}</Text>
          <Text>Monitored workflows: {String(overview?.summary?.monitoredWorkflows ?? "-")}</Text>
          <Text>Last checked: {String(overview?.summary?.lastCheckedUtc ?? "-")}</Text>
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Active incidents</Text>
          {incidents.length === 0 ? (
            <Text>No incidents returned at the current threshold.</Text>
          ) : (
            <Flex direction="column" gap="small">
              {incidents.map((incident) => (
                <Box key={incident.id}>
                  <Text format={{ fontWeight: "bold" }}>
                    [{String(incident.severity).toUpperCase()}] {incident.title}
                  </Text>
                  <Text>ID: {incident.id}</Text>
                  <Text>Affected records: {String(incident.affectedRecords ?? "-")}</Text>
                  <Text>Recommended next step: {incident.recommendation}</Text>
                </Box>
              ))}
            </Flex>
          )}
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Debug context</Text>
          <Text>Portal ID from HubSpot context: {String(context?.portal?.id ?? "unknown")}</Text>
          <Text>User ID from HubSpot context: {String(context?.user?.id ?? "unknown")}</Text>
          <Text>Portal ID seen by backend: {String(overview?.debug?.portalId ?? "unknown")}</Text>
          <Text>User ID seen by backend: {String(overview?.debug?.userId ?? "unknown")}</Text>
        </Box>
      </Flex>
    </>
  );
};
