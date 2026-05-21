import json


class DummyBotService:
    def start_with_public_code(self, code):
        return {"action": "start", "public_code": code}

    def handle_action(self, action, payload):
        return {"action": action}


class DummyPublicService:
    def get_entrance_page(self, code): return {"public_code": code}
    def list_districts(self): return [{"id": "d1"}]
    def list_houses(self, district_id): return [{"district_id": district_id}]
    def list_entrances(self, house_id): return [{"house_id": house_id}]
    def create_subscription(self, body): return {"created": True}


class DummyAdminService:
    def login(self, body): return {"token": "t"}
    def me(self, headers): return {"role": "super_admin"}
    def send_test_notification(self, body): return {"sent": 1}


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


def test_admin_api_routes(monkeypatch):
    _patch_container(monkeypatch)
    from functions.admin_api.handler import handler

    resp = handler({"httpMethod": "POST", "path": "/api/v1/admin/auth/login", "body": "{}"}, None)
    assert resp["statusCode"] == 200
    assert "token" in json.loads(resp["body"])


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
