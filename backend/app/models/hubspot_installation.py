from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HubSpotInstallation(Base):
    __tablename__ = "hubspot_installations"

    portal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hub_domain: Mapped[str] = mapped_column(String(255), default="")
    installing_user_email: Mapped[str] = mapped_column(String(255), default="")
    user_id: Mapped[str] = mapped_column(String(64), default="")
    app_id: Mapped[str] = mapped_column(String(64), default="")

    access_token: Mapped[str] = mapped_column(Text, default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    token_type: Mapped[str] = mapped_column(String(64), default="Bearer")
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
    )