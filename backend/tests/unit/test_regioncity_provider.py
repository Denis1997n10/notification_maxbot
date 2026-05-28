from datetime import UTC, datetime

from domain.entities.models import Subject
from domain.value_objects.enums import SubjectType
from infrastructure.regioncity.regioncity_mapper import RegionCityMapper
from infrastructure.regioncity.regioncity_task_provider import RegionCityTaskProvider


class FakeClient:
    def __init__(self, tasks):
        self.tasks = tasks

    async def list_tasks(self, date_from, date_to):
        return self.tasks


class FakeSubjectRepo:
    def __init__(self, subjects):
        self.subjects = subjects
        self.lookups = []

    def find_by_external_ref(self, external_ref: str):
        self.lookups.append(external_ref)
        return self.subjects.get(external_ref)


def make_task(task_id="1", task_type=51, status=3, map_object_id="m1"):
    return {
        "taskID": task_id,
        "taskTypeID": task_type,
        "status": status,
        "mapObjectID": map_object_id,
        "lastStatusChangeDate": "2026-01-01T12:00:00+00:00",
        "title": "Подъезд 1",
        "address": "ул. Ленина, 1",
        "description": "МУ-1",
        "customFieldFormItems": [{"name": "worker-id", "value": "123"}, {"name": "ml-verdict", "value": "ok"}],
    }


def test_mapper_filters_status_and_type():
    mapper = RegionCityMapper()
    subject = Subject("s1", SubjectType.ENTRANCE, "E", True, "m1")
    assert mapper.map_task_to_event(make_task(status=0), subject) is None
    assert mapper.map_task_to_event(make_task(status=2), subject) is None
    assert mapper.map_task_to_event(make_task(task_type=99), subject) is None


def test_mapper_worker_id_not_in_payload_and_custom_fields_mapped():
    mapper = RegionCityMapper()
    subject = Subject("s1", SubjectType.ENTRANCE, "E", True, "m1")
    event = mapper.map_task_to_event(make_task(), subject)
    assert event is not None
    assert event.event_type.value == "cleaning.completed"
    assert "worker-id" not in event.metadata["custom_fields"]
    assert event.metadata["custom_fields"]["ml-verdict"] == "ok"
    assert event.images == []
    payload = mapper.to_resident_payload(event)
    assert payload.title == "Уборка выполнена"
    assert "worker-id" not in payload.body


def test_provider_uses_map_object_lookup_and_skips_missing_subject():
    import asyncio
    tasks = [make_task(task_id="1", map_object_id="found"), make_task(task_id="2", map_object_id="missing")]
    repo = FakeSubjectRepo({"found": Subject("s1", SubjectType.ENTRANCE, "E", True, "found")})
    provider = RegionCityTaskProvider(FakeClient(tasks), repo, RegionCityMapper())
    events = asyncio.run(provider.fetch_events(datetime.now(UTC), datetime.now(UTC)))
    assert len(events) == 1
    assert events[0].external_id == "1"
    assert repo.lookups == ["found", "missing"]


def test_regioncity_map_objects_response_maps_candidates():
    from composition.container import AdminService

    class FakeRegionCityClient:
        async def list_map_objects(self, path, address=None):
            assert path == "/mapObjectManagement/mapObjects"
            return [
                {"mapObjectID": "18864279", "address": "Санкт-Петербург, Приморский район, дом 1, подъезд 2", "name": "Подъезд 2", "objectType": "entrance"},
                {"objectID": "no-address"},
            ]

    class Service(AdminService):
        def __init__(self):
            self.regioncity_client = FakeRegionCityClient()
            self.regioncity_map_objects_path = "/mapObjectManagement/mapObjects"

        def _principal(self, headers):
            return {"sub": "a1", "role": "super_admin"}

    result = Service().search_regioncity_map_objects({}, {"address": "Санкт-Петербург Приморский дом 1 подъезд 2"})
    assert result["items"][0]["map_object_id"] == "18864279"
    assert result["items"][0]["object_type"] == "entrance"
    assert result["items"][0]["score"] > 0.5
