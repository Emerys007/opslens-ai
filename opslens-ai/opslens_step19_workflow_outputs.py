import json
from pathlib import Path

path = Path(r"C:\OpsLens AI\opslens-ai\src\app\workflow-actions\workflow-actions-hsmeta.json")
data = json.loads(path.read_text(encoding="utf-8-sig"))

config = data.setdefault("config", {})
labels = config.setdefault("labels", {})
en = labels.setdefault("en", {})

config["outputFields"] = [
    {
        "typeDefinition": {
            "name": "deliveryStatus",
            "type": "string",
            "fieldType": "text",
        }
    },
    {
        "typeDefinition": {
            "name": "deliveryChannel",
            "type": "string",
            "fieldType": "text",
        }
    },
    {
        "typeDefinition": {
            "name": "deliveryReason",
            "type": "string",
            "fieldType": "text",
        }
    },
    {
        "typeDefinition": {
            "name": "severityUsed",
            "type": "string",
            "fieldType": "text",
        }
    },
    {
        "typeDefinition": {
            "name": "portalIdUsed",
            "type": "string",
            "fieldType": "text",
        }
    },
    {
        "typeDefinition": {
            "name": "callbackId",
            "type": "string",
            "fieldType": "text",
        }
    },
]

config["executionRules"] = [
    {
        "labelName": "slackSent",
        "conditions": {
            "deliveryStatus": "SLACK_SENT"
        }
    },
    {
        "labelName": "slackSkippedNoWebhook",
        "conditions": {
            "deliveryStatus": "SLACK_SKIPPED_NO_WEBHOOK"
        }
    },
    {
        "labelName": "slackSkippedThreshold",
        "conditions": {
            "deliveryStatus": "SLACK_SKIPPED_THRESHOLD"
        }
    },
    {
        "labelName": "slackFailed",
        "conditions": {
            "deliveryStatus": "SLACK_FAILED"
        }
    },
]

output_labels = en.setdefault("outputFieldLabels", {})
output_labels.update({
    "deliveryStatus": "Delivery status",
    "deliveryChannel": "Delivery channel",
    "deliveryReason": "Delivery reason",
    "severityUsed": "Severity used",
    "portalIdUsed": "Portal ID used",
    "callbackId": "Callback ID",
})

execution_rule_labels = en.setdefault("executionRules", {})
execution_rule_labels.update({
    "slackSent": "Slack alert sent successfully.",
    "slackSkippedNoWebhook": "Slack alert skipped because no Slack webhook is configured.",
    "slackSkippedThreshold": "Slack alert skipped because severity {{ severityUsed }} is below the saved threshold.",
    "slackFailed": "Slack alert failed. Reason: {{ deliveryReason }}",
})

path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Updated workflow action config: {path}")