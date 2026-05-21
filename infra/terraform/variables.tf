variable "cloud_id" { type = string }
variable "folder_id" { type = string }
variable "zone" { type = string default = "ru-central1-a" }
variable "environment" { type = string }
variable "ydb_location_id" { type = string default = "ru-central1" }
variable "bucket_prefix" { type = string default = "notification-maxbot" }
variable "function_zip" { type = string default = "build/functions.zip" }
variable "function_env" { type = map(string) default = {} }
