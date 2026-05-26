# Quick Start: dev smoke deploy в Yandex Cloud

Этот документ описывает фактически проверенный первый запуск dev-контура.

Цель первого запуска — поднять инфраструктуру и проверить, что API Gateway вызывает Cloud Functions. Это не production-запуск бизнес-логики.

## 1. Клонировать репозиторий

```bash
git clone https://github.com/Denis1997n10/notification_maxbot.git
cd notification_maxbot
```

Если репозиторий уже есть:

```bash
git pull
```

## 2. Проверить инструменты

```bash
bash scripts/check_tools.sh
```

Должны быть установлены:

- yc
- terraform
- python / python3
- pip
- node
- npm
- git
- zip
- jq

Для Ubuntu/WSL может понадобиться:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates zip unzip jq python3 python3-pip python3-venv python-is-python3 nodejs npm
```

## 3. Авторизоваться в Yandex Cloud

```bash
yc init
```

Во время `yc init` нужно выбрать cloud и folder.

Рекомендации:

- для первого запуска можно выбрать существующий folder, например `default`;
- если нужна отдельная folder, лучше создать её заранее в Yandex Cloud Console;
- имя folder лучше использовать латиницей и через дефисы, например `notification-maxbot-dev`;
- не рекомендуется создавать folder с русским названием через WSL/CLI, могут быть ошибки UTF-8.

Проверка:

```bash
yc config list
yc config get cloud-id
yc config get folder-id
```

## 4. Настроить Terraform provider mirror

Если Terraform не может скачать provider `yandex-cloud/yandex` из `registry.terraform.io`, создайте `~/.terraformrc`:

```bash
cat > ~/.terraformrc <<'EOF'
provider_installation {
  network_mirror {
    url     = "https://terraform-mirror.yandexcloud.net/"
    include = ["registry.terraform.io/yandex-cloud/yandex"]
  }

  direct {
    exclude = ["registry.terraform.io/yandex-cloud/yandex"]
  }
}
EOF
```

## 5. Bootstrap dev

```bash
bash scripts/bootstrap_yc.sh dev
```

Bootstrap автоматически:

- создаёт или переиспользует deploy service account;
- создаёт bucket для Terraform state;
- создаёт S3 access key для Terraform backend;
- создаёт или обновляет Lockbox secrets;
- генерирует `.local/dev/backend.env`;
- генерирует `infra/terraform/backend-dev.hcl`;
- генерирует `infra/terraform/env/dev.auto.tfvars`.

Для первого smoke-запуска можно оставить значения по умолчанию:

```text
PUBLIC origin [http://localhost:5173]: Enter
ADMIN origin [http://localhost:5174]: Enter
MAX API base URL [https://botapi.max.ru]: Enter
```

Токены внешних систем вводятся только в терминал. Не коммитить и не отправлять их в чат.

Для dev по умолчанию:

```hcl
function_use_mocks = true
enable_polling_timer = false
```

## 6. Deploy dev

```bash
bash scripts/deploy_all.sh dev
```

На вопрос:

```text
Confirm terraform apply? [yes/no]:
```

нужно ввести строго:

```text
yes
```

Что делает deploy:

- собирает ZIP-пакеты функций;
- загружает большие function packages через Object Storage;
- выполняет `terraform init`, `validate`, `plan`, `apply`;
- скипает реальные YDB migrations в dev/mock режиме;
- собирает и загружает public/admin static frontend;
- запускает smoke tests.

Успешный результат:

```text
Skipping real YDB migrations because USE_MOCKS=true or ENV=dev
[upload-static] uploaded to rn-public-dev and rn-admin-dev
smoke ok (dev)
API Gateway: https://...
Health: https://.../api/v1/system/health
```

## 7. Проверить API вручную

```bash
API_DOMAIN=$(cd infra/terraform && terraform output -raw api_gateway_domain)

curl "https://${API_DOMAIN}/api/v1/system/health"
curl "https://${API_DOMAIN}/api/v1/system/version"
curl "https://${API_DOMAIN}/api/v1/public/districts"
```

## 8. Проверить bot webhook без MAX

```bash
API_DOMAIN=$(cd infra/terraform && terraform output -raw api_gateway_domain)

curl -i -X POST "https://${API_DOMAIN}/api/v1/bot/webhook" \
  -H "Content-Type: application/json" \
  -d '{"update_type":"message_created","message":{"body":{"text":"/start"}},"user":{"user_id":"test-user"}}'
```

Ожидаемый smoke-результат: HTTP 200 и JSON-ответ. Это проверяет, что API Gateway вызывает bot webhook Cloud Function.

## Текущие ограничения dev smoke mode

Сейчас dev-контур работает как инфраструктурный smoke mode:

- `USE_MOCKS=true`;
- реальные YDB migrations не применяются;
- real repositories/runtime wiring ещё не включены;
- polling timer выключен по умолчанию;
- notification sender не вынесен в отдельную функцию из-за возможных квот;
- public/admin site URLs в первом bootstrap могут быть `localhost`, хотя статика загружается в Object Storage buckets.

## Что нельзя удалять

Не удалять bucket:

```text
rn-dev-terraform-state
```

В нём хранится Terraform state.

## Повторный deploy

```bash
git pull
bash scripts/deploy_all.sh dev
```

## CI/CD

CI deploy требует runner-side `.local/<env>` или эквивалентных секретов. Пока основной поддерживаемый путь — локальный deploy с машины, где выполнен `yc init`.
