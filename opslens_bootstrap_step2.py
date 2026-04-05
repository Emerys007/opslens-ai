
from pathlib import Path
import textwrap
import shutil

ROOT = Path.cwd()

def write_file(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")

files = {
    "backend/app/main.py": """
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
""",
    "backend/app/api/__init__.py": "",
    "backend/app/api/v1/__init__.py": "",
    "backend/app/api/v1/router.py": """
from fastapi import APIRouter

from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.webhooks import router as webhook_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhook_router)
""",
    "backend/app/api/v1/routes/__init__.py": "",
    "backend/app/api/v1/routes/health.py": """
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
""",
    "backend/app/api/v1/routes/webhooks.py": """
from fastapi import APIRouter, Header, Request

from app.core.security import validate_hubspot_v3_signature

router = APIRouter(prefix="/webhooks/hubspot", tags=["hubspot-webhooks"])


@router.get("/test")
def hubspot_webhook_test():
    return {
        "status": "ok",
        "message": "HubSpot webhook route is wired correctly.",
    }


@router.post("/validate-demo")
async def validate_demo(
    request: Request,
    x_hubspot_signature_v3: str | None = Header(default=None),
    x_hubspot_request_timestamp: str | None = Header(default=None),
):
    raw_body = await request.body()
    is_valid = validate_hubspot_v3_signature(
        method=request.method,
        uri=str(request.url),
        body=raw_body,
        signature=x_hubspot_signature_v3,
        timestamp=x_hubspot_request_timestamp,
    )
    return {
        "received": True,
        "signature_present": bool(x_hubspot_signature_v3),
        "timestamp_present": bool(x_hubspot_request_timestamp),
        "signature_valid": is_valid,
    }
""",
    "backend/app/core/logging.py": """
import logging
import sys

LOGGER_NAME = "opslens"
logger = logging.getLogger(LOGGER_NAME)


def configure_logging() -> None:
    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
""",
    "backend/app/core/security.py": """
import base64
import hashlib
import hmac
import time
from urllib.parse import unquote, urlparse

from app.config import settings


def _normalize_uri(uri: str) -> str:
    parsed = urlparse(uri)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return unquote(normalized)


def validate_hubspot_v3_signature(
    method: str,
    uri: str,
    body: bytes,
    signature: str | None,
    timestamp: str | None,
    max_age_seconds: int = 300,
) -> bool:
    if not settings.hubspot_webhook_secret:
        return False

    if not signature or not timestamp:
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    current_millis = int(time.time() * 1000)
    if abs(current_millis - timestamp_int) > max_age_seconds * 1000:
        return False

    source = (
        method.upper()
        + _normalize_uri(uri)
        + body.decode("utf-8")
        + timestamp
    ).encode("utf-8")

    digest = hmac.new(
        settings.hubspot_webhook_secret.encode("utf-8"),
        source,
        hashlib.sha256,
    ).digest()

    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)
""",
    "backend/app/schemas/__init__.py": "",
    "backend/app/schemas/webhooks.py": """
from pydantic import BaseModel


class HubSpotWebhookValidationResult(BaseModel):
    received: bool
    signature_present: bool
    timestamp_present: bool
    signature_valid: bool
""",
}

for relative_path, content in files.items():
    write_file(relative_path, content)

env_example = ROOT / ".env.example"
env_file = ROOT / ".env"
if env_example.exists() and not env_file.exists():
    shutil.copyfile(env_example, env_file)

print("OpsLens AI step 2 scaffold created successfully.")
print(f"Project root: {ROOT}")
print()
print("Updated / created files:")
for relative_path in sorted(files.keys()):
    print(f" - {relative_path}")

if env_file.exists():
    print(" - .env")
