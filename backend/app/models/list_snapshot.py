from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ListSnapshot(Base):
    """Last-known state for every HubSpot list observed in a portal."""

    __tablename__ = "list_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    list_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    list_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    list_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    definition_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )

    __table_args__ = (
        UniqueConstraint("portal_id", "list_id", name="uq_list_snapshots_portal_list"),
        Index("ix_list_snapshots_portal_seen", "portal_id", "last_seen_at"),
    )
