from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PortalEntitlement(Base):
    __tablename__ = "portal_entitlements"

    portal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    install_session_id: Mapped[str] = mapped_column(String(96), default="")
    plan: Mapped[str] = mapped_column(String(32), default="")
    billing_interval: Mapped[str] = mapped_column(String(16), default="")
    subscription_status: Mapped[str] = mapped_column(String(32), default="pending")
    trial_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_customer_id: Mapped[str] = mapped_column(String(128), default="")
    stripe_checkout_session_id: Mapped[str] = mapped_column(String(128), default="")
    stripe_subscription_id: Mapped[str] = mapped_column(String(128), default="")
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_payment_failed_at: Mapped[datetime | None] = mapped_column(
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
