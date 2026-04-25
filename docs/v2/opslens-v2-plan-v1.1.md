# OpsLens v2 — the plan (v1.1)

**Version**: 1.1, April 24 2026
**Owner**: Joël Katako
**Working with**: Claude (strategy, content, Cowork task prompts) and Cowork (implementation)
**Supersedes**: opslens-v2-plan.md v1.0

**What changed in v1.1**: positioning sharpened from "change intelligence" to "workflow-impacting change alerting" after the week 1 research found that HubSpot does not expose per-execution workflow errors via public API. The product is no longer pretending to catch runtime errors it cannot see.

---

## 1. The positioning, once

**What OpsLens is, in one sentence**: OpsLens alerts HubSpot consultants when client portal changes are likely to break workflows.

**Who it's for**: HubSpot consultants, agencies, and Solutions Partners who manage multiple client portals and cannot manually watch every workflow on every portal every day. Also fits fractional HubSpot admins managing a single complex portal.

**Why they'll buy it**: the most expensive moments in a consultant's week are when something quietly broke in a client's portal and the client found it before they did. OpsLens flips that — they hear about the breakage from OpsLens, fix it, and the client never knows there was a problem.

**Why it wins against WorkflowGuard, Platform Audit Pro, and Portal Audit System**: those products are reactive (after-the-fact audit, after-the-fact rollback, point-in-time scans). OpsLens is forward-looking — it watches for changes and tells you which workflows are about to break because of them. Different verb: *audit* vs. *alert*.

**What we do not say**: "change intelligence," "operational assurance," "AI-powered insights," any percentage claim about coverage. We use specific language: "this property got archived, here are the 3 workflows that will fail," "this workflow was disabled at 3:42 PM, here's why."

**What we are honest about**: OpsLens detects workflow-level and configuration-level breakage. It does not detect individual action runtime failures (a Send Email step that fails for one contact due to graymail suppression). HubSpot does not expose that data via public API. Customers who need per-execution coverage can opt into the Deep Coverage workflow action — but that is not the wedge, it's an add-on.

---

## 2. What OpsLens v2 actually does

### v2 core feature: workflow-impacting change alerting
OpsLens continuously polls every workflow in a connected HubSpot portal, maintains a dependency map of which properties / lists / templates each workflow uses, and watches for portal changes that will break those workflows. When a breaking change is detected, OpsLens opens an alert within minutes — routed to the consultant's Slack and to a ticket in the OpsLens Alerts pipeline inside HubSpot — with:

- which change happened (property archived, workflow disabled, workflow edited, etc.)
- which workflows are impacted by it
- which step of which workflow will fail and why
- what the consultant should do next
- a direct link to the HubSpot workflow editor at the affected step

One alert per (change, impacted workflow) pair, deduplicated. Repeated changes to the same dependency don't re-spam.

This is the hero feature. It solves a real consultant pain. It is what the LinkedIn post is about. It is what the 30-second demo shows.

### What v2 actually detects (the honest list)

- **Workflow disabled** — `isEnabled` flips false. Either auto-disabled by HubSpot or manually disabled by a user.
- **Workflow edited** — `revisionId` increments. Diffed against the prior version: which step changed, which field changed, which branch was added or removed.
- **Enrollment criteria changed** — the trigger for the workflow has changed; flag because this often silently changes who gets enrolled.
- **New workflow created** — flagged as "needs review" so the consultant knows the client team built something new.
- **Workflow deleted** — flagged because deletion is rare and high-stakes.
- **Property archived, renamed, or type-changed** AND **referenced by an active workflow** — pre-emptive alert: "This change will break workflow X on next run." Property changes that aren't referenced by any workflow get a notice, not an alert.
- **Email template archived or deleted** AND **referenced by an active workflow's Send Email action** — same pre-emptive logic.
- **List archived or deleted** AND **used as enrollment criteria** — same.

### What v2 does not do, and we say so plainly

- Per-execution action failures (a step failed for contact X). Optional Deep Coverage workflow action covers this for customers who add it.
- Enrollment failures for individual records.
- General audit trail across non-workflow assets (no broad "who changed what" log — that's WorkflowGuard's territory).

### v2 supporting features

- **OpsLens Alerts ticket pipeline** — the existing pipeline from v1 stays, becomes the canonical inbox for all alerts. Each alert is one ticket. New / Investigating / Resolved stages.
- **App Home** — rebuilt around two questions: *"what changed in my portals in the last 24 hours?"* and *"which workflows are at risk right now?"* Live list, click-through to the relevant HubSpot screen. No charts, no summary stats, no webhook feed.
- **Settings page** — Slack webhook, alert severity threshold, auto-resolve window. Nothing else.
- **OAuth install + 14-day free trial** — every new install gets 14 days free, no credit card, auto-activated. No reviewer-special path.
- **Optional Deep Coverage workflow action** — ships as a published custom workflow action in the app schema. Customers who want per-execution coverage on critical workflows wire it into the error branch. Not required, not the wedge, not on the homepage. Available, opt-in.

