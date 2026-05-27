from __future__ import annotations
from dataclasses import dataclass
from domain.entities.models import Subscription
from domain.value_objects.enums import SubjectType
from domain.ports.interfaces import ExternalTaskProvider, PublicPageCacheRepository, SubjectRepository, SubscriptionRepository
from application.errors.exceptions import DuplicateSubscriptionError, SubjectInactiveError, SubscriptionLimitExceededError
from application.services import NotificationService

MAX_ACTIVE_SUBSCRIPTIONS = 20
DEFAULT_PUBLIC_PAGE_LIMIT = 10
DEFAULT_PUBLIC_PAGE_TTL_SECONDS = 600


@dataclass
class SubscribeUserToSubjectUseCase:
    subjects: SubjectRepository
    subscriptions: SubscriptionRepository

    def execute(self, subscription: Subscription) -> Subscription:
        subject = self.subjects.get_by_id(subscription.subject_id)
        if not subject or not subject.is_active or subject.subject_type != SubjectType.ENTRANCE:
            raise SubjectInactiveError
        if self.subscriptions.get_active(subscription.user_id, subscription.subject_id):
            raise DuplicateSubscriptionError
        if len(self.subscriptions.list_active_by_user(subscription.user_id)) >= MAX_ACTIVE_SUBSCRIPTIONS:
            raise SubscriptionLimitExceededError
        self.subscriptions.save(subscription)
        return subscription


@dataclass
class ListUserSubscriptionsUseCase:
    subscriptions: SubscriptionRepository

    def execute(self, user_id: str):
        return self.subscriptions.list_active_by_user(user_id)


@dataclass
class UnsubscribeUserFromSubjectUseCase:
    subscriptions: SubscriptionRepository

    def execute(self, user_id: str, subject_id: str) -> None:
        self.subscriptions.deactivate(user_id, subject_id)


@dataclass
class DisableAllUserNotificationsUseCase:
    subscriptions: SubscriptionRepository

    def execute(self, user_id: str) -> int:
        return self.subscriptions.deactivate_all(user_id)


@dataclass
class GetPublicSubjectPageUseCase:
    cache_repo: PublicPageCacheRepository

    def execute(self, subject_id: str, events_fetcher, limit: int = DEFAULT_PUBLIC_PAGE_LIMIT, ttl_seconds: int = DEFAULT_PUBLIC_PAGE_TTL_SECONDS):
        key=f"public:{subject_id}:{limit}"
        cached=self.cache_repo.get(key)
        if cached:
            return cached
        data={"subject_id":subject_id,"events":events_fetcher(subject_id, limit)}
        self.cache_repo.set(key,data,ttl_seconds)
        return data


@dataclass
class ProcessExternalEventsUseCase:
    provider: ExternalTaskProvider
    notifier: NotificationService

    def execute(self, subscribers_resolver) -> int:
        total = 0
        for event in self.provider.fetch_events():
            users = subscribers_resolver(event.subject_id)
            total += self.notifier.notify_users(event, users)
        return total


@dataclass
class SendTestNotificationUseCase:
    notifier: NotificationService

    def execute(self, event, user_id: str) -> int:
        return self.notifier.notify_users(event, [user_id])
