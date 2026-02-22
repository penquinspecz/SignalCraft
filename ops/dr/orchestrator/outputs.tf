output "state_machine_arn" {
  value = aws_sfn_state_machine.dr_orchestrator.arn
}

output "state_machine_name" {
  value = aws_sfn_state_machine.dr_orchestrator.name
}

output "runner_lambda_name" {
  value = aws_lambda_function.runner.function_name
}

output "infra_codebuild_project_name" {
  value = aws_codebuild_project.dr_infra.name
}

output "schedule_rule_name" {
  value = aws_cloudwatch_event_rule.schedule.name
}

output "schedule_rule_enabled" {
  value = var.enable_triggers
}

output "pipeline_freshness_alarm_name" {
  value = aws_cloudwatch_metric_alarm.pipeline_freshness.alarm_name
}

output "publish_correctness_alarm_name" {
  value = aws_cloudwatch_metric_alarm.publish_correctness.alarm_name
}

output "terraform_state_bucket" {
  value = local.tf_state_bucket_name
}

output "terraform_state_key" {
  value = local.tf_state_key
}

output "terraform_lock_table" {
  value = local.tf_lock_table_name
}

output "terraform_bundle_s3_uri" {
  value = "s3://${var.receipt_bucket}/${local.tf_bundle_key}"
}
