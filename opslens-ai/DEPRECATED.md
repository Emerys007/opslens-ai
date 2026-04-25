# OpsLens — Deprecated for v2

This file tracks features that were demoted or removed in the v2 scope reduction on branch `v2-rebuild` (April 2026). The v2 product is repositioning around alerting consultants when client portal changes are likely to break workflows. Anything that does not support that positioning has been cut from the user-facing UI.

## Removed in this pass

### Contact Risk card (CRM record tab)
- **Why:** The v2 product does not surface per-contact risk scores in the CRM UI. Alerts are delivered via Slack/email on workflow-level events, not on individual records.
- **UI state:** `opslens-ai/src/app/cards/NewCard.tsx` and `opslens-ai/src/app/cards/card-hsmeta.json` are stubbed to disable registration. These two files must be physically removed (`rm`) before `hs project validate` will pass — the agent that performed this pass did not have shell access.
- **Backend state:** `backend/app/api/v1/routes/record_risk.py` is untouched and still mounted in `backend/app/api/v1/router.py`.

### Custom workflow action "Send OpsLens alert" (v1 contact-risk action)
- **Why:** The v1 action was tied to the per-contact risk model and doesn't fit the v2 workflow-change-alert positioning. A new "Deep Coverage" workflow action is planned as an opt-in v2 add-on and will be shipped separately.
- **UI state:** `opslens-ai/src/app/workflow-actions/workflow-actions-hsmeta.json` is stubbed to disable registration. File must be physically removed before `hs project validate` will pass. `opslens-ai/src/app/workflow-actions/HUBSPOT_WORKFLOW_ACTIONS.md` is left in place as historical documentation.
- **Backend state:** `backend/app/api/v1/routes/workflow_actions.py` is intact on disk. It is no longer mounted in `backend/app/api/v1/router.py` — both the import and the `include_router` call are commented out with a marker explaining the deactivation.

### Webhook feed panel on App Home
- **Why:** The current Home is being rebuilt in week 3. The webhook feed panel specifically is not coming back — the v2 Home surfaces workflow health, not raw webhook traffic.
- **UI state:** The "Webhook activity" Tile was removed from `opslens-ai/src/app/pages/Home.tsx`. Data-loading plumbing (state, fetch helpers, debug fields) is intentionally left untouched because the file is being rewritten imminently.

## Demoted (kept in source, not linked from UI)

### Native contact sync, contact segments, critical-segment export
- **Why:** These were v1 infrastructure for syncing OpsLens alert context into native HubSpot contact properties and list segments. v2 doesn't use native contact properties as the alert surface, so this plumbing is not on the v2 critical path. The bootstrap scripts are historical and may inform later work.
- **Files kept for reference (do NOT delete):**
  - `opslens-ai/opslens_step23_native_contact_properties.py`
  - `opslens-ai/opslens_step23_create_hubspot_contact_properties.py`
  - `opslens-ai/opslens_step23_fix_native_contact_sync.py`
  - `opslens-ai/opslens_step24_organize_native_contact_properties.py`
  - `opslens-ai/opslens_step25_create_contact_segments.py`
  - `opslens-ai/opslens_step26_export_critical_segment.py`
- **Service state:** `backend/app/services/hubspot_native_contact_sync.py` is unchanged. It is still referenced from `backend/app/api/v1/routes/workflow_actions.py`, which is no longer mounted but remains on disk.

## Not touched in this pass

### Stripe checkout on install
- Auto-trial is being handled as a separate week 2 task with its own tests. No changes made here.

## Manual follow-up required

The agent that performed the scope reduction had no shell and no git access. The following steps must be completed manually:

```
# From the repo root:
rm "opslens-ai/src/app/cards/NewCard.tsx"
rm "opslens-ai/src/app/cards/card-hsmeta.json"
rm "opslens-ai/src/app/workflow-actions/workflow-actions-hsmeta.json"

# Then validate:
cd opslens-ai
hs project validate

# Then commit the four changes listed in the task spec on v2-rebuild and push.
```
