from __future__ import annotations

from domain.entities.models import NotificationPayload
from domain.ports.interfaces import TemplateProvider


class MaxMessageRenderer:
    def __init__(self, template_provider: TemplateProvider) -> None:
        self._template_provider = template_provider

    def render(self, template_key: str, context: dict, user_id: str) -> NotificationPayload:
        title, body = self._template_provider.render(template_key, "max", context)
        return NotificationPayload(user_id=user_id, channel="max", title=title, body=body, metadata={})

    def render_services_placeholder(self, user_id: str) -> NotificationPayload:
        return NotificationPayload(
            user_id=user_id,
            channel="max",
            title="Сервисы",
            body="Скоро здесь можно будет заказать дополнительные услуги",
            metadata={},
        )
