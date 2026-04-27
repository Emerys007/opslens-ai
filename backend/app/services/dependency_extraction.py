"""Pure functions that walk a HubSpot workflow definition and return
the list of external things it depends on (properties, lists, email
templates, owners). No database access lives here — the result is a
plain ``list[dict]`` that the dependency-mapping service persists.

The HubSpot workflow definition schema is loosely structured and
varies by `actionTypeId`. We err on the side of over-extraction: any
field that smells like an external reference is emitted with
``dependency_type='unknown'`` rather than dropped, on the theory that
false positives are easier to filter out later than false negatives
are to discover. Schema-shape mismatches must NEVER raise — bad input
just yields fewer dependencies.

See:
  docs/v2/workflow-failure-detection-research.md
  docs/v2/workflow-failure-detection-followup.md
for the documented response shape we're parsing.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.models.workflow_dependency import (
    DEPENDENCY_TYPE_EMAIL_TEMPLATE,
    DEPENDENCY_TYPE_LIST,
    DEPENDENCY_TYPE_OWNER,
    DEPENDENCY_TYPE_PROPERTY,
    DEPENDENCY_TYPE_UNKNOWN,
)


# Personalization tokens. HubSpot's content engine substitutes
# `{{ contact.firstname }}` → the contact's firstname value. The first
# group is the scope (contact / company / deal / ticket / owner / etc.)
# and the second is the property name. Whitespace is permitted around
# the dot and inside the braces.
PERSONALIZATION_TOKEN_RE = re.compile(
    r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}"
)


# Scope → HubSpot object type id. Anything not in this map falls back
# to the workflow's `objectTypeId` (or stays empty for cases where we
# legitimately can't tell).
_SCOPE_TO_OBJECT_TYPE: dict[str, str] = {
    "contact": "0-1",
    "company": "0-2",
    "deal": "0-3",
    "ticket": "0-5",
}


# Keys we recognise inside an action's `fields` block. The mapping is
# intentionally explicit so adding support for a new HubSpot action
# type is a single-line change.
_ACTION_FIELD_RULES: tuple[tuple[str, str], ...] = (
    # (field_key, dependency_type)
    ("property_name", DEPENDENCY_TYPE_PROPERTY),
    ("value_property_name", DEPENDENCY_TYPE_PROPERTY),
    ("email_id", DEPENDENCY_TYPE_EMAIL_TEMPLATE),
    ("email_content_id", DEPENDENCY_TYPE_EMAIL_TEMPLATE),
    ("template_id", DEPENDENCY_TYPE_EMAIL_TEMPLATE),
    ("list_id", DEPENDENCY_TYPE_LIST),
    ("static_list_id", DEPENDENCY_TYPE_LIST),
    ("owner_id", DEPENDENCY_TYPE_OWNER),
    ("ownerId", DEPENDENCY_TYPE_OWNER),
    ("assigned_user_id", DEPENDENCY_TYPE_OWNER),
    ("assignedOwnerId", DEPENDENCY_TYPE_OWNER),
)

# Same keys as a set, for O(1) "is this a recognised key?" checks
# inside the unknown-id sweep.
_RECOGNISED_FIELD_KEYS: frozenset[str] = frozenset(
    key for key, _ in _ACTION_FIELD_RULES
)

# Action field keys that are list-valued (each entry is a separate dep).
_ACTION_LIST_FIELD_RULES: tuple[tuple[str, str], ...] = (
    ("included_list_ids", DEPENDENCY_TYPE_LIST),
    ("excluded_list_ids", DEPENDENCY_TYPE_LIST),
)


def _normalise(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _emit(
    deps: list[dict[str, Any]],
    *,
    dependency_type: str,
    dependency_id: str,
    location: str,
    dependency_object_type: str | None = None,
) -> None:
    if not dependency_id:
        return
    deps.append(
        {
            "dependency_type": dependency_type,
            "dependency_id": dependency_id,
            "dependency_object_type": (dependency_object_type or None),
            "location": location,
        }
    )


def _resolve_object_type(scope: str, fallback: str) -> str:
    mapped = _SCOPE_TO_OBJECT_TYPE.get(_normalise(scope).lower())
    if mapped:
        return mapped
    return fallback


def _scan_string_for_tokens(
    text: str,
    location: str,
    deps: list[dict[str, Any]],
    default_object_type: str,
) -> None:
    if not isinstance(text, str) or "{{" not in text:
        return
    for match in PERSONALIZATION_TOKEN_RE.finditer(text):
        scope = match.group(1)
        prop = match.group(2)
        if not prop:
            continue
        obj_type = _resolve_object_type(scope, default_object_type)
        _emit(
            deps,
            dependency_type=DEPENDENCY_TYPE_PROPERTY,
            dependency_id=prop,
            location=location,
            dependency_object_type=obj_type or None,
        )


def _scan_container_for_tokens(
    obj: Any,
    location_prefix: str,
    deps: list[dict[str, Any]],
    default_object_type: str,
    *,
    exclude_keys: Iterable[str] = (),
) -> None:
    """Walk an arbitrary nested container looking for personalization
    tokens inside string values. Recurses through dicts and lists.
    """
    excluded = set(exclude_keys)
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in excluded:
                continue
            child_location = f"{location_prefix}.{key}" if location_prefix else str(key)
            if isinstance(value, str):
                _scan_string_for_tokens(value, child_location, deps, default_object_type)
            elif isinstance(value, (dict, list)):
                _scan_container_for_tokens(
                    value, child_location, deps, default_object_type
                )
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            child_location = f"{location_prefix}[{i}]"
            if isinstance(value, str):
                _scan_string_for_tokens(value, child_location, deps, default_object_type)
            elif isinstance(value, (dict, list)):
                _scan_container_for_tokens(
                    value, child_location, deps, default_object_type
                )


def _looks_like_external_id(raw: Any) -> bool:
    """Heuristic for the unknown-id sweep: numeric or hyphenated id."""
    text = _normalise(raw)
    if not text:
        return False
    cleaned = text.replace("-", "").replace("_", "")
    return cleaned.isdigit() and 1 <= len(cleaned) <= 32


def _walk_filter_tree(
    node: Any,
    location_prefix: str,
    deps: list[dict[str, Any]],
    default_object_type: str,
) -> None:
    """Recursively walk a filter / filterBranch / criteria subtree and
    emit property dependencies. Filter nodes use a `property` key to
    name the field they target and may be nested via `filterBranches`,
    `filters`, or `filterBranch`.
    """
    if isinstance(node, dict):
        if "property" in node:
            prop_name = _normalise(node.get("property"))
            if prop_name:
                obj_type = (
                    _normalise(node.get("propertyObjectType"))
                    or _normalise(node.get("objectTypeId"))
                    or default_object_type
                )
                _emit(
                    deps,
                    dependency_type=DEPENDENCY_TYPE_PROPERTY,
                    dependency_id=prop_name,
                    location=f"{location_prefix}.property",
                    dependency_object_type=obj_type or None,
                )

        for nested_key in ("filterBranches", "filters", "filterBranch"):
            child = node.get(nested_key)
            if isinstance(child, list):
                for i, item in enumerate(child):
                    _walk_filter_tree(
                        item,
                        f"{location_prefix}.{nested_key}[{i}]",
                        deps,
                        default_object_type,
                    )
            elif isinstance(child, dict):
                _walk_filter_tree(
                    child,
                    f"{location_prefix}.{nested_key}",
                    deps,
                    default_object_type,
                )

        # Personalization tokens may show up inside operator strings
        # like "EQ" filters that compare against `{{contact.email}}`.
        _scan_container_for_tokens(
            node,
            location_prefix,
            deps,
            default_object_type,
            exclude_keys={"property", "propertyObjectType", "objectTypeId"},
        )
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk_filter_tree(
                item, f"{location_prefix}[{i}]", deps, default_object_type
            )


def _process_action(
    action: dict[str, Any],
    location_prefix: str,
    deps: list[dict[str, Any]],
    default_object_type: str,
) -> None:
    fields = action.get("fields")
    if isinstance(fields, dict):
        # Single-valued, recognised field keys.
        for key, dep_type in _ACTION_FIELD_RULES:
            if key not in fields:
                continue
            value = _normalise(fields.get(key))
            if not value:
                continue
            obj_type = (
                default_object_type
                if dep_type == DEPENDENCY_TYPE_PROPERTY
                else None
            )
            _emit(
                deps,
                dependency_type=dep_type,
                dependency_id=value,
                location=f"{location_prefix}.fields.{key}",
                dependency_object_type=obj_type,
            )

        # List-valued, recognised field keys.
        for key, dep_type in _ACTION_LIST_FIELD_RULES:
            values = fields.get(key)
            if not isinstance(values, list):
                continue
            for i, raw in enumerate(values):
                value = _normalise(raw)
                if not value:
                    continue
                _emit(
                    deps,
                    dependency_type=dep_type,
                    dependency_id=value,
                    location=f"{location_prefix}.fields.{key}[{i}]",
                )

        # Unknown-id sweep — anything ending in `_id` with a numeric-
        # looking value is emitted with type='unknown' so we can audit
        # later.
        for key, value in fields.items():
            if not isinstance(key, str):
                continue
            if key in _RECOGNISED_FIELD_KEYS:
                continue
            if not key.endswith("_id"):
                continue
            if _looks_like_external_id(value):
                _emit(
                    deps,
                    dependency_type=DEPENDENCY_TYPE_UNKNOWN,
                    dependency_id=_normalise(value),
                    location=f"{location_prefix}.fields.{key}",
                )

        # Personalization tokens hiding inside text fields, subject
        # lines, etc.
        _scan_container_for_tokens(
            fields,
            f"{location_prefix}.fields",
            deps,
            default_object_type,
            exclude_keys=set(_RECOGNISED_FIELD_KEYS),
        )

    # Some action types embed branching logic on outgoing connections.
    connection = action.get("connection")
    if isinstance(connection, dict):
        for nested_key in ("filterBranches", "filters", "filterBranch"):
            child = connection.get(nested_key)
            if child is None:
                continue
            _walk_filter_tree(
                child,
                f"{location_prefix}.connection.{nested_key}",
                deps,
                default_object_type,
            )

    connections = action.get("connections")
    if isinstance(connections, list):
        for i, conn in enumerate(connections):
            if not isinstance(conn, dict):
                continue
            for nested_key in ("filterBranches", "filters", "filterBranch"):
                child = conn.get(nested_key)
                if child is None:
                    continue
                _walk_filter_tree(
                    child,
                    f"{location_prefix}.connections[{i}].{nested_key}",
                    deps,
                    default_object_type,
                )


def extract_dependencies(
    workflow_definition: dict[str, Any] | None,
    *,
    default_object_type_id: str = "",
) -> list[dict[str, Any]]:
    """Walk a HubSpot workflow definition and return every external
    dependency.

    Returns a list of dicts with keys: ``dependency_type``,
    ``dependency_id``, ``dependency_object_type`` (may be ``None``),
    and ``location``.

    ``default_object_type_id`` is used as the fallback for property
    references that don't carry their own object type. Pass the
    workflow's top-level ``objectTypeId`` (e.g. ``"0-1"`` for a
    contact-based workflow).
    """
    deps: list[dict[str, Any]] = []
    if not isinstance(workflow_definition, dict):
        return deps

    object_type = (
        _normalise(workflow_definition.get("objectTypeId"))
        or _normalise(default_object_type_id)
    )

    # 1. Enrollment criteria.
    criteria = workflow_definition.get("enrollmentCriteria")
    if isinstance(criteria, dict):
        for branch_key in (
            "listFilterBranches",
            "eventFilterBranches",
            "reEnrollmentTriggersFilterBranches",
            "filterBranches",
        ):
            branches = criteria.get(branch_key)
            if isinstance(branches, list):
                for i, branch in enumerate(branches):
                    _walk_filter_tree(
                        branch,
                        f"enrollmentCriteria.{branch_key}[{i}]",
                        deps,
                        object_type,
                    )

    # 2. Actions.
    actions = workflow_definition.get("actions")
    if isinstance(actions, list):
        for i, action in enumerate(actions):
            if isinstance(action, dict):
                _process_action(action, f"actions[{i}]", deps, object_type)

    return deps
