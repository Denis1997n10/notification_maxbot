class ApplicationError(Exception):
    pass


class SubscriptionLimitExceededError(ApplicationError):
    pass


class DuplicateSubscriptionError(ApplicationError):
    pass


class SubjectInactiveError(ApplicationError):
    pass
