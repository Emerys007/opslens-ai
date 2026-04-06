import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    database_url = os.getenv("DATABASE_URL", "").strip()
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

    # Import models so they are registered with Base.metadata
    from app.models.alert_event import AlertEvent  # noqa: F401
    from app.models.portal_setting import PortalSetting  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return True


def get_session() -> Optional[Session]:
    engine = get_engine()
    if engine is None or _SessionLocal is None:
        return None
    return _SessionLocal()
