from __future__ import annotations
from datetime import UTC, datetime
from domain.entities.models import NotificationPayload, TaskEvent
from domain.ports.interfaces import NotificationChannelRegistry, ProcessedEventRepository, TemplateProvider


class NotificationService:
    def __init__(self, processed_repo: ProcessedEventRepository, channel_registry: NotificationChannelRegistry, template_provider: TemplateProvider) -> None:
        self.processed_repo = processed_repo
        self.channel_registry = channel_registry
        self.template_provider = template_provider

    def notify_users(self, event: TaskEvent, user_ids: list[str], channel: str = "max") -> int:
        if self.processed_repo.is_processed(event.source.value, event.external_id, event.event_type.value):
            return 0
        self.processed_repo.mark_processed(event.source.value, event.external_id, event.event_type.value, datetime.now(UTC))
        sent = 0
        for user_id in user_ids:
            title, body = self.template_provider.render(event.event_type.value, channel, {"subject_title": event.metadata.get("subject_title", "подъезд")})
            payload = NotificationPayload(user_id=user_id, channel=channel, title=title, body=body)
            try:
                self.channel_registry.get(channel).send(payload)
                sent += 1
            except Exception:
                continue
        return sent


class FeatureFlagService:
    def __init__(self, global_repo, user_repo) -> None:
        self.global_repo = global_repo
        self.user_repo = user_repo

    def is_enabled(self, key: str, user_id: str | None = None) -> bool:
        if user_id:
            return self.user_repo.is_enabled_for_user(user_id, key)
        return self.global_repo.is_enabled(key)
