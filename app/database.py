"""Database configuration for OpsPilot AI."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///./data/opspilot.db"
DATABASE_URL = os.getenv("OPSPILOT_DATABASE_URL", DEFAULT_DATABASE_URL)

if DATABASE_URL.startswith("sqlite:///./"):
    database_path = Path(DATABASE_URL.removeprefix("sqlite:///./"))
    database_path.parent.mkdir(parents=True, exist_ok=True)

engine_options: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
if DATABASE_URL == "sqlite://":
    engine_options["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def initialise_database() -> None:
    """Create database tables that do not already exist."""

    from app import models  # noqa: F401  # Register models before create_all.

    Base.metadata.create_all(bind=engine)


def database_is_healthy() -> bool:
    """Return True when a basic database query succeeds."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
