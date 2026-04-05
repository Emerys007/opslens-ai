from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "opslens-api",
        "environment": settings.app_env,
        "utc_time": datetime.now(timezone.utc).isoformat(),
    }
