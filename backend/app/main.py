from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config import settings
from app.core.logging import configure_logging, logger

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
    yield
    logger.info("Stopping OpsLens AI API")


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "OpsLens AI backend is running.",
        "environment": settings.app_env,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
