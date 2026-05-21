from __future__ import annotations

import asyncio
import logging

import httpx

from domain.ports.interfaces import SecretProvider
from infrastructure.max.errors import MaxImageError, MaxRequestError


class MaxClient:
    def __init__(self, secret_provider: SecretProvider, base_url: str, timeout_seconds: float = 10.0, max_retries: int = 2) -> None:
        self._secret_provider = secret_provider
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._logger = logging.getLogger(__name__)

    async def send_text(self, chat_id: str, text: str) -> None:
        await self._request("/messages/send", {"chat_id": chat_id, "text": text})

    async def send_with_image(self, chat_id: str, text: str, image_bytes: bytes | None) -> None:
        if not image_bytes:
            await self.send_text(chat_id, text)
            return
        try:
            await self._request("/messages/sendWithAttachment", {"chat_id": chat_id, "text": text, "attachment": "binary"})
        except Exception as exc:
            self._logger.warning("max_image_send_failed_fallback_to_text", extra={"chat_id": chat_id, "error": str(type(exc).__name__)})
            raise MaxImageError from exc

    async def _request(self, path: str, json_body: dict) -> dict:
        token = self._secret_provider.get_secret("MAX_BOT_TOKEN")
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self._base_url}{path}"
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    resp = await client.post(url, headers=headers, json=json_body)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise MaxRequestError(f"retryable {resp.status_code}")
                resp.raise_for_status()
                return resp.json() if resp.content else {}
            except Exception as exc:
                last_error = exc
                self._logger.warning("max_request_failed", extra={"path": path, "attempt": attempt, "status": getattr(getattr(exc,'response',None),'status_code',None)})
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(0.2 * (attempt + 1))
        raise MaxRequestError(f"MAX request failed {path}") from last_error
