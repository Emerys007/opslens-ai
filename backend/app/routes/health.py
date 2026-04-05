from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "opslens-api",
        "utc_time": datetime.now(timezone.utc).isoformat(),
    }
