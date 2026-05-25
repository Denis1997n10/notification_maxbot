from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import UTC, datetime

@dataclass(frozen=True)
class VersionInfo:
    version: str
    build: str
    commit: str
    build_time_utc: str


def get_version_info() -> VersionInfo:
    return VersionInfo(
        version=os.getenv("APP_VERSION", "0.1.0"),
        build=os.getenv("APP_BUILD", "dev"),
        commit=os.getenv("APP_COMMIT", "unknown"),
        build_time_utc=os.getenv("APP_BUILD_TIME_UTC", datetime.now(UTC).isoformat()),
    )
