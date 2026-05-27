from application.use_cases.use_cases import (
    DisableAllUserNotificationsUseCase,
    ListUserSubscriptionsUseCase,
    SubscribeUserToSubjectUseCase,
)
from composition.container import BotService
from domain.entities.models import Subject, User
from domain.value_objects.enums import SubjectType


class FakeUsers:
    def __init__(self):
        self.user = User(user_id="u1")

    def get_or_create_channel_user(self, channel, external_user_id, display_name=""):
        return self.user


class FakeSubjects:
    def __init__(self):
        self.subject = Subject(
            subject_id="entrance-1",
            subject_type=SubjectType.ENTRANCE,
            title="Сочи, Морская 1, подъезд 2",
        )

    def get_by_public_code(self, code):
        return self.subject if code == "code1" else None

    def get_by_id(self, subject_id):
        return self.subject if subject_id == self.subject.subject_id else None


class FakeSubscriptions:
    def __init__(self):
        self.items = []

    def get_active(self, user_id, subject_id):
        for item in self.items:
            if item.user_id == user_id and item.subject_id == subject_id and item.is_active:
                return item
        return None

    def list_active_by_user(self, user_id):
        return [item for item in self.items if item.user_id == user_id and item.is_active]

    def save(self, subscription):
        self.items.append(subscription)

    def deactivate(self, user_id, subject_id):
        for item in self.items:
            if item.user_id == user_id and item.subject_id == subject_id:
                item.is_active = False

    def deactivate_all(self, user_id):
        active = self.list_active_by_user(user_id)
        for item in active:
            item.is_active = False
        return len(active)


def make_service(public_site_url=""):
    users = FakeUsers()
    subjects = FakeSubjects()
    subscriptions = FakeSubscriptions()
    return BotService(
        users,
        subjects,
        subscriptions,
        SubscribeUserToSubjectUseCase(subjects, subscriptions),
        ListUserSubscriptionsUseCase(subscriptions),
        DisableAllUserNotificationsUseCase(subscriptions),
        public_site_url,
    )


def test_start_with_public_code_subscribes_user():
    service = make_service()

    result = service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "/start e_code1"}}})

    assert "Готово" in result["message"]
    assert "Морская 1" in result["message"]
    assert result["keyboard"]


def test_start_without_code_shows_menu():
    service = make_service()

    result = service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "/start"}}})

    assert "Как начать" in result["message"]
    assert "Мои адреса" in str(result["keyboard"])


def test_start_menu_can_open_address_picker():
    service = make_service("https://public.example.com")

    result = service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "/start"}}})

    assert result["keyboard"][0][0] == {
        "type": "link",
        "text": "Выбрать адрес",
        "url": "https://public.example.com/?view=select",
    }


def test_list_and_unsubscribe_by_number():
    service = make_service()
    service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "/start e_code1"}}})

    listed = service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "Мои адреса"}}})
    removed = service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "Отписаться 1"}}})

    assert "1. Сочи" in listed["message"]
    assert "Отключил" in removed["message"]
    assert "Отписаться 1" not in str(removed["keyboard"])


def test_disable_all_is_direct_command():
    service = make_service()
    service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "/start e_code1"}}})

    result = service.handle_payload({"message": {"sender": {"user_id": "42"}, "body": {"text": "Отключить все"}}})

    assert "Отключил подписки: 1" in result["message"]
