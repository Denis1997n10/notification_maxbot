import json


class DummyBotService:
    def start_with_public_code(self, code):
        return {"action": "start", "public_code": code}

    def handle_action(self, action, payload):
        return {"action": action}


class DummyPublicService:
    def get_entrance_page(self, code): return {"public_code": code}
    def list_cities(self): return [{"id": "c1"}]
    def list_city_districts(self, city_id): return [{"city_id": city_id}]
    def list_districts(self): return [{"id": "d1"}]
    def list_streets(self, district_id): return [{"district_id": district_id}]
    def list_houses(self, district_id): return [{"district_id": district_id}]
    def list_street_houses(self, street_id): return [{"street_id": street_id}]
    def list_entrances(self, house_id): return [{"house_id": house_id}]
    def subscribe_from_mini_app(self, body): return {"status": "subscribed"}
    def create_subscription(self, body): return {"created": True}


class DummyAdminService:
    def login(self, body): return {"token": "t"}
    def me(self, headers): return {"role": "super_admin"}
    def list_cities(self, headers): return {"items": [{"id": "c1"}]}
    def create_city(self, headers, body): return {"item": {"id": "c2"}}
    def list_city_districts(self, headers, city_id): return {"items": [{"city_id": city_id}]}
    def create_city_district(self, headers, city_id, body): return {"item": {"city_id": city_id}}
    def assign_district_to_city(self, headers, city_id, body): return {"item": {"city_id": city_id}}
    def deactivate_city(self, headers, city_id): return {"item": {"id": city_id, "is_active": False}}
    def list_unassigned_districts(self, headers): return {"items": []}
    def list_districts(self, headers): return {"items": [{"id": "d1"}]}
    def create_district(self, headers, body): return {"item": {"id": "d2"}}
    def list_houses(self, headers, district_id): return {"items": [{"district_id": district_id}]}
    def create_house(self, headers, district_id, body): return {"item": {"district_id": district_id}}
    def list_streets(self, headers, district_id): return {"items": [{"district_id": district_id}]}
    def create_street(self, headers, district_id, body): return {"item": {"district_id": district_id}}
    def list_street_houses(self, headers, street_id): return {"items": [{"street_id": street_id}]}
    def create_street_house(self, headers, street_id, body): return {"item": {"street_id": street_id}}
    def list_entrances(self, headers, house_id): return {"items": [{"house_id": house_id}]}
    def create_entrance(self, headers, house_id, body): return {"item": {"house_id": house_id}}
    def deactivate_district(self, headers, district_id): return {"item": {"id": district_id, "is_active": False}}
    def deactivate_street(self, headers, street_id): return {"item": {"id": street_id, "is_active": False}}
    def deactivate_house(self, headers, house_id): return {"item": {"id": house_id, "is_active": False}}
    def deactivate_entrance(self, headers, entrance_id): return {"item": {"id": entrance_id, "is_active": False}}
    def list_resident_users(self, headers): return {"items": [{"id": "u1"}]}
    def deactivate_resident_user(self, headers, user_id): return {"item": {"id": user_id, "is_active": False}}
    def list_admin_users(self, headers): return {"items": [{"id": "a1"}]}
    def create_admin_user(self, headers, body): return {"item": {"id": "a2"}}
    def deactivate_admin_user(self, headers, admin_id): return {"item": {"id": admin_id, "is_active": False}}
    def send_test_notification(self, headers, body): return {"sent": 1}


class DummyPolling:
    async def execute(self, date_from, date_to):
        return {"fetched_count": 1, "processed_count": 1, "skipped_count": 0, "sent_count": 1, "failed_count": 0}


class DummySender:
    def send_batch(self, event): return {"sent_count": 1, "failed_count": 0}


def _patch_container(monkeypatch):
    from composition.container import AppContainer

    def build():
        return AppContainer(
            bot_service=DummyBotService(),
            public_service=DummyPublicService(),
            admin_service=DummyAdminService(),
            polling_use_case=DummyPolling(),
            notification_service=DummySender(),
        )

    monkeypatch.setattr("functions.bot_webhook.handler.build_container", build)
    monkeypatch.setattr("functions.public_api.handler.build_container", build)
    monkeypatch.setattr("functions.admin_api.handler.build_container", build)
    monkeypatch.setattr("functions.regioncity_polling.handler.build_container", build)
    monkeypatch.setattr("functions.notification_sender.handler.build_container", build)


