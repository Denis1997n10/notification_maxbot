terraform {
  required_version = ">= 1.5.0"
  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = ">= 0.120.0"
    }
  }
}

provider "yandex" {
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.zone
}

locals {
  env = var.environment
}

resource "yandex_iam_service_account" "functions" { name = "notify-fn-${local.env}" }
resource "yandex_iam_service_account" "gateway" { name = "notify-gw-${local.env}" }

resource "yandex_ydb_database_serverless" "db" {
  name      = "notification-${local.env}"
  folder_id = var.folder_id
  location_id = var.ydb_location_id
}

resource "yandex_storage_bucket" "public_site" { bucket = "${var.bucket_prefix}-public-${local.env}" }
resource "yandex_storage_bucket" "admin_panel" { bucket = "${var.bucket_prefix}-admin-${local.env}" }

resource "yandex_function" "bot_webhook" { name="bot-webhook-${local.env}" user_hash="1" runtime="python312" entrypoint="handler.handler" memory=256 execution_timeout="30s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = var.function_zip } environment = var.function_env }
resource "yandex_function" "public_api" { name="public-api-${local.env}" user_hash="1" runtime="python312" entrypoint="handler.handler" memory=256 execution_timeout="30s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = var.function_zip } environment = var.function_env }
resource "yandex_function" "admin_api" { name="admin-api-${local.env}" user_hash="1" runtime="python312" entrypoint="handler.handler" memory=256 execution_timeout="30s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = var.function_zip } environment = var.function_env }
resource "yandex_function" "regioncity_polling" { name="regioncity-polling-${local.env}" user_hash="1" runtime="python312" entrypoint="handler.handler" memory=256 execution_timeout="60s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = var.function_zip } environment = var.function_env }
resource "yandex_function" "notification_sender" { name="notification-sender-${local.env}" user_hash="1" runtime="python312" entrypoint="handler.handler" memory=256 execution_timeout="60s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = var.function_zip } environment = var.function_env }

resource "yandex_api_gateway" "gateway" {
  name = "notification-api-${local.env}"
  spec = file("${path.module}/../../openapi/api-gateway.yaml")
}

resource "yandex_function_trigger" "polling_timer" {
  name = "regioncity-polling-${local.env}"
  timer {
    cron_expression = "0 */20 * * * ?"
  }
  function {
    id = yandex_function.regioncity_polling.id
    service_account_id = yandex_iam_service_account.functions.id
  }
}
