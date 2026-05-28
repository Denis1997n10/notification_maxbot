# 10_third_party_components

## Python
- pytest/pytest-asyncio/PyYAML/ruff (dev/build checks).

## Frontend npm
- react/react-dom/react-router-dom
- qrcode (QR rendering for MAX deep links)
- xlsx (admin Excel import/export)
- vite/@vitejs/plugin-react

## Terraform
- provider: yandex-cloud/yandex

## Managed services
- Yandex Cloud Functions, API Gateway, YDB Serverless, Lockbox, Object Storage

## External APIs
- RegionCity/MPOISK (runtime-critical for event ingestion)
- MAX API (runtime-critical for notifications)

Назначение и критичность документируются в release inventory (dependency-inventory.txt).
