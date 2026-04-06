import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

_engine = None
_SessionLocal = None
_initialized = False


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine():
    global _engine
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None
    if _engine is None:
        _engine = create_engine(
            _normalize_database_url(database_url),
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session() -> Optional[Session]:
    global _SessionLocal
    engine = get_engine()
    if engine is None:
        return None
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
    return _SessionLocal()


def init_db() -> bool:
    global _initialized
    engine = get_engine()
    if engine is None:
        return False
    if _initialized:
        return True
    from app.models.alert_event import AlertEvent  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _initialized = True
    return True
