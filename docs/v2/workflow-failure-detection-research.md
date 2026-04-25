# HubSpot Workflow Failure Detection — Research for OpsLens v2

**Branch:** `v2-rebuild` · **Date:** 2026-04-24 · **Status:** research only, no code changes

The v2 goal is to raise an alert within 5 minutes of a workflow error in a connected HubSpot portal. This document evaluates the three public mechanisms HubSpot exposes and recommends a path forward.

---

## 1. Webhooks v3 — is there a "workflow error" subscription?

**No.** HubSpot's Webhooks API (guide version `2026-03`) does not publish a subscription type for workflow failures, failed actions, enrollment errors, or any automation health signal.

The available subscription types are all CRM-object lifecycle events — `contact.creation`, `contact.propertyChange`, `deal.propertyChange`, `ticket.*`, plus the recently added `*.merge`, `*.restore`, and `*.associationChange` events. None of these fire on workflow execution failure. The only workflow-adjacent webhook capability is the **POST webhook action** that a customer manually drops into their own workflow — that's an outbound HTTP call the customer configures, not a subscription we can subscribe to from our app.

**Scopes:** N/A — no subscription to request.

## 2. Automation v4 API — can we poll for errors?

**Partially.** The Automation v4 API (still flagged BETA as of Spring 2026) exposes workflow metadata but **not per-execution error state**.

- `GET /automation/v4/flows` — lists all workflows in the portal. Returns `id`, `isEnabled`, `objectTypeId`, `revisionId`. Useful for detecting a workflow that's been *disabled by HubSpot* (the clearest workflow-level failure signal exposed publicly), and for detecting revision drift.
- `GET /automation/v4/flows/{flowId}` — returns the full workflow definition including action configuration. Can be diffed to detect missing-property or broken-reference errors in setup, but does **not** return execution history or per-action failure counts.
- There is no `/flows/{id}/executions`, `/flows/{id}/errors`, or `/flows/{id}/performance` endpoint in the public v4 beta. HubSpot's in-app "Performance" tab surfaces enrollment and action-error counts but is not exposed via public API.

**Scope:** `automation` (Professional+ tier portal required).

**Rate limit:** Standard OAuth app limit — **110 requests per 10 seconds per installed portal**, plus the subscription-tier daily limit (250k Pro, 1M Enterprise).

**Example response — `GET /automation/v4/flows`:**

```json
{
  "results": [
    {
      "id": "567890123",
      "isEnabled": true,
      "objectTypeId": "0-1",
      "revisionId": "42",
      "createdAt": "2026-03-14T10:12:00Z",
      "updatedAt": "2026-04-20T08:44:10Z"
    }
  ],
  "paging": { "next": { "after": "MjU=" } }
}
```

## 3. Audit Log API — viable Enterprise fallback?

**Partially viable, Enterprise-only.** `GET /account-info/v3/activity/audit-logs` records user actions (including workflow edits, enables/disables, and some automation-related changes), but it is **not a workflow-execution error stream**. It will show *"user X disabled workflow Y"* and similar events, which is a useful secondary signal, but it will not show *"action N in workflow Y failed to run for contact Z at 10:02"*.

**Scope:** `account-info.security.read`.

**Caveats:** Enterprise-tier portals only. The API is cursor-paginated at 100 records per page and is known to 500 under high-volume traversal. Reasonable as a **secondary confirmation signal for Enterprise customers**, not as our primary detection.

## 4. Enrollment failures vs. action failures vs. workflow-level errors

These are three distinct concepts in HubSpot and we should model them separately:

**Enrollment failure** — a record met the trigger criteria but did not enter the workflow (suppression list, re-enrollment disabled, missing property on a dependency). Surfaced per-record in the UI's "Enrollment history"; no public API.

**Action failure** — a record was enrolled, an individual step failed at runtime (external API 5xx, missing required property at step time, permission revoked on a send-email action, custom code action timeout). Surfaced in the record's workflow history and the workflow's Performance tab; no public API.

**Workflow-level error** — the workflow itself is broken or has been auto-disabled (trigger property deleted, required field now empty in configuration, HubSpot auto-paused for repeated failures, plan downgrade). Partially surfaced via `GET /automation/v4/flows` (`isEnabled` flips to `false`) and via the Audit Log on Enterprise.

OpsLens v2 should expose all three as distinct alert categories. Only the third is currently detectable via public API — the first two require either a customer-side opt-in (see §5) or scraping private endpoints, which we won't do.

## 5. Recommendation

**Primary mechanism: a hybrid of (a) a published custom workflow action + (b) polling `/automation/v4/flows`.**

- **(a) Custom workflow action "Report Error to OpsLens"** — we ship this as part of the app and document a one-time setup where the customer adds it to the error branch of each critical workflow (or to a single global error-branch template). When the action fires, we get a direct callback with the flow id, contact id, and step metadata. This is the only way to catch per-action and per-enrollment failures within 5 minutes today, because HubSpot does not broadcast them.
- **(b) `GET /automation/v4/flows` poll every 2 minutes** — detects the workflow-level case (auto-disabled, revision churn) with sub-5-minute latency. Cheap and universal.

**Tradeoff:** Freshness is excellent (custom action is synchronous; poll is 2-min). Rate-limit cost is trivial (see §6). Scope cost is one new OAuth scope (`automation`). The weakness is that the custom action requires customer setup — we need onboarding tooling and clear docs, because customers who don't wire it up will only get workflow-level alerts, not action-level alerts.

**Fallback: Audit Log API for Enterprise portals.** If the `/automation/v4/flows` poll misses a disable event (e.g. HubSpot outage), the audit log is the confirmatory source. Gated behind `account-info.security.read` and Enterprise tier, so it's a nice-to-have, not a primary.

## 6. Per-portal API volume estimate

Assume 50 active workflows, polled on the recommended schedule:

- List poll every 2 min: `30 req/hour` = `720 req/day`.
- On each detected revision/enablement change, one detail fetch: worst-case 50 changes/day = `50 req/day`.
- Audit log poll every 15 min (Enterprise only): `96 req/day`.
- Custom workflow action callbacks: inbound, no quota cost.

**Total: ≈ 770–870 req/day per portal.**

Against the standard OAuth limit of **110 req / 10s** and the 250k/day (Pro) or 1M/day (Enterprise) daily cap, we're at roughly **0.3%** of daily quota and peak burst of ~1 req/sec — comfortably within standard limits with no need for the API Limit Increase pack.

## 7. New OAuth scopes for `src/app/app-hsmeta.json`

Current `requiredScopes`: `oauth`, `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.schemas.contacts.write`, `tickets`.

**Required for v2:**

- `automation` — needed for `GET /automation/v4/flows` polling and for registering the custom workflow action through the developer platform. This is the core scope for the v2 feature.

**Nice to have (move to `optionalScopes` or `conditionallyRequiredScopes`):**

- `account-info.security.read` — unlocks the Audit Log fallback on Enterprise portals. Should be optional so we don't block installs on non-Enterprise tiers where the scope grant path differs.
- `crm.objects.companies.read` — needed to enrich action-failure alerts with the owning company record for B2B-centric portals. Pure enrichment, not required for detection.
- `crm.objects.deals.read` — same rationale for deal-object workflows.

No existing scope should be removed.

---

**Sources consulted:** HubSpot Webhooks API guide (2026-03), Automation v4 API guide (BETA), Account Activity API (Audit Log v3), HubSpot Scopes reference, HubSpot API usage guidelines, Spring 2026 Spotlight changelog, HubSpot knowledge base articles on workflow enrollment and troubleshooting.
