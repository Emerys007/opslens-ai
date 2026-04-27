from __future__ import annotations

import copy
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.alert import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SOURCE_EVENT_LIST_ARCHIVED,
    SOURCE_EVENT_LIST_CRITERIA_CHANGED,
    SOURCE_EVENT_LIST_DELETED,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_EVENT_PROPERTY_DELETED,
    SOURCE_EVENT_PROPERTY_RENAMED,
    SOURCE_EVENT_PROPERTY_TYPE_CHANGED,
    SOURCE_EVENT_TEMPLATE_ARCHIVED,
    SOURCE_EVENT_TEMPLATE_DELETED,
    SOURCE_EVENT_TEMPLATE_EDITED,
    SOURCE_EVENT_WORKFLOW_DISABLED,
    SOURCE_EVENT_WORKFLOW_EDITED,
)
from app.models.monitoring_exclusion import (
    EXCLUSION_TYPE_LIST,
    EXCLUSION_TYPE_PROPERTY,
    EXCLUSION_TYPE_TEMPLATE,
    EXCLUSION_TYPE_WORKFLOW,
    MonitoringExclusion,
)
from app.models.portal_setting import PortalSetting
from app.services.portal_settings import SEVERITY_ORDER


MONITORING_CATEGORY_PROPERTY_ARCHIVED = SOURCE_EVENT_PROPERTY_ARCHIVED
MONITORING_CATEGORY_PROPERTY_DELETED = SOURCE_EVENT_PROPERTY_DELETED
MONITORING_CATEGORY_PROPERTY_RENAMED = SOURCE_EVENT_PROPERTY_RENAMED
MONITORING_CATEGORY_PROPERTY_TYPE_CHANGED = SOURCE_EVENT_PROPERTY_TYPE_CHANGED
MONITORING_CATEGORY_WORKFLOW_DISABLED = SOURCE_EVENT_WORKFLOW_DISABLED
MONITORING_CATEGORY_WORKFLOW_EDITED = SOURCE_EVENT_WORKFLOW_EDITED
MONITORING_CATEGORY_LIST_ARCHIVED = SOURCE_EVENT_LIST_ARCHIVED
MONITORING_CATEGORY_LIST_DELETED = SOURCE_EVENT_LIST_DELETED
MONITORING_CATEGORY_LIST_CRITERIA_CHANGED = SOURCE_EVENT_LIST_CRITERIA_CHANGED
MONITORING_CATEGORY_TEMPLATE_ARCHIVED = SOURCE_EVENT_TEMPLATE_ARCHIVED
MONITORING_CATEGORY_TEMPLATE_DELETED = SOURCE_EVENT_TEMPLATE_DELETED
MONITORING_CATEGORY_TEMPLATE_EDITED = SOURCE_EVENT_TEMPLATE_EDITED

MONITORING_CATEGORY_DEFAULT_SEVERITIES: dict[str, str] = {
    MONITORING_CATEGORY_PROPERTY_ARCHIVED: SEVERITY_HIGH,
    MONITORING_CATEGORY_PROPERTY_DELETED: SEVERITY_HIGH,
    MONITORING_CATEGORY_PROPERTY_RENAMED: SEVERITY_LOW,
    MONITORING_CATEGORY_PROPERTY_TYPE_CHANGED: SEVERITY_MEDIUM,
    MONITORING_CATEGORY_WORKFLOW_DISABLED: SEVERITY_HIGH,
    MONITORING_CATEGORY_WORKFLOW_EDITED: SEVERITY_MEDIUM,
    MONITORING_CATEGORY_LIST_ARCHIVED: SEVERITY_HIGH,
    MONITORING_CATEGORY_LIST_DELETED: SEVERITY_HIGH,
    MONITORING_CATEGORY_LIST_CRITERIA_CHANGED: SEVERITY_MEDIUM,
    MONITORING_CATEGORY_TEMPLATE_ARCHIVED: SEVERITY_HIGH,
    MONITORING_CATEGORY_TEMPLATE_DELETED: SEVERITY_HIGH,
    MONITORING_CATEGORY_TEMPLATE_EDITED: SEVERITY_MEDIUM,
}

MONITORING_CATEGORIES = tuple(MONITORING_CATEGORY_DEFAULT_SEVERITIES.keys())
VALID_SEVERITY_OVERRIDES = tuple(SEVERITY_ORDER.keys())


def default_monitoring_coverage() -> dict:
    return {
        category: {"enabled": True, "severityOverride": None}
        for category in MONITORING_CATEGORIES
    }


def _coerce_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off", ""):
        return False
    return default


