# Troubleshooting

- `yc not authenticated` -> выполните `yc init`.
- `no billing account` -> подключите биллинг к облаку/папке.
- `access denied` -> проверьте роли сервисного аккаунта.
- `bucket already exists globally` -> смените имена bucket в tfvars.
- `Lockbox access denied` -> проверьте роль `lockbox.payloadViewer`.
- `Terraform state backend error` -> проверьте `AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY` в `.local/<env>/backend.env`.
- `missing YDB_ENDPOINT/YDB_DATABASE` -> проверьте terraform outputs и успешность apply.
- `NotImplementedError from composition root` -> включите `USE_MOCKS=true` для dev или доделайте runtime wiring.
- `CORS error` -> проверьте `public_origin/admin_origin` в tfvars и redeploy gateway.
- `API Gateway health/version 404` -> проверьте template OpenAPI и deploy gateway.
- `function package missing` -> перезапустите `backend/scripts/build_functions.sh <env>`.
- `yc CLI not authenticated` -> заново `yc init`.
- `MAX webhook points to wrong env` -> убедитесь, что prod webhook смотрит на prod gateway.
