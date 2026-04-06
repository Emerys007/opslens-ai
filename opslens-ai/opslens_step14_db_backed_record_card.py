from pathlib import Path
import textwrap

ROOT = Path(r"C:\OpsLens AI")
BACKEND = ROOT / "backend"
PROJECT = ROOT / "opslens-ai"

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

write_file(BACKEND / "app" / "api" / "v1" / "routes" / "record_risk.py", """
from pathlib import Path
import json

from fastapi import APIRouter, Request
from sqlalchemy import desc, select

from app.db import get_session, init_db
from app.models.alert_event import AlertEvent

router = APIRouter(prefix="/records", tags=["records"])

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

    settings = _read_portal_settings(portal_id)
    threshold = _normalize_severity(settings.get("alertThreshold"), "high")

    db_ready = init_db()
    session = get_session()

    if not db_ready or session is None:
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
            },
        }

    try:
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
                },
            }

        resolved_level = _normalize_severity(
            row.severity_override if row.severity_override not in (None, "", "use_settings") else threshold,
            threshold,
        )
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
            },
        }
    finally:
        session.close()
""")

write_file(PROJECT / "src" / "app" / "cards" / "NewCard.tsx", """
import React, { useEffect, useState } from "react";
import { Button, Divider, Flex, Text, hubspot } from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

type CardPayload = {
  status?: string;
  settings?: {
    alertThreshold?: string;
    criticalWorkflows?: string;
  };
  risk?: {
    level?: string;
    incidentTitle?: string;
    recommendation?: string;
  };
  visibility?: {
    threshold?: string;
    visible?: boolean;
  };
  latestAlert?: {
    id?: number;
    receivedAtUtc?: string;
    callbackId?: string;
    portalId?: string;
    workflowId?: string;
    objectType?: string;
    objectId?: string;
    severityOverride?: string;
    analystNote?: string;
    result?: string;
    reason?: string;
  } | null;
};

function safeText(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

function formatDateTime(value: unknown): string {
  if (!value) return "-";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

hubspot.extend(({ context }) => <NewCard context={context} />);

const NewCard = ({ context }: { context: any }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState<CardPayload | null>(null);

  const recordId = String(context?.crm?.objectId ?? "");
  const objectTypeId = String(context?.crm?.objectTypeId ?? "0-1");

  const loadRisk = async () => {
    if (!recordId) {
      setError("Record ID is missing from HubSpot context.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await hubspot.fetch(
        `${BACKEND_BASE_URL}/api/v1/records/contact-risk?recordId=${encodeURIComponent(recordId)}&objectTypeId=${encodeURIComponent(objectTypeId)}`
      );

      if (!response.ok) {
        throw new Error(`Record risk request failed with status ${response.status}`);
      }

      const json: CardPayload = await response.json();
      setPayload(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRisk();
  }, [recordId, objectTypeId]);

  const latest = payload?.latestAlert;

  return (
    <Flex direction="column">
      <Text>OpsLens AI</Text>
      <Text>This record card now reads the latest saved alert for this contact from Postgres.</Text>

      <Button onClick={loadRisk}>Refresh record risk</Button>

      <Divider />

      {loading ? (
        <Text>Loading...</Text>
      ) : error ? (
        <Text>Error: {error}</Text>
      ) : latest ? (
        <>
          <Text>Alert threshold: {safeText(payload?.visibility?.threshold).toUpperCase()}</Text>
          <Text>Risk level: {safeText(payload?.risk?.level).toUpperCase()}</Text>
          <Text>Visible at threshold: {String(Boolean(payload?.visibility?.visible))}</Text>
          <Text>Latest event at: {formatDateTime(latest.receivedAtUtc)}</Text>
          <Text>Workflow ID: {safeText(latest.workflowId)}</Text>
          <Text>Callback ID: {safeText(latest.callbackId)}</Text>
          <Text>Result: {safeText(latest.result)}</Text>
          <Text>Reason: {safeText(latest.reason, "No rejection reason")}</Text>
          <Text>Analyst note: {safeText(latest.analystNote, "No analyst note")}</Text>
          <Text>Object: {safeText(latest.objectType)} / {safeText(latest.objectId)}</Text>
        </>
      ) : (
        <>
          <Text>Alert threshold: {safeText(payload?.visibility?.threshold).toUpperCase()}</Text>
          <Text>Risk level: {safeText(payload?.risk?.level).toUpperCase()}</Text>
          <Text>{safeText(payload?.risk?.incidentTitle, "No saved alert")}</Text>
          <Text>{safeText(payload?.risk?.recommendation, "Run the workflow and refresh this card.")}</Text>
        </>
      )}
    </Flex>
  );
};

export default NewCard;
""")

print("OpsLens step 14 scaffold created successfully.")
print("Updated files:")
print(" - backend/app/api/v1/routes/record_risk.py")
print(" - src/app/cards/NewCard.tsx")