def _raw_coverage(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def normalize_monitoring_coverage(raw: Any) -> dict:
    merged = default_monitoring_coverage()
    for category, config in _raw_coverage(raw).items():
        if category not in merged or not isinstance(config, dict):
            continue

        enabled = _coerce_bool(config.get("enabled"), True)
        severity_override = config.get("severityOverride")
        if severity_override is not None:
            severity_override = str(severity_override).strip().lower()
            if severity_override not in SEVERITY_ORDER:
                severity_override = None

        merged[category] = {
            "enabled": enabled,
            "severityOverride": severity_override,
        }
    return merged


def load_monitoring_coverage(session, portal_id: str) -> dict:
    """Returns the merged config (defaults + portal overrides)."""
    portal_key = str(portal_id or "").strip()
    if not portal_key or session is None:
        return default_monitoring_coverage()

    row = session.get(PortalSetting, portal_key)
    if row is None:
        return default_monitoring_coverage()
    return normalize_monitoring_coverage(getattr(row, "monitoring_coverage", None))


def is_category_enabled(coverage: dict, category: str) -> bool:
    """True if the category is enabled (default true if not set)."""
    config = coverage.get(category) if isinstance(coverage, dict) else None
    if not isinstance(config, dict):
        return True
    return _coerce_bool(config.get("enabled"), True)


def get_category_severity(coverage: dict, category: str, default: str) -> str:
    """Returns the override if set, else the default."""
    config = coverage.get(category) if isinstance(coverage, dict) else None
    if isinstance(config, dict):
        override = config.get("severityOverride")
        if override is not None:
            severity = str(override).strip().lower()
            if severity in SEVERITY_ORDER:
                return severity
    return default


def is_workflow_excluded(session, portal_id: str, workflow_id: str) -> bool:
    portal_key = str(portal_id or "").strip()
    workflow_key = str(workflow_id or "").strip()
    if not portal_key or not workflow_key:
        return False
    return (
        session.query(MonitoringExclusion.id)
        .filter(
            MonitoringExclusion.portal_id == portal_key,
            MonitoringExclusion.exclusion_type == EXCLUSION_TYPE_WORKFLOW,
            MonitoringExclusion.exclusion_id == workflow_key,
            MonitoringExclusion.object_type_id.is_(None),
        )
        .first()
        is not None
    )


def is_property_excluded(
    session,
    portal_id: str,
    property_name: str,
    object_type_id: str,
) -> bool:
    portal_key = str(portal_id or "").strip()
    property_key = str(property_name or "").strip()
    object_type_key = str(object_type_id or "").strip()
    if not portal_key or not property_key or not object_type_key:
        return False
    return (
        session.query(MonitoringExclusion.id)
        .filter(
            MonitoringExclusion.portal_id == portal_key,
            MonitoringExclusion.exclusion_type == EXCLUSION_TYPE_PROPERTY,
            MonitoringExclusion.exclusion_id == property_key,
            MonitoringExclusion.object_type_id == object_type_key,
        )
        .first()
        is not None
    )


def is_list_excluded(session, portal_id: str, list_id: str) -> bool:
    portal_key = str(portal_id or "").strip()
    list_key = str(list_id or "").strip()
    if not portal_key or not list_key:
        return False
    return (
        session.query(MonitoringExclusion.id)
        .filter(
            MonitoringExclusion.portal_id == portal_key,
            MonitoringExclusion.exclusion_type == EXCLUSION_TYPE_LIST,
            MonitoringExclusion.exclusion_id == list_key,
            MonitoringExclusion.object_type_id.is_(None),
        )
        .first()
        is not None
    )


def is_template_excluded(session, portal_id: str, template_id: str) -> bool:
    portal_key = str(portal_id or "").strip()
    template_key = str(template_id or "").strip()
    if not portal_key or not template_key:
        return False
    return (
        session.query(MonitoringExclusion.id)
        .filter(
            MonitoringExclusion.portal_id == portal_key,
            MonitoringExclusion.exclusion_type == EXCLUSION_TYPE_TEMPLATE,
            MonitoringExclusion.exclusion_id == template_key,
            MonitoringExclusion.object_type_id.is_(None),
        )
        .first()
        is not None
    )


def merge_monitoring_coverage_update(existing: Any, payload: dict) -> dict:
    updated = copy.deepcopy(normalize_monitoring_coverage(existing))
    for category, config in payload.items():
        current = updated[category]
        if "enabled" in config:
            current["enabled"] = bool(config["enabled"])
        if "severityOverride" in config:
            override = config["severityOverride"]
            current["severityOverride"] = (
                str(override).strip().lower() if override is not None else None
            )
    return updated


def category_metadata(coverage: dict) -> list[dict]:
    return [
        {
            "name": category,
            "defaultSeverity": MONITORING_CATEGORY_DEFAULT_SEVERITIES[category],
            "enabled": bool(coverage[category]["enabled"]),
            "severityOverride": coverage[category]["severityOverride"],
        }
        for category in MONITORING_CATEGORIES
    ]
