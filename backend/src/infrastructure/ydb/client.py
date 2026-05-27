from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class YdbConfig:
    endpoint: str
    database: str


class YdbSession:
    def __init__(self, pool) -> None:
        self._pool = pool

    def execute(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        import ydb

        def _query(session) -> list[dict[str, Any]]:
            tx = session.transaction(ydb.SerializableReadWrite()).begin()
            result = tx.execute(
                query,
                parameters=parameters or {},
                commit_tx=True,
            )
            rows: list[dict[str, Any]] = []
            for rs in result:
                for row in rs.rows:
                    rows.append(dict(row))
            return rows

        return self._pool.retry_operation_sync(_query)


class YdbClient:
    def __init__(self, config: YdbConfig) -> None:
        self.config = config
        import ydb

        self._driver = ydb.Driver(
            endpoint=config.endpoint,
            database=config.database,
            credentials=ydb.credentials_from_env_variables(),
        )
        self._driver.wait(fail_fast=True, timeout=10)
        self._pool = ydb.QuerySessionPool(self._driver)

    def session(self) -> YdbSession:
        return YdbSession(self._pool)
