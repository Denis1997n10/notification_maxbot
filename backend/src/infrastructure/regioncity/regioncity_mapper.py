from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from domain.entities.models import NotificationPayload, Subject, TaskEvent, TaskImage
from domain.value_objects.enums import ChannelType, EventType, Source, SubjectType


class RegionCityMapper:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def map_task_to_event(self, task: dict, subject: Subject | None, task_type_id: int = 51) -> TaskEvent | None:
        if task.get("taskTypeID") != task_type_id:
            return None
        if task.get("status") != 3:
            return None
        if subject is None or not subject.is_active or subject.subject_type != SubjectType.ENTRANCE:
            self._logger.info("Skipping task due to missing active entrance", extra={"task_id": task.get("taskID"), "map_object_id": task.get("mapObjectID")})
            return None

        metadata = self._build_metadata(task)
        metadata["subject_title"] = subject.title
        occurred_at = self._parse_dt(task.get("lastStatusChangeDate"))
        return TaskEvent(
            external_id=str(task.get("taskID")),
            subject_id=subject.subject_id,
            source=Source.REGIONCITY,
            event_type=EventType.CLEANING_COMPLETED,
            occurred_at=occurred_at,
            metadata=metadata,
            images=self._extract_images(task),
        )

    def to_resident_payload(self, event: TaskEvent) -> NotificationPayload:
        description = f"{event.metadata.get('address') or event.metadata.get('title') or 'Подъезд'}\nЗавершено: {event.occurred_at.isoformat()}"
        mu = event.metadata.get("district_mu")
        if mu:
            description += f"\n{mu}"
        return NotificationPayload(
            user_id="",
            channel=ChannelType.MAX,
            title="Уборка выполнена",
            body=description,
            metadata={},
        )

    def _build_metadata(self, task: dict) -> dict:
        fields = {}
        for item in task.get("customFieldFormItems") or []:
            name = item.get("name")
            if name:
                fields[name] = item.get("value")

        md = {
            "title": task.get("title"),
            "address": task.get("address"),
            "description": task.get("description"),
            "custom_fields": fields,
            "ml-verdict": fields.get("ml-verdict"),
            "customStatusID": task.get("customStatusID"),
            "subscriberID": task.get("subscriberID"),
            "longitude": task.get("longitude"),
            "latitude": task.get("latitude"),
            "startDate": task.get("startDate"),
            "deadline": task.get("deadline"),
            "creationDate": task.get("creationDate"),
        }
        if "worker-id" in md["custom_fields"]:
            md["custom_fields"].pop("worker-id")
        return md

    def _extract_images(self, task: dict) -> list[TaskImage]:
        images: list[TaskImage] = []
        seen: set[str] = set()

        def add(url: str, label: str | None = None) -> None:
            normalized = str(url or "").strip()
            if not normalized.startswith(("http://", "https://")) or normalized in seen:
                return
            seen.add(normalized)
            images.append(TaskImage(url=normalized, label=label))

        for key, value in task.items():
            if self._is_image_key(key):
                self._collect_image_urls(value, str(key), add)
        for item in task.get("customFieldFormItems") or []:
            name = str(item.get("name") or "")
            if self._is_image_key(name):
                self._collect_image_urls(item.get("value"), name, add)
        return images

    def _collect_image_urls(self, value: Any, label: str | None, add) -> None:
        if isinstance(value, str):
            for match in re.findall(r"https?://[^\s,;]+", value):
                add(match.rstrip(").]\"'"), label)
        elif isinstance(value, dict):
            for key in ("url", "src", "href", "link"):
                if key in value:
                    self._collect_image_urls(value[key], label, add)
            for nested_key, nested_value in value.items():
                if self._is_image_key(str(nested_key)):
                    self._collect_image_urls(nested_value, str(nested_key), add)
        elif isinstance(value, list):
            for item in value:
                self._collect_image_urls(item, label, add)

    def _is_image_key(self, key: str) -> bool:
        normalized = key.lower()
        return any(marker in normalized for marker in ("photo", "image", "фото", "картин", "file", "attachment"))

    def _parse_dt(self, value: str | None) -> datetime:
        if not value:
            return datetime.now()
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
