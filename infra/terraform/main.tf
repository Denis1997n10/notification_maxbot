terraform {
  required_version = ">= 1.5.0"

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = ">= 0.120.0"
    }
  }

  backend "s3" {}
}

provider "yandex" {
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.zone
}

locals {
  env = var.environment

  bot_webhook_zip_path          = "../../dist/functions/bot_webhook.zip"
  public_api_zip_path           = "../../dist/functions/public_api.zip"
  admin_api_zip_path            = "../../dist/functions/admin_api.zip"
  regioncity_polling_zip_path   = "../../dist/functions/regioncity_polling.zip"
  notification_sender_zip_path  = "../../dist/functions/notification_sender.zip"

  common_env = {
    ENV                        = var.environment
    REGIONCITY_BASE_URL        = var.regioncity_base_url
    MAX_API_BASE_URL           = var.max_api_base_url
    PUBLIC_SITE_URL            = var.public_site_url
    ADMIN_SITE_URL             = var.admin_site_url
    CACHE_TTL_MINUTES          = tostring(var.cache_ttl_minutes)
    POLLING_INTERVAL_MINUTES   = tostring(var.polling_interval_minutes)
    POLLING_OVERLAP_MINUTES    = tostring(var.polling_overlap_minutes)
    MAX_SUBSCRIPTIONS_PER_USER = tostring(var.max_subscriptions_per_user)
    YDB_ENDPOINT               = yandex_ydb_database_serverless.db.document_api_endpoint
    YDB_DATABASE               = yandex_ydb_database_serverless.db.database_path

    REGIONCITY_API_TOKEN_SECRET_ID = var.regioncity_api_token_secret_id
    MAX_BOT_TOKEN_SECRET_ID        = var.max_bot_token_secret_id
    ADMIN_JWT_SECRET_ID            = var.admin_jwt_secret_id
    USE_MOCKS                      = var.function_use_mocks ? "true" : "false"
  }
}

resource "yandex_iam_service_account" "functions" {
  name = "${var.resource_prefix}-fn-${local.env}"
}

resource "yandex_iam_service_account" "gateway" {
  name = "${var.resource_prefix}-gw-${local.env}"
}

