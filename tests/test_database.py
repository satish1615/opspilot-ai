from sqlalchemy import create_engine, inspect, text

from app.database import Base, migrate_legacy_sqlite_schema


def test_legacy_incidents_table_is_preserved_and_replaced(tmp_path):
    database_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{database_path}")

    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE incidents (
                    alert_id VARCHAR PRIMARY KEY,
                    status VARCHAR,
                    received_at VARCHAR
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO incidents (alert_id, status, received_at)
                VALUES ('legacy-alert-1', 'analysed', '2026-07-22T00:00:00Z')
                """
            )
        )

    legacy_table = migrate_legacy_sqlite_schema(legacy_engine)
    assert legacy_table is not None
    assert legacy_table.startswith("incidents_legacy_")

    Base.metadata.create_all(bind=legacy_engine)
    inspector = inspect(legacy_engine)

    assert "incidents" in inspector.get_table_names()
    assert legacy_table in inspector.get_table_names()
    assert "incident_id" in {
        column["name"] for column in inspector.get_columns("incidents")
    }

    with legacy_engine.connect() as connection:
        preserved_count = connection.execute(
            text(f'SELECT COUNT(*) FROM "{legacy_table}"')
        ).scalar_one()

    assert preserved_count == 1
