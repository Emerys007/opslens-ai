"""Portal data lifecycle — delete a portal's stored data.

Used for uninstall / "delete my data" (GDPR) requests so OpsLens does not
retain a customer's CRM-derived data forever. Operational data (snapshots,
change events, alerts, dependencies, settings, exclusions, webhook events) is
always purged; identity/billing rows (installation, entitlement, install
sessions) are purged only when ``include_billing`` is set, so an accidental
uninstall doesn't destroy the billing record.

The deletion is atomic: either every table is cleared and committed, or
nothing is (rollback + raise).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.models.email_template_change_event import EmailTemplateChangeEvent
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.models.hubspot_installation import HubSpotInstallation
from app.models.list_change_event import ListChangeEvent
from app.models.list_snapshot import ListSnapshot
from app.models.marketplace_install_session import MarketplaceInstallSession
from app.models.monitoring_exclusion import MonitoringExclusion
from app.models.owner_change_event import OwnerChangeEvent
from app.models.owner_snapshot import OwnerSnapshot
from app.models.portal_entitlement import PortalEntitlement
from app.models.portal_setting import PortalSetting
from app.models.property_change_event import PropertyChangeEvent
from app.models.property_snapshot import PropertySnapshot
from app.models.webhook_event import WebhookEvent
from app.models.workflow_change_event import WorkflowChangeEvent
from app.models.workflow_dependency import WorkflowDependency
from app.models.workflow_snapshot import WorkflowSnapshot

logger = logging.getLogger(__name__)

# (model, portal-id column name). Most use ``portal_id``; a few differ.
_OPERATIONAL_MODELS = [
    (WorkflowSnapshot, "portal_id"),
    (PropertySnapshot, "portal_id"),
    (ListSnapshot, "portal_id"),
    (EmailTemplateSnapshot, "portal_id"),
    (OwnerSnapshot, "portal_id"),
    (WorkflowChangeEvent, "portal_id"),
    (PropertyChangeEvent, "portal_id"),
    (ListChangeEvent, "portal_id"),
    (EmailTemplateChangeEvent, "portal_id"),
    (OwnerChangeEvent, "portal_id"),
    (Alert, "portal_id"),
    (AlertEvent, "portal_id"),
    (WorkflowDependency, "portal_id"),
    (MonitoringExclusion, "portal_id"),
    (PortalSetting, "portal_id"),
    (WebhookEvent, "portal_id"),
]

_BILLING_MODELS = [
    (PortalEntitlement, "portal_id"),
    (MarketplaceInstallSession, "hubspot_portal_id"),
    (HubSpotInstallation, "portal_id"),
]


def purge_portal_data(
    session: Session, portal_id: str, *, include_billing: bool = False
) -> dict[str, int]:
    """Delete all stored rows for ``portal_id``. Returns ``{table: rows_deleted}``."""
    portal_id = str(portal_id or "").strip()
    if not portal_id:
        raise ValueError("portal_id is required.")

    models = list(_OPERATIONAL_MODELS)
    if include_billing:
        models += _BILLING_MODELS

    deleted: dict[str, int] = {}
    try:
        for model, column in models:
            count = (
                session.query(model)
                .filter(getattr(model, column) == portal_id)
                .delete(synchronize_session=False)
            )
            deleted[model.__tablename__] = int(count or 0)
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("portal_purge.failed", extra={"portal_id": portal_id})
        raise

    logger.info(
        "portal_purge.completed",
        extra={
            "portal_id": portal_id,
            "include_billing": include_billing,
            "rows_deleted": sum(deleted.values()),
        },
    )
    return deleted
