# Deployment

## Environments

- `dev`: локальный полный deploy одной командой `bash scripts/deploy_all.sh dev`; mock-секреты включены по умолчанию.
- `prod`: только после явного подтверждения оператора; автоматическое изменение production из CI отключено до настройки защищённого approval/secrets flow.

## Generated configuration

`scripts/bootstrap_yc.sh <env>` создаёт:

- `.local/<env>/backend.env` с S3 backend credentials и Yandex Cloud IDs;
- `infra/terraform/backend-<env>.hcl` для удалённого state;
- `infra/terraform/env/<env>.auto.tfvars` со всеми переменными deploy.

Файлы локальные и исключены из Git. `cloud_id`, `folder_id` и `environment` не могут быть пустыми; Terraform scripts используют `-input=false` и не запрашивают переменные интерактивно.

## Remote state

Terraform state хранится в Yandex Object Storage через S3-compatible backend:

- `resident-notifications/dev/terraform.tfstate`
- `resident-notifications/prod/terraform.tfstate`

Object Storage objects копируются и удаляются через `yc storage s3 ...`. Credentials не коммитятся.

## Deploy flow

```bash
bash scripts/deploy_all.sh dev
```

Последовательность: bootstrap dev-конфигурации, сборка Cloud Function archives, `terraform init/validate/plan/apply`, миграции YDB, загрузка статических сайтов и smoke checks. ZIP-архивы Cloud Functions содержат `backend/src` в корне архива для корректных импортов runtime.

Production функции получают значения секретов через Lockbox bindings (`secrets` blocks), а не через tfvars. Admin/public buckets настроены как static websites, и frontend build получает фактический URL API Gateway.

Для production smoke admin/bot:

```bash
bash scripts/bootstrap_yc.sh prod
ADMIN_BOOTSTRAP_LOGIN='<login>' ADMIN_BOOTSTRAP_PASSWORD='<strong-password>' bash scripts/deploy_all.sh prod
MAX_BOT_TOKEN='<token>' MAX_WEBHOOK_SECRET='<non-empty-secret-entered-during-bootstrap>' bash scripts/max_webhook.sh set
```

Polling timer остаётся выключенным, пока отдельно не подтверждён end-to-end поток RegionCity events -> subscriptions -> MAX notifications.

## Destroy flow

```bash
bash scripts/destroy_all.sh dev
```

Сначала удаляются objects из Terraform-managed public/admin/release buckets, затем выполняется `terraform destroy`. State bucket намеренно не очищается этим скриптом.

## Concurrency

Yandex Object Storage backend не предоставляет DynamoDB-style locking. Не запускайте параллельные apply/destroy для одного окружения; CI concurrency group сохраняется как дополнительная защита.
