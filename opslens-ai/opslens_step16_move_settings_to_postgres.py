from pathlib import Path
import textwrap

ROOT = Path(r"C:\OpsLens AI")
BACKEND = ROOT / "backend"
PROJECT = ROOT / "opslens-ai"

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

write_file(BACKEND / "app" / "db.py", """
import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    return _engine


def init_db() -> bool:
    engine = get_engine()
    if engine is None:
        return False

    # Import models so they are registered with Base.metadata
    from app.models.alert_event import AlertEvent  # noqa: F401
    from app.models.portal_setting import PortalSetting  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return True


def get_session() -> Optional[Session]:
    engine = get_engine()
    if engine is None or _SessionLocal is None:
        return None
    return _SessionLocal()
""")

write_file(BACKEND / "app" / "models" / "portal_setting.py", """
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PortalSetting(Base):
    __tablename__ = "portal_settings"

    portal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slack_webhook_url: Mapped[str] = mapped_column(Text, default="")
    alert_threshold: Mapped[str] = mapped_column(String(32), default="high")
    critical_workflows: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
""")

write_file(BACKEND / "app" / "services" / "portal_settings.py", """
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
        critical_workflows = "\\n".join(str(item) for item in critical_workflows)

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
""")

write_file(BACKEND / "app" / "api" / "v1" / "routes" / "settings_store.py", """
from fastapi import APIRouter, Request

from app.db import get_session, init_db
from app.services.portal_settings import load_portal_settings, save_portal_settings

router = APIRouter(prefix="/settings-store", tags=["settings-store"])


@router.get("")
def get_settings(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        return {
            "status": "ok",
            "portalId": portal_id or "not-provided",
            "settings": load_portal_settings(None, portal_id),
            "dbConfigured": False,
        }

    try:
        return {
            "status": "ok",
            "portalId": portal_id or "not-provided",
            "settings": load_portal_settings(session, portal_id),
            "dbConfigured": True,
        }
    finally:
        session.close()


@router.post("")
async def save_settings(request: Request):
    portal_id = str(request.query_params.get("portalId", "")).strip()
    payload = await request.json()

    if not portal_id:
        return {
            "status": "error",
            "message": "portalId is required.",
        }

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        return {
            "status": "error",
            "message": "Database is not configured.",
        }

    try:
        settings = save_portal_settings(session, portal_id, payload)
        return {
            "status": "ok",
            "portalId": portal_id,
            "settings": settings,
            "dbConfigured": True,
        }
    finally:
        session.close()
""")

write_file(BACKEND / "app" / "api" / "v1" / "routes" / "dashboard.py", """
from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent
from app.services.portal_settings import (
    SEVERITY_ORDER,
    load_portal_settings,
    normalize_severity,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _resolved_level(row: AlertEvent, threshold: str) -> str:
    override = str(row.severity_override or "").strip().lower()
    if override in ("", "use_settings"):
        return threshold
    return normalize_severity(override, threshold)


def _visible(level: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(level, 0) >= SEVERITY_ORDER.get(threshold, 0)


@router.get("/overview")
def dashboard_overview(request: Request):
    query = request.query_params

    portal_id = str(query.get("portalId", "")).strip()
    user_id = str(query.get("userId", "")).strip()
    user_email = str(query.get("userEmail", "")).strip()
    app_id = str(query.get("appId", "")).strip()

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        settings = load_portal_settings(None, portal_id)
        return {
            "status": "ok",
            "app": "OpsLens AI",
            "connectedBackend": True,
            "settings": settings,
            "summary": {
                "openIncidents": 0,
                "criticalIssues": 0,
                "monitoredWorkflows": 0,
                "lastCheckedUtc": None,
                "activeIncidents": [],
            },
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": False,
            },
        }

    try:
        settings = load_portal_settings(session, portal_id)
        threshold = normalize_severity(settings.get("alertThreshold"), "high")

        stmt = select(AlertEvent).where(AlertEvent.result == "accepted")
        if portal_id:
            stmt = stmt.where(AlertEvent.portal_id == portal_id)

        stmt = stmt.order_by(desc(AlertEvent.received_at_utc))
        rows = session.execute(stmt).scalars().all()

        monitored_workflows = len(
            {str(row.workflow_id) for row in rows if str(row.workflow_id or "").strip()}
        )

        visible_rows = []
        for row in rows:
            level = _resolved_level(row, threshold)
            if _visible(level, threshold):
                visible_rows.append((row, level))

        critical_issues = sum(1 for _, level in visible_rows if level == "critical")

        active_incidents = []
        for row, level in visible_rows[:5]:
            workflow_id_text = str(row.workflow_id).strip() if row.workflow_id is not None else "unknown"
            object_label = str(row.object_type or "record").strip()
            object_id = str(row.object_id or "").strip()

            active_incidents.append(
                {
                    "id": row.callback_id or f"alert-{row.id}",
                    "severity": level,
                    "title": f"Workflow {workflow_id_text} alert",
                    "affectedRecords": 1,
                    "recommendation": row.analyst_note or f"Review the latest saved alert for {object_label} {object_id}.",
                }
            )

        last_checked = rows[0].received_at_utc.isoformat() if rows and rows[0].received_at_utc else None

        return {
            "status": "ok",
            "app": "OpsLens AI",
            "connectedBackend": True,
            "settings": settings,
            "summary": {
                "openIncidents": len(visible_rows),
                "criticalIssues": critical_issues,
                "monitoredWorkflows": monitored_workflows,
                "lastCheckedUtc": last_checked,
                "activeIncidents": active_incidents,
            },
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": True,
                "savedAlertRows": len(rows),
                "visibleRowsAtThreshold": len(visible_rows),
                "settingsStorage": settings.get("storage", "unknown"),
            },
        }
    finally:
        session.close()
""")

