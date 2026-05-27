from __future__ import annotations

import os
from pathlib import Path

from config.settings import load_settings


def _list_migrations() -> list[Path]:
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations" / "ydb"
    return sorted(migrations_dir.glob("*.sql"))


def main() -> None:
    settings = load_settings()
    use_mocks = os.getenv("USE_MOCKS", "false").lower() == "true"

    if use_mocks or settings.env == "dev":
        print("Skipping real YDB migrations because USE_MOCKS=true or ENV=dev")
        return

    if not settings.ydb_endpoint or not settings.ydb_database:
        raise SystemExit("YDB_ENDPOINT/YDB_DATABASE are required for real migrations")

    from infrastructure.ydb.client import YdbClient, YdbConfig
    from datetime import UTC, datetime

    client = YdbClient(YdbConfig(endpoint=settings.ydb_endpoint, database=settings.ydb_database))
    session = client.session()

    session.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          id Utf8,
          applied_at Timestamp,
          PRIMARY KEY (id)
        );
        """
    )

    applied_rows = session.execute("SELECT id FROM schema_migrations")
    applied_ids = {row["id"] for row in applied_rows}

    for migration in _list_migrations():
        if migration.name in applied_ids:
            print(f"skip {migration.name}")
            continue

        sql = migration.read_text(encoding="utf-8")
        print(f"apply {migration.name}")
        session.execute(sql)
        session.execute(
            "UPSERT INTO schema_migrations (id, applied_at) VALUES ($id, $applied_at)",
            {
                "$id": migration.name,
                "$applied_at": datetime.now(UTC),
            },
        )


if __name__ == "__main__":
    main()
