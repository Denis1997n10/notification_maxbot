# Инструкция по установке, развертыванию и эксплуатации

## 1. Назначение документа

Документ описывает порядок подготовки окружения, развертывания dev/prod-контуров и базовой эксплуатации программного обеспечения.

## 2. Требования к окружению

Для локальной машины или CI/CD runner требуются:

- Git;
- Yandex Cloud CLI `yc`;
- Terraform;
- Python 3;
- pip;
- Node.js;
- npm;
- jq;
- zip;
- bash-compatible shell.

Перед первым развертыванием необходимо выполнить авторизацию:

```bash
yc init
```

Профиль `yc` должен содержать непустые значения:

```bash
yc config get cloud-id
yc config get folder-id
```

## 3. Подготовка исходного кода

```bash
git clone https://github.com/Denis1997n10/notification_maxbot.git
cd notification_maxbot
```

## 4. Dev-развертывание

Dev-контур предназначен для проверки инфраструктуры, frontend, API Gateway, Cloud Functions и smoke-сценариев.

Основная команда:

```bash
bash scripts/deploy_all.sh dev
```

Если локальные bootstrap-файлы еще не созданы, сначала выполнить:

```bash
bash scripts/bootstrap_yc.sh dev
bash scripts/deploy_all.sh dev
```

В dev-режиме допускается использование mock-секретов. Terraform не должен запрашивать значения переменных вручную. Если такое произошло, процесс развертывания считается некорректным и должен быть остановлен.

## 5. Production-развертывание

Production требует явного подтверждения и реальных секретов.

Базовый порядок:

```bash
bash scripts/bootstrap_yc.sh prod
ADMIN_BOOTSTRAP_LOGIN='<login>' ADMIN_BOOTSTRAP_PASSWORD='<strong-password>' bash scripts/deploy_all.sh prod
bash scripts/register_max_webhook.sh prod set
```

Production-секреты должны храниться в Yandex Lockbox. Не допускается хранение production-токенов в исходном коде, истории shell или публичных файлах конфигурации.

## 6. Сборка Cloud Functions

Сборка выполняется скриптом:

```bash
bash backend/scripts/build_functions.sh dev
```

Требование к ZIP-архиву: содержимое `backend/src` должно быть помещено в корень ZIP. Это необходимо для корректной работы импортов вида:

```python
from composition.container import api_response
```

## 7. Загрузка frontend

Frontend собирается и загружается в Object Storage скриптом deploy workflow. Для ручной проверки используется:

```bash
bash backend/scripts/upload_static.sh dev
```

Для Object Storage должны использоваться команды:

```bash
yc storage s3 cp
yc storage s3 rm
```

Команда `yc storage cp` не является корректной для данного сценария.

## 8. Reset / destroy dev

Для полного удаления dev-ресурсов используется:

```bash
bash scripts/destroy_all.sh dev
```

Скрипт должен сначала очистить Object Storage buckets, а затем выполнить Terraform destroy. Это необходимо, потому что облако не удаляет непустые бакеты.

Если требуется ручная очистка:

```bash
yc storage s3 rm --recursive s3://rn-public-dev/
yc storage s3 rm --recursive s3://rn-admin-dev/
yc storage s3 rm --recursive s3://rn-release-dev/
```

После этого:

```bash
cd infra/terraform
terraform destroy -var-file="env/dev.auto.tfvars"
```

Ручной Terraform запуск допустим только для диагностики. Нормальный процесс должен идти через scripts.

## 9. Проверка работоспособности

После deploy проверить health endpoint:

```bash
API_DOMAIN=$(cd infra/terraform && terraform output -raw api_gateway_domain)
curl "https://${API_DOMAIN}/api/v1/system/health"
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

Также проверить версию:

```bash
curl "https://${API_DOMAIN}/api/v1/system/version"
```

## 10. Логи и диагностика

Логи Cloud Functions просматриваются через Yandex Cloud CLI:

```bash
yc serverless function list
yc serverless function logs <FUNCTION_ID_OR_NAME> --limit 100
```

При ошибке `502 Bad Gateway` в API Gateway необходимо проверять логи соответствующей Cloud Function. Обычно 502 означает, что API Gateway вызвал функцию, но функция упала на импорте, конфигурации, runtime-ошибке или вернула некорректный формат ответа.

## 11. Типовые эксплуатационные ошибки

### 11.1. Terraform спрашивает переменные руками

Причина: не создан или не передан `env/dev.auto.tfvars`.

Решение:

```bash
bash scripts/bootstrap_yc.sh dev
bash scripts/deploy_all.sh dev
```

### 11.2. `folder_id must not be empty`

Причина: в `yc config` отсутствует folder-id или bootstrap был выполнен с пустыми значениями.

Решение:

```bash
yc config get folder-id
yc config set folder-id <folder_id>
bash scripts/bootstrap_yc.sh dev
```

### 11.3. `BucketNotEmpty`

Причина: попытка удалить Object Storage bucket с файлами внутри.

Решение:

```bash
bash scripts/empty_storage_buckets.sh dev
bash scripts/destroy_all.sh dev
```

### 11.4. `ModuleNotFoundError` в Cloud Function

Причина: неправильная структура ZIP-архива.

Решение: пересобрать функции через актуальный скрипт:

```bash
bash backend/scripts/build_functions.sh dev
bash scripts/deploy_all.sh dev
```

## 12. Резервное копирование и восстановление

На текущем этапе резервное копирование должно быть отдельно спроектировано для production. Минимальные объекты для контроля:

- Terraform state bucket;
- YDB database;
- Lockbox secrets;
- исходный код и release artifacts.

## 13. Обновление версии

Рекомендуемый порядок обновления:

1. Получить актуальный код.
2. Проверить изменения.
3. Выполнить сборку и тесты.
4. Выполнить deploy.
5. Проверить smoke endpoints.
6. Проверить пользовательские сценарии.

```bash
git pull
bash scripts/deploy_all.sh dev
```
