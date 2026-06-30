from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Raw change-event types emitted by the pipeline poller. ``unarchived`` is a
# recovery signal the poller records but the correlator does not alert on
# (mirrors owner_reactivated).
PIPELINE_EVENT_ARCHIVED = "pipeline_archived"
PIPELINE_EVENT_UNARCHIVED = "pipeline_unarchived"
PIPELINE_EVENT_DELETED = "pipeline_deleted"
PIPELINE_EVENT_RENAMED = "pipeline_renamed"
PIPELINE_EVENT_STAGE_ADDED = "pipeline_stage_added"
PIPELINE_EVENT_STAGE_REMOVED = "pipeline_stage_removed"
PIPELINE_EVENT_STAGE_RENAMED = "pipeline_stage_renamed"
PIPELINE_EVENT_STAGE_REORDERED = "pipeline_stage_reordered"


class PipelineChangeEvent(Base):
    """One row per detected HubSpot deal pipeline / stage change.

    The diff detail (stage id, old/new labels, order) is serialized into
    ``payload_json`` so the table schema stays stable across event types,
    exactly like ``OwnerChangeEvent``. ``processed_at`` is the correlation
    cursor: NULL until the correlation engine turns it into an Alert.
    """

    __tablename__ = "pipeline_change_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pipeline_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    __table_args__ = (
        Index(
            "ix_pipeline_change_events_processing",
            "portal_id",
            "processed_at",
            "detected_at",
        ),
    )
