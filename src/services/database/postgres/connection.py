import logging
from contextlib import contextmanager
from typing import Iterator

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import get_settings

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        logger.info("Initializing SQLAlchemy engine")
        _engine = create_engine(get_settings().database.url, pool_pre_ping=True)
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal()


@contextmanager
def session_scope(error_message: str = "Unhandled database error") -> Iterator[Session]:
    # Standardizes rollback/close around a session; callers still commit() themselves.
    # Not suited for call sites that need to swallow errors instead of raising (e.g. logout).
    session = get_session()
    try:
        yield session
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        logger.exception(error_message)
        raise HTTPException(status_code=500, detail="Internal error") from None
    finally:
        session.close()
