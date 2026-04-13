from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    received_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    portal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subscription_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_type_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    property_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    property_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_flag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    request_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)