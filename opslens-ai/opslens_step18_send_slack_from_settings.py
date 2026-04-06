from pathlib import Path

PROJECT_ROOT = Path.cwd()
WORKSPACE_ROOT = PROJECT_ROOT.parent
ROUTE_FILE = WORKSPACE_ROOT / "backend" / "app" / "api" / "v1" / "routes" / "workflow_actions.py"

if not ROUTE_FILE.exists():
    raise SystemExit(f"Route file not found: {ROUTE_FILE}")

text = ROUTE_FILE.read_text(encoding="utf-8")


def ensure_line_after(source: str, anchor: str, line_to_add: str) -> str:
    if line_to_add in source:
        return source
    if anchor not in source:
        raise SystemExit(f"Anchor not found while adding import: {anchor}")
    return source.replace(anchor, anchor + line_to_add + "\n", 1)


# Imports
text = ensure_line_after(text, "import json\n", "import urllib.error")
text = ensure_line_after(text, "import urllib.error\n", "import urllib.request")
text = ensure_line_after(text, "from fastapi import APIRouter, Request\n", "from app.db import get_session, init_db")
text = ensure_line_after(text, "from app.db import get_session, init_db\n", "from app.models.portal_setting import PortalSetting")

HELPERS = '''
# STEP18_SLACK_HELPERS_START
SEVERITY_RANK = {
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def _normalize_slack_severity(value: str) -> str:
    value = str(value or "").strip().lower()
    if value in SEVERITY_RANK:
        return value
    return "high"


def _should_send_to_slack(event_severity: str, threshold: str) -> bool:
    return SEVERITY_RANK[_normalize_slack_severity(event_severity)] >= SEVERITY_RANK[_normalize_slack_severity(threshold)]


def _load_portal_settings_from_db(portal_id: str) -> dict:
    session = None
    try:
        if not init_db():
            return {}

        session = get_session()
        if session is None:
            return {}

        row = (
            session.query(PortalSetting)
            .filter(PortalSetting.portal_id == str(portal_id))
            .order_by(PortalSetting.updated_at_utc.desc())
            .first()
        )

        if row is None:
            return {}

        return {
            "slackWebhookUrl": getattr(row, "slack_webhook_url", "") or "",
            "alertThreshold": getattr(row, "alert_threshold", "high") or "high",
            "criticalWorkflows": getattr(row, "critical_workflows", "") or "",
        }
    except Exception:
        return {}
    finally:
        if session is not None:
            session.close()


def _send_slack_webhook(webhook_url: str, text: str) -> dict:
    body = json.dumps({"text": text}).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            response_body = response.read().decode("utf-8", errors="replace")
            return {
                "ok": 200 <= status_code < 300,
                "statusCode": status_code,
                "body": response_body,
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = str(exc)

        return {
            "ok": False,
            "statusCode": exc.code,
            "body": error_body,
            "error": error_body or str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "statusCode": None,
            "body": "",
            "error": str(exc),
        }


def _build_slack_message(details: dict, portal_id: str, severity: str) -> str:
    workflow_id = str(details.get("workflowId", "unknown"))
    object_type = str(details.get("objectType", "unknown"))
    object_id = str(details.get("objectId", "unknown"))
    callback_id = str(details.get("callbackId", "") or "")
    analyst_note = str(details.get("analystNote", "") or "").strip()

    lines = [
        "OpsLens alert received",
        f"Severity: {severity.upper()}",
        f"Portal ID: {portal_id}",
        f"Workflow ID: {workflow_id}",
        f"Object: {object_type} / {object_id}",
    ]

    if callback_id:
        lines.append(f"Callback ID: {callback_id}")

    if analyst_note:
        lines.append(f"Analyst note: {analyst_note}")

    return "\\n".join(lines)
# STEP18_SLACK_HELPERS_END
'''.strip("\n")

if "# STEP18_SLACK_HELPERS_START" not in text:
    decorator_anchor = '@router.post("/notify")'
    if decorator_anchor not in text:
        raise SystemExit('Could not find @router.post("/notify") in workflow_actions.py')
    text = text.replace(decorator_anchor, HELPERS + "\n\n\n" + decorator_anchor, 1)

SLACK_RUNTIME = '''
    # STEP18_SLACK_RUNTIME_START
    slack_attempted = False
    slack_sent = False
    slack_status_code = None
    slack_error = ""
    slack_threshold = "high"
    slack_webhook_configured = False

    try:
        portal_id_for_slack = str(
            request.query_params.get("portalId")
            or details.get("portalId")
            or "not-provided"
        ).strip()

        portal_settings = _load_portal_settings_from_db(portal_id_for_slack)
        slack_webhook_url = str(portal_settings.get("slackWebhookUrl", "") or "").strip()
        slack_threshold = _normalize_slack_severity(portal_settings.get("alertThreshold", "high"))
        slack_webhook_configured = bool(slack_webhook_url)

        raw_severity = (
            details.get("severityOverride")
            or details.get("severity")
            or request.query_params.get("severityOverride")
            or "high"
        )

        if str(raw_severity or "").strip().lower() == "use_settings":
            incoming_severity = slack_threshold
        else:
            incoming_severity = _normalize_slack_severity(raw_severity)

        if slack_webhook_url and _should_send_to_slack(incoming_severity, slack_threshold):
            slack_attempted = True
            slack_text = _build_slack_message(details, portal_id_for_slack, incoming_severity)
            slack_result = _send_slack_webhook(slack_webhook_url, slack_text)
            slack_sent = bool(slack_result["ok"])
            slack_status_code = slack_result["statusCode"]
            slack_error = str(slack_result["error"] or "")
    except Exception as exc:
        slack_error = str(exc)
    # STEP18_SLACK_RUNTIME_END
'''.strip("\n")

success_return_anchor = '''    return {
        "status": "ok",
        "message": "Workflow action event captured by OpsLens AI.",'''

if "# STEP18_SLACK_RUNTIME_START" not in text:
    if success_return_anchor not in text:
        raise SystemExit("Could not find the success return block in workflow_actions.py")
    text = text.replace(success_return_anchor, SLACK_RUNTIME + "\n\n" + success_return_anchor, 1)

response_anchor = '        "dbError": db_error,\n'
response_addition = '''        "dbError": db_error,
        "slackAttempted": slack_attempted,
        "slackSent": slack_sent,
        "slackStatusCode": slack_status_code,
        "slackError": slack_error,
        "slackThreshold": slack_threshold,
        "slackWebhookConfigured": slack_webhook_configured,
'''

if '"slackAttempted": slack_attempted,' not in text:
    if response_anchor not in text:
        raise SystemExit('Could not find \'"dbError": db_error,\' in workflow_actions.py')
    text = text.replace(response_anchor, response_addition, 1)

ROUTE_FILE.write_text(text, encoding="utf-8")
print(f"Step 18 Slack delivery patch applied successfully: {ROUTE_FILE}")