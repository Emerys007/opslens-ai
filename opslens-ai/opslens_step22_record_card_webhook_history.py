from pathlib import Path

PROJECT_ROOT = Path(r"C:\OpsLens AI\opslens-ai")
WORKSPACE_ROOT = Path(r"C:\OpsLens AI")

webhooks_path = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "webhooks.py"
card_path = PROJECT_ROOT / "src" / "app" / "cards" / "NewCard.tsx"

webhooks_content = r'''from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import base64
import hashlib
import hmac
import json
import os

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import desc

from app.db import get_session, init_db
from app.models.webhook_event import WebhookEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
WEBHOOK_LOG_FILE = DATA_DIR / "hubspot_webhook_events.jsonl"

MAX_SIGNATURE_AGE_MS = 5 * 60 * 1000

URI_DECODE_MAP = {
    "%3A": ":",
    "%2F": "/",
    "%3F": "?",
    "%40": "@",
    "%21": "!",
    "%24": "$",
    "%27": "'",
    "%28": "(",
    "%29": ")",
    "%2A": "*",
    "%2C": ",",
    "%3B": ";",
}


def _first_header_value(value: str | None) -> str:
    return str(value or "").split(",")[0].strip()


def _public_request_uri(request: Request) -> str:
    scheme = _first_header_value(request.headers.get("x-forwarded-proto")) or request.url.scheme
    host = (
        _first_header_value(request.headers.get("x-forwarded-host"))
        or _first_header_value(request.headers.get("host"))
        or request.url.netloc
    )

    path = request.scope.get("raw_path", b"").decode("utf-8") or request.url.path
    query_string = request.scope.get("query_string", b"").decode("utf-8")

    uri = f"{scheme}://{host}{path}"
    if query_string:
        uri += f"?{query_string}"

    for encoded, decoded in URI_DECODE_MAP.items():
        uri = uri.replace(encoded, decoded).replace(encoded.lower(), decoded)

    return uri


def _validate_v3_signature(request: Request, raw_body: bytes) -> dict:
    client_secret = os.getenv("HUBSPOT_CLIENT_SECRET", "").strip()
    signature = request.headers.get("x-hubspot-signature-v3", "")
    timestamp = request.headers.get("x-hubspot-request-timestamp", "")
    uri = _public_request_uri(request)

    result = {
        "enabled": True,
        "valid": False,
        "reason": "",
        "signatureVersion": "v3",
        "uri": uri,
        "timestamp": timestamp,
    }

    if not client_secret:
        result["reason"] = "HUBSPOT_CLIENT_SECRET is not configured."
        return result

    if not signature:
        result["reason"] = "Missing X-HubSpot-Signature-V3 header."
        return result

    if not timestamp:
        result["reason"] = "Missing X-HubSpot-Request-Timestamp header."
        return result

    try:
        timestamp_ms = int(timestamp)
    except ValueError:
        result["reason"] = "Invalid HubSpot timestamp."
        return result

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if abs(now_ms - timestamp_ms) > MAX_SIGNATURE_AGE_MS:
        result["reason"] = "HubSpot timestamp is older than 5 minutes."
        return result

    body_text = raw_body.decode("utf-8") if raw_body else ""
    source = f"{request.method.upper()}{uri}{body_text}{timestamp}"
    digest = hmac.new(
        client_secret.encode("utf-8"),
        source.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")

    if not hmac.compare_digest(expected_signature, signature):
        result["reason"] = "Invalid HubSpot v3 signature."
        return result

    result["valid"] = True
    return result


def _append_webhook_log(item: dict) -> None:
    with WEBHOOK_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item) + "\n")


def _ms_to_dt(value) -> datetime | None:
    try:
        if value in (None, ""):
            return None
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except Exception:
        return None


def _save_event_row(event: dict, validation: dict) -> tuple[bool, str]:
    session = None
    try:
        init_db()
        session = get_session()
        if session is None:
            return False, "DATABASE_URL not configured"

        row = WebhookEvent(
            received_at_utc=datetime.now(timezone.utc),
            portal_id=str(event.get("portalId")) if event.get("portalId") is not None else None,
            app_id=str(event.get("appId")) if event.get("appId") is not None else None,
            subscription_type=event.get("subscriptionType"),
            object_type_id=str(event.get("objectTypeId")) if event.get("objectTypeId") is not None else None,
            object_id=str(event.get("objectId")) if event.get("objectId") is not None else None,
            property_name=event.get("propertyName"),
            property_value=str(event.get("propertyValue")) if event.get("propertyValue") is not None else None,
            change_source=event.get("changeSource"),
            change_flag=event.get("changeFlag"),
            source_id=event.get("sourceId"),
            event_id=str(event.get("eventId")) if event.get("eventId") is not None else None,
            subscription_id=str(event.get("subscriptionId")) if event.get("subscriptionId") is not None else None,
            attempt_number=int(event["attemptNumber"]) if event.get("attemptNumber") is not None else None,
            occurred_at_utc=_ms_to_dt(event.get("occurredAt")),
            signature_version=validation.get("signatureVersion"),
            request_uri=validation.get("uri"),
            payload_json=json.dumps(event),
        )
        session.add(row)
        session.commit()
        return True, ""
    except Exception as exc:
        if session is not None:
            session.rollback()
        return False, str(exc)
    finally:
        if session is not None:
            session.close()


@router.post("/hubspot")
async def receive_hubspot_webhooks(request: Request):
    raw_body = await request.body()
    validation = _validate_v3_signature(request, raw_body)

    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=validation["reason"],
        )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else []
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body must be valid JSON.",
        ) from exc

    if not isinstance(payload, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body must be a JSON array.",
        )

    saved = 0
    errors: list[str] = []

    for event in payload:
        if not isinstance(event, dict):
            continue

        log_item = {
            "receivedAtUtc": datetime.now(timezone.utc).isoformat(),
            "validation": validation,
            "event": event,
        }
        _append_webhook_log(log_item)

        ok, error = _save_event_row(event, validation)
        if ok:
            saved += 1
        elif error:
            errors.append(error)

    return {
        "status": "ok",
        "message": "HubSpot webhook events received.",
        "acceptedEvents": len(payload),
        "savedEvents": saved,
        "dbErrors": errors,
        "signatureVersion": validation["signatureVersion"],
        "uriUsedForValidation": validation["uri"],
        "loggedTo": str(WEBHOOK_LOG_FILE),
    }


@router.get("/recent")
async def recent_webhooks(
    portalId: str | None = Query(default=None),
    objectId: str | None = Query(default=None),
    subscriptionType: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    session = None
    try:
        init_db()
        session = get_session()
        if session is None:
            return {
                "status": "ok",
                "dbConfigured": False,
                "events": [],
            }

        query = session.query(WebhookEvent)

        if portalId:
            query = query.filter(WebhookEvent.portal_id == str(portalId))

        if objectId:
            query = query.filter(WebhookEvent.object_id == str(objectId))

        if subscriptionType:
            query = query.filter(WebhookEvent.subscription_type == str(subscriptionType))

        rows = (
            query.order_by(desc(WebhookEvent.received_at_utc))
            .limit(limit)
            .all()
        )

        events = []
        for row in rows:
            events.append(
                {
                    "receivedAtUtc": row.received_at_utc.isoformat() if row.received_at_utc else None,
                    "portalId": row.portal_id,
                    "appId": row.app_id,
                    "subscriptionType": row.subscription_type,
                    "objectTypeId": row.object_type_id,
                    "objectId": row.object_id,
                    "propertyName": row.property_name,
                    "propertyValue": row.property_value,
                    "changeSource": row.change_source,
                    "changeFlag": row.change_flag,
                    "sourceId": row.source_id,
                    "eventId": row.event_id,
                    "subscriptionId": row.subscription_id,
                    "attemptNumber": row.attempt_number,
                    "occurredAtUtc": row.occurred_at_utc.isoformat() if row.occurred_at_utc else None,
                }
            )

        return {
            "status": "ok",
            "dbConfigured": True,
            "count": len(events),
            "events": events,
        }
    finally:
        if session is not None:
            session.close()
'''

