from __future__ import annotations

import os
from typing import Protocol

from domain.ports.interfaces import SecretProvider


class LockboxClient(Protocol):
    def get_secret(self, key: str) -> str: ...


class YandexLockboxSecretProvider(SecretProvider):
    REQUIRED_KEYS = {"REGIONCITY_API_TOKEN", "MAX_BOT_TOKEN", "ADMIN_JWT_SECRET", "MAX_WEBHOOK_SECRET"}

    def __init__(self, env: str, client: LockboxClient | None = None) -> None:
        self._env = env
        self._client = client
        self._cache: dict[str, str] = {}

    def get_secret(self, key: str) -> str:
        if key not in self.REQUIRED_KEYS:
            raise ValueError(f"Unknown secret key: {key}")
        if key in self._cache:
            return self._cache[key]

        # Cloud Functions exposes explicitly bound Lockbox values through
        # environment variables without putting their values in Terraform state.
        value = os.getenv(key)
        if value:
            self._cache[key] = value
            return value

        if self._client is None:
            raise RuntimeError(f"Lockbox-bound environment variable is missing: {key}")

        value = self._client.get_secret(key)
        if not value:
            raise RuntimeError(f"Secret value is empty: {key}")
        self._cache[key] = value
        return value