write_file(BACKEND / "app" / "api" / "v1" / "routes" / "record_risk.py", """
from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent
from app.services.portal_settings import (
    SEVERITY_ORDER,
    load_portal_settings,
    normalize_severity,
)

router = APIRouter(prefix="/records", tags=["records"])


def _severity_visible_at_threshold(level: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(level, 0) >= SEVERITY_ORDER.get(threshold, 0)


def _object_type_candidates(object_type_id: str) -> list[str]:
    value = str(object_type_id or "").strip()
    if value == "0-1":
        return ["CONTACT", "0-1"]
    return [value] if value else ["CONTACT", "0-1"]


@router.get("/contact-risk")
def contact_risk(request: Request):
    query = request.query_params

    record_id = str(query.get("recordId", "")).strip()
    object_type_id = str(query.get("objectTypeId", "0-1")).strip() or "0-1"
    portal_id = str(query.get("portalId", "")).strip()
    user_id = str(query.get("userId", "")).strip()
    user_email = str(query.get("userEmail", "")).strip()
    app_id = str(query.get("appId", "")).strip()

    if not record_id:
        return {
            "status": "error",
            "message": "recordId is required.",
        }

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
        settings = load_portal_settings(None, portal_id)
        threshold = normalize_severity(settings.get("alertThreshold"), "high")

        return {
            "status": "ok",
            "record": {
                "recordId": record_id,
                "objectTypeId": object_type_id,
            },
            "settings": settings,
            "risk": {
                "level": "unknown",
                "incidentTitle": "Database unavailable",
                "recommendation": "Check DATABASE_URL and database connectivity.",
            },
            "visibility": {
                "threshold": threshold,
                "visible": False,
            },
            "latestAlert": None,
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": False,
            },
        }

    try:
        settings = load_portal_settings(session, portal_id)
        threshold = normalize_severity(settings.get("alertThreshold"), "high")

        stmt = (
            select(AlertEvent)
            .where(AlertEvent.object_id == record_id)
            .where(AlertEvent.object_type.in_(_object_type_candidates(object_type_id)))
            .where(AlertEvent.result == "accepted")
        )

        if portal_id:
            stmt = stmt.where(AlertEvent.portal_id == portal_id)

        stmt = stmt.order_by(desc(AlertEvent.received_at_utc)).limit(1)
        row = session.execute(stmt).scalars().first()

        if row is None:
            return {
                "status": "ok",
                "record": {
                    "recordId": record_id,
                    "objectTypeId": object_type_id,
                },
                "settings": settings,
                "risk": {
                    "level": "none",
                    "incidentTitle": "No saved OpsLens alert for this record",
                    "recommendation": "Run the workflow action for this contact, then refresh the card.",
                },
                "visibility": {
                    "threshold": threshold,
                    "visible": False,
                },
                "latestAlert": None,
                "debug": {
                    "portalId": portal_id or "not-provided",
                    "userId": user_id or "not-provided",
                    "userEmail": user_email or "not-provided",
                    "appId": app_id or "not-provided",
                    "dbConfigured": True,
                    "settingsStorage": settings.get("storage", "unknown"),
                },
            }

        override = str(row.severity_override or "").strip().lower()
        resolved_level = threshold if override in ("", "use_settings") else normalize_severity(override, threshold)
        visible = _severity_visible_at_threshold(resolved_level, threshold)

        latest_alert = {
            "id": row.id,
            "receivedAtUtc": row.received_at_utc.isoformat() if row.received_at_utc else None,
            "callbackId": row.callback_id,
            "portalId": row.portal_id,
            "workflowId": row.workflow_id,
            "objectType": row.object_type,
            "objectId": row.object_id,
            "severityOverride": row.severity_override,
            "analystNote": row.analyst_note,
            "result": row.result,
            "reason": row.reason,
        }

        return {
            "status": "ok",
            "record": {
                "recordId": record_id,
                "objectTypeId": object_type_id,
            },
            "settings": settings,
            "risk": {
                "level": resolved_level,
                "incidentTitle": "Latest saved OpsLens alert",
                "recommendation": row.analyst_note or "Review the latest workflow execution details.",
            },
            "visibility": {
                "threshold": threshold,
                "visible": visible,
            },
            "latestAlert": latest_alert,
            "debug": {
                "portalId": portal_id or "not-provided",
                "userId": user_id or "not-provided",
                "userEmail": user_email or "not-provided",
                "appId": app_id or "not-provided",
                "dbConfigured": True,
                "settingsStorage": settings.get("storage", "unknown"),
            },
        }
    finally:
        session.close()
""")

print("OpsLens step 16 scaffold created successfully.")
print("Updated files:")
print(" - backend/app/db.py")
print(" - backend/app/models/portal_setting.py")
print(" - backend/app/services/portal_settings.py")
print(" - backend/app/api/v1/routes/settings_store.py")
print(" - backend/app/api/v1/routes/dashboard.py")
print(" - backend/app/api/v1/routes/record_risk.py")
