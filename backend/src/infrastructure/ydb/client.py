from __future__ import annotations

from dataclasses import dataclass


@dataclass
class YdbConfig:
    endpoint: str
    database: str


class YdbSession:
    def execute(self, query: str, parameters: dict | None = None) -> list[dict]:
        return []


class YdbClient:
    def __init__(self, config: YdbConfig) -> None:
        self.config = config

    def session(self) -> YdbSession:
        return YdbSession()
