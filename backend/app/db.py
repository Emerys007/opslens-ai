import os
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

_engine = None
_SessionLocal = None


# Idempotent column additions for environments where Alembic is not in use.
# Each entry is (table_name, column_name, ddl_type_clause).
_BACKFILL_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("portal_entitlements", "trial_started_at", "TIMESTAMP WITH TIME ZONE"),
    ("portal_entitlements", "trial_expires_at", "TIMESTAMP WITH TIME ZONE"),
    ("marketplace_install_sessions", "trial_started_at", "TIMESTAMP WITH TIME ZONE"),
    ("marketplace_install_sessions", "trial_expires_at", "TIMESTAMP WITH TIME ZONE"),
)


def _backfill_column_type(engine, ddl_type_clause: str) -> str:
    # SQLite does not support `TIMESTAMP WITH TIME ZONE`; SQLAlchemy stores
    # timezone-aware datetimes in a plain TIMESTAMP column on that backend.
    if engine.dialect.name == "sqlite":
        return "TIMESTAMP"
    return ddl_type_clause


def _backfill_missing_columns(engine) -> None:
    inspector = inspect(engine)
    for table_name, column_name, ddl_type_clause in _BACKFILL_COLUMNS:
        if not inspector.has_table(table_name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table_name)}
        if column_name in existing:
            continue
        column_type = _backfill_column_type(engine, ddl_type_clause)
        with engine.begin() as connection:
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            )


def _normalize_database_url(url: str) -> str:
    url = (url or "").strip()

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


def get_engine():
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    database_url = _normalize_database_url(os.getenv("DATABASE_URL", ""))
    if not database_url:
        return None

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )

    return _engine


def init_db() -> bool:
    engine = get_engine()
    if engine is None:
        return False

    from app.models.alert import Alert  # noqa: F401
    from app.models.alert_event import AlertEvent  # noqa: F401
    from app.models.hubspot_installation import HubSpotInstallation  # noqa: F401
    from app.models.marketplace_install_session import MarketplaceInstallSession  # noqa: F401
    from app.models.portal_setting import PortalSetting  # noqa: F401
    from app.models.portal_entitlement import PortalEntitlement  # noqa: F401
    from app.models.property_change_event import PropertyChangeEvent  # noqa: F401
    from app.models.property_snapshot import PropertySnapshot  # noqa: F401
    from app.models.webhook_event import WebhookEvent  # noqa: F401
    from app.models.workflow_change_event import WorkflowChangeEvent  # noqa: F401
    from app.models.workflow_dependency import WorkflowDependency  # noqa: F401
    from app.models.workflow_snapshot import WorkflowSnapshot  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _backfill_missing_columns(engine)
    return True


def get_session() -> Optional[Session]:
    engine = get_engine()
    if engine is None or _SessionLocal is None:
        return None
    return _SessionLocal()
