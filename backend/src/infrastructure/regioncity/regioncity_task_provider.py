from __future__ import annotations

from datetime import UTC, datetime, timedelta

from domain.entities.models import Subject, TaskEvent
from domain.ports.interfaces import ExternalTaskProvider, SubjectRepository
from infrastructure.regioncity.regioncity_client import RegionCityClient
from infrastructure.regioncity.regioncity_mapper import RegionCityMapper


class RegionCityTaskProvider(ExternalTaskProvider):
    def __init__(
        self,
        client: RegionCityClient,
        subject_repository: SubjectRepository,
        mapper: RegionCityMapper,
        latest_period_days: int = 7,
    ) -> None:
        self._client = client
        self._subject_repository = subject_repository
        self._mapper = mapper
        self._latest_period_days = latest_period_days

    async def fetch_events(self, date_from: datetime, date_to: datetime) -> list[TaskEvent]:
        tasks = await self._client.list_tasks(date_from=date_from, date_to=date_to)
        events: list[TaskEvent] = []
        for task in tasks:
            external_ref = str(task.get("mapObjectID") or "")
            subject = self._subject_repository.find_by_external_ref(external_ref)
            event = self._mapper.map_task_to_event(task, subject)
            if event:
                events.append(event)
        return events

    async def get_latest_events_for_subject(self, subject: Subject, limit: int = 10) -> list[TaskEvent]:
        now = datetime.now(UTC)
        date_from = now - timedelta(days=self._latest_period_days)
        tasks = await self._client.list_tasks(date_from=date_from, date_to=now)
        events: list[TaskEvent] = []
        for task in tasks:
            if str(task.get("mapObjectID") or "") != (subject.external_ref or ""):
                continue
            mapped = self._mapper.map_task_to_event(task, subject)
            if mapped:
                events.append(mapped)
        events.sort(key=lambda x: x.occurred_at, reverse=True)
        return events[:limit]
