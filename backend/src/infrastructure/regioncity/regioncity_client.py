from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx

from domain.ports.interfaces import SecretProvider
from infrastructure.regioncity.errors import RegionCityRequestError


class RegionCityClient:
    def __init__(
        self,
        secret_provider: SecretProvider,
        base_url: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        task_type_id: int = 51,
    ) -> None:
        self._secret_provider = secret_provider
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._task_type_id = task_type_id
        self._logger = logging.getLogger(__name__)

    async def list_tasks(self, date_from: datetime, date_to: datetime) -> list[dict]:
        return await self._request(
            "/taskManagement/tasks",
            params={
                "dateFrom": date_from.isoformat(),
                "dateTo": date_to.isoformat(),
                "taskTypeIDs": str(self._task_type_id),
            },
        )

    async def get_task_detail(self, task_id: str) -> dict:
        return await self._request(f"/taskManagement/tasks/{task_id}")

    async def _request(self, path: str, params: dict | None = None) -> dict | list[dict]:
        token = self._secret_provider.get_secret("REGIONCITY_API_TOKEN")
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self._base_url}{path}"

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.get(url, headers=headers, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise RegionCityRequestError(f"Retryable status: {response.status_code}")
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                self._logger.warning("RegionCity request failed", extra={"url": url, "status": getattr(getattr(exc, 'response', None), 'status_code', None), "attempt": attempt})
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(0.2 * (attempt + 1))
        raise RegionCityRequestError(f"Request failed: {path}") from last_error
