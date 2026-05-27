from __future__ import annotations

import logging
from datetime import datetime

from domain.entities.models import NotificationPayload, Subject, TaskEvent
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

    def _extract_images(self, task: dict) -> list:
        # TODO: real photo source must be implemented when API endpoint/field is confirmed.
        return []

    def _parse_dt(self, value: str | None) -> datetime:
        if not value:
            return datetime.now()
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
