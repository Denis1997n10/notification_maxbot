# Техническое описание программного обеспечения

## 1. Общая архитектура

Система реализована как serverless-приложение для Yandex Cloud. Пользовательские и административные интерфейсы размещаются как статические приложения, API публикуется через Yandex API Gateway, бизнес-операции выполняются в Yandex Cloud Functions, данные хранятся в YDB Serverless, секреты — в Yandex Lockbox.

Архитектурный стиль: layered/hexagonal architecture.

Основные слои:

- `domain` — доменные сущности и базовые правила;
- `application` — use cases, сервисы и порты;
- `infrastructure` — адаптеры для YDB, MAX, RegionCity/MPOISK, Lockbox;
- `functions` — тонкие serverless-обработчики;
- `frontend` — public site и admin panel;
- `infra/terraform` — описание облачной инфраструктуры;
- `openapi` — спецификация маршрутов API Gateway;
- `scripts` и `backend/scripts` — эксплуатационные скрипты.

## 2. Основные компоненты

### 2.1. Public Site

Публичный web-интерфейс для жителей. Используется для открытия страницы объекта по QR-коду или ссылке, отображения сведений об объекте и перехода в MAX-бота.

### 2.2. Admin Panel

Административный web-интерфейс для управления справочниками, пользователями, ролями и тестовыми действиями.

### 2.3. API Gateway

Публикует HTTP API и маршрутизирует запросы в Cloud Functions. CORS настраивается на основе public/admin origin.

### 2.4. Public API Function

Обслуживает публичные запросы:

- health/version;
- получение публичной страницы подъезда;
- публичную навигацию по справочникам;
- создание подписок через public/miniapp endpoint.

### 2.5. Admin API Function

Обслуживает административные запросы:

- login;
- данные текущего администратора;
- CRUD/soft-deactivation справочников;
- управление администраторами;
- тестовые уведомления.

### 2.6. Bot Webhook Function

Принимает webhook-события от MAX, извлекает сообщение/команду, вызывает прикладной сервис бота и возвращает результат обработки.

### 2.7. RegionCity Polling Function

Предназначена для периодического получения событий из RegionCity/MPOISK. В MVP фильтрует события по уборкам и завершенному статусу, сопоставляет их с подъездами и передает на обработку уведомлений.

### 2.8. Notification Sender / Notification Service

Отвечает за подготовку и отправку уведомлений активным подписчикам через канал уведомлений. Текущий канал — MAX.

## 3. Данные и сущности

Основные доменные сущности:

- Subject / Directory Object — объект справочника, на который можно подписаться;
- Subscription — подписка пользователя на объект;
- TaskEvent — событие внешней задачи;
- NotificationPayload — данные уведомления;
- NotificationChannel — канал доставки;
- ExternalTaskProvider — источник внешних событий;
- TemplateProvider — источник шаблонов сообщений.

Справочник MVP:

- город;
- район;
- улица;
- дом;
- подъезд.

Объект подписки MVP: подъезд.

## 4. Интеграции

### 4.1. RegionCity/MPOISK

Внешняя система-источник задач. Для MVP используется API `https://api.mpoisk.ru/v6/api`.

Правила обработки:

- endpoint списка задач: `/taskManagement/tasks`;
- endpoint детализации задачи: `/taskManagement/tasks/{taskID}`;
- уборка определяется `taskTypeID=51`;
- завершенная задача определяется `status=3`;
- внешний идентификатор задачи `taskID` используется для идемпотентности;
- внешний объект `mapObjectID` сопоставляется с `regioncity_external_ref` подъезда.

### 4.2. MAX

Канал коммуникации с жителями. Система принимает webhook-события от MAX и отправляет сообщения пользователям. Токен бота и webhook secret должны храниться в Lockbox.

### 4.3. Yandex Lockbox

Хранит секреты:

- RegionCity API token;
- MAX bot token;
- Admin JWT secret;
- MAX webhook secret, если включена проверка webhook-запросов.

## 5. Инфраструктура

Основные облачные ресурсы:

- Yandex API Gateway;
- Yandex Cloud Functions;
- YDB Serverless;
- Object Storage buckets для public/admin frontend и release artifacts;
- IAM service accounts для функций и gateway;
- IAM bindings для доступа к YDB, Lockbox и вызову функций;
- optional timer trigger для polling.

Terraform-модуль расположен в `infra/terraform`.

## 6. Развертывание

Основной dev workflow:

```bash
bash scripts/bootstrap_yc.sh dev
bash scripts/deploy_all.sh dev
```

Reset dev workflow:

```bash
bash scripts/destroy_all.sh dev
```

Для production операции требуют явного подтверждения и реальных секретов.

## 7. Безопасность и ограничения хранения данных

Система должна соблюдать принцип минимизации данных:

- не хранить квартиры;
- не хранить фотографии;
- не хранить детальные delivery logs по пользователям;
- не отображать жителям служебные поля внешней системы;
- использовать soft deactivation вместо hard delete;
- использовать processed external task IDs для предотвращения повторной обработки событий.

## 8. Контроль качества и проверки

В проекте предусмотрены или должны использоваться следующие проверки:

- Python unit/integration tests;
- ruff check;
- terraform fmt;
- terraform validate;
- OpenAPI validation;
- проверка архитектурных ограничений;
- smoke test после deploy.

## 9. Расширяемость

Архитектура допускает добавление:

- новых типов объектов справочника;
- новых типов событий;
- новых внешних источников задач;
- новых каналов уведомлений;
- новых шаблонов сообщений;
- дополнительных пользовательских сценариев, включая сервисные заявки.

Расширение должно выполняться через новые адаптеры и use cases без внедрения инфраструктурных зависимостей в domain/application слои.
