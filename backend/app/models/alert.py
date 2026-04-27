from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
SEVERITY_CRITICAL = "critical"

ALL_SEVERITIES = (SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

STATUS_OPEN = "open"
STATUS_ACKNOWLEDGED = "acknowledged"
STATUS_RESOLVED = "resolved"

ALL_STATUSES = (STATUS_OPEN, STATUS_ACKNOWLEDGED, STATUS_RESOLVED)
ACTIVE_STATUSES = (STATUS_OPEN, STATUS_ACKNOWLEDGED)


# ---------------------------------------------------------------------------
# Source-event types
# ---------------------------------------------------------------------------

SOURCE_EVENT_PROPERTY_ARCHIVED = "property_archived"
SOURCE_EVENT_PROPERTY_TYPE_CHANGED = "property_type_changed"
SOURCE_EVENT_PROPERTY_DELETED = "property_deleted"
SOURCE_EVENT_PROPERTY_RENAMED = "property_renamed"
SOURCE_EVENT_WORKFLOW_DISABLED = "workflow_disabled"
SOURCE_EVENT_WORKFLOW_EDITED = "workflow_edited"
SOURCE_EVENT_WORKFLOW_DELETED = "workflow_deleted"
SOURCE_EVENT_WORKFLOW_CREATED = "workflow_created"
SOURCE_EVENT_LIST_ARCHIVED = "list_archived"
SOURCE_EVENT_LIST_DELETED = "list_deleted"
SOURCE_EVENT_LIST_CRITERIA_CHANGED = "list_criteria_changed"


# ---------------------------------------------------------------------------
# Source-event kinds — tells consumers which table source_event_id points into
# ---------------------------------------------------------------------------

SOURCE_KIND_WORKFLOW = "workflow_change_event"
SOURCE_KIND_PROPERTY = "property_change_event"
SOURCE_KIND_LIST = "list_change_event"


class Alert(Base):
    """One row per (portal, change signature, impacted workflow).

    Deduplicated via ``alert_signature`` — a deterministic hash of
    ``(portal_id, source_event_type, source_dependency_id, impacted_workflow_id)``.
    Repeats within the dedup window increment ``repeat_count`` rather
    than inserting a new row.

    Slack senders, ticket creators, and the LLM "plain English"
    rewriter all read from this table; the raw change events are
    consumed only by the correlation engine that produces these rows.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Deterministic dedup key. See alert_correlation._compute_signature.
    alert_signature: Mapped[str] = mapped_column(String(128), nullable=False)

    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_OPEN)

    source_event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_event_kind: Mapped[str] = mapped_column(String(64), nullable=False)

    source_dependency_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dependency_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_object_type_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    impacted_workflow_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    impacted_workflow_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # Populated by the LLM rewriter in a later task. Null on creation.
    plain_english_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )

    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_repeated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Populated by the Slack-sender / ticket-creator tasks.
    slack_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    hubspot_ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        # Dashboard read path: "give me open alerts for this portal sorted by recency."
        Index("ix_alerts_portal_status_created", "portal_id", "status", "created_at"),
        # Dedup lookup.
        Index("ix_alerts_signature", "alert_signature"),
    )
