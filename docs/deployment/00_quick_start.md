# Quick Start: Dev Deploy and Reset

Этот workflow разворачивает dev-контур serverless resident notification platform. MVP обрабатывает события уборки подъездов из RegionCity/MPOISK, но инфраструктура и доменная модель остаются универсальными для подписок и уведомлений по объектам справочника.

## Требования

Установите `yc`, `terraform`, `python3`, `pip`, `node`, `npm`, `git`, `zip` и `jq`, затем авторизуйтесь:

```bash
yc init
```

В профиле `yc` должны быть заданы непустые `cloud-id` и `folder-id`.

## Полный dev deploy

Запускайте из корня репозитория:

```bash
bash scripts/deploy_all.sh dev
```

Это единая команда для dev. Она:

- создаёт или переиспользует deploy service account, bucket состояния Terraform и S3 access key;
- генерирует `.local/dev/backend.env`, `infra/terraform/backend-dev.hcl` и `infra/terraform/env/dev.auto.tfvars`;
- использует mock-заглушки секретов и `function_use_mocks=true` по умолчанию;
- собирает Cloud Function ZIP так, чтобы содержимое `backend/src` находилось в корне архива;
- выполняет Terraform с `-input=false`, миграции, сборку/загрузку frontend и smoke check.

Для другого frontend origin задайте значения при запуске:

```bash
PUBLIC_ORIGIN=https://dev-public.example.com ADMIN_ORIGIN=https://dev-admin.example.com bash scripts/deploy_all.sh dev
```

Terraform не должен запрашивать значения вручную. При пустых `environment`, `cloud_id` или `folder_id` запуск завершается ошибкой до изменения инфраструктуры.

## Dev с реальными интеграциями

Mock-режим предназначен для безопасного первого deploy. Для проверки RegionCity/MAX в dev явно создайте dev-секреты в Lockbox:

```bash
bash scripts/bootstrap_yc.sh dev
bash scripts/switch_dev_to_real.sh
bash scripts/deploy_all.sh dev
bash scripts/seed_functional_dev.sh
```

Вернуться к mock-режиму:

```bash
bash scripts/switch_dev_to_smoke.sh
bash scripts/deploy_all.sh dev
```

## Reset dev

Для полного удаления Terraform-managed dev-ресурсов:

```bash
bash scripts/destroy_all.sh dev
```

Скрипт сначала очищает public/admin/release buckets командой `yc storage s3 rm --recursive`, и только после успешной очистки запускает `terraform destroy -input=false -auto-approve`. Bucket удалённого Terraform state сохраняется для управления состоянием и повторного deploy.

## Production

Dev может использовать mock-секреты. Production не изменяется автоматически: `bootstrap_yc.sh prod`, `deploy_all.sh prod`, `destroy_all.sh prod` и обновление production Lockbox требуют явного текстового подтверждения. Workflow GitHub Actions для production не выполняет mutation до настройки защищённого approval/secrets flow.

Для smoke-проверки production admin UI и MAX bot:

```bash
bash scripts/bootstrap_yc.sh prod
ADMIN_BOOTSTRAP_LOGIN='<login>' ADMIN_BOOTSTRAP_PASSWORD='<strong-password>' bash scripts/deploy_all.sh prod
bash scripts/register_max_webhook.sh prod set
```

`bootstrap_yc.sh prod` запрашивает RegionCity API token, MAX bot token, admin JWT secret и MAX webhook secret и сохраняет в локальные файлы только Lockbox IDs/version IDs. `deploy_all.sh prod` создаёт static website buckets и собирает admin/public frontend с URL созданного API Gateway. `register_max_webhook.sh prod set` получает токен и secret непосредственно из Lockbox и регистрирует события `message_created` и `bot_started`; значение `MAX_WEBHOOK_SECRET` защищает входящие webhook-вызовы заголовком `X-Max-Bot-Api-Secret`.

Если инфраструктура и frontend уже развернуты, а создание администратора было пропущено или завершилось ошибкой, не запускайте bootstrap повторно. Создайте или обновите администратора отдельно:

```bash
ADMIN_BOOTSTRAP_LOGIN='<login>' ADMIN_BOOTSTRAP_PASSWORD='<strong-password>' bash scripts/seed_admin_user.sh prod
```

Timer RegionCity polling по умолчанию остаётся выключенным (`enable_polling_timer=false`). До отдельной проверки end-to-end обработки внешних событий production smoke ограничен входом в админку, тестовым уведомлением из неё и командами MAX bot.

Сгенерированные backend/tfvars/env-файлы и локальные Terraform state/cache не должны коммититься.
