
from pathlib import Path
import textwrap

ROOT = Path.cwd()

files = {
    "src/app/pages/Home.tsx": """
import React from "react";
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

hubspot.extend(({ context }) => {
  return <Home context={context} />;
});

const Home = ({ context }) => {
  return (
    <>
      <HeaderActions>
        <PrimaryHeaderActionButton onClick={() => console.log("refresh-queue")}>
          Refresh queue
        </PrimaryHeaderActionButton>
        <SecondaryHeaderActionButton onClick={() => console.log("open-settings")}>
          Settings
        </SecondaryHeaderActionButton>
      </HeaderActions>

      <Flex direction="column" gap="medium">
        <EmptyState title="OpsLens AI is connected" layout="vertical">
          <Text>
            This is the first local build of the OpsLens AI home page inside HubSpot.
          </Text>
        </EmptyState>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>What this page will become</Text>
          <Text>• Active incidents and severity</Text>
          <Text>• Recent workflow and property changes</Text>
          <Text>• Recommended next actions for admins</Text>
        </Box>

        <Divider />

        <Box>
          <Text format={{ fontWeight: "bold" }}>Debug context</Text>
          <Text>Portal ID: {String(context?.portal?.id ?? "unknown")}</Text>
          <Text>User ID: {String(context?.user?.id ?? "unknown")}</Text>
        </Box>
      </Flex>
    </>
  );
};
""",
    "src/app/cards/NewCard.tsx": """
import React from "react";
import { Button, Divider, Flex, Text, hubspot } from "@hubspot/ui-extensions";

hubspot.extend(({ context }) => {
  return <NewCard context={context} />;
});

const NewCard = ({ context }) => {
  return (
    <Flex direction="column" gap="small">
      <Text format={{ fontWeight: "bold" }}>OpsLens AI</Text>
      <Text>
        This record card will surface operational risk, recent changes, and recommended actions.
      </Text>
      <Divider />
      <Text>CRM object type: {String(context?.crm?.objectTypeId ?? "unknown")}</Text>
      <Text>Record ID: {String(context?.crm?.objectId ?? "unknown")}</Text>
      <Button onClick={() => console.log("open-opslens-record-view")}>
        Open incident view
      </Button>
    </Flex>
  );
};
""",
    "src/app/settings/SettingsPage.tsx": """
import React from "react";
import {
  Box,
  Divider,
  EmptyState,
  Flex,
  Text,
  hubspot,
} from "@hubspot/ui-extensions";

hubspot.extend(({ context }) => {
  return <SettingsPage context={context} />;
});

const SettingsPage = ({ context }) => {
  return (
    <Flex direction="column" gap="medium">
      <EmptyState title="OpsLens AI settings" layout="vertical">
        <Text>
          This page will store portal-level configuration for notifications and monitoring.
        </Text>
      </EmptyState>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Planned settings</Text>
        <Text>• Alert thresholds</Text>
        <Text>• Slack / email routing</Text>
        <Text>• Critical workflows to monitor</Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Debug context</Text>
        <Text>Portal ID: {String(context?.portal?.id ?? "unknown")}</Text>
        <Text>User ID: {String(context?.user?.id ?? "unknown")}</Text>
      </Box>
    </Flex>
  );
};
""",
}

for rel_path, content in files.items():
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")

print("OpsLens HubSpot step 3 branding scaffold created successfully.")
print(f"Project root: {ROOT}")
print()
print("Updated files:")
for rel_path in sorted(files):
    print(f" - {rel_path}")
