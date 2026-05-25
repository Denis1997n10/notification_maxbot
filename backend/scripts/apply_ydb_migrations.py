from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from config.settings import load_settings
from infrastructure.ydb.client import YdbClient, YdbConfig


def main() -> None:
    settings = load_settings()
    use_mocks = os.getenv("USE_MOCKS", "false").lower() == "true"
    if use_mocks or settings.env == "dev":
        print("Skipping real YDB migrations because USE_MOCKS=true or ENV=dev")
        return

    if not settings.ydb_endpoint or not settings.ydb_database:
        raise SystemExit("YDB_ENDPOINT/YDB_DATABASE are required for real migrations")

    raise SystemExit("Real YDB migration execution is not implemented yet; set USE_MOCKS=true for dev smoke")


if __name__ == "__main__":
    main()
