from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PropertySnapshot(Base):
    """Last-known schema state for every CRM property we've observed.

    One row per (portal_id, object_type_id, property_name). Refreshed
    on every property-poll cycle. The change-detection logic in
    ``app.services.property_polling`` compares the incoming HubSpot
    payload against this row; this row is the source of truth for
    "what we knew about this property last time we polled."

    Properties that disappear from the API response keep their snapshot
    row but get ``deleted_at`` set, so reverse queries from the
    dependency map can distinguish hard-delete from archive.
    """

    __tablename__ = "property_snapshots"

    portal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    object_type_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    property_name: Mapped[str] = mapped_column(String(255), primary_key=True)

    label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    field_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    calculated: Mapped[bool] = mapped_column(Boolean, default=False)

    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    hubspot_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    hubspot_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

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
