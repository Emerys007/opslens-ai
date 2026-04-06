from pathlib import Path
import textwrap

ROOT = Path(r"C:\OpsLens AI")
BACKEND = ROOT / "backend"
PROJECT = ROOT / "opslens-ai"

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

write_file(BACKEND / "app" / "api" / "v1" / "routes" / "dashboard.py", """
from pathlib import Path
import json

from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "portal_settings.json"

SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _normalize_severity(value: str | None, fallback: str = "high") -> str:
    text = str(value or "").strip().lower()
    return text if text in SEVERITY_ORDER else fallback


def _read_portal_settings(portal_id: str | None) -> dict:
    defaults = {
        "slackWebhookUrl": "",
        "alertThreshold": "high",
        "criticalWorkflows": "",
    }

    if not portal_id or not SETTINGS_FILE.exists():
        return defaults

    try:
        all_settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return defaults

    portal_settings = all_settings.get(str(portal_id), {})
    if not isinstance(portal_settings, dict):
        return defaults

    merged = defaults.copy()
    merged.update(portal_settings)
    merged["alertThreshold"] = _normalize_severity(merged.get("alertThreshold"), "high")
    return merged


def _resolved_level(row: AlertEvent, threshold: str) -> str:
    override = str(row.severity_override or "").strip().lower()
    if override in ("", "use_settings"):
        return threshold
    return _normalize_severity(override, threshold)


def _visible(level: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(level, 0) >= SEVERITY_ORDER.get(threshold, 0)


@router.get("/overview")
def dashboard_overview(request: Request):
    query = request.query_params

    portal_id = str(query.get("portalId", "")).strip()
    user_id = str(query.get("userId", "")).strip()
    user_email = str(query.get("userEmail", "")).strip()
    app_id = str(query.get("appId", "")).strip()

    settings = _read_portal_settings(portal_id)
    threshold = _normalize_severity(settings.get("alertThreshold"), "high")

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
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
            },
        }
    finally:
        session.close()
""")

print("OpsLens step 15 scaffold created successfully.")
print("Updated files:")
print(" - backend/app/api/v1/routes/dashboard.py")