### What gets cut, moved, or demoted from v1

| Current v1 feature | Fate in v2 |
|---|---|
| Contact-record Risk card | **Cut from UI**. Code stays in repo, not referenced. |
| Existing custom workflow action "Run intelligence check" | **Cut entirely**. Different from Deep Coverage — the v1 one was contact-risk-scoring, doesn't fit v2. |
| Native contact property sync, contact segments, critical-segment export | **Cut from user-facing story**. |
| Webhook feed on App Home | **Cut**. Goes into the alerting engine instead of being displayed raw. |
| Daily/weekly digest | **Deferred to v3**. |
| Stripe checkout flow for new installs | **Replaced** with auto-trial. Stripe checkout only appears at trial-end. |

### What's genuinely new in v2

- **Dependency mapping engine** — for every active workflow, parse `actions[]` and `enrollmentCriteria`, extract every property / list / email template / owner reference, build and maintain a reverse index. *This is the core of the product. Without it, "workflow-impacting" is meaningless.*
- **Workflow polling and diffing** — `GET /automation/v4/flows` every 2 min per portal; on revision change, fetch full definition and diff against last known.
- **Property/list/template change watcher** — separate poller, joined against the dependency map.
- **Alert correlation engine** — one breaking change → one alert per impacted workflow, deduplicated.
- **Slack webhook sender** — meaningful payload format (sample in appendix A).
- **"Plain English consequence" layer** — small LLM call per alert to explain in one sentence what the change means and what to do. Use Haiku, cache by change signature. ($0.02/alert ceiling.)
- **Rebuilt App Home, rebuilt Settings.**
- **Auto-trial on install.**
- **Optional Deep Coverage workflow action** (published in app schema, customer wires in).

---

## 3. Schedule: 8 weeks, 10 hours/week of Joël's time

### Week 1 — foundation and research (April 24 – May 1) — IN PROGRESS
**Outcome**: detection mechanism decided, old UI cleaned out.

- ✅ Track A: research spike on HubSpot workflow APIs. **Done.** Findings: per-execution errors not exposed; pivot positioning to workflow-impacting changes.
- ⏳ Track B: scope reduction. Remove contact Risk card, existing custom workflow action, webhook feed, segment code paths.
- ⏳ Claude task: draft auto-trial implementation spec for week 2.
- ⏳ Joël: pick test portal with Operations Hub access and 3+ active workflows.

### Week 2 — dependency mapping + alerting backend (May 2 – 8)
**Outcome**: backend can detect a workflow-impacting change, identify affected workflows, deduplicate, open ticket and Slack alert.

- Cowork: implement dependency-mapping engine. Walk every workflow's `actions[]` and `enrollmentCriteria`, extract references, build reverse index, persist.
- Cowork: implement workflow polling and diffing. `GET /automation/v4/flows` every 2 min; on `revisionId` change, fetch detail and diff.
- Cowork: implement property change watcher. Subscribe to property-archive events via webhooks v3 if available; otherwise poll Properties API.
- Cowork: implement deduplication. Key is (portal_id, change_signature, impacted_workflow_id).
- Cowork: implement Slack webhook sender + ticket creation.
- Cowork: implement auto-trial on install.
- Joël: test by intentionally archiving a property used by a workflow on the test portal. Confirm alert fires within 5 min in Slack and ticket pipeline.

This week is the one that matters most for technical risk. Dependency mapping has to work. Allocate Joël's time toward reviewing the mapping output before approving the rest.

### Week 3 — UI rebuild and first pilot (May 9 – 15)
**Outcome**: v2 is in production, one real consultant is piloting it on one client portal.

- Cowork: rebuild App Home around "what changed / what's at risk" view.
- Cowork: rebuild Settings.
- Cowork: integrate plain-English consequence LLM layer.
- Cowork: ship optional Deep Coverage workflow action in app schema (does not block alerts, just enables per-execution coverage when wired in).
- Joël: post LinkedIn pilot offer (draft in appendix C). Recruit 5, expect 1-3 to actually install.
- Joël: install OpsLens with first pilot in a 20-min Zoom. White-glove. Confirm alerts working on their real portal.

### Week 4 — first pilot feedback, fixes, recruit 2 and 3 (May 16 – 22)
**Outcome**: pilot 1 has used OpsLens for a week. Pilots 2 and 3 are installing.

- Joël: 15-min Zoom check-in with pilot 1. What worked, what's confusing, what's missing.
- Claude + Joël: triage feedback into "fix this week," "fix before listing," "v3."
- Cowork: implement "fix this week" items.
- Joël: onboard pilots 2 and 3.

### Week 5 — broaden detection and capture metrics (May 23 – 29)
**Outcome**: more change types detected. Three pilots running. We know what we're catching.

- Cowork: add list-change and email-template-change detection to dependency map.
- Cowork: add Audit Log integration for Enterprise pilots (fallback signal).
- Cowork: ship a simple internal metrics page — for each pilot, count of alerts raised, count confirmed useful by the consultant, count dismissed as noise.
- Joël: weekly check-ins with all 3 pilots. Second LinkedIn post.

