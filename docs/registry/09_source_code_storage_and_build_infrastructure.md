# 09_source_code_storage_and_build_infrastructure

Целевой процесс:
- основной git-репозиторий + зеркало в российской инфраструктуре;
- self-hosted runner (labels: `self-hosted, linux, rn-prod-builder`) в Yandex Cloud/РФ;
- release-артефакты, function zip и checksums в Yandex Object Storage;
- Terraform state в Yandex Object Storage (раздельные ключи dev/prod);
- секреты в Yandex Lockbox;
- runtime в Yandex Cloud ru-central1.

GitHub может использоваться для разработки, но не является единственным обязательным production-контуром сборки.
