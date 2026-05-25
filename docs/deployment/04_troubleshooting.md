# Troubleshooting

- `yc not authenticated` -> выполните `yc init`.
- `no billing account` -> подключите биллинг к облаку/папке.
- `access denied` -> проверьте роли сервисного аккаунта.
- `bucket already exists globally` -> смените имя bucket в tfvars.
- `Lockbox access denied` -> добавьте lockbox payload viewer роли.
- `Terraform state backend error` -> проверьте backend-<env>.hcl и ключ SA.
- `CORS error` -> проверьте public_origin/admin_origin и redeploy gateway.
- `function deploy failed` -> проверьте zip, SA runtime и Cloud Logs.
- `smoke test failed` -> проверьте API domain, миграции, health endpoint.
- `MAX webhook wrong env` -> убедитесь что prod webhook указывает на prod gateway.
