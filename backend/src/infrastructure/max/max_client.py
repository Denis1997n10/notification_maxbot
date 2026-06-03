from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qs, urlparse

import httpx

from domain.ports.interfaces import SecretProvider
from infrastructure.max.errors import MaxImageError
from infrastructure.max.errors import MaxRequestError


class MaxClient:
    def __init__(self, secret_provider: SecretProvider, base_url: str, timeout_seconds: float = 10.0, max_retries: int = 2) -> None:
        self._secret_provider = secret_provider
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._logger = logging.getLogger(__name__)

    async def send_text(self, user_id: str, text: str, keyboard: list[list[dict]] | None = None) -> None:
        body: dict = {"text": text}
        if keyboard:
            body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": keyboard}}]
        await self._request("/messages", body, params={"user_id": user_id})

    async def answer_callback(self, callback_id: str, text: str, keyboard: list[list[dict]] | None = None) -> None:
        message: dict = {"text": text}
        if keyboard:
            message["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": keyboard}}]
        await self._request("/answers", {"message": message}, params={"callback_id": callback_id})

    async def send_with_image(self, user_id: str, text: str, image_bytes: bytes | None) -> None:
        if not image_bytes:
            await self.send_text(user_id, text)
            return
        try:
            token = await self._upload_image(image_bytes)
            await self._request("/messages", {"text": text, "attachments": [{"type": "image", "payload": {"token": token}}]}, params={"user_id": user_id})
        except Exception as exc:
            raise MaxImageError("MAX image send failed") from exc

    async def _upload_image(self, image_bytes: bytes) -> str:
        upload_data = await self._request("/uploads", None, params={"type": "image"})
        upload_url = upload_data.get("url")
        if not upload_url:
            raise MaxImageError("MAX upload URL is missing")
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(upload_url, files={"data": ("notification.png", image_bytes, "image/png")})
        response.raise_for_status()
        data = response.json() if response.content else {}
        token = data.get("token") or upload_data.get("token") or parse_qs(urlparse(upload_url).query).get("token", [""])[0]
        if not token:
            raise MaxImageError("MAX upload token is missing")
        return token

    async def _request(self, path: str, json_body: dict | None, params: dict | None = None) -> dict:
        token = self._secret_provider.get_secret("MAX_BOT_TOKEN")
        headers = {"Authorization": token}
        url = f"{self._base_url}{path}"
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    if json_body is None:
                        resp = await client.post(url, headers=headers, params=params)
                    else:
                        resp = await client.post(url, headers=headers, params=params, json=json_body)
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