### Week 6 — polish, icon, public site, docs (May 30 – June 5)
**Outcome**: public surface ready for Marketplace submission, contingent on pilot signal.

- Cowork: apply final 800×800 icon (PNG from SVG, or designer's version).
- Cowork: rewrite `public-site/opslens/` around new positioning. Copy from Claude.
- Cowork: rewrite `public-site/opslens/setup/` around v2 features.
- Claude: rewrite reviewer test instructions for v2.

### Decision point: end of week 6
We look at the metrics page from week 5 and 3 weeks of pilot feedback:
- **How many real breaking changes did OpsLens detect across 3 portals?** This is the headline metric.
- **What was the false-positive rate?** Alerts the consultant marked as "not useful."
- **What was missed?** Things that broke that OpsLens didn't catch.
- **Did any pilot say "I'd pay $X for this"?** What was X?

Three paths:
- **Strong signal** (real catches, low false-positive, paying intent) → week 7 is Marketplace submission.
- **Mixed signal** → week 7-8 is one more iteration cycle, Marketplace pushed to week 10.
- **Weak signal** → pause, reassess, possibly pivot wedge again. Not failure — exactly why we did pilots.

### Week 7 — Marketplace submission (June 6 – 12)
**Outcome (assuming strong signal)**: submitted for HubSpot Marketplace review.

### Week 8 — Marketplace review period + v3 prep (June 13 – 19)
**Outcome**: HubSpot reviewing. v3 roadmap drafted. First marketing cycle prepped.

---

## 4. Distribution plan (parallel to the build)

(Unchanged from v1.0 — three LinkedIn posts at weeks 3, 5, 7; HubSpot community engagement; FR-language post at week 5 or 6 as bilingual differentiator.)

The week 3 post is in appendix C, updated for the new positioning.

---

## 5. Roles

(Unchanged from v1.0. Claude does writing and product thinking. Cowork does code. Joël does posting, calls, money decisions, breaking-test-workflows, and reviewer comms.)

---

## 6. Success criteria

**By end of week 4**: 1 pilot installed, first week of usage caught at least 1 real breaking change confirmed useful by the consultant.

**By end of week 6**: 3 pilots running. Across 3 portals × 3 weeks, OpsLens detected at least 5 real breaking changes the consultant says would have taken >30 min to find manually. False-positive rate under 30%.

**By end of week 8**: Marketplace submission filed. At least 1 pilot has named a price they'd pay.

**By end of week 12**: Marketplace approved. First paying customer.

If by end of week 6 we have 0 confirmed useful detections, we stop and reassess before submitting.

---

## 7. What I'm not including, and why

(Unchanged. No coverage percentages. No SOC 2. No detailed architecture diagram. No deep competitor analysis beyond WorkflowGuard's docs.)

---

## Appendix A — Slack alert payload (draft, will iterate with pilot feedback)

```
🔴 Workflow at risk: "New Contact Routing"
Portal: Acme Client (1234567)
Trigger: Property "sales_rep_email" was archived 4 minutes ago by Austin Courreges
Impact: Workflow "New Contact Routing" — step 3 (Send email) references this property in the personalization token. Next enrollment will fail.
Recommended action: Update the email template to remove the reference, or restore the property from the property history.
Open in HubSpot: [link to workflow step 3]
First detected: 4 min ago · Severity: High
```

## Appendix B — "Plain English consequence" LLM prompt (draft)

```
You are OpsLens, a HubSpot operational assistant.
Input: a structured description of a portal change and a list of workflows it impacts.
Output: one sentence, max 25 words, explaining what's about to break and what to do, in language a HubSpot consultant understands.
Do not speculate beyond the input. Do not say "it appears" or "may have" — be direct or say you don't know.
Use property names and workflow names verbatim from the input.
```

Cost: under $0.02/alert. Haiku. Cache by change signature.

## Appendix C — Week 3 LinkedIn pilot offer (updated for v2.1 positioning)

```
I built something for HubSpot consultants.

You know that thing where a client admin archives a property, or edits a
workflow on a Friday afternoon, or adds a new automation you didn't know
about — and you find out three weeks later when something's already broken?

OpsLens watches for those changes across your client portals and tells you,
in Slack, the moment one is likely to break a workflow. Before the client
notices anything is wrong.

I'm looking for 5 HubSpot consultants to pilot it on one client portal, free,
for 30 days. No credit card. I'll install it with you in a 20-min call.

If you manage 3+ HubSpot client portals and you've ever been surprised by a
silent change you didn't catch, comment "pilot" and I'll DM you.

(FR: Si vous gérez plusieurs portails HubSpot clients et vous avez déjà
découvert qu'un changement silencieux a cassé un workflow, écrivez "pilote".)
```

---

## How we work this plan

(Unchanged. Monday check-ins with Claude in chat. Cowork prompts come from Claude. Friday status notes. Plan updated as we learn.)

The plan is not sacred. The outcome is: a product that catches real breaking changes for real consultants, marketed honestly, that people want to pay for.
