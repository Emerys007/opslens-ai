from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Allowed values for `event_type`. Stored as a plain string column so we can
# add new event types in future tasks without a schema migration.
EVENT_TYPE_CREATED = "created"
EVENT_TYPE_DELETED = "deleted"
EVENT_TYPE_EDITED = "edited"
EVENT_TYPE_ENABLED = "enabled"
EVENT_TYPE_DISABLED = "disabled"


class WorkflowChangeEvent(Base):
    """One row per detected change to a workflow.

    This is the canonical event log that future tasks (alerting,
    dependency mapping, audit trail) will consume. Polling writes new
    rows here; nothing in this task reads them back beyond the tests.
    """

    __tablename__ = "workflow_change_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # One of EVENT_TYPE_* constants above.
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    previous_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    previous_is_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    new_is_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )

    # Set when downstream alerting/processing consumes the event.
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
