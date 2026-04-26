from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PortalSetting(Base):
    __tablename__ = "portal_settings"

    portal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slack_webhook_url: Mapped[str] = mapped_column(Text, default="")
    # The existing v1 column. Re-used as the v2 ``alert_severity_threshold``
    # to avoid a schema rename. Values: high / medium / low (low → all alerts
    # delivered, medium → high+medium, high → high only).
    alert_threshold: Mapped[str] = mapped_column(String(32), default="medium")
    critical_workflows: Mapped[str] = mapped_column(Text, default="")
    # v2 delivery toggles. Both default True so a freshly installed portal
    # starts receiving Slack notifications and tickets without configuration.
    slack_delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ticket_delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
