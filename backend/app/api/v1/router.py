from fastapi import APIRouter

from app.api.v1.routes.alerts_feed import router as alerts_feed_router
from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.record_risk import router as record_risk_router
from app.api.v1.routes.settings_store import router as settings_store_router
from app.api.v1.routes.webhooks import router as webhook_router
from app.api.v1.routes.workflow_actions import router as workflow_actions_router
from app.api.v1.routes.ticket_maintenance import router as ticket_maintenance_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhook_router)
api_router.include_router(dashboard_router)
api_router.include_router(settings_store_router)
api_router.include_router(record_risk_router)
api_router.include_router(workflow_actions_router)
api_router.include_router(alerts_feed_router)
api_router.include_router(
    ticket_maintenance_router,
    prefix="/tickets",
    tags=["ticket-maintenance"],
)
