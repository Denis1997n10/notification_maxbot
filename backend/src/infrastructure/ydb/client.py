from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class YdbConfig:
    endpoint: str
    database: str


def _normalize_endpoint(endpoint: str) -> str:
    return endpoint if "://" in endpoint else f"grpcs://{endpoint}"


def _typed_parameters(parameters: dict[str, Any] | None) -> dict[str, Any]:
    import ydb

    return {
        name: ydb.TypedValue(value, ydb.PrimitiveType.Timestamp) if isinstance(value, datetime) else value
        for name, value in (parameters or {}).items()
    }


class YdbSession:
    def __init__(self, query_pool, scheme_pool) -> None:
        self._query_pool = query_pool
        self._scheme_pool = scheme_pool

    def execute(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        import ydb

        def _query(session) -> list[dict[str, Any]]:
            tx = session.transaction(ydb.QuerySerializableReadWrite()).begin()
            result = tx.execute(
                query,
                parameters=_typed_parameters(parameters),
                commit_tx=True,
            )
            rows: list[dict[str, Any]] = []
            for rs in result:
                for row in rs.rows:
                    rows.append(dict(row))
            return rows

        return self._query_pool.retry_operation_sync(_query)

    def execute_scheme(self, query: str) -> None:
        self._scheme_pool.retry_operation_sync(lambda session: session.execute_scheme(query))


class YdbClient:
    def __init__(self, config: YdbConfig) -> None:
        self.config = config
        import ydb

        self._driver = ydb.Driver(
            endpoint=_normalize_endpoint(config.endpoint),
            database=config.database,
            credentials=ydb.credentials_from_env_variables(),
        )
        self._driver.wait(fail_fast=True, timeout=10)
        self._query_pool = ydb.QuerySessionPool(self._driver)
        self._scheme_pool = ydb.SessionPool(self._driver)

    def session(self) -> YdbSession:
        return YdbSession(self._query_pool, self._scheme_pool)
