from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Allowed `dependency_type` values. Stored as a plain string column so we
# can add new categories (e.g. `survey`, `playbook`) in future weeks
# without a schema migration.
DEPENDENCY_TYPE_PROPERTY = "property"
DEPENDENCY_TYPE_LIST = "list"
DEPENDENCY_TYPE_EMAIL_TEMPLATE = "email_template"
DEPENDENCY_TYPE_OWNER = "owner"
DEPENDENCY_TYPE_UNKNOWN = "unknown"

KNOWN_DEPENDENCY_TYPES = (
    DEPENDENCY_TYPE_PROPERTY,
    DEPENDENCY_TYPE_LIST,
    DEPENDENCY_TYPE_EMAIL_TEMPLATE,
    DEPENDENCY_TYPE_OWNER,
    DEPENDENCY_TYPE_UNKNOWN,
)


class WorkflowDependency(Base):
    """One row per (portal_id, workflow_id, dependency_type, dependency_id, location).

    The dependency map is the reverse index that lets us answer
    "if property X is archived, which workflows break?" in a single
    indexed lookup. Rows are rebuilt every time a workflow's
    `revisionId` advances — see
    `app.services.dependency_mapping.rebuild_workflow_dependencies`.
    """

    __tablename__ = "workflow_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    portal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    dependency_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dependency_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # For property dependencies: the HubSpot object type id (e.g. "0-1"
    # for contact, "0-2" for company). Null for non-property
    # dependencies.
    dependency_object_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Short, human-readable identifier of where in the workflow this
    # dependency lives. Specific enough that two refs to the same
    # property at different steps are distinguishable.
    location: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    # The workflow revision this dependency was extracted from. Used by
    # the rebuild path to verify it's working with the current version.
    revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        # Reverse-index lookups: "which workflows depend on this thing?"
        Index(
            "ix_workflow_dependencies_reverse",
            "portal_id",
            "dependency_type",
            "dependency_id",
        ),
        # Forward lookups: "what does this workflow depend on?"
        Index(
            "ix_workflow_dependencies_workflow",
            "portal_id",
            "workflow_id",
        ),
    )
