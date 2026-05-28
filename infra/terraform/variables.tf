variable "cloud_id" {
  type = string

  validation {
    condition     = length(trimspace(var.cloud_id)) > 0
    error_message = "cloud_id must not be empty. Generate the environment configuration with scripts/bootstrap_yc.sh."
  }
}

variable "folder_id" {
  type = string

  validation {
    condition     = length(trimspace(var.folder_id)) > 0
    error_message = "folder_id must not be empty. Generate the environment configuration with scripts/bootstrap_yc.sh."
  }
}

variable "zone" {
  type    = string
  default = "ru-central1-a"
}

variable "environment" {
  type = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be either dev or prod."
  }
}

variable "project_name" {
  type    = string
  default = "resident-notifications"
}

variable "resource_prefix" {
  type    = string
  default = "rn"
}

variable "ydb_location_id" {
  type    = string
  default = "ru-central1"
}

variable "ydb_name" {
  type    = string
  default = "resident-notifications"
}

variable "bucket_public_name" {
  type = string
}

variable "bucket_admin_name" {
  type = string
}

variable "function_runtime" {
  type    = string
  default = "python312"
}

variable "function_memory" {
  type    = number
  default = 256
}

variable "function_timeout_seconds" {
  type    = number
  default = 60
}

variable "gateway_name" {
  type    = string
  default = "resident-notifications-api"
}

variable "public_origin" {
  type = string
}

variable "admin_origin" {
  type = string
}

variable "public_site_url" {
  type = string
}

variable "admin_site_url" {
  type = string
}

variable "regioncity_base_url" {
  type    = string
  default = "https://api.mpoisk.ru/v6/api"
}

variable "regioncity_map_objects_path" {
  type    = string
  default = "/mapObjectManagement/mapObjects"
}

variable "max_api_base_url" {
  type    = string
  default = "https://platform-api.max.ru"
}

variable "max_bot_deeplink_base" {
  type    = string
  default = ""
}

variable "cache_ttl_minutes" {
  type    = number
  default = 10
}

variable "polling_interval_minutes" {
  type    = number
  default = 20
}

variable "polling_overlap_minutes" {
  type    = number
  default = 5
}

variable "max_subscriptions_per_user" {
  type    = number
  default = 20
}

variable "regioncity_api_token_secret_id" {
  type = string
}

variable "regioncity_api_token_secret_version_id" {
  type    = string
  default = ""
}

variable "max_bot_token_secret_id" {
  type = string
}

variable "max_bot_token_secret_version_id" {
  type    = string
  default = ""
}

variable "admin_jwt_secret_id" {
  type = string
}

variable "admin_jwt_secret_version_id" {
  type    = string
  default = ""
}

variable "max_webhook_secret_id" {
  type    = string
  default = ""
}

variable "max_webhook_secret_version_id" {
  type    = string
  default = ""
}

variable "release_artifacts_bucket_name" {
  type = string
}

variable "function_use_mocks" {
  type    = bool
  default = false
}

variable "enable_polling_timer" {
  type    = bool
  default = false
}
