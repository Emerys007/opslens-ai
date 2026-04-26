import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.portal_setting import PortalSetting

LEGACY_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "portal_settings.json"

DEFAULT_SETTINGS = {
    "slackWebhookUrl": "",
    # v2 default is `medium` — high+medium delivered, low suppressed. v1
    # portals provisioned with `high` keep that value; the change only
    # affects fresh installs.
    "alertThreshold": "medium",
    "criticalWorkflows": "",
    "slackDeliveryEnabled": True,
    "ticketDeliveryEnabled": True,
}

SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def normalize_severity(value: Optional[str], fallback: str = "medium") -> str:
    text = str(value or "").strip().lower()
    return text if text in SEVERITY_ORDER else fallback


def severity_meets_threshold(severity: Optional[str], threshold: Optional[str]) -> bool:
    """Returns True when an alert at ``severity`` should be delivered
    given the portal's ``threshold``. Both are normalised against
    ``SEVERITY_ORDER``; unknown values are treated as ``medium``.
    """
    severity_rank = SEVERITY_ORDER.get(normalize_severity(severity), 2)
    threshold_rank = SEVERITY_ORDER.get(normalize_severity(threshold), 2)
    return severity_rank >= threshold_rank


def _settings_dict(
    portal_id: str,
    slack_webhook_url: str = "",
    alert_threshold: str = "medium",
    critical_workflows: str = "",
    slack_delivery_enabled: bool = True,
    ticket_delivery_enabled: bool = True,
    updated_at=None,
    storage: str = "postgres",
):
    return {
        "portalId": str(portal_id),
        "slackWebhookUrl": slack_webhook_url or "",
        "alertThreshold": normalize_severity(alert_threshold, "medium"),
        "criticalWorkflows": critical_workflows or "",
        "slackDeliveryEnabled": bool(slack_delivery_enabled),
        "ticketDeliveryEnabled": bool(ticket_delivery_enabled),
        "updatedAtUtc": updated_at.isoformat() if updated_at else None,
        "storage": storage,
    }


