"""Plan -> capability policy: the single source of truth for tier gating.

Maps an OpsLens plan to (a) which detection category groups it includes and
(b) how many portals it may connect, per the published pricing tiers
(starter / professional / agency). Legacy "business" is treated as
agency-level; contact-sales "enterprise" as unlimited.

The policy FAILS OPEN: any unknown / empty / unmapped plan (active trials,
legacy rows, not-yet-billed installs) gets FULL capability. We would rather
over-deliver monitoring than silently suppress a real alert for a customer
who should receive it.

This module only DEFINES the policy. Enforcement (locking coverage
categories, capping portal connections) is wired in separately so the
policy can be reviewed and flipped in one place.
"""

from __future__ import annotations

# Detection category groups, keyed off the prefix the monitoring-coverage
# system uses for category names (e.g. "list_criteria_changed" -> "list").
DETECTION_GROUP_PROPERTY = "property"
DETECTION_GROUP_WORKFLOW = "workflow"
DETECTION_GROUP_LIST = "list"
DETECTION_GROUP_TEMPLATE = "template"
DETECTION_GROUP_OWNER = "owner"

ALL_DETECTION_GROUPS = frozenset(
    {
        DETECTION_GROUP_PROPERTY,
        DETECTION_GROUP_WORKFLOW,
        DETECTION_GROUP_LIST,
        DETECTION_GROUP_TEMPLATE,
        DETECTION_GROUP_OWNER,
    }
)

# Ordered so prefix matching is deterministic.
_GROUP_ORDER = (
    DETECTION_GROUP_PROPERTY,
    DETECTION_GROUP_WORKFLOW,
    DETECTION_GROUP_LIST,
    DETECTION_GROUP_TEMPLATE,
    DETECTION_GROUP_OWNER,
)

# Pricing-page matrix: Starter = property + workflow (7 categories);
# Professional = + list + template (13); Agency = + owner (15).
_PLAN_DETECTION_GROUPS = {
    "starter": frozenset({DETECTION_GROUP_PROPERTY, DETECTION_GROUP_WORKFLOW}),
    "professional": frozenset(
        {
            DETECTION_GROUP_PROPERTY,
            DETECTION_GROUP_WORKFLOW,
            DETECTION_GROUP_LIST,
            DETECTION_GROUP_TEMPLATE,
        }
    ),
    "agency": ALL_DETECTION_GROUPS,
    "business": ALL_DETECTION_GROUPS,  # legacy top tier == agency
    "enterprise": ALL_DETECTION_GROUPS,
}

# Pricing-page portal counts. None == unlimited / custom.
_PLAN_PORTAL_LIMITS = {
    "starter": 1,
    "professional": 3,
    "agency": 10,
    "business": 10,
    "enterprise": None,
}


def _normalize(plan: str | None) -> str:
    return str(plan or "").strip().lower()


def detection_group_for_category(category_name: str | None) -> str:
    """Map a monitoring category (e.g. 'list_criteria_changed') to its
    capability group ('list'). Returns '' for unrecognized inputs."""
    name = _normalize(category_name)
    for group in _GROUP_ORDER:
        if name == group or name.startswith(f"{group}_"):
            return group
    return ""


def allowed_detection_groups(plan: str | None) -> frozenset[str]:
    """Detection groups this plan includes. Unknown plans fail OPEN to all."""
    return _PLAN_DETECTION_GROUPS.get(_normalize(plan), ALL_DETECTION_GROUPS)


def plan_allows_detection_group(plan: str | None, group: str | None) -> bool:
    normalized_group = _normalize(group)
    if not normalized_group:
        return True
    return normalized_group in allowed_detection_groups(plan)


def plan_allows_category(plan: str | None, category_name: str | None) -> bool:
    """Whether a plan should receive alerts for a given detection category.
    Unrecognized categories fail OPEN (allowed)."""
    group = detection_group_for_category(category_name)
    if not group:
        return True
    return plan_allows_detection_group(plan, group)


def plan_portal_limit(plan: str | None) -> int | None:
    """Max connected portals for this plan, or None for unlimited.
    Unknown plans fail OPEN to unlimited."""
    return _PLAN_PORTAL_LIMITS.get(_normalize(plan), None)


def plan_portal_limit_reached(plan: str | None, current_count: int) -> bool:
    """True only when a finite limit is configured and already met/exceeded."""
    limit = plan_portal_limit(plan)
    if limit is None:
        return False
    return int(current_count) >= int(limit)