def test_bot_webhook_routes(monkeypatch):
    _patch_container(monkeypatch)
    from functions.bot_webhook.handler import handler

    resp = handler({"body": json.dumps({"text": "/start AB12"})}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["public_code"] == "AB12"


def test_public_api_routes(monkeypatch):
    _patch_container(monkeypatch)
    from functions.public_api.handler import handler

    resp = handler({"httpMethod": "GET", "path": "/api/v1/public/districts"}, None)
    assert resp["statusCode"] == 200

    resp = handler({"httpMethod": "GET", "path": "/api/v1/public/cities"}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])[0]["id"] == "c1"

    resp = handler(
        {
            "httpMethod": "GET",
            "path": "/api/v1/public/districts/d1/streets",
        },
        None,
    )
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])[0]["district_id"] == "d1"

    resp = handler({"httpMethod": "POST", "path": "/api/v1/public/miniapp/subscriptions", "body": "{}"}, None)
    assert resp["statusCode"] == 200


def test_admin_api_routes(monkeypatch):
    _patch_container(monkeypatch)
    from functions.admin_api.handler import handler

    resp = handler({"httpMethod": "POST", "path": "/api/v1/admin/auth/login", "body": "{}"}, None)
    assert resp["statusCode"] == 200
    assert "token" in json.loads(resp["body"])

    resp = handler({"httpMethod": "POST", "path": "/api/v1/admin/test-notification", "headers": {}, "body": "{}"}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["sent"] == 1

    resp = handler({"httpMethod": "GET", "path": "/api/v1/admin/districts", "headers": {}}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["items"][0]["id"] == "d1"

    resp = handler({"httpMethod": "GET", "path": "/api/v1/admin/cities", "headers": {}}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["items"][0]["id"] == "c1"

    resp = handler({"httpMethod": "POST", "path": "/api/v1/admin/cities/c1/districts", "headers": {}, "body": "{}"}, None)
    assert resp["statusCode"] == 201
    assert json.loads(resp["body"])["item"]["city_id"] == "c1"

    resp = handler({"httpMethod": "POST", "path": "/api/v1/admin/cities/c1/districts/assign", "headers": {}, "body": "{}"}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["item"]["city_id"] == "c1"

    resp = handler(
        {
            "httpMethod": "POST",
            "path": "/api/v1/admin/districts/d1/houses",
            "headers": {},
            "body": "{}",
        },
        None,
    )
    assert resp["statusCode"] == 201
    assert json.loads(resp["body"])["item"]["district_id"] == "d1"

    resp = handler(
        {
            "httpMethod": "GET",
            "path": "/api/v1/admin/districts/d1/streets",
            "headers": {},
        },
        None,
    )
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["items"][0]["district_id"] == "d1"

    resp = handler({"httpMethod": "GET", "path": "/api/v1/admin/admin-users", "headers": {}}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["items"][0]["id"] == "a1"

    resp = handler(
        {
            "httpMethod": "PATCH",
            "path": "/api/v1/admin/entrances/e1/deactivate",
            "headers": {},
        },
        None,
    )
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["item"]["is_active"] is False


def test_bot_webhook_rejects_invalid_secret(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("MAX_WEBHOOK_SECRET", "expected")
    from functions.bot_webhook.handler import handler

    resp = handler({"headers": {"X-Max-Bot-Api-Secret": "invalid"}, "body": "{}"}, None)
    assert resp["statusCode"] == 401


def test_regioncity_polling_handler(monkeypatch):
    _patch_container(monkeypatch)
    from functions.regioncity_polling.handler import handler

    resp = handler({}, None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["fetched_count"] == 1


def test_notification_sender_handler(monkeypatch):
    _patch_container(monkeypatch)
    from functions.notification_sender.handler import handler

    resp = handler({"records": []}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["sent_count"] == 1
