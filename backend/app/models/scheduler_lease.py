from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SchedulerLease(Base):
    """A single-holder lease for cross-replica leader election. Only the holder
    whose lease is current may run the polling cycle, so multiple Render
    replicas don't each poll every portal (and double-deliver alerts).

    Naive-UTC timestamps on purpose: keeps ``expires_at <= now`` comparisons
    correct on both SQLite (tests) and Postgres without timezone ambiguity.
    """

    __tablename__ = "scheduler_leases"

    lease_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    holder: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
