from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from domain.entities.models import Subject, TaskEvent
from domain.ports.interfaces import ExternalTaskProvider, SubjectRepository
from infrastructure.regioncity.errors import RegionCityRequestError
from infrastructure.regioncity.regioncity_client import RegionCityClient
from infrastructure.regioncity.regioncity_mapper import RegionCityMapper


class RegionCityTaskProvider(ExternalTaskProvider):
    def __init__(
        self,
        client: RegionCityClient,
        subject_repository: SubjectRepository,
        mapper: RegionCityMapper,
        latest_period_days: int = 7,
        forms_path: str = "/formManagement/forms",
        forms_batch_size: int = 50,
    ) -> None:
        self._client = client
        self._subject_repository = subject_repository
        self._mapper = mapper
        self._latest_period_days = latest_period_days
        self._forms_path = forms_path
        self._forms_batch_size = forms_batch_size
        self._logger = logging.getLogger(__name__)

    async def fetch_events(self, date_from: datetime, date_to: datetime) -> list[TaskEvent]:
        tasks = await self._client.list_tasks(date_from=date_from, date_to=date_to)
        forms_by_task_id = await self._forms_by_task_id(tasks)
        events: list[TaskEvent] = []
        for task in tasks:
            external_ref = str(task.get("mapObjectID") or "")
            subject = self._subject_repository.find_by_external_ref(external_ref)
            event = self._mapper.map_task_to_event(task, subject, forms_by_task_id.get(str(task.get("taskID"))))
            if event:
                events.append(event)
        return events

    async def get_latest_events_for_subject(self, subject: Subject, limit: int = 10) -> list[TaskEvent]:
        now = datetime.now(UTC)
        date_from = now - timedelta(days=self._latest_period_days)
        tasks = await self._client.list_tasks(date_from=date_from, date_to=now)
        forms_by_task_id = await self._forms_by_task_id(tasks)
        events: list[TaskEvent] = []
        for task in tasks:
            if str(task.get("mapObjectID") or "") != (subject.external_ref or ""):
                continue
            mapped = self._mapper.map_task_to_event(task, subject, forms_by_task_id.get(str(task.get("taskID"))))
            if mapped:
                events.append(mapped)
        events.sort(key=lambda x: x.occurred_at, reverse=True)
        return events[:limit]

    async def _forms_by_task_id(self, tasks: list[dict]) -> dict[str, list[dict]]:
        task_ids = [
            str(task.get("taskID"))
            for task in tasks
            if task.get("taskID")
        ]
        result: dict[str, list[dict]] = {}
        for index in range(0, len(task_ids), self._forms_batch_size):
            chunk = task_ids[index : index + self._forms_batch_size]
            try:
                forms = await self._client.list_forms(chunk, self._forms_path)
            except RegionCityRequestError:
                self._logger.warning("RegionCity forms request failed", extra={"task_count": len(chunk)})
                continue
            for form in forms:
                task_id = str(form.get("taskID") or "")
                if task_id:
                    result.setdefault(task_id, []).append(form)
        return result
