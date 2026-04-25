# HubSpot Workflow Failure Detection — Follow-up Research

**Branch:** `v2-rebuild` · **Date:** 2026-04-24 · **Supersedes specific findings in `workflow-failure-detection-research.md` §5**

## Q1 — Can we get action-level execution logs via any API?

**No public API exposes per-execution workflow errors. Full stop.**

Exhaustive check of what exists:

- **Automation v4 (BETA)** — `/automation/v4/flows`, `/flows/{id}`, `/flows/batch/read`, `/flows/batch/update`. No `/executions`, `/errors`, `/logs`, or `/performance` sub-resource exists or is planned in any changelog entry from June 2024 through April 2026.
- **Legacy Workflows v3** (`/automation/v3/workflows`) — metadata only. Never exposed execution history.
- **Legacy Workflow Log API (v1)** — this *did* exist historically and was **disabled by HubSpot without a replacement**. Community threads (#321316, #543326) contain years of complaints from developers about this exact gap, still unresolved.
- **`/automation/v3/workflows/{id}/enrollments`** — this endpoint is current-enrollments only (records currently in the workflow). It does not return history, does not return errors, and is being deprecated in favor of list membership queries via `/crm/v3/lists/records/...`.
- **Internal endpoints behind the HubSpot UI "Action Logs" tab** — these back the UI view that shows per-action failure reasons. I found no reverse-engineering posts in the community or on GitHub that document them, and HubSpot's ToS forbid their use even if we did. Not a path we'd take.
- **Changelog sweep, June 2024 through April 2026** — batch read/update for v4 (Jan 2025), generic webhook subscriptions beta, date-based API versioning, IP Ranges API, App Uninstallation API. **Zero entries announcing a Workflow Errors or Execution History API.** Nothing on the `upcoming` tag either.

**One partial workaround exists.** HubSpot shipped a UI feature — in the workflow's Action Logs view, filter `Events = Errors`, then *Export records to list* — that writes the affected contact IDs to a CRM list. That list is readable via the public Lists API (`/crm/v3/lists/...`) and the CRM Exports API (`/crm/v3/exports/export/async`, requires `crm.export` scope, Super Admin to authorize, max 30 exports per rolling 24h). This gives us *which records hit errors*, not *why* or *which action*. It requires either customer setup or an automated flow that re-runs the export. Latency is minutes-to-hours, not seconds. Useful as enrichment, not as our primary detector.

## Q2 — What does `GET /automation/v4/flows/{flowId}` actually return?

Documented response shape (contact-based workflow):

```json
{
  "id": "12345678",
  "name": "New form submission workflow",
  "flowType": "WORKFLOW",
  "isEnabled": true,
  "revisionId": "7",
  "createdAt": "2024-06-07T17:27:08.101Z",
  "updatedAt": "2024-06-07T17:31:11.263Z",
  "startActionId": "1",
  "nextAvailableActionId": "3",
  "enrollmentCriteria": {
    "shouldReEnroll": false,
    "listFilterBranches": [],
    "reEnrollmentTriggersFilterBranches": [],
    "eventFilterBranches": [],
    "unEnrollmentType": "NEVER_UNENROLL",
    "type": "LIST_BASED"
  },
  "timeWindows": [],
  "blockedDates": [],
  "scheduling": {},
  "actions": [
    {
      "type": "SINGLE_CONNECTION",
      "actionId": "1",
      "actionTypeVersion": 0,
      "actionTypeId": "0-13",
      "connection": { "edgeType": "STANDARD", "nextActionId": "2" },
      "fields": { "property_name": "lifecyclestage", "value": "lead" }
    }
  ]
}
```

**Fields that DO NOT exist in this response:** `hasErrors`, `needsReview`, `lastErrorTimestamp`, `errorCount`, `executionStats`, `lastRunAt`, `healthStatus`, `performanceSummary`, or anything equivalent. I checked the beta changelog entries and the full documented schema — there is no execution-health telemetry anywhere on the workflow object.

What polling this every 2 minutes CAN detect:

1. **Workflow disabled** — `isEnabled` flips `true → false`. HubSpot auto-disables workflows under a narrow set of conditions (trigger property deleted, plan downgrade, repeated critical failures). A human disabling a workflow also shows here.
2. **Workflow edited** — `revisionId` increments and/or `updatedAt` advances. We can diff the `actions` array to identify what changed (step added/removed, field value changed, new branch added).
3. **Enrollment criteria changed** — `enrollmentCriteria` differs. Important because a broken criteria is a common way workflows silently stop enrolling records.
4. **Action references a now-invalid property** — by joining `actions[*].fields` against the Properties API, we can flag actions that reference a property that has been deleted or renamed. This is a pre-emptive signal, not reactive.
5. **New workflow appeared / existing workflow deleted** — by diffing the list response.

What polling this CANNOT detect: any runtime failure of any kind. A workflow with `isEnabled: true` and stable `revisionId` can be silently failing 100% of its enrollments and this endpoint tells us nothing.

## Q3 — Honest assessment and repositioning options

**The gap is real and it's a dealbreaker for the current positioning.** "Detect any workflow error within 5 minutes" against a portal of 50 workflows is not achievable via public API today for the per-execution/per-action case. The only sub-5-minute path to individual action failures is the custom workflow action, which we've rejected because it requires customer setup. HubSpot has had this gap for years, has actively removed prior capability (v1 Workflow Log API), and has announced nothing to close it. We cannot wait them out.

That said, there IS a smaller, credible product in what IS accessible. Two honest pivots, in order of how much of the original vision they preserve:

**Option A — "HubSpot Workflow Health Monitor" (recommended).** Zero-config. Poll `/automation/v4/flows` every 2 minutes plus the Audit Log API (Enterprise) every 15 minutes. Detect and alert on: workflow auto-disabled, workflow manually disabled, workflow edited (with diff), enrollment criteria changed, action references a deleted property, new unreviewed workflow created. This is ~70% of what customers actually call "a broken workflow" in support tickets, based on the community threads. It will not catch "Send email action failed for contact X due to graymail suppression" — we need to tell customers that explicitly and not pretend otherwise.

**Option B — "HubSpot Change Intelligence." Narrower, higher-precision.** Same polling, but frame the product as pre-emptive: we flag the property/schema changes and workflow edits *that are likely to cause failures* before they cascade. Less overlap with HubSpot's own in-app alerts, stronger wedge for RevOps teams. Smaller TAM though.

**Option A+optional-C:** Ship A as the zero-config default, and offer the custom workflow action as an opt-in "Deep Coverage" add-on for customers who want per-execution detection and are willing to do the 10-minute setup. This gets us to honest marketing ("zero-config catches workflow-level problems; add our workflow action to catch action-level failures") without depending on setup for the core product to work.

**My recommendation: ship Option A + optional-C.** Rewrite the landing page to promise "workflow-level and configuration failure detection in under 5 minutes, zero setup" and surface per-execution detection as a Pro feature. The alternative — pretending we can do what we can't — burns trust the first time a customer's Send Email action silently fails and we don't alert.

---

**Sources:** HubSpot Workflows v4 API guide (BETA), Workflows v4 changelog tag, legacy `/automation/v3/workflows` reference, legacy Workflow Log API community threads (#321316, #543326, #1093895), CRM Exports API guide, CRM Lists API, Account Activity API guide, Spring 2026 Spotlight, December 2025 Developer Rollup, HubSpot KB on workflow action logs and troubleshooting.
