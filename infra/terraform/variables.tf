variable "cloud_id" {
  type = string
}

variable "folder_id" {
  type = string
}

variable "zone" {
  type    = string
  default = "ru-central1-a"
}

variable "environment" {
  type = string
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

variable "max_api_base_url" {
  type    = string
  default = "https://botapi.max.ru"
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

variable "max_bot_token_secret_id" {
  type = string
}

variable "admin_jwt_secret_id" {
  type = string
}

variable "release_artifacts_bucket_name" {
  type    = string
  default = ""
}

variable "function_use_mocks" {
  type    = bool
  default = false
}

variable "enable_notification_sender" {
  type    = bool
  default = false
}
