from infrastructure.max.max_message_renderer import MaxMessageRenderer
from infrastructure.max.max_notification_channel import MaxNotificationChannel
from infrastructure.max.max_webhook_parser import MaxWebhookParser


class FakeTemplateProvider:
    def render(self, template_key, channel, context):
        if template_key == "cleaning.completed":
            return ("Уборка выполнена", f"Адрес: {context.get('address','')}")
        if template_key == "services.placeholder":
            return ("Сервисы", "Скоро здесь можно будет заказать дополнительные услуги")
        return ("X", "Y")


class FakeMaxClient:
    def __init__(self, fail_image=False, fail_text=False):
        self.fail_image = fail_image
        self.fail_text = fail_text
        self.sent_text = []
        self.sent_img = []
        self.answered = []

    async def send_text(self, chat_id, text, keyboard=None):
        if self.fail_text:
            raise RuntimeError("api error")
        self.sent_text.append((chat_id, text, keyboard))

    async def send_with_image(self, chat_id, text, image_bytes):
        if self.fail_image:
            from infrastructure.max.errors import MaxImageError
            raise MaxImageError("img error")
        self.sent_img.append((chat_id, text, image_bytes))

    async def answer_callback(self, callback_id, text, keyboard=None):
        self.answered.append((callback_id, text, keyboard))


def test_render_cleaning_completed_message():
    renderer = MaxMessageRenderer(FakeTemplateProvider())
    payload = renderer.render("cleaning.completed", {"address": "ул. Ленина, 1"}, "u1")
    assert payload.title == "Уборка выполнена"
    assert "Ленина" in payload.body


def test_send_text_only_notification():
    client = FakeMaxClient()
    channel = MaxNotificationChannel(client)
    from domain.entities.models import NotificationPayload
    payload = NotificationPayload(user_id="u1", channel="max", title="T", body="B", metadata={})
    channel.send(payload)
    assert len(client.sent_text) == 1


def test_send_text_with_keyboard():
    client = FakeMaxClient()
    channel = MaxNotificationChannel(client)
    from domain.entities.models import NotificationPayload

    keyboard = [[{"type": "message", "text": "Мои адреса"}]]
    payload = NotificationPayload(user_id="u1", channel="max", title="", body="B", metadata={"keyboard": keyboard})
    channel.send(payload)
    assert client.sent_text == [("u1", "B", keyboard)]


def test_answer_callback_with_keyboard():
    client = FakeMaxClient()
    channel = MaxNotificationChannel(client)
    keyboard = [[{"type": "callback", "text": "Назад", "payload": "menu:main"}]]
    channel.answer_callback("cb1", "B", keyboard=keyboard)
    assert client.answered == [("cb1", "B", keyboard)]


def test_image_failure_still_sends_text():
    client = FakeMaxClient(fail_image=True)
    channel = MaxNotificationChannel(client)
    from domain.entities.models import NotificationPayload
    payload = NotificationPayload(user_id="u1", channel="max", title="T", body="B", metadata={"image_bytes": b"x"})
    channel.send(payload)
    assert len(client.sent_text) == 1


def test_start_payload_parsed():
    parser = MaxWebhookParser()
    payload = {"message": {"sender": {"user_id": 42}, "body": {"text": "/start ABC123"}}}
    code = parser.parse_start_public_code(payload)
    assert code == "ABC123"
    assert parser.external_user_id(payload) == "42"


def test_callback_payload_parsed():
    parser = MaxWebhookParser()
    assert parser.callback_payload({"callback": {"payload": "menu:addresses"}}) == "menu:addresses"
    assert parser.callback_payload({"callback": {"button": {"payload": "address:open:s1"}}}) == "address:open:s1"
    assert parser.callback_id({"callback": {"callback_id": "cb1"}}) == "cb1"
    payload = {"callback": {"user": {"id": 42, "username": "resident"}, "button": {"callback_data": "menu:help"}}}
    assert parser.callback_payload(payload) == "menu:help"
    assert parser.external_user_id(payload) == "42"
    assert parser.display_name(payload) == "resident"


def test_services_placeholder_rendered_when_disabled():
    renderer = MaxMessageRenderer(FakeTemplateProvider())
    payload = renderer.render_services_placeholder("u1")
    assert "Скоро здесь" in payload.body


def test_max_api_error_does_not_crash_whole_batch():
    from application.services import NotificationService
    from domain.entities.models import TaskEvent
    from domain.value_objects.enums import EventType, Source
    from datetime import UTC, datetime

    class ProcRepo:
        def __init__(self): self.done=set()
        def is_processed(self, s,e,t): return False
        def mark_processed(self, s,e,t,at): self.done.add((s,e,t))

    class Registry:
        def __init__(self, ch): self.ch=ch
        def get(self, name): return self.ch

    class ChannelWrapper:
        def __init__(self): self.calls=0
        def send(self, payload):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("max down")

    svc = NotificationService(ProcRepo(), Registry(ChannelWrapper()), FakeTemplateProvider())
    event = TaskEvent("e1", "s1", Source.REGIONCITY, EventType.CLEANING_COMPLETED, datetime.now(UTC), {"subject_title": "E"})
    sent = svc.notify_users(event, ["u1", "u2"])
    assert sent == 1
