from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceInstallSession(Base):
    __tablename__ = "marketplace_install_sessions"

    install_session_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    return_url: Mapped[str] = mapped_column(Text, default="")
    tenant_context_json: Mapped[str] = mapped_column(Text, default="{}")
    partner_user_id: Mapped[str] = mapped_column(String(128), default="")
    partner_user_email: Mapped[str] = mapped_column(String(255), default="")
    requested_plan: Mapped[str] = mapped_column(String(32), default="")
    billing_interval: Mapped[str] = mapped_column(String(16), default="")
    stripe_customer_id: Mapped[str] = mapped_column(String(128), default="")
    stripe_checkout_session_id: Mapped[str] = mapped_column(String(128), default="")
    stripe_subscription_id: Mapped[str] = mapped_column(String(128), default="")
    subscription_status: Mapped[str] = mapped_column(String(32), default="pending")
    trial_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    hubspot_portal_id: Mapped[str] = mapped_column(String(64), default="")
    hub_domain: Mapped[str] = mapped_column(String(255), default="")
    bootstrap_status: Mapped[str] = mapped_column(String(32), default="pending")
    bootstrap_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    install_error: Mapped[str] = mapped_column(Text, default="")
    payment_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    oauth_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trial_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trial_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
    )
