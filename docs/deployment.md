# Deployment

## Environments
- Dev: auto deploy from `main`.
- Prod: manual workflow dispatch.

## Terraform remote state
Use S3-compatible backend in Yandex Object Storage.
Example state keys:
- `resident-notifications/dev/terraform.tfstate`
- `resident-notifications/prod/terraform.tfstate`

Do not commit credentials. Pass backend settings via CLI/CI secrets.

## Locking strategy
Yandex Object Storage backend does not provide DynamoDB-style locking.
Use GitHub Actions concurrency groups (`deploy-dev`, `deploy-prod`) and never run concurrent applies manually.

## Pre-apply required values
Fill:
- `cloud_id`, `folder_id`
- bucket names
- frontend origins/urls
- lockbox secret IDs (not values)

## Deploy flow
1. build function artifacts
2. terraform apply
3. apply YDB migrations
4. deploy function versions
5. deploy API Gateway
6. upload static frontends
7. run smoke tests (dev)
