from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineSnapshot(Base):
    """Last-known state of every HubSpot deal pipeline observed in a portal.

    One row per pipeline (mirrors the one-row-per-entity model used by every
    other snapshot table). The full ordered stage list — each stage's
    ``id``/``label``/``displayOrder`` — is serialized into ``stages_json`` so
    stage add/remove/rename/reorder changes can be detected by diffing
    successive snapshots, the same way ``ListSnapshot`` stores its nested
    criteria. Pipeline-level scalars (``label``/``is_active``) stay in columns
    so pipeline rename / archive detection is a cheap compare.
    """

    __tablename__ = "pipeline_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pipeline_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # archived pipeline -> is_active False (mirrors OwnerSnapshot.is_active).
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Serialized [{id,label,displayOrder}, ...] ordered by displayOrder.
    stages_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")

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
        UniqueConstraint(
            "portal_id", "pipeline_id", name="uq_pipeline_snapshots_portal_pipeline"
        ),
        Index("ix_pipeline_snapshots_portal_seen", "portal_id", "last_seen_at"),
    )
