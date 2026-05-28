# Предварительный реестр зависимостей

Документ фиксирует зависимости, найденные в текущих manifest-файлах проекта. Это не финальный SBOM. Перед подачей документов необходимо сформировать список по фактически установленным версиям и подтвердить лицензии.

## Backend Python

Источник: `backend/requirements-dev.txt`.

| Пакет | Версия/ограничение | Назначение | Предварительная лицензия | Статус |
|---|---:|---|---|---|
| pytest | `>=8.0` | Тестирование backend | MIT | Проверить по SBOM |
| pytest-asyncio | `>=0.23` | Тестирование async-кода | Apache-2.0 | Проверить по SBOM |
| PyYAML | `>=6.0` | Работа с YAML/OpenAPI/config | MIT | Проверить по SBOM |
| ruff | `>=0.6` | Линтинг и статическая проверка Python | MIT | Проверить по SBOM |
| httpx | `>=0.27` | HTTP-клиент для интеграций | BSD-3-Clause | Проверить по SBOM |
| yandexcloud | `>=0.327.0` | Yandex Cloud SDK | Apache-2.0 | Проверить по SBOM |
| ydb | `>=3.6` | Клиент YDB | Apache-2.0 | Проверить по SBOM |

## Frontend Node.js

Источники: `frontend/public-site/package.json`, `frontend/admin-panel/package.json`.

| Пакет | Версия/ограничение | Приложение | Назначение | Предварительная лицензия | Статус |
|---|---:|---|---|---|---|
| react | `^18.3.1` | public-site, admin-panel | UI library | MIT | Проверить по SBOM |
| react-dom | `^18.3.1` | public-site, admin-panel | DOM renderer для React | MIT | Проверить по SBOM |
| react-router-dom | `^6.30.1` | public-site, admin-panel | Маршрутизация frontend | MIT | Проверить по SBOM |
| @vitejs/plugin-react | `^4.3.1` | public-site, admin-panel | Vite React plugin | MIT | Проверить по SBOM |
| vite | `^5.4.10` | public-site, admin-panel | Сборка frontend | MIT | Проверить по SBOM |

## Terraform

| Компонент | Версия | Назначение | Статус |
|---|---:|---|---|
| yandex-cloud/yandex provider | `>= 0.120.0` | Управление ресурсами Yandex Cloud | Проверить условия использования |

## Что нужно сделать дальше

1. Сгенерировать lock-файлы, если они отсутствуют.
2. Сформировать SBOM по backend и frontend.
3. Подтвердить лицензии по фактически установленным версиям.
4. Сверить ограничения лицензий с моделью распространения продукта.
5. Внести подтвержденные данные в `06_components_and_rights_register.md`.
