from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PortalSetting(Base):
    __tablename__ = "portal_settings"

    portal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slack_webhook_url: Mapped[str] = mapped_column(Text, default="")
    alert_threshold: Mapped[str] = mapped_column(String(32), default="high")
    critical_workflows: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