card_content = r'''import React, { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Divider,
  Flex,
  Text,
  hubspot,
} from "@hubspot/ui-extensions";

const BACKEND_BASE_URL = "https://api.app-sync.com";

hubspot.extend(({ context }) => {
  return <NewCard context={context} />;
});

type RecordRiskResponse = {
  alertThreshold?: string;
  visibleAtThreshold?: boolean;
  risk?: {
    level?: string;
    incidentTitle?: string;
    affectedWorkflows?: number;
    recommendation?: string;
  };
  latestSavedAlert?: {
    receivedAtUtc?: string;
    workflowId?: string;
    callbackId?: string;
    result?: string;
    reason?: string;
    analystNote?: string;
    objectType?: string;
    objectId?: string;
    severity?: string;
    deliveryStatus?: string;
  };
};

type WebhookEvent = {
  receivedAtUtc?: string;
  portalId?: string;
  subscriptionType?: string;
  objectTypeId?: string | null;
  objectId?: string;
  propertyName?: string | null;
  propertyValue?: string | null;
  changeSource?: string | null;
  sourceId?: string | null;
  eventId?: string | null;
  occurredAtUtc?: string | null;
};

type RecentWebhooksResponse = {
  status?: string;
  dbConfigured?: boolean;
  count?: number;
  events?: WebhookEvent[];
};

const NewCard = ({ context }: { context: any }) => {
  const recordId = useMemo(
    () => String(context?.crm?.objectId ?? context?.objectId ?? ""),
    [context]
  );
  const objectTypeId = useMemo(
    () => String(context?.crm?.objectTypeId ?? context?.objectTypeId ?? ""),
    [context]
  );

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [recordRisk, setRecordRisk] = useState<RecordRiskResponse | null>(null);
  const [recentWebhookActivity, setRecentWebhookActivity] = useState<WebhookEvent[]>([]);

  const formatDate = (value?: string | null) => {
    if (!value) return "-";
    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  };

  const loadRecordRisk = async () => {
    const response = await hubspot.fetch(
      `${BACKEND_BASE_URL}/api/v1/records/contact-risk?recordId=${encodeURIComponent(recordId)}&objectTypeId=${encodeURIComponent(objectTypeId)}`,
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Record risk request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecordRiskResponse;
    setRecordRisk(data);
  };

  const loadRecentWebhooks = async () => {
    const response = await hubspot.fetch(
      `${BACKEND_BASE_URL}/api/v1/webhooks/recent?objectId=${encodeURIComponent(recordId)}&limit=5`,
      {
        method: "GET",
        timeout: 5000,
      }
    );

    if (!response.ok) {
      throw new Error(`Webhook history request failed with status ${response.status}`);
    }

    const data = (await response.json()) as RecentWebhooksResponse;
    setRecentWebhookActivity(Array.isArray(data?.events) ? data.events : []);
  };

  const refreshAll = async () => {
    if (!recordId) {
      setErrorMessage("No recordId was provided by HubSpot context.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setErrorMessage("");

    try {
      await Promise.all([loadRecordRisk(), loadRecentWebhooks()]);
    } catch (err) {
      console.error("New Card refresh failed", err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll().catch((err) =>
      console.error("Unexpected New Card load error", err)
    );
  }, [recordId, objectTypeId]);

  const latestSavedAlert = recordRisk?.latestSavedAlert;

  return (
    <Flex direction="column" gap="medium">
      <Box>
        <Text format={{ fontWeight: "bold" }}>OpsLens AI</Text>
        <Text>
          This record card now reads the latest saved alert and the most recent webhook history for this record.
        </Text>
      </Box>

      <Button
        onClick={() => {
          refreshAll().catch((err) =>
            console.error("Unexpected New Card refresh error", err)
          );
        }}
      >
        Refresh record risk
      </Button>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Card status</Text>
        <Text>{loading ? "Loading..." : "Ready"}</Text>
        <Text>{errorMessage ? `Error: ${errorMessage}` : "No card fetch error detected."}</Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Latest saved alert</Text>
        <Text>Alert threshold: {String(recordRisk?.alertThreshold ?? "-")}</Text>
        <Text>Risk level: {String(recordRisk?.risk?.level ?? "-").toUpperCase()}</Text>
        <Text>Visible at threshold: {String(recordRisk?.visibleAtThreshold ?? "-")}</Text>
        <Text>Latest event at: {formatDate(latestSavedAlert?.receivedAtUtc)}</Text>
        <Text>Workflow ID: {String(latestSavedAlert?.workflowId ?? "-")}</Text>
        <Text>Callback ID: {String(latestSavedAlert?.callbackId ?? "-")}</Text>
        <Text>Result: {String(latestSavedAlert?.result ?? "-")}</Text>
        <Text>Reason: {String(latestSavedAlert?.reason ?? "-")}</Text>
        <Text>Analyst note: {String(latestSavedAlert?.analystNote ?? "-")}</Text>
        <Text>
          Object: {String(latestSavedAlert?.objectType ?? "-")} / {String(latestSavedAlert?.objectId ?? "-")}
        </Text>
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Recent webhook activity for this record</Text>
        {recentWebhookActivity.length === 0 ? (
          <Text>No recent webhook events found for this record.</Text>
        ) : (
          <Flex direction="column" gap="small">
            {recentWebhookActivity.map((event, idx) => (
              <Box key={event?.eventId ?? `${event?.subscriptionType ?? "event"}-${idx}`}>
                <Text>
                  {String(event?.subscriptionType ?? "-")} on object {String(event?.objectId ?? "-")}
                </Text>
                <Text>Received: {formatDate(event?.receivedAtUtc)}</Text>
                <Text>Occurred: {formatDate(event?.occurredAtUtc)}</Text>
                <Text>Property: {String(event?.propertyName ?? "-")}</Text>
                <Text>Value: {String(event?.propertyValue ?? "-")}</Text>
                <Text>Change source: {String(event?.changeSource ?? "-")}</Text>
                <Text>Source ID: {String(event?.sourceId ?? "-")}</Text>
                <Text>Event ID: {String(event?.eventId ?? "-")}</Text>
              </Box>
            ))}
          </Flex>
        )}
      </Box>

      <Divider />

      <Box>
        <Text format={{ fontWeight: "bold" }}>Debug context</Text>
        <Text>Record ID: {recordId || "unknown"}</Text>
        <Text>Object type ID: {objectTypeId || "unknown"}</Text>
        <Text>Portal ID: {String(context?.portal?.id ?? "unknown")}</Text>
        <Text>User ID: {String(context?.user?.id ?? "unknown")}</Text>
        <Text>User Email: {String(context?.user?.email ?? "unknown")}</Text>
      </Box>
    </Flex>
  );
};

export default NewCard;
'''

webhooks_path.write_text(webhooks_content, encoding="utf-8")
card_path.write_text(card_content, encoding="utf-8")

print(f"Updated backend route: {webhooks_path}")
print(f"Updated record card: {card_path}")