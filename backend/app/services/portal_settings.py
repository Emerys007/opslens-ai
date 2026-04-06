import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.portal_setting import PortalSetting

LEGACY_SETTINGS_FILE = Path(__file__).resolve().parents[3] / "data" / "portal_settings.json"

DEFAULT_SETTINGS = {
    "slackWebhookUrl": "",
    "alertThreshold": "high",
    "criticalWorkflows": "",
}

SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def normalize_severity(value: Optional[str], fallback: str = "high") -> str:
    text = str(value or "").strip().lower()
    return text if text in SEVERITY_ORDER else fallback


def _settings_dict(
    portal_id: str,
    slack_webhook_url: str = "",
    alert_threshold: str = "high",
    critical_workflows: str = "",
    updated_at=None,
    storage: str = "postgres",
):
    return {
        "portalId": str(portal_id),
        "slackWebhookUrl": slack_webhook_url or "",
        "alertThreshold": normalize_severity(alert_threshold, "high"),
        "criticalWorkflows": critical_workflows or "",
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
        )
        session.add(row)
        session.commit()
        session.refresh(row)

        return _settings_dict(
            portal_id=row.portal_id,
            slack_webhook_url=row.slack_webhook_url,
            alert_threshold=row.alert_threshold,
            critical_workflows=row.critical_workflows,
            updated_at=row.updated_at,
            storage="postgres-migrated-from-file",
        )

    return _settings_dict(
        portal_id=str(portal_id),
        slack_webhook_url=DEFAULT_SETTINGS["slackWebhookUrl"],
        alert_threshold=DEFAULT_SETTINGS["alertThreshold"],
        critical_workflows=DEFAULT_SETTINGS["criticalWorkflows"],
        updated_at=None,
        storage="defaults",
    )


def save_portal_settings(session: Session, portal_id: str, payload: dict):
    row = session.get(PortalSetting, str(portal_id))
    if row is None:
        row = PortalSetting(portal_id=str(portal_id))
        session.add(row)

    critical_workflows = payload.get("criticalWorkflows", "")
    if isinstance(critical_workflows, list):
        critical_workflows = "\n".join(str(item) for item in critical_workflows)

    row.slack_webhook_url = str(payload.get("slackWebhookUrl", "") or "")
    row.alert_threshold = normalize_severity(payload.get("alertThreshold"), "high")
    row.critical_workflows = str(critical_workflows or "")

    session.commit()
    session.refresh(row)

    return _settings_dict(
        portal_id=row.portal_id,
        slack_webhook_url=row.slack_webhook_url,
        alert_threshold=row.alert_threshold,
        critical_workflows=row.critical_workflows,
        updated_at=row.updated_at,
        storage="postgres",
    )
