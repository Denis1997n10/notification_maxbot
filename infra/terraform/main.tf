terraform {
  required_version = ">= 1.5.0"
  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = ">= 0.120.0"
    }
  }
}
provider "yandex" { cloud_id = var.cloud_id folder_id = var.folder_id zone = var.zone }

locals {
  env = var.environment
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
    USE_MOCKS                       = var.function_use_mocks ? "true" : "false"
  }
}
resource "yandex_iam_service_account" "functions" { name = "${var.resource_prefix}-fn-${local.env}" }
resource "yandex_iam_service_account" "gateway" { name = "${var.resource_prefix}-gw-${local.env}" }

resource "yandex_resourcemanager_folder_iam_member" "fn_ydb" { folder_id = var.folder_id role = "ydb.editor" member = "serviceAccount:${yandex_iam_service_account.functions.id}" }
resource "yandex_resourcemanager_folder_iam_member" "fn_lockbox" { folder_id = var.folder_id role = "lockbox.payloadViewer" member = "serviceAccount:${yandex_iam_service_account.functions.id}" }
resource "yandex_resourcemanager_folder_iam_member" "gw_invoker" { folder_id = var.folder_id role = "serverless.functions.invoker" member = "serviceAccount:${yandex_iam_service_account.gateway.id}" }

resource "yandex_ydb_database_serverless" "db" { name = "${var.ydb_name}-${local.env}" folder_id = var.folder_id location_id = var.ydb_location_id }
resource "yandex_storage_bucket" "public_site" { bucket = var.bucket_public_name }
resource "yandex_storage_bucket" "admin_panel" { bucket = var.bucket_admin_name }
resource "yandex_storage_bucket" "release_artifacts" {
  count  = var.release_artifacts_bucket_name == "" ? 0 : 1
  bucket = var.release_artifacts_bucket_name
}


resource "yandex_function" "bot_webhook" { name="bot-webhook-${local.env}" user_hash="1" runtime=var.function_runtime entrypoint="handler.handler" memory=var.function_memory execution_timeout="${var.function_timeout_seconds}s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = "../../dist/functions/bot_webhook.zip" } environment = local.common_env }
resource "yandex_function" "public_api" { name="public-api-${local.env}" user_hash="1" runtime=var.function_runtime entrypoint="handler.handler" memory=var.function_memory execution_timeout="${var.function_timeout_seconds}s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = "../../dist/functions/public_api.zip" } environment = local.common_env }
resource "yandex_function" "admin_api" { name="admin-api-${local.env}" user_hash="1" runtime=var.function_runtime entrypoint="handler.handler" memory=var.function_memory execution_timeout="${var.function_timeout_seconds}s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = "../../dist/functions/admin_api.zip" } environment = local.common_env }
resource "yandex_function" "regioncity_polling" { name="regioncity-polling-${local.env}" user_hash="1" runtime=var.function_runtime entrypoint="handler.handler" memory=var.function_memory execution_timeout="${var.function_timeout_seconds}s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = "../../dist/functions/regioncity_polling.zip" } environment = local.common_env }
resource "yandex_function" "notification_sender" { name="notification-sender-${local.env}" user_hash="1" runtime=var.function_runtime entrypoint="handler.handler" memory=var.function_memory execution_timeout="${var.function_timeout_seconds}s" service_account_id=yandex_iam_service_account.functions.id content { zip_filename = "../../dist/functions/notification_sender.zip" } environment = local.common_env }

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
  timer { cron_expression = "0 */20 * * * ?" }
  function { id = yandex_function.regioncity_polling.id service_account_id = yandex_iam_service_account.functions.id }
}
output "api_gateway_domain" { value = yandex_api_gateway.gateway.domain }

output "ydb_endpoint" { value = yandex_ydb_database_serverless.db.document_api_endpoint }
output "ydb_database" { value = yandex_ydb_database_serverless.db.database_path }
output "function_service_account_id" { value = yandex_iam_service_account.functions.id }
output "public_site_url" { value = var.public_site_url }
output "admin_site_url" { value = var.admin_site_url }
