from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


LIST_EVENT_ARCHIVED = "list_archived"
LIST_EVENT_DELETED = "list_deleted"
LIST_EVENT_CRITERIA_CHANGED = "list_criteria_changed"
LIST_EVENT_UNARCHIVED = "list_unarchived"


class ListChangeEvent(Base):
    """One row per detected HubSpot list change."""

    __tablename__ = "list_change_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    list_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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
            "ix_list_change_events_processing",
            "portal_id",
            "processed_at",
            "detected_at",
        ),
    )
