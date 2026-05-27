from domain.ports.interfaces import TemplateProvider


class CodeTemplateProvider(TemplateProvider):
    def __init__(self) -> None:
        self._templates = {
            ("cleaning.completed", "max"): (
                "Уборка завершена",
                "Уборка в подъезде завершена: {subject_title}",
            ),
            ("services.placeholder", "max"): (
                "Сервисы",
                "Раздел сервисов пока в разработке",
            ),
            ("notification.test", "max"): (
                "Тестовое уведомление",
                "Проверка уведомлений: {subject_title}",
            ),
        }

    def render(self, template_key: str, channel: str, context: dict) -> tuple[str, str]:
        title_t, body_t = self._templates[(template_key, channel)]
        return title_t.format(**context), body_t.format(**context)