resource "yandex_resourcemanager_folder_iam_member" "fn_ydb" {
  folder_id = var.folder_id
  role      = "ydb.editor"
  member    = "serviceAccount:${yandex_iam_service_account.functions.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "fn_lockbox" {
  folder_id = var.folder_id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.functions.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "gw_invoker" {
  folder_id = var.folder_id
  role      = "serverless.functions.invoker"
  member    = "serviceAccount:${yandex_iam_service_account.gateway.id}"
}

resource "yandex_ydb_database_serverless" "db" {
  name        = "${var.ydb_name}-${local.env}"
  folder_id   = var.folder_id
  location_id = var.ydb_location_id
}

resource "yandex_storage_bucket" "public_site" {
  bucket    = var.bucket_public_name
  folder_id = var.folder_id
}

resource "yandex_storage_bucket" "admin_panel" {
  bucket    = var.bucket_admin_name
  folder_id = var.folder_id
}

resource "yandex_storage_bucket" "release_artifacts" {
  bucket    = var.release_artifacts_bucket_name
  folder_id = var.folder_id
}

resource "yandex_storage_object" "bot_webhook_zip" {
  bucket       = yandex_storage_bucket.release_artifacts.bucket
  key          = "functions/${local.env}/bot_webhook-${filesha256(local.bot_webhook_zip_path)}.zip"
  source       = local.bot_webhook_zip_path
  source_hash  = filemd5(local.bot_webhook_zip_path)
  content_type = "application/zip"
}

resource "yandex_storage_object" "public_api_zip" {
  bucket       = yandex_storage_bucket.release_artifacts.bucket
  key          = "functions/${local.env}/public_api-${filesha256(local.public_api_zip_path)}.zip"
  source       = local.public_api_zip_path
  source_hash  = filemd5(local.public_api_zip_path)
  content_type = "application/zip"
}

resource "yandex_storage_object" "admin_api_zip" {
  bucket       = yandex_storage_bucket.release_artifacts.bucket
  key          = "functions/${local.env}/admin_api-${filesha256(local.admin_api_zip_path)}.zip"
  source       = local.admin_api_zip_path
  source_hash  = filemd5(local.admin_api_zip_path)
  content_type = "application/zip"
}

resource "yandex_storage_object" "regioncity_polling_zip" {
  bucket       = yandex_storage_bucket.release_artifacts.bucket
  key          = "functions/${local.env}/regioncity_polling-${filesha256(local.regioncity_polling_zip_path)}.zip"
  source       = local.regioncity_polling_zip_path
  source_hash  = filemd5(local.regioncity_polling_zip_path)
  content_type = "application/zip"
}

resource "yandex_storage_object" "notification_sender_zip" {
  bucket       = yandex_storage_bucket.release_artifacts.bucket
  key          = "functions/${local.env}/notification_sender-${filesha256(local.notification_sender_zip_path)}.zip"
  source       = local.notification_sender_zip_path
  source_hash  = filemd5(local.notification_sender_zip_path)
  content_type = "application/zip"
}

resource "yandex_function" "bot_webhook" {
  name               = "bot-webhook-${local.env}"
  user_hash          = filesha256(local.bot_webhook_zip_path)
  runtime            = var.function_runtime
  entrypoint         = "handler.handler"
  memory             = var.function_memory
  execution_timeout  = tostring(var.function_timeout_seconds)
  service_account_id = yandex_iam_service_account.functions.id
  environment        = local.common_env

  package {
    bucket_name = yandex_storage_object.bot_webhook_zip.bucket
    object_name = yandex_storage_object.bot_webhook_zip.key
    sha_256     = filesha256(local.bot_webhook_zip_path)
  }
}

resource "yandex_function" "public_api" {
  name               = "public-api-${local.env}"
  user_hash          = filesha256(local.public_api_zip_path)
  runtime            = var.function_runtime
  entrypoint         = "handler.handler"
  memory             = var.function_memory
  execution_timeout  = tostring(var.function_timeout_seconds)
  service_account_id = yandex_iam_service_account.functions.id
  environment        = local.common_env

  package {
    bucket_name = yandex_storage_object.public_api_zip.bucket
    object_name = yandex_storage_object.public_api_zip.key
    sha_256     = filesha256(local.public_api_zip_path)
  }
}

resource "yandex_function" "admin_api" {
  name               = "admin-api-${local.env}"
  user_hash          = filesha256(local.admin_api_zip_path)
  runtime            = var.function_runtime
  entrypoint         = "handler.handler"
  memory             = var.function_memory
  execution_timeout  = tostring(var.function_timeout_seconds)
  service_account_id = yandex_iam_service_account.functions.id
  environment        = local.common_env

  package {
    bucket_name = yandex_storage_object.admin_api_zip.bucket
    object_name = yandex_storage_object.admin_api_zip.key
    sha_256     = filesha256(local.admin_api_zip_path)
  }
}

resource "yandex_function" "regioncity_polling" {
  name               = "regioncity-polling-${local.env}"
  user_hash          = filesha256(local.regioncity_polling_zip_path)
  runtime            = var.function_runtime
  entrypoint         = "handler.handler"
  memory             = var.function_memory
  execution_timeout  = tostring(var.function_timeout_seconds)
  service_account_id = yandex_iam_service_account.functions.id
  environment        = local.common_env

  package {
    bucket_name = yandex_storage_object.regioncity_polling_zip.bucket
    object_name = yandex_storage_object.regioncity_polling_zip.key
    sha_256     = filesha256(local.regioncity_polling_zip_path)
  }
}

resource "yandex_function" "notification_sender" {
  name               = "notification-sender-${local.env}"
  user_hash          = filesha256(local.notification_sender_zip_path)
  runtime            = var.function_runtime
  entrypoint         = "handler.handler"
  memory             = var.function_memory
  execution_timeout  = tostring(var.function_timeout_seconds)
  service_account_id = yandex_iam_service_account.functions.id
  environment        = local.common_env

  package {
    bucket_name = yandex_storage_object.notification_sender_zip.bucket
    object_name = yandex_storage_object.notification_sender_zip.key
    sha_256     = filesha256(local.notification_sender_zip_path)
  }
}

resource "yandex_api_gateway" "gateway" {
  name = "${var.gateway_name}-${local.env}"
  spec = templatefile("${path.module}/../../openapi/api-gateway.yaml.tftpl", {
    bot_webhook_function_id = yandex_function.bot_webhook.id
    public_api_function_id  = yandex_function.public_api.id
    admin_api_function_id   = yandex_function.admin_api.id
    public_origin           = var.public_origin
    admin_origin            = var.admin_origin
  })
}

resource "yandex_function_trigger" "polling_timer" {
  name = "regioncity-polling-${local.env}"

  timer {
    cron_expression = "0 */20 * * * ?"
  }

  function {
    id                 = yandex_function.regioncity_polling.id
    service_account_id = yandex_iam_service_account.functions.id
  }
}

output "api_gateway_domain" {
  value = yandex_api_gateway.gateway.domain
}

output "ydb_endpoint" {
  value = yandex_ydb_database_serverless.db.document_api_endpoint
}

output "ydb_database" {
  value = yandex_ydb_database_serverless.db.database_path
}

output "function_service_account_id" {
  value = yandex_iam_service_account.functions.id
}

output "public_site_url" {
  value = var.public_site_url
}

output "admin_site_url" {
  value = var.admin_site_url
}

output "public_bucket_name" {
  value = yandex_storage_bucket.public_site.bucket
}

output "admin_bucket_name" {
  value = yandex_storage_bucket.admin_panel.bucket
}

output "release_artifacts_bucket_name" {
  value = yandex_storage_bucket.release_artifacts.bucket
}
