"""Per-portal HubSpot deal-pipeline poller.

Deal pipelines and their ordered stages drive every deal-based workflow and
pipeline report. A renamed/deleted/reordered stage or an archived pipeline
silently breaks that automation, so each cycle we snapshot pipeline + stage
state and emit ``PipelineChangeEvent`` rows on any structural drift.

Mirrors ``owner_polling`` exactly for HTTP/auth/error handling and the
snapshot/diff/deleted-sweep lifecycle. The one genuinely new piece is the
nested stage diff (no other category has a child collection). Reading deal
pipelines needs only ``crm.schemas.deals.read``, which the app already
requests — so this works on the next poll for every connected portal with no
reinstall.

Standard library only; the access-token getter is imported into this module's
namespace so tests can patch it. First poll of a portal is silent (baseline).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.pipeline_change_event import (
    PIPELINE_EVENT_ARCHIVED,
    PIPELINE_EVENT_DELETED,
    PIPELINE_EVENT_RENAMED,
    PIPELINE_EVENT_STAGE_ADDED,
    PIPELINE_EVENT_STAGE_REMOVED,
    PIPELINE_EVENT_STAGE_RENAMED,
    PIPELINE_EVENT_STAGE_REORDERED,
    PIPELINE_EVENT_UNARCHIVED,
    PipelineChangeEvent,
)
from app.models.pipeline_snapshot import PipelineSnapshot
from app.services.hubspot_oauth import get_portal_access_token

logger = logging.getLogger(__name__)

HUBSPOT_PIPELINES_URL = "https://api.hubapi.com/crm/v3/pipelines/deals"
DEFAULT_PAGE_LIMIT = 100
MAX_PAGES = 50


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


# ---------------------------------------------------------------------------
# HTTP — identical pattern to owner_polling
# ---------------------------------------------------------------------------


def _http_get_json(url: str, access_token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response_body = response.read().decode("utf-8", errors="replace")
        return json.loads(response_body) if response_body.strip() else {}


def _fetch_page(access_token: str, params: dict[str, Any], http_client=None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{HUBSPOT_PIPELINES_URL}?{query}"
    if http_client is None:
        return _http_get_json(url, access_token)
    if hasattr(http_client, "get_json"):
        return http_client.get_json(url, access_token)
    return http_client(url, access_token)


def _pipeline_pages(access_token: str, *, archived: bool, http_client=None) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    after = ""
    for _ in range(MAX_PAGES):
        params: dict[str, Any] = {
            "limit": str(DEFAULT_PAGE_LIMIT),
            "archived": "true" if archived else "false",
        }
        if after:
            params["after"] = after
        payload = _fetch_page(access_token, params, http_client)
        results = payload.get("results") or []
        if isinstance(results, list):
            collected.extend(item for item in results if isinstance(item, dict))
        paging = payload.get("paging") or {}
        next_block = paging.get("next") if isinstance(paging, dict) else {}
        next_after = _clean((next_block or {}).get("after"))
        if not next_after or next_after == after:
            break
        after = next_after
    else:
        logger.warning(
            "pipeline_polling hit MAX_PAGES; truncating",
            extra={"max_pages": MAX_PAGES, "archived": archived},
        )
    return collected


def _classify_http_error(http_err: urllib.error.HTTPError) -> tuple[str, str]:
    status = int(getattr(http_err, "code", 0) or 0)
    if status == 401:
        return "skipped", "hubspot_unauthorized"
    if status == 429:
        return "error", "hubspot_rate_limited"
    if 500 <= status < 600:
        return "error", f"hubspot_server_error_{status}"
    return "error", f"hubspot_http_error_{status}"


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def _pipeline_id(item: dict[str, Any]) -> str:
    return _clean(item.get("id") or item.get("pipelineId"))


def _normalize_archived(item: dict[str, Any], *, fallback: bool = False) -> bool:
    raw = item.get("archived")
    if raw is None:
        raw = item.get("isArchived")
    if raw is None:
        return fallback
    return bool(raw)


def _normalize_stages(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Ordered, minimal stage shape for diffing: [{id,label,displayOrder}]."""
    stages = item.get("stages") or []
    out: list[dict[str, Any]] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        stage_id = _clean(stage.get("id") or stage.get("stageId"))
        if not stage_id:
            continue
        order = stage.get("displayOrder")
        out.append(
            {
                "id": stage_id,
                "label": _clean(stage.get("label")),
                "displayOrder": order if isinstance(order, int) else None,
            }
        )
    out.sort(key=lambda s: (s["displayOrder"] is None, s["displayOrder"] or 0, s["id"]))
    return out


def _stages_json(stages: list[dict[str, Any]]) -> str:
    return json.dumps(stages, separators=(",", ":"), sort_keys=True)


