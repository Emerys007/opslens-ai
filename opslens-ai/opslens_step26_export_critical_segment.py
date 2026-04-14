import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://api.hubapi.com"
CONTACT_OBJECT_TYPE_ID = "0-1"
CONTACT_OBJECT_NAME = "CONTACT"
LIST_NAME = "OpsLens - Critical + Slack Sent"

EXPORT_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "createdate",
    "lastmodifieddate",
    "opslens_last_alert_at",
    "opslens_last_alert_severity",
    "opslens_last_alert_result",
    "opslens_last_alert_callback_id",
    "opslens_last_alert_workflow_id",
    "opslens_last_alert_reason",
    "opslens_last_alert_analyst_note",
    "opslens_last_alert_delivery_status",
]

EXPORTS_DIR = Path(r"C:\OpsLens AI\exports")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpsLensExport/1.0"


def get_token() -> str:
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "HUBSPOT_PRIVATE_APP_TOKEN is not set in this PowerShell session."
        )
    return token


def hs_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status_code = resp.getcode()
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return status_code, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw": raw}
        return exc.code, payload


def get_list_by_name(list_name: str) -> dict:
    encoded_name = urllib.parse.quote(list_name, safe="")
    status, payload = hs_request(
        "GET",
        f"/crm/lists/2026-03/object-type-id/{CONTACT_OBJECT_TYPE_ID}/name/{encoded_name}?includeFilters=true",
    )

    if status != 200:
        raise SystemExit(
            f"Failed to retrieve list '{list_name}': {status}\n{json.dumps(payload, indent=2)}"
        )

    list_obj = payload.get("list", {})
    if not list_obj:
        raise SystemExit(f"List '{list_name}' was found, but no list object was returned.")

    return list_obj


def start_list_export(list_id: int | str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H-%M-%S UTC")

    body = {
        "exportType": "LIST",
        "listId": int(list_id),
        "exportName": f"OpsLens Critical Slack Sent Contacts - {timestamp}",
        "format": "CSV",
        "language": "EN",
        "objectType": CONTACT_OBJECT_NAME,
        "objectProperties": EXPORT_PROPERTIES,
    }

    status, payload = hs_request("POST", "/crm/v3/exports/export/async", body)

    if status not in (200, 201, 202):
        raise SystemExit(
            f"Failed to start export: {status}\n{json.dumps(payload, indent=2)}"
        )

    export_id = str(payload.get("id", "")).strip()
    if not export_id:
        raise SystemExit(f"Export started but no export id was returned: {payload}")

    return export_id


def get_export_status(export_id: str) -> dict:
    status_code, payload = hs_request(
        "GET",
        f"/crm/v3/exports/export/async/tasks/{export_id}/status",
    )

    if status_code != 200:
        raise SystemExit(
            f"Failed while checking export status: {status_code}\n{json.dumps(payload, indent=2)}"
        )

    return payload


def poll_export(export_id: str, timeout_seconds: int = 180) -> str:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        payload = get_export_status(export_id)
        export_status = str(payload.get("status", "")).upper()

        if export_status == "COMPLETE":
            result_url = str(payload.get("result", "")).strip()
            if not result_url:
                raise SystemExit(
                    f"Export completed but no result URL was returned:\n{json.dumps(payload, indent=2)}"
                )
            return result_url

        if export_status == "CANCELED":
            raise SystemExit(
                f"Export was canceled:\n{json.dumps(payload, indent=2)}"
            )

        print(f"Export {export_id} status: {export_status or 'UNKNOWN'} ... waiting 5 seconds")
        time.sleep(5)

    raise SystemExit(f"Timed out waiting for export {export_id} to complete.")


def choose_extension(resp, download_url: str) -> str:
    content_type = ""
    try:
        content_type = resp.headers.get_content_type()
    except Exception:
        content_type = resp.headers.get("Content-Type", "")

    disposition = resp.headers.get("Content-Disposition", "")
    lowered = f"{content_type} {disposition} {download_url}".lower()

    if ".zip" in lowered or "zip" in lowered:
        return ".zip"
    return ".csv"


def attempt_download(url: str, use_auth_header: bool) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if use_auth_header:
        headers["Authorization"] = f"Bearer {get_token()}"

    req = urllib.request.Request(url, method="GET", headers=headers)

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        attempt_download.last_extension = choose_extension(resp, url)
        return data


attempt_download.last_extension = ".csv"


def download_export_with_retries(export_id: str) -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    last_error = None

    for attempt_number in range(1, 4):
        download_url = poll_export(export_id, timeout_seconds=60)
        print(f"Download attempt {attempt_number}: trying fresh export URL")

        for use_auth in (False, True):
            try:
                file_bytes = attempt_download(download_url, use_auth_header=use_auth)
                suffix = attempt_download.last_extension
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                output_path = EXPORTS_DIR / f"opslens_critical_slack_sent_contacts_{timestamp}{suffix}"
                output_path.write_bytes(file_bytes)
                return output_path
            except urllib.error.HTTPError as exc:
                last_error = exc
                print(
                    f"Download failed with HTTP {exc.code} "
                    f"(auth_header={'yes' if use_auth else 'no'})."
                )
            except Exception as exc:
                last_error = exc
                print(
                    f"Download failed ({type(exc).__name__}) "
                    f"(auth_header={'yes' if use_auth else 'no'}): {exc}"
                )

        print("Refreshing export status to request a new download URL...")
        time.sleep(2)

    raise SystemExit(f"Failed to download export after retries: {last_error}")


def main() -> None:
    print(f"Looking up segment: {LIST_NAME}")
    list_obj = get_list_by_name(LIST_NAME)

    list_id = list_obj.get("listId")
    list_size = list_obj.get("size", "unknown")

    print(f"Found listId={list_id} size={list_size}")

    export_id = start_list_export(list_id)
    print(f"Started export: exportId={export_id}")

    saved_path = download_export_with_retries(export_id)
    print(f"Saved export to: {saved_path}")


if __name__ == "__main__":
    main()