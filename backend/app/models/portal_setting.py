from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, JSON, String, Text
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
    monitoring_coverage: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Pipeline routing for ticket delivery. ``opslens_pipeline_mode`` is
    # either ``"dedicated"`` (we created the OpsLens Alerts pipeline) or
    # ``"shared"`` (the portal hit the ticket-pipeline limit so we attached
    # OpsLens-prefixed stages to an existing pipeline). Stage IDs are
    # persisted so ticket creation does not need to look up the pipeline by
    # name on every request.
    opslens_pipeline_mode: Mapped[str] = mapped_column(String(16), default="dedicated")
    opslens_ticket_pipeline_id: Mapped[str] = mapped_column(String(64), default="")
    opslens_stage_new_alert_id: Mapped[str] = mapped_column(String(64), default="")
    opslens_stage_investigating_id: Mapped[str] = mapped_column(String(64), default="")
    opslens_stage_waiting_id: Mapped[str] = mapped_column(String(64), default="")
    opslens_stage_resolved_id: Mapped[str] = mapped_column(String(64), default="")
    opslens_stage_duplicate_id: Mapped[str] = mapped_column(String(64), default="")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
