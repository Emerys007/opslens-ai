from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Allowed values for ``event_type``. Stored as a plain string column so
# new event types can be added without a schema migration.
PROPERTY_EVENT_CREATED = "created"
PROPERTY_EVENT_ARCHIVED = "archived"
PROPERTY_EVENT_UNARCHIVED = "unarchived"
PROPERTY_EVENT_TYPE_CHANGED = "type_changed"
PROPERTY_EVENT_RENAMED = "renamed"
PROPERTY_EVENT_DELETED = "deleted"


class PropertyChangeEvent(Base):
    """One row per detected change to a CRM property.

    The alert correlation engine consumes these events alongside
    ``WorkflowChangeEvent`` rows to flag workflow-impacting schema
    changes.
    """

    __tablename__ = "property_change_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_type_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    property_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # One of PROPERTY_EVENT_* constants above.
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    previous_archived: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    new_archived: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    previous_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    previous_label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    new_label: Mapped[str | None] = mapped_column(String(512), nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )

    # Set when downstream alerting/processing has consumed the event.
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
