from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    received_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    callback_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    portal_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action_definition_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_definition_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    workflow_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    severity_override: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analyst_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signature_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
