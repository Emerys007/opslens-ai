from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config import settings
from app.core.logging import configure_logging, logger
from app.db import get_session, init_db
from app.routes.oauth import router as oauth_router
from app.services.workflow_polling_scheduler import WorkflowPollingScheduler

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting OpsLens AI API",
        extra={
            "app_env": settings.app_env,
            "app_host": settings.app_host,
            "app_port": settings.app_port,
        },
    )

    # Make sure tables exist before the polling loop tries to write to
    # them. init_db() is idempotent and a no-op when DATABASE_URL is
    # unset (e.g. unit tests that patch state in setUp).
    try:
        init_db()
    except Exception:  # noqa: BLE001 — never block startup on DB init
        logger.exception("init_db_failed_during_startup")

    scheduler = WorkflowPollingScheduler(get_session)
    app.state.workflow_polling_scheduler = scheduler
    scheduler.start()

    try:
        yield
    finally:
        await scheduler.stop()
        logger.info("Stopping OpsLens AI API")


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Top-level OAuth routes must not sit behind /api/v1 because the configured
# HubSpot redirect URL is https://api.app-sync.com/oauth-callback
app.include_router(oauth_router)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "OpsLens AI backend is running.",
        "environment": settings.app_env,
        "docs": "/docs",
        "health": "/api/v1/health",
        "oauthStart": "/oauth/start",
        "oauthCallback": "/oauth-callback",
    }
