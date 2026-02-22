variable "region" {
  type    = string
  default = "us-east-1"
}

variable "expected_account_id" {
  type = string
}

variable "project" {
  type    = string
  default = "signalcraft"
}

variable "publish_bucket" {
  type = string
}

variable "publish_prefix" {
  type    = string
  default = "jobintel"
}

variable "backup_bucket" {
  type = string
}

variable "backup_uri" {
  type = string
}

variable "backup_required_keys" {
  type    = list(string)
  default = ["metadata.json", "state.tar.zst", "manifests.tar.zst"]
}

variable "receipt_bucket" {
  type = string
}

variable "receipt_prefix" {
  type    = string
  default = "jobintel/dr-orchestrator/receipts"
}

variable "notification_topic_arn" {
  type = string
}

variable "alarm_topic_arn" {
  type    = string
  default = ""
}

variable "enable_triggers" {
  type    = bool
  default = false
}

variable "schedule_expression" {
  type    = string
  default = "rate(15 minutes)"
}

variable "publish_provider" {
  type    = string
  default = "openai"
}

variable "profile" {
  type    = string
  default = "cs"
}

variable "expected_marker_file" {
  type    = string
  default = "openai_top.cs.md"
}

variable "max_freshness_hours" {
  type    = number
  default = 6
}

variable "metric_namespace" {
  type    = string
  default = "SignalCraft/DR"
}

variable "alarm_period_seconds" {
  type    = number
  default = 300
}

variable "alarm_evaluation_periods" {
  type    = number
  default = 1
}

variable "dr_runner_name" {
  type    = string
  default = "jobintel-dr-runner"
}

variable "dr_vpc_id" {
  type = string
}

variable "dr_subnet_id" {
  type = string
}

variable "dr_allowed_cidr" {
  type    = string
  default = "10.0.0.0/8"
}

variable "dr_key_name" {
  type    = string
  default = ""
}

variable "dr_instance_type" {
  type    = string
  default = "t4g.small"
}

variable "dr_ami_id" {
  type    = string
  default = ""
}

variable "namespace" {
  type    = string
  default = "jobintel"
}

variable "validate_timeout_seconds" {
  type    = number
  default = 300
}

variable "manual_approval_timeout_seconds" {
  type    = number
  default = 86400
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 600
}

variable "lambda_memory_mb" {
  type    = number
  default = 512
}

variable "terraform_version" {
  type    = string
  default = "1.8.5"
}

variable "tf_state_key_prefix" {
  type    = string
  default = "jobintel/dr/terraform"
}

variable "create_tf_backend_resources" {
  type    = bool
  default = true
}

variable "tf_state_bucket_name" {
  type    = string
  default = ""
}

variable "tf_lock_table_name" {
  type    = string
  default = ""
}

variable "tf_bundle_s3_key" {
  type    = string
  default = "jobintel/dr-orchestrator/artifacts/dr-terraform-module.zip"
}

variable "codebuild_image" {
  type    = string
  default = "aws/codebuild/standard:7.0"
}

variable "codebuild_compute_type" {
  type    = string
  default = "BUILD_GENERAL1_MEDIUM"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
