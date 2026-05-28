from composition.container import AdminService
from domain.entities.models import Subject
from domain.value_objects.enums import SubjectType


class FakeAdminRepository:
    def find_by_login(self, login):
        return None


class FakePermissions:
    def can_manage_subject(self, admin_id, district_id):
        return admin_id == "limited" and district_id == "assigned"


class FakeSubjects:
    def __init__(self):
        self.cities = [
            {"id": "city-assigned", "name": "Assigned city", "is_active": True},
            {"id": "city-hidden", "name": "Hidden city", "is_active": True},
        ]
        self.districts = [
            {"id": "assigned", "name": "Assigned", "is_active": True},
            {"id": "hidden", "name": "Hidden", "is_active": True},
        ]

    def list_cities(self):
        return self.cities

    def list_districts_by_city(self, city_id):
        return [self.districts[0]] if city_id == "city-assigned" else [self.districts[1]]

    def list_districts(self):
        return self.districts

    def get_district(self, district_id):
        return next((item for item in self.districts if item["id"] == district_id), None)

    def list_houses_by_district(self, district_id):
        return [{"id": "house", "district_id": district_id}]


class FakeAddressSubjects(FakeSubjects):
    def __init__(self):
        super().__init__()
        self.cities = [{"id": "c1", "name": "City", "is_active": True}]
        self.districts = [{"id": "d1", "name": "District", "is_active": True}]
        self.streets = [{"id": "s1", "district_id": "d1", "name": "Street", "is_active": True}]
        self.houses = [{"id": "h1", "district_id": "d1", "house_number": "1", "building": "", "is_active": True}]
        self.created_entrances = 0

    def get_house(self, house_id):
        return next((item for item in self.houses if item["id"] == house_id), None)

    def get_district(self, district_id):
        return next((item for item in self.districts if item["id"] == district_id), None)

    def list_districts_by_city(self, city_id):
        return self.districts

    def list_streets_by_district(self, district_id):
        return self.streets

    def list_houses_by_street(self, street_id):
        return self.houses

    def list_entrances_by_house(self, house_id):
        return []

    def get_by_public_code(self, public_code):
        return None

    def find_by_external_ref(self, external_ref):
        if external_ref == "map-conflict":
            return Subject("other", SubjectType.ENTRANCE, "Other", True, external_ref)
        return None

    def create_entrance(self, house_id, entrance_number, public_code, external_ref):
        self.created_entrances += 1
        return {
            "id": "e1",
            "house_id": house_id,
            "entrance_number": entrance_number,
            "public_code": public_code,
            "regioncity_external_ref": external_ref,
            "is_active": True,
        }


class FakeSecretProvider:
    def get_secret(self, key):
        return "admin-test-secret"


class FakeNotifier:
    pass


class FakeUsers:
    pass


class FakeSubscriptions:
    pass


def _service():
    return AdminService(
        FakeAdminRepository(),
        FakePermissions(),
        FakeSubjects(),
        FakeUsers(),
        FakeSubscriptions(),
        FakeSecretProvider(),
        FakeNotifier(),
        None,
    )


def _address_service(subjects=None):
    return AdminService(
        FakeAdminRepository(),
        FakePermissions(),
        subjects or FakeAddressSubjects(),
        FakeUsers(),
        FakeSubscriptions(),
        FakeSecretProvider(),
        FakeNotifier(),
        None,
    )


def _headers(service, admin_id, role):
    return {"Authorization": f"Bearer {service._issue(admin_id, role)}"}


def test_district_admin_only_lists_and_reads_assigned_districts():
    service = _service()
    headers = _headers(service, "limited", "district_admin")

    result = service.list_districts(headers)
    assert [item["id"] for item in result["items"]] == ["assigned"]
    assert service.list_houses(headers, "assigned")["items"][0]["id"] == "house"
    assert service.list_houses(headers, "hidden") == {"error": "forbidden"}
    assert [item["id"] for item in service.list_cities(headers)["items"]] == ["city-assigned"]


def test_district_admin_cannot_create_top_level_district():
    service = _service()
    headers = _headers(service, "limited", "district_admin")

    assert service.create_district(headers, {"name": "New"}) == {"error": "forbidden"}
    assert service.create_city(headers, {"name": "New"}) == {"error": "forbidden"}


def test_create_entrance_rejects_duplicate_regioncity_map_object_id():
    subjects = FakeAddressSubjects()
    service = _address_service(subjects)
    headers = _headers(service, "super", "super_admin")

    result = service.create_entrance(headers, "h1", {"entrance_number": "1", "regioncity_external_ref": "map-conflict"})

    assert result == {"error": "regioncity_map_object_id_conflict"}
    assert subjects.created_entrances == 0


def test_address_import_preview_rejects_conflicting_regioncity_map_object_id():
    service = _address_service()
    headers = _headers(service, "super", "super_admin")

    result = service.preview_address_import(
        headers,
        {
            "items": [
                {
                    "city": "City",
                    "district": "District",
                    "street": "Street",
                    "house_number": "1",
                    "entrance_number": "1",
                    "public_code": "new-code",
                    "regioncity_map_object_id": "map-conflict",
                }
            ]
        },
    )

    assert result["items"][0]["action"] == "error"
    assert "regioncity_map_object_id_conflict" in result["items"][0]["errors"]


def test_district_admin_cannot_import_addresses():
    service = _address_service()
    headers = _headers(service, "limited", "district_admin")

    result = service.preview_address_import(headers, {"items": [{"city": "City"}]})

    assert result == {"error": "forbidden"}