def _event_payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _record_event(
    session: Session,
    *,
    portal_id: str,
    pipeline_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        PipelineChangeEvent(
            portal_id=portal_id,
            pipeline_id=pipeline_id,
            event_type=event_type,
            payload_json=_event_payload_json(payload),
        )
    )


def _fetch_pipelines(access_token: str, http_client=None) -> list[dict[str, Any]]:
    """Active + archived merged into one dict keyed by id (archived wins),
    so an archive shows up in the same cycle — mirrors owner polling."""
    active = _pipeline_pages(access_token, archived=False, http_client=http_client)
    archived = _pipeline_pages(access_token, archived=True, http_client=http_client)
    merged: dict[str, dict[str, Any]] = {}
    for item in active:
        pid = _pipeline_id(item)
        if pid:
            merged[pid] = {**item, "archived": _normalize_archived(item)}
    for item in archived:
        pid = _pipeline_id(item)
        if pid:
            merged[pid] = {**item, "archived": _normalize_archived(item, fallback=True)}
    return list(merged.values())


# ---------------------------------------------------------------------------
# Stage diff
# ---------------------------------------------------------------------------


def _diff_stages(prev: list[dict], curr: list[dict]) -> dict[str, Any]:
    """added / removed / renamed (id,from,to) and a reordered bool over the
    surviving (common) stage ids, so an add/remove doesn't read as a reorder."""
    prev_by_id = {s["id"]: s for s in prev if s.get("id")}
    curr_by_id = {s["id"]: s for s in curr if s.get("id")}

    added = [curr_by_id[i] for i in curr_by_id if i not in prev_by_id]
    removed = [prev_by_id[i] for i in prev_by_id if i not in curr_by_id]
    renamed = [
        {"id": i, "from": prev_by_id[i]["label"], "to": curr_by_id[i]["label"]}
        for i in curr_by_id
        if i in prev_by_id and prev_by_id[i]["label"] != curr_by_id[i]["label"]
    ]
    prev_common = [s["id"] for s in prev if s.get("id") in curr_by_id]
    curr_common = [s["id"] for s in curr if s.get("id") in prev_by_id]
    reordered = prev_common != curr_common
    return {
        "added": added,
        "removed": removed,
        "renamed": renamed,
        "reordered": reordered,
        "prev_order": prev_common,
        "curr_order": curr_common,
    }


# ---------------------------------------------------------------------------
# Main poller
# ---------------------------------------------------------------------------


