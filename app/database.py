"""Database configuration and lightweight schema compatibility handling."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
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


def migrate_legacy_sqlite_schema(target_engine: Engine = engine) -> str | None:
    """Preserve an old Sprint 4 table and make room for the final schema.

    Early project versions used ``alert_id`` as the incidents table primary key.
    The final release uses ``incident_id`` and many additional fields. SQLAlchemy's
    ``create_all`` does not alter an existing table, so an upgraded local checkout
    would otherwise fail when the dashboard queries the old database.

    When that legacy shape is detected, the table is renamed instead of deleted.
    The caller can then create the final table while the old data remains preserved
    under an ``incidents_legacy_*`` name.
    """

    if target_engine.dialect.name != "sqlite":
        return None

    inspector = inspect(target_engine)
    if "incidents" not in inspector.get_table_names():
        return None

    columns = {column["name"] for column in inspector.get_columns("incidents")}
    if "incident_id" in columns:
        return None
    if "alert_id" not in columns:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    legacy_table = f"incidents_legacy_{timestamp}_{uuid4().hex[:8]}"

    with target_engine.begin() as connection:
        connection.execute(
            text(f'ALTER TABLE "incidents" RENAME TO "{legacy_table}"')
        )

    return legacy_table


def initialise_database() -> None:
    """Prepare compatibility and create database tables that do not exist."""

    from app import models  # noqa: F401  # Register models before create_all.

    migrate_legacy_sqlite_schema(engine)
    Base.metadata.create_all(bind=engine)


def database_is_healthy() -> bool:
    """Return True when a basic database query succeeds."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
