from __future__ import annotations

import httpx

from domain.entities.models import TaskEvent
from domain.ports.interfaces import ImageLoader


class HttpImageLoader(ImageLoader):
    def __init__(self, timeout_seconds: float = 10.0, max_bytes: int = 5 * 1024 * 1024) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    def load(self, event: TaskEvent) -> list[bytes]:
        images: list[bytes] = []
        for image in event.images:
            data = self._load_url(image.url)
            if data:
                images.append(data)
        return images

    def _load_url(self, url: str) -> bytes | None:
        if not url.startswith(("http://", "https://")):
            return None
        response = httpx.get(url, timeout=self._timeout_seconds, follow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        content = response.content
        if not content or len(content) > self._max_bytes:
            return None
        if not content_type.startswith("image/") and not self._looks_like_image(content):
            return None
        return content

    def _looks_like_image(self, content: bytes) -> bool:
        return (
            content.startswith(b"\x89PNG\r\n\x1a\n")
            or content.startswith(b"\xff\xd8\xff")
            or content.startswith(b"GIF87a")
            or content.startswith(b"GIF89a")
            or (len(content) > 12 and content[0:4] == b"RIFF" and content[8:12] == b"WEBP")
        )
