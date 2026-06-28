"""Deterministic 'how to fix it' guidance per detection type.

Grounded in what HubSpot actually permits as of 2026:
  - Archived properties are restorable from Settings -> Properties -> Archived
    for 90 days, after which they are permanently purged.
  - A property *label* rename does not change the internal name automations
    reference, so workflows are unaffected.
  - HubSpot sends no notification when a workflow is disabled/deleted or when
    an owner is deactivated; deactivated owners are silently skipped in
    routing, leaving records unassigned.

This is always-present, read-only guidance (no API calls, no AI key needed).
It complements the AI ``recommended_action`` with a reliable, HubSpot-correct
playbook. The ``restorable`` flag marks cases where a straightforward
one-click undo is realistic — those are the candidates for the Phase B
one-click fix buttons.
"""

from __future__ import annotations

from app.models.alert import (
    SOURCE_EVENT_LIST_ARCHIVED,
    SOURCE_EVENT_LIST_CRITERIA_CHANGED,
    SOURCE_EVENT_LIST_DELETED,
    SOURCE_EVENT_OWNER_DEACTIVATED,
    SOURCE_EVENT_OWNER_DELETED,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_EVENT_PROPERTY_DELETED,
    SOURCE_EVENT_PROPERTY_RENAMED,
    SOURCE_EVENT_PROPERTY_TYPE_CHANGED,
    SOURCE_EVENT_TEMPLATE_ARCHIVED,
    SOURCE_EVENT_TEMPLATE_DELETED,
    SOURCE_EVENT_TEMPLATE_EDITED,
    SOURCE_EVENT_WORKFLOW_DELETED,
    SOURCE_EVENT_WORKFLOW_DISABLED,
    SOURCE_EVENT_WORKFLOW_EDITED,
)

_DEFAULT_GUIDANCE = {
    "summary": "Review the change in HubSpot and confirm it was intended.",
    "steps": ["Open the affected asset in HubSpot and verify the change is correct."],
    "restorable": False,
}

_GUIDANCE: dict[str, dict] = {
    SOURCE_EVENT_PROPERTY_ARCHIVED: {
        "summary": "If you still need this property, restore it before it's purged.",
        "steps": [
            "Open Settings -> Properties and select the Archived tab.",
            "Find the property and click Restore (available for 90 days after archiving).",
            "Re-add it to any view, form, or report it was removed from — those references are not restored automatically.",
        ],
        "restorable": True,
    },
    SOURCE_EVENT_PROPERTY_DELETED: {
        "summary": "Permanently deleted properties can't be restored — recreate and re-wire if it's still needed.",
        "steps": [
            "Confirm it's truly gone (archived properties are purged 90 days after archiving).",
            "If needed, recreate it with the same internal name and field type.",
            "Update every workflow, list, form, and report that referenced it.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_PROPERTY_TYPE_CHANGED: {
        "summary": "A field-type change can silently break filters, calculations, and reports — verify the dependents.",
        "steps": [
            "Review the workflows in the blast radius for filters or branches that assumed the old type.",
            "Check any calculated or rollup properties that reference it.",
            "Confirm reports and lists filtered on this property still return the right records.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_PROPERTY_RENAMED: {
        "summary": "Label-only change — the internal name automations use is unchanged, so workflows are unaffected.",
        "steps": [
            "No action needed for automation; the internal name did not change.",
            "Update saved views or report labels only if the new name confuses your team.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_WORKFLOW_DISABLED: {
        "summary": "If turning this workflow off was unintended, re-enable it — HubSpot notified no one.",
        "steps": [
            "Open Automation -> Workflows and find this workflow.",
            "Check the revision history for who turned it off and whether it was deliberate.",
            "If it should be running, toggle it back on.",
        ],
        "restorable": True,
    },
    SOURCE_EVENT_WORKFLOW_EDITED: {
        "summary": "Review the edit against the prior version to confirm enrollment and actions still work.",
        "steps": [
            "Open the workflow and use its revision history (Professional+) to compare versions.",
            "Confirm enrollment triggers and actions still behave as intended.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_WORKFLOW_DELETED: {
        "summary": "Confirm this deletion was intended; restore or rebuild if it was revenue-critical.",
        "steps": [
            "In Automation -> Workflows, check for a recently-deleted / restore option within HubSpot's window.",
            "If it can't be restored, rebuild it and re-enroll the affected records.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_LIST_ARCHIVED: {
        "summary": "Restore the list so workflows that enroll from it resume.",
        "steps": [
            "Open Contacts -> Lists and find the recently-deleted / archived view.",
            "Restore the list if it's within HubSpot's restore window.",
            "Confirm workflows that use it as an enrollment trigger are active again.",
        ],
        "restorable": True,
    },
    SOURCE_EVENT_LIST_DELETED: {
        "summary": "Workflows enrolling from this list will stop — restore it or repoint them.",
        "steps": [
            "Check Contacts -> Lists for a restore option within HubSpot's window.",
            "If unrecoverable, recreate the list or repoint dependent workflows to another list.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_LIST_CRITERIA_CHANGED: {
        "summary": "Membership may have shifted silently — verify the new criteria match intent.",
        "steps": [
            "Open the list and review its filters against what enrollment and segmentation expect.",
            "Check workflows that enroll from it for unexpected enrollment changes.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_TEMPLATE_ARCHIVED: {
        "summary": "Restore the template so workflows that send it don't fail.",
        "steps": [
            "Find the archived email/template in HubSpot and restore it.",
            "Confirm workflows that send it can find it again.",
        ],
        "restorable": True,
    },
    SOURCE_EVENT_TEMPLATE_DELETED: {
        "summary": "Workflows that send this template will error — restore or replace it.",
        "steps": [
            "Check for a restore option within HubSpot's window.",
            "If unrecoverable, recreate the email and update the send actions in dependent workflows.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_TEMPLATE_EDITED: {
        "summary": "Content or personalization changes affect every workflow that sends this template — review the edit.",
        "steps": [
            "Open the template and confirm the change is intended.",
            "Check personalization tokens still resolve; broken tokens send blank or default values.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_OWNER_DEACTIVATED: {
        "summary": "Reassign anything pointing at this user — HubSpot silently skips deactivated owners, leaving leads unassigned.",
        "steps": [
            "Use the blast radius to find workflows that rotate to or filter on this owner.",
            "Edit those actions and filters to an active owner or rotation.",
            "Reassign open records still owned by the deactivated user.",
        ],
        "restorable": False,
    },
    SOURCE_EVENT_OWNER_DELETED: {
        "summary": "Records and routing referencing this owner are now orphaned — reassign them.",
        "steps": [
            "Reassign open records previously owned by this user.",
            "Update workflow rotation/assignment actions and filters to an active owner.",
        ],
        "restorable": False,
    },
}


def fix_guidance_for(source_event_type: str | None) -> dict:
    """Return grounded remediation guidance for a detection type.

    Always returns a dict with summary/steps/restorable; unknown types get a
    safe generic fallback. The returned dict is a fresh copy so callers can
    mutate it without affecting the table.
    """
    guidance = _GUIDANCE.get(str(source_event_type or "").strip(), _DEFAULT_GUIDANCE)
    return {
        "summary": guidance["summary"],
        "steps": list(guidance["steps"]),
        "restorable": bool(guidance["restorable"]),
    }