def _read_legacy_settings(portal_id: str):
    if not LEGACY_SETTINGS_FILE.exists():
        return None

    try:
        all_settings = json.loads(LEGACY_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

    portal_settings = all_settings.get(str(portal_id))
    if not isinstance(portal_settings, dict):
        return None

    return {
        "slackWebhookUrl": str(portal_settings.get("slackWebhookUrl", "") or ""),
        "alertThreshold": normalize_severity(portal_settings.get("alertThreshold"), "high"),
        "criticalWorkflows": str(portal_settings.get("criticalWorkflows", "") or ""),
    }


def load_portal_settings(session: Optional[Session], portal_id: Optional[str]):
    if not portal_id:
        data = DEFAULT_SETTINGS.copy()
        data["portalId"] = ""
        data["updatedAtUtc"] = None
        data["storage"] = "defaults"
        return data

    if session is None:
        data = DEFAULT_SETTINGS.copy()
        data["portalId"] = str(portal_id)
        data["updatedAtUtc"] = None
        data["storage"] = "defaults"
        return data

    row = session.get(PortalSetting, str(portal_id))
    if row is not None:
        return _settings_dict(
            portal_id=row.portal_id,
            slack_webhook_url=row.slack_webhook_url,
            alert_threshold=row.alert_threshold,
            critical_workflows=row.critical_workflows,
            slack_delivery_enabled=getattr(row, "slack_delivery_enabled", True),
            ticket_delivery_enabled=getattr(row, "ticket_delivery_enabled", True),
            updated_at=row.updated_at,
            storage="postgres",
        )

    legacy = _read_legacy_settings(str(portal_id))
    if legacy is not None:
        row = PortalSetting(
            portal_id=str(portal_id),
            slack_webhook_url=legacy["slackWebhookUrl"],
            alert_threshold=legacy["alertThreshold"],
            critical_workflows=legacy["criticalWorkflows"],
            slack_delivery_enabled=True,
            ticket_delivery_enabled=True,
        )
        session.add(row)
        session.commit()
        session.refresh(row)

        return _settings_dict(
            portal_id=row.portal_id,
            slack_webhook_url=row.slack_webhook_url,
            alert_threshold=row.alert_threshold,
            critical_workflows=row.critical_workflows,
            slack_delivery_enabled=getattr(row, "slack_delivery_enabled", True),
            ticket_delivery_enabled=getattr(row, "ticket_delivery_enabled", True),
            updated_at=row.updated_at,
            storage="postgres-migrated-from-file",
        )

    return _settings_dict(
        portal_id=str(portal_id),
        slack_webhook_url=DEFAULT_SETTINGS["slackWebhookUrl"],
        alert_threshold=DEFAULT_SETTINGS["alertThreshold"],
        critical_workflows=DEFAULT_SETTINGS["criticalWorkflows"],
        slack_delivery_enabled=DEFAULT_SETTINGS["slackDeliveryEnabled"],
        ticket_delivery_enabled=DEFAULT_SETTINGS["ticketDeliveryEnabled"],
        updated_at=None,
        storage="defaults",
    )


def ensure_default_portal_settings(session: Session, portal_id: str):
    cleaned_portal_id = str(portal_id or "").strip()
    if not cleaned_portal_id:
        raise RuntimeError("portal_id is required.")

    row = session.get(PortalSetting, cleaned_portal_id)
    created = False
    if row is None:
        row = PortalSetting(
            portal_id=cleaned_portal_id,
            slack_webhook_url=DEFAULT_SETTINGS["slackWebhookUrl"],
            alert_threshold=DEFAULT_SETTINGS["alertThreshold"],
            critical_workflows=DEFAULT_SETTINGS["criticalWorkflows"],
            slack_delivery_enabled=DEFAULT_SETTINGS["slackDeliveryEnabled"],
            ticket_delivery_enabled=DEFAULT_SETTINGS["ticketDeliveryEnabled"],
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        created = True

    return _settings_dict(
        portal_id=row.portal_id,
        slack_webhook_url=row.slack_webhook_url,
        alert_threshold=row.alert_threshold,
        critical_workflows=row.critical_workflows,
        slack_delivery_enabled=getattr(row, "slack_delivery_enabled", True),
        ticket_delivery_enabled=getattr(row, "ticket_delivery_enabled", True),
        updated_at=row.updated_at,
        storage="postgres",
    ), created


def _coerce_bool(value, default: bool) -> bool:
    """Be liberal in what we accept on the inbound payload — Slack and
    ticket toggles are likely to come in via JSON (true/false), via
    HTML forms (``"on"`` / ``""``), or omitted entirely.
    """
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


def save_portal_settings(session: Session, portal_id: str, payload: dict):
    row = session.get(PortalSetting, str(portal_id))
    if row is None:
        row = PortalSetting(portal_id=str(portal_id))
        session.add(row)

    critical_workflows = payload.get("criticalWorkflows", "")
    if isinstance(critical_workflows, list):
        critical_workflows = "\n".join(str(item) for item in critical_workflows)

    row.slack_webhook_url = str(payload.get("slackWebhookUrl", "") or "")
    row.alert_threshold = normalize_severity(payload.get("alertThreshold"), "medium")
    row.critical_workflows = str(critical_workflows or "")
    if "slackDeliveryEnabled" in payload:
        row.slack_delivery_enabled = _coerce_bool(payload.get("slackDeliveryEnabled"), True)
    if "ticketDeliveryEnabled" in payload:
        row.ticket_delivery_enabled = _coerce_bool(payload.get("ticketDeliveryEnabled"), True)

    session.commit()
    session.refresh(row)

    return _settings_dict(
        portal_id=row.portal_id,
        slack_webhook_url=row.slack_webhook_url,
        alert_threshold=row.alert_threshold,
        critical_workflows=row.critical_workflows,
        slack_delivery_enabled=getattr(row, "slack_delivery_enabled", True),
        ticket_delivery_enabled=getattr(row, "ticket_delivery_enabled", True),
        updated_at=row.updated_at,
        storage="postgres",
    )
