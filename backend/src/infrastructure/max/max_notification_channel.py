from __future__ import annotations

import asyncio

from domain.entities.models import NotificationPayload
from domain.ports.interfaces import NotificationChannel
from infrastructure.max.errors import MaxImageError
from infrastructure.max.max_client import MaxClient


class MaxNotificationChannel(NotificationChannel):
    def __init__(self, client: MaxClient) -> None:
        self._client = client

    def send(self, payload: NotificationPayload) -> None:
        text = f"{payload.title}\n\n{payload.body}" if payload.title else payload.body
        image_bytes = payload.metadata.get("image_bytes") if payload.metadata else None
        if image_bytes:
            try:
                asyncio.run(self._client.send_with_image(payload.user_id, text, image_bytes))
                return
            except MaxImageError:
                pass
        asyncio.run(self._client.send_text(payload.user_id, text))
