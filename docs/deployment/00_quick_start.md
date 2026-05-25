# Quick Start

1. Установите инструменты: yc, terraform, python3, pip, node, npm, git, zip, jq.
2. Выполните `yc init`.
3. Выполните bootstrap:
   - `./scripts/bootstrap_yc.sh dev`
4. Выполните деплой:
   - `./scripts/deploy_all.sh dev`

Bootstrap автоматически:
- создаёт/переиспользует deploy SA,
- создаёт bucket для terraform state,
- создаёт S3 access key для backend,
- создаёт/обновляет Lockbox secrets,
- генерирует `.local/dev/backend.env`, `infra/terraform/backend-dev.hcl`, `infra/terraform/env/dev.auto.tfvars`.

Если real wiring ещё не завершён, dev может работать в smoke-режиме с `USE_MOCKS=true`.
Для prod по умолчанию `USE_MOCKS=false`.

После deploy URL печатаются в конце `deploy_all.sh`.
