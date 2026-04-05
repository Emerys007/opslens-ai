
from pathlib import Path
import textwrap

ROOT = Path.cwd()

files = {
    ".gitignore": """
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.venv/
venv/
env/

# Environment
.env
.env.local
.env.production

# Logs
logs/
*.log

# OS / Editor
.vscode/
.idea/
.DS_Store
Thumbs.db
""",
    "README.md": """
# OpsLens AI

Local-first foundation for the OpsLens AI project.

## What this step created
- a Python backend scaffold
- config placeholders
- a health-check API
- a secure-by-default project layout

## Next steps
1. Create a virtual environment
2. Install dependencies
3. Start the local API
4. Open http://127.0.0.1:8000/health

""",
    ".env.example": """
# Copy this file to .env later
APP_NAME=OpsLens AI
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=INFO

# Fill these in later when we connect HubSpot
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
HUBSPOT_REDIRECT_URI=
HUBSPOT_APP_ID=
HUBSPOT_WEBHOOK_SECRET=
""",
    "backend/requirements.txt": """
fastapi==0.115.12
uvicorn[standard]==0.34.2
pydantic==2.11.3
pydantic-settings==2.8.1
python-dotenv==1.1.0
httpx==0.28.1
jinja2==3.1.6
""",
    "backend/app/__init__.py": "",
    "backend/app/main.py": """
from fastapi import FastAPI
from app.config import settings
from app.routes.health import router as health_router

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health_router)

@app.get("/")
def root():
    return {
        "message": "OpsLens AI backend is running.",
        "environment": settings.app_env,
        "docs": "/docs",
        "health": "/health",
    }
""",
    "backend/app/config.py": """
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "OpsLens AI"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    hubspot_redirect_uri: str = ""
    hubspot_app_id: str = ""
    hubspot_webhook_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
""",
    "backend/app/routes/__init__.py": "",
    "backend/app/routes/health.py": """
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
""",
    "backend/app/services/__init__.py": "",
    "backend/app/models/__init__.py": "",
    "backend/app/core/__init__.py": "",
    "backend/tests/__init__.py": "",
    "backend/start_local.py": """
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
""",
}

for relative_path, content in files.items():
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")

print("OpsLens AI step 1 scaffold created successfully.")
print(f"Project root: {ROOT}")
print()
print("Created files:")
for relative_path in sorted(files.keys()):
    print(f" - {relative_path}")
