# Quick Start

1. Установите инструменты: yc, terraform, python3, pip, node, npm, git, zip, jq.
2. Выполните `yc init`.
3. Выполните bootstrap:
   - `./scripts/bootstrap_yc.sh dev`
4. Выполните деплой:
   - `./scripts/deploy_all.sh dev`
5. Smoke-тест:
   - `bash backend/scripts/smoke_test.sh dev`
6. URL выводятся в конце deploy_all.sh.

Если скрипт падает — смотрите `docs/deployment/04_troubleshooting.md` и сообщение шага.
