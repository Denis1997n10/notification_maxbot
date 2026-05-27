from composition.container import AdminService


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
