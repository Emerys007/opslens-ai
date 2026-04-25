from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowSnapshot(Base):
    """Last-known state for every workflow we've observed across every portal.

    One row per (portal_id, workflow_id). Refreshed on every poll cycle:
      * `last_seen_at` is updated whenever the workflow appears in a poll.
      * `deleted_at` is set when a workflow that was previously seen is
        absent from a poll. It is cleared if the workflow reappears.

    The change-detection logic in `workflow_polling.py` compares the
    incoming HubSpot payload against the stored snapshot row; the
    snapshot row itself is the source of truth for "what we knew last
    time we polled this portal."
    """

    __tablename__ = "workflow_snapshots"

    portal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    name: Mapped[str] = mapped_column(String(512), default="")
    flow_type: Mapped[str] = mapped_column(String(64), default="")
    object_type_id: Mapped[str] = mapped_column(String(64), default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    revision_id: Mapped[str] = mapped_column(String(64), default="")

    # Full HubSpot definition (only refetched when revisionId changes).
    definition_json: Mapped[str] = mapped_column(Text, default="")
    definition_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps reported by HubSpot for the workflow itself.
    hubspot_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    hubspot_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Local observation timestamps.
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
