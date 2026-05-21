from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from config.settings import load_settings
from infrastructure.ydb.client import YdbClient, YdbConfig


def main() -> None:
    settings = load_settings()
    client = YdbClient(YdbConfig(endpoint=settings.ydb_endpoint, database=settings.ydb_database))
    session = client.session()

    migrations_dir = Path(__file__).resolve().parents[1] / "migrations" / "ydb"
    session.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version Utf8, applied_at Timestamp, PRIMARY KEY(version));"
    )
    applied_rows = session.execute("SELECT version FROM schema_migrations")
    applied = {row["version"] for row in applied_rows}

    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        if version in applied:
            continue
        session.execute(path.read_text())
        session.execute(
            "UPSERT INTO schema_migrations (version, applied_at) VALUES ($v, $t)",
            {"$v": version, "$t": datetime.now(UTC).isoformat()},
        )
        print(f"Applied migration {path.name}")


if __name__ == "__main__":
    main()
