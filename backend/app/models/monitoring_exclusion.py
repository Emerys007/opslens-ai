from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


EXCLUSION_TYPE_WORKFLOW = "workflow"
EXCLUSION_TYPE_PROPERTY = "property"


class MonitoringExclusion(Base):
    __tablename__ = "monitoring_exclusions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exclusion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    exclusion_id: Mapped[str] = mapped_column(String(255), nullable=False)
    object_type_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_monitoring_exclusions_portal_type", "portal_id", "exclusion_type"),
        UniqueConstraint(
            "portal_id",
            "exclusion_type",
            "exclusion_id",
            "object_type_id",
            name="uq_monitoring_exclusions_scope",
        ),
    )