def poll_portal_pipelines(
    session: Session,
    portal_id: str,
    http_client=None,
) -> dict[str, Any]:
    """Poll HubSpot deal pipelines for one portal; emit pipeline/stage events."""
    portal_key = _clean(portal_id)
    if not portal_key:
        raise ValueError("portal_id is required.")

    summary: dict[str, Any] = {
        "portalId": portal_key,
        "status": "ok",
        "polled": 0,
        "events_emitted": 0,
        "archivedEvents": 0,
        "unarchivedEvents": 0,
        "deletedEvents": 0,
        "renamedEvents": 0,
        "stageAddedEvents": 0,
        "stageRemovedEvents": 0,
        "stageRenamedEvents": 0,
        "stageReorderedEvents": 0,
        "errors": [],
    }

    try:
        access_token = get_portal_access_token(session, portal_key)
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "skipped"
        summary["reason"] = f"no_access_token: {exc}"
        return summary

    try:
        pipelines = _fetch_pipelines(access_token, http_client)
    except urllib.error.HTTPError as http_err:
        status, reason = _classify_http_error(http_err)
        summary["status"] = status
        summary["reason"] = reason
        summary["errors"].append({"status": status, "reason": reason})
        return summary
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "error"
        summary["reason"] = f"transport_error: {exc}"
        summary["errors"].append({"status": "error", "reason": summary["reason"]})
        return summary

    summary["polled"] = len(pipelines)
    now = _utc_now()
    seen_pipeline_ids: set[str] = set()

    for item in pipelines:
        pipeline_id = _pipeline_id(item)
        if not pipeline_id:
            continue
        seen_pipeline_ids.add(pipeline_id)

        label = _clean(item.get("label")) or None
        is_active = not _normalize_archived(item)
        order = item.get("displayOrder")
        display_order = order if isinstance(order, int) else None
        stages = _normalize_stages(item)
        stages_json = _stages_json(stages)

        snapshot = (
            session.query(PipelineSnapshot)
            .filter(
                PipelineSnapshot.portal_id == portal_key,
                PipelineSnapshot.pipeline_id == pipeline_id,
            )
            .one_or_none()
        )

        # First sight: seed snapshot silently (baseline), no events — owner parity.
        if snapshot is None:
            session.add(
                PipelineSnapshot(
                    portal_id=portal_key,
                    pipeline_id=pipeline_id,
                    label=label,
                    display_order=display_order,
                    is_active=is_active,
                    stages_json=stages_json,
                    last_seen_at=now,
                )
            )
            continue

        previous_active = bool(snapshot.is_active)
        prev_label = snapshot.label
        try:
            prev_stages = json.loads(snapshot.stages_json or "[]")
        except Exception:  # noqa: BLE001
            prev_stages = []
        if not isinstance(prev_stages, list):
            prev_stages = []

        if snapshot.deleted_at is not None:
            snapshot.deleted_at = None  # resurrection (mirror owners)

        # Pipeline archived / unarchived (active-flag transition).
        if previous_active and not is_active:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=pipeline_id,
                event_type=PIPELINE_EVENT_ARCHIVED,
                payload={"pipeline_id": pipeline_id, "label": label},
            )
            summary["archivedEvents"] += 1
        elif is_active and not previous_active:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=pipeline_id,
                event_type=PIPELINE_EVENT_UNARCHIVED,
                payload={"pipeline_id": pipeline_id, "label": label},
            )
            summary["unarchivedEvents"] += 1

        # Pipeline renamed.
        if prev_label != label:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=pipeline_id,
                event_type=PIPELINE_EVENT_RENAMED,
                payload={
                    "pipeline_id": pipeline_id,
                    "previous_label": prev_label,
                    "new_label": label,
                },
            )
            summary["renamedEvents"] += 1

        # Stage-level diffs.
        diff = _diff_stages(prev_stages, stages)
        for stage in diff["added"]:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=pipeline_id,
                event_type=PIPELINE_EVENT_STAGE_ADDED,
                payload={
                    "pipeline_id": pipeline_id,
                    "stage_id": stage["id"],
                    "stage_label": stage["label"],
                },
            )
            summary["stageAddedEvents"] += 1
        for stage in diff["removed"]:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=pipeline_id,
                event_type=PIPELINE_EVENT_STAGE_REMOVED,
                payload={
                    "pipeline_id": pipeline_id,
                    "stage_id": stage["id"],
                    "stage_label": stage["label"],
                },
            )
            summary["stageRemovedEvents"] += 1
        for renamed in diff["renamed"]:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=pipeline_id,
                event_type=PIPELINE_EVENT_STAGE_RENAMED,
                payload={
                    "pipeline_id": pipeline_id,
                    "stage_id": renamed["id"],
                    "previous_label": renamed["from"],
                    "new_label": renamed["to"],
                },
            )
            summary["stageRenamedEvents"] += 1
        if diff["reordered"]:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=pipeline_id,
                event_type=PIPELINE_EVENT_STAGE_REORDERED,
                payload={
                    "pipeline_id": pipeline_id,
                    "previous_order": diff["prev_order"],
                    "new_order": diff["curr_order"],
                },
            )
            summary["stageReorderedEvents"] += 1

        # Upsert snapshot (always, on the existing path).
        snapshot.label = label
        snapshot.display_order = display_order
        snapshot.is_active = is_active
        snapshot.stages_json = stages_json
        snapshot.last_seen_at = now
        snapshot.updated_at = now

    # Deleted sweep: a live snapshot not seen this cycle => pipeline_deleted.
    # Guard against a false mass-delete: a deals portal ALWAYS has at least the
    # un-deletable "default" pipeline, so a zero-result fetch is a transient API
    # glitch, not "every pipeline was deleted". Skip the sweep entirely rather
    # than tombstone every snapshot and storm Slack with bogus delete alerts.
    if seen_pipeline_ids:
        missing_pipelines = (
            session.query(PipelineSnapshot)
            .filter(
                PipelineSnapshot.portal_id == portal_key,
                PipelineSnapshot.deleted_at.is_(None),
                ~PipelineSnapshot.pipeline_id.in_(seen_pipeline_ids),
            )
            .all()
        )
        for missing in missing_pipelines:
            _record_event(
                session,
                portal_id=portal_key,
                pipeline_id=missing.pipeline_id,
                event_type=PIPELINE_EVENT_DELETED,
                payload={"pipeline_id": missing.pipeline_id, "label": missing.label},
            )
            missing.deleted_at = now
            missing.updated_at = now
            summary["deletedEvents"] += 1

    summary["events_emitted"] = (
        int(summary["archivedEvents"])
        + int(summary["unarchivedEvents"])
        + int(summary["deletedEvents"])
        + int(summary["renamedEvents"])
        + int(summary["stageAddedEvents"])
        + int(summary["stageRemovedEvents"])
        + int(summary["stageRenamedEvents"])
        + int(summary["stageReorderedEvents"])
    )
    session.commit()
    return summary
