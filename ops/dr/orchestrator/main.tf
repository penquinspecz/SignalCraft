provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix   = "${var.project}-dr-orchestrator"
  lambda_name   = "${local.name_prefix}-runner"
  sfn_name      = "${local.name_prefix}-state-machine"
  log_group_sfn = "/aws/vendedlogs/states/${local.sfn_name}"

  alarm_topic_arn_effective = var.alarm_topic_arn != "" ? var.alarm_topic_arn : var.notification_topic_arn
  alarm_actions             = local.alarm_topic_arn_effective != "" ? [local.alarm_topic_arn_effective] : []

  tf_state_bucket_name = var.tf_state_bucket_name != "" ? var.tf_state_bucket_name : "${var.project}-dr-tfstate-${data.aws_caller_identity.current.account_id}-${var.region}"
  tf_lock_table_name   = var.tf_lock_table_name != "" ? var.tf_lock_table_name : "${var.project}-dr-tf-lock"
  tf_state_key         = "${trim(var.tf_state_key_prefix, "/")}/dr-runner.tfstate"
  tf_bundle_key        = trim(var.tf_bundle_s3_key, "/")
  dr_infra_buildspec   = yamlencode(yamldecode(file("${path.module}/buildspec-dr-infra.yml")))

  common_tags = merge(
    {
      ManagedBy = "terraform"
      Purpose   = "jobintel-dr"
      Project   = var.project
    },
    var.tags
  )

  schedule_input = {
    expected_account_id      = var.expected_account_id
    region                   = var.region
    project                  = var.project
    publish_bucket           = var.publish_bucket
    publish_prefix           = var.publish_prefix
    backup_bucket            = var.backup_bucket
    backup_uri               = var.backup_uri
    backup_required_keys     = var.backup_required_keys
    receipt_bucket           = var.receipt_bucket
    receipt_prefix           = var.receipt_prefix
    notification_topic_arn   = var.notification_topic_arn
    provider                 = var.publish_provider
    profile                  = var.profile
    expected_marker_file     = var.expected_marker_file
    max_freshness_hours      = var.max_freshness_hours
    metric_namespace         = var.metric_namespace
    dr_runner_name           = var.dr_runner_name
    dr_vpc_id                = var.dr_vpc_id
    dr_subnet_id             = var.dr_subnet_id
    dr_allowed_cidr          = var.dr_allowed_cidr
    dr_key_name              = var.dr_key_name
    dr_instance_type         = var.dr_instance_type
    dr_ami_id                = var.dr_ami_id
    namespace                = var.namespace
    validate_timeout_seconds = var.validate_timeout_seconds
    force_run                = false
  }
}

data "archive_file" "runner_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/dr_orchestrator.py"
  output_path = "${path.module}/dr_orchestrator_lambda.zip"
}

data "archive_file" "dr_tf_bundle" {
  type        = "zip"
  output_path = "${path.module}/dr_terraform_module.zip"

  source {
    content  = file("${path.module}/../terraform/backend.tf")
    filename = "backend.tf"
  }

  source {
    content  = file("${path.module}/../terraform/main.tf")
    filename = "main.tf"
  }

  source {
    content  = file("${path.module}/../terraform/outputs.tf")
    filename = "outputs.tf"
  }

  source {
    content  = file("${path.module}/../terraform/variables.tf")
    filename = "variables.tf"
  }

  source {
    content  = file("${path.module}/../terraform/versions.tf")
    filename = "versions.tf"
  }
}

resource "aws_s3_bucket" "tf_state" {
  count  = var.create_tf_backend_resources ? 1 : 0
  bucket = local.tf_state_bucket_name
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  count                   = var.create_tf_backend_resources ? 1 : 0
  bucket                  = aws_s3_bucket.tf_state[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "tf_state" {
  count  = var.create_tf_backend_resources ? 1 : 0
  bucket = aws_s3_bucket.tf_state[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  count  = var.create_tf_backend_resources ? 1 : 0
  bucket = aws_s3_bucket.tf_state[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_dynamodb_table" "tf_lock" {
  count        = var.create_tf_backend_resources ? 1 : 0
  name         = local.tf_lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = local.common_tags
}

resource "aws_s3_object" "dr_tf_bundle" {
  bucket = var.receipt_bucket
  key    = local.tf_bundle_key
  source = data.archive_file.dr_tf_bundle.output_path
  etag   = filemd5(data.archive_file.dr_tf_bundle.output_path)
  tags   = local.common_tags
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = local.log_group_sfn
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "codebuild" {
  name              = "/aws/codebuild/${local.name_prefix}-dr-infra"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
      },
      {
        Sid      = "DescribeRunner"
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
      },
      {
        Sid    = "SSMValidate"
        Effect = "Allow"
        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:ListCommands",
          "ssm:ListCommandInvocations"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ListBucketsUsed"
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.publish_bucket}",
          "arn:aws:s3:::${var.backup_bucket}",
          "arn:aws:s3:::${var.receipt_bucket}"
        ]
      },
      {
        Sid    = "S3ReadPublishAndBackup"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:HeadObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.publish_bucket}/${var.publish_prefix}/*",
          "arn:aws:s3:::${var.backup_bucket}/*"
        ]
      },
      {
        Sid      = "S3WriteReceipts"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:aws:s3:::${var.receipt_bucket}/${var.receipt_prefix}/*"
      },
      {
        Sid      = "PublishSNS"
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = var.notification_topic_arn
      },
      {
        Sid      = "CloudWatchMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
      {
        Sid      = "ReadIdentity"
        Effect   = "Allow"
        Action   = ["sts:GetCallerIdentity"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "runner" {
  function_name    = local.lambda_name
  filename         = data.archive_file.runner_zip.output_path
  source_code_hash = data.archive_file.runner_zip.output_base64sha256
  role             = aws_iam_role.lambda.arn
  handler          = "dr_orchestrator.handler"
  runtime          = "python3.12"
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb
  tags             = local.common_tags

  # Lambda reserves AWS_REGION; region is passed via event payload
}

resource "aws_iam_role" "codebuild" {
  name = "${local.name_prefix}-codebuild-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "codebuild.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "codebuild" {
  name = "${local.name_prefix}-codebuild-policy"
  role = aws_iam_role.codebuild.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CodeBuildLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadTerraformBundle"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:HeadObject"
        ]
        Resource = "arn:aws:s3:::${var.receipt_bucket}/${local.tf_bundle_key}"
      },
      {
        Sid      = "WriteReceipts"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:aws:s3:::${var.receipt_bucket}/${var.receipt_prefix}/*"
      },
      {
        Sid    = "RemoteStateBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketVersioning",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::${local.tf_state_bucket_name}",
          "arn:aws:s3:::${local.tf_state_bucket_name}/*"
        ]
      },
      {
        Sid    = "RemoteStateLockTable"
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${local.tf_lock_table_name}"
      },
      {
        Sid    = "TerraformInfraMutations"
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "ec2:RunInstances",
          "ec2:TerminateInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:CreateTags",
          "ec2:DeleteTags",
          "ec2:AssociateIamInstanceProfile",
          "ec2:DisassociateIamInstanceProfile",
          "ec2:ReplaceIamInstanceProfileAssociation",
          "ec2:DescribeIamInstanceProfileAssociations"
        ]
        Resource = "*"
      },
      {
        Sid    = "TerraformIamMutations"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:GetInstanceProfile",
          "iam:PassRole"
        ]
        Resource = "*"
      },
      {
        Sid      = "TerraformIamRoleInlinePolicyRead"
        Effect   = "Allow"
        Action   = ["iam:ListRolePolicies"]
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role"
      },
      {
        Sid      = "TerraformIamRoleAttachedPolicyRead"
        Effect   = "Allow"
        Action   = ["iam:ListAttachedRolePolicies"]
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role"
      },
      {
        Sid      = "ReadIdentity"
        Effect   = "Allow"
        Action   = ["sts:GetCallerIdentity"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_codebuild_project" "dr_infra" {
  name         = "${local.name_prefix}-dr-infra"
  description  = "Controlled Terraform mutation runner for SignalCraft DR"
  service_role = aws_iam_role.codebuild.arn
  tags         = local.common_tags

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = var.codebuild_compute_type
    image                       = var.codebuild_image
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "TF_VERSION"
      value = var.terraform_version
      type  = "PLAINTEXT"
    }
  }

  logs_config {
    cloudwatch_logs {
      group_name = aws_cloudwatch_log_group.codebuild.name
    }
  }

  source {
    type      = "NO_SOURCE"
    buildspec = local.dr_infra_buildspec
  }

  build_timeout          = 30
  queued_timeout         = 60
  concurrent_build_limit = 1
}

resource "aws_iam_role" "sfn" {
  name = "${local.name_prefix}-sfn-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "sfn" {
  name = "${local.name_prefix}-sfn-policy"
  role = aws_iam_role.sfn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeRunnerLambda"
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = [aws_lambda_function.runner.arn, "${aws_lambda_function.runner.arn}:*"]
      },
      {
        Sid      = "RunCodeBuild"
        Effect   = "Allow"
        Action   = ["codebuild:StartBuild", "codebuild:BatchGetBuilds"]
        Resource = aws_codebuild_project.dr_infra.arn
      },
      {
        Sid    = "StepFunctionLogging"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:CreateLogStream",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutLogEvents",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      },
      {
        Sid      = "EventBridgeManagedRule"
        Effect   = "Allow"
        Action   = ["events:PutRule", "events:PutTargets", "events:DescribeRule"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_sfn_state_machine" "dr_orchestrator" {
  name     = local.sfn_name
  role_arn = aws_iam_role.sfn.arn
  definition = jsonencode({
    Comment = "SignalCraft DR orchestrator: auto-detect -> auto-validate -> manual promote"
    StartAt = "SetPhaseCheckHealth"
    States = {
      SetPhaseCheckHealth = {
        Type       = "Pass"
        Result     = { name = "check_health" }
        ResultPath = "$.current_phase"
        Next       = "CheckHealth"
      }
      CheckHealth = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                   = "check_health"
            "execution_id.$"         = "$$.Execution.Name"
            "expected_account_id.$"  = "$.expected_account_id"
            "region.$"               = "$.region"
            "project.$"              = "$.project"
            "publish_bucket.$"       = "$.publish_bucket"
            "publish_prefix.$"       = "$.publish_prefix"
            "provider.$"             = "$.provider"
            "profile.$"              = "$.profile"
            "expected_marker_file.$" = "$.expected_marker_file"
            "max_freshness_hours.$"  = "$.max_freshness_hours"
            "metric_namespace.$"     = "$.metric_namespace"
            "force_run.$"            = "$.force_run"
            "receipt_bucket.$"       = "$.receipt_bucket"
            "receipt_prefix.$"       = "$.receipt_prefix"
          }
        }
        ResultSelector = {
          "phase_name.$"     = "$.Payload.phase_name"
          "phase_inputs.$"   = "$.Payload.phase_inputs"
          "phase_outputs.$"  = "$.Payload.phase_outputs"
          "receipt_uri.$"    = "$.Payload.receipt_uri"
          "failure_reason.$" = "$.Payload.failure_reason"
        }
        ResultPath = "$.phase_results.check_health"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "ShouldRunDR"
      }
      ShouldRunDR = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.force_run"
            BooleanEquals = true
            Next          = "SetPhaseBringup"
          },
          {
            Variable      = "$.phase_results.check_health.phase_outputs.needs_dr"
            BooleanEquals = true
            Next          = "SetPhaseBringup"
          }
        ]
        Default = "HealthyNoop"
      }
      HealthyNoop = {
        Type = "Pass"
        Result = {
          status = "healthy_noop"
        }
        End = true
      }
      SetPhaseBringup = {
        Type       = "Pass"
        Result     = { name = "bringup" }
        ResultPath = "$.current_phase"
        Next       = "BringupInfra"
      }
      BringupInfra = {
        Type     = "Task"
        Resource = "arn:aws:states:::codebuild:startBuild.sync"
        Parameters = {
          ProjectName = aws_codebuild_project.dr_infra.name
          EnvironmentVariablesOverride = [
            { Name = "ACTION", Value = "bringup", Type = "PLAINTEXT" },
            { Name = "EXECUTION_ID", "Value.$" = "$$.Execution.Name", Type = "PLAINTEXT" },
            { Name = "EXPECTED_ACCOUNT_ID", "Value.$" = "$.expected_account_id", Type = "PLAINTEXT" },
            { Name = "AWS_REGION", "Value.$" = "$.region", Type = "PLAINTEXT" },
            { Name = "RECEIPT_BUCKET", "Value.$" = "$.receipt_bucket", Type = "PLAINTEXT" },
            { Name = "RECEIPT_PREFIX", "Value.$" = "$.receipt_prefix", Type = "PLAINTEXT" },
            { Name = "TF_BUNDLE_BUCKET", Value = var.receipt_bucket, Type = "PLAINTEXT" },
            { Name = "TF_BUNDLE_KEY", Value = local.tf_bundle_key, Type = "PLAINTEXT" },
            { Name = "TF_STATE_BUCKET", Value = local.tf_state_bucket_name, Type = "PLAINTEXT" },
            { Name = "TF_STATE_KEY", Value = local.tf_state_key, Type = "PLAINTEXT" },
            { Name = "TF_STATE_DYNAMODB_TABLE", Value = local.tf_lock_table_name, Type = "PLAINTEXT" },
            { Name = "TF_VAR_region", "Value.$" = "$.region", Type = "PLAINTEXT" },
            { Name = "TF_VAR_vpc_id", "Value.$" = "$.dr_vpc_id", Type = "PLAINTEXT" },
            { Name = "TF_VAR_subnet_id", "Value.$" = "$.dr_subnet_id", Type = "PLAINTEXT" },
            { Name = "TF_VAR_allowed_cidr", "Value.$" = "$.dr_allowed_cidr", Type = "PLAINTEXT" },
            { Name = "TF_VAR_key_name", "Value.$" = "$.dr_key_name", Type = "PLAINTEXT" },
            { Name = "TF_VAR_instance_type", "Value.$" = "$.dr_instance_type", Type = "PLAINTEXT" },
            { Name = "TF_VAR_ami_id", "Value.$" = "$.dr_ami_id", Type = "PLAINTEXT" }
          ]
        }
        ResultSelector = {
          phase_name = "bringup"
          phase_inputs = {
            action       = "bringup"
            backend_key  = local.tf_state_key
            backend_lock = local.tf_lock_table_name
          }
          "phase_outputs.$" = "$.Build"
          "receipt_uri.$"   = "States.Format('s3://{}/{}/{}/codebuild-bringup.json', $.receipt_bucket, $.receipt_prefix, $$.Execution.Name)"
          failure_reason    = ""
        }
        ResultPath = "$.phase_results.bringup"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "SetPhaseResolveRunner"
      }
      SetPhaseResolveRunner = {
        Type       = "Pass"
        Result     = { name = "resolve_runner" }
        ResultPath = "$.current_phase"
        Next       = "ResolveRunner"
      }
      ResolveRunner = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                  = "resolve_runner"
            "execution_id.$"        = "$$.Execution.Name"
            "expected_account_id.$" = "$.expected_account_id"
            "region.$"              = "$.region"
            "dr_runner_name.$"      = "$.dr_runner_name"
            "receipt_bucket.$"      = "$.receipt_bucket"
            "receipt_prefix.$"      = "$.receipt_prefix"
          }
        }
        ResultSelector = {
          "phase_name.$"     = "$.Payload.phase_name"
          "phase_inputs.$"   = "$.Payload.phase_inputs"
          "phase_outputs.$"  = "$.Payload.phase_outputs"
          "receipt_uri.$"    = "$.Payload.receipt_uri"
          "failure_reason.$" = "$.Payload.failure_reason"
        }
        ResultPath = "$.phase_results.resolve_runner"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "SetPhaseRestore"
      }
      SetPhaseRestore = {
        Type       = "Pass"
        Result     = { name = "restore" }
        ResultPath = "$.current_phase"
        Next       = "Restore"
      }
      Restore = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                   = "restore"
            "execution_id.$"         = "$$.Execution.Name"
            "expected_account_id.$"  = "$.expected_account_id"
            "region.$"               = "$.region"
            "backup_uri.$"           = "$.backup_uri"
            "backup_required_keys.$" = "$.backup_required_keys"
            "receipt_bucket.$"       = "$.receipt_bucket"
            "receipt_prefix.$"       = "$.receipt_prefix"
          }
        }
        ResultSelector = {
          "phase_name.$"     = "$.Payload.phase_name"
          "phase_inputs.$"   = "$.Payload.phase_inputs"
          "phase_outputs.$"  = "$.Payload.phase_outputs"
          "receipt_uri.$"    = "$.Payload.receipt_uri"
          "failure_reason.$" = "$.Payload.failure_reason"
        }
        ResultPath = "$.phase_results.restore"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "SetPhaseValidate"
      }
      SetPhaseValidate = {
        Type       = "Pass"
        Result     = { name = "validate" }
        ResultPath = "$.current_phase"
        Next       = "Validate"
      }
      Validate = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                       = "validate"
            "execution_id.$"             = "$$.Execution.Name"
            "expected_account_id.$"      = "$.expected_account_id"
            "region.$"                   = "$.region"
            "instance_id.$"              = "$.phase_results.resolve_runner.phase_outputs.instance_id"
            "namespace.$"                = "$.namespace"
            "validate_timeout_seconds.$" = "$.validate_timeout_seconds"
            "receipt_bucket.$"           = "$.receipt_bucket"
            "receipt_prefix.$"           = "$.receipt_prefix"
          }
        }
        ResultSelector = {
          "phase_name.$"     = "$.Payload.phase_name"
          "phase_inputs.$"   = "$.Payload.phase_inputs"
          "phase_outputs.$"  = "$.Payload.phase_outputs"
          "receipt_uri.$"    = "$.Payload.receipt_uri"
          "failure_reason.$" = "$.Payload.failure_reason"
        }
        ResultPath = "$.phase_results.validate"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "SetPhaseNotify"
      }
      SetPhaseNotify = {
        Type       = "Pass"
        Result     = { name = "notify" }
        ResultPath = "$.current_phase"
        Next       = "NotifyValidation"
      }
      NotifyValidation = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                     = "notify"
            "execution_id.$"           = "$$.Execution.Name"
            "expected_account_id.$"    = "$.expected_account_id"
            "region.$"                 = "$.region"
            "notification_topic_arn.$" = "$.notification_topic_arn"
            status                     = "dr_validation_completed"
            summary = {
              "needs_dr.$"    = "$.phase_results.check_health.phase_outputs.needs_dr"
              "reasons.$"     = "$.phase_results.check_health.phase_outputs.reasons"
              "instance_id.$" = "$.phase_results.resolve_runner.phase_outputs.instance_id"
              "public_ip.$"   = "$.phase_results.resolve_runner.phase_outputs.public_ip"
              "backup_uri.$"  = "$.phase_results.restore.phase_outputs.backup_uri"
              "validate.$"    = "$.phase_results.validate.phase_outputs.status"
            }
            "receipt_bucket.$" = "$.receipt_bucket"
            "receipt_prefix.$" = "$.receipt_prefix"
          }
        }
        ResultSelector = {
          "phase_name.$"     = "$.Payload.phase_name"
          "phase_inputs.$"   = "$.Payload.phase_inputs"
          "phase_outputs.$"  = "$.Payload.phase_outputs"
          "receipt_uri.$"    = "$.Payload.receipt_uri"
          "failure_reason.$" = "$.Payload.failure_reason"
        }
        ResultPath = "$.phase_results.notify"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "SetPhaseManualApproval"
      }
      SetPhaseManualApproval = {
        Type       = "Pass"
        Result     = { name = "request_manual_approval" }
        ResultPath = "$.current_phase"
        Next       = "RequestManualApproval"
      }
      RequestManualApproval = {
        Type           = "Task"
        Resource       = "arn:aws:states:::lambda:invoke.waitForTaskToken"
        TimeoutSeconds = var.manual_approval_timeout_seconds
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                     = "request_manual_approval"
            "execution_id.$"           = "$$.Execution.Name"
            "expected_account_id.$"    = "$.expected_account_id"
            "region.$"                 = "$.region"
            "notification_topic_arn.$" = "$.notification_topic_arn"
            "task_token.$"             = "$$.Task.Token"
            summary = {
              "instance_id.$" = "$.phase_results.resolve_runner.phase_outputs.instance_id"
              "public_ip.$"   = "$.phase_results.resolve_runner.phase_outputs.public_ip"
              "backup_uri.$"  = "$.phase_results.restore.phase_outputs.backup_uri"
              "validate.$"    = "$.phase_results.validate.phase_outputs.status"
            }
            "receipt_bucket.$" = "$.receipt_bucket"
            "receipt_prefix.$" = "$.receipt_prefix"
          }
        }
        ResultPath = "$.manual_approval_callback"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "CaptureManualApproval"
      }
      CaptureManualApproval = {
        Type = "Pass"
        Parameters = {
          phase_name = "request_manual_approval"
          phase_inputs = {
            mode = "wait_for_task_token"
          }
          "phase_outputs.$" = "$.manual_approval_callback"
          "receipt_uri.$"   = "States.Format('s3://{}/{}/{}/request_manual_approval.json', $.receipt_bucket, $.receipt_prefix, $$.Execution.Name)"
          failure_reason    = ""
        }
        ResultPath = "$.phase_results.request_manual_approval"
        Next       = "SetPhasePromote"
      }
      SetPhasePromote = {
        Type       = "Pass"
        Result     = { name = "promote" }
        ResultPath = "$.current_phase"
        Next       = "Promote"
      }
      Promote = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                  = "promote"
            "execution_id.$"        = "$$.Execution.Name"
            "expected_account_id.$" = "$.expected_account_id"
            "region.$"              = "$.region"
            "approved.$"            = "$.phase_results.request_manual_approval.phase_outputs.approved"
            "approver.$"            = "$.phase_results.request_manual_approval.phase_outputs.approver"
            "reason.$"              = "$.phase_results.request_manual_approval.phase_outputs.reason"
            "ticket.$"              = "$.phase_results.request_manual_approval.phase_outputs.ticket"
            "receipt_bucket.$"      = "$.receipt_bucket"
            "receipt_prefix.$"      = "$.receipt_prefix"
          }
        }
        ResultSelector = {
          "phase_name.$"     = "$.Payload.phase_name"
          "phase_inputs.$"   = "$.Payload.phase_inputs"
          "phase_outputs.$"  = "$.Payload.phase_outputs"
          "receipt_uri.$"    = "$.Payload.receipt_uri"
          "failure_reason.$" = "$.Payload.failure_reason"
        }
        ResultPath = "$.phase_results.promote"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.failure"
            Next        = "HandlePhaseFailure"
          }
        ]
        Next = "ManualDecision"
      }
      ManualDecision = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.phase_results.promote.phase_outputs.approved"
            BooleanEquals = true
            Next          = "PromoteApproved"
          }
        ]
        Default = "PromotionRejected"
      }
      PromoteApproved = {
        Type = "Pass"
        Result = {
          status = "approved_but_auto_promote_disabled"
        }
        End = true
      }
      PromotionRejected = {
        Type = "Pass"
        Result = {
          status = "manual_promotion_rejected"
        }
        End = true
      }
      HandlePhaseFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.runner.arn
          Payload = {
            action                     = "notify"
            "execution_id.$"           = "$$.Execution.Name"
            "expected_account_id.$"    = "$.expected_account_id"
            "region.$"                 = "$.region"
            "notification_topic_arn.$" = "$.notification_topic_arn"
            status                     = "dr_orchestrator_phase_failed"
            summary = {
              "phase_name.$"     = "$.current_phase.name"
              "failure_reason.$" = "$.failure.Cause"
              "failure_error.$"  = "$.failure.Error"
            }
            "receipt_bucket.$" = "$.receipt_bucket"
            "receipt_prefix.$" = "$.receipt_prefix"
          }
        }
        ResultPath = "$.failure_notification"
        Next       = "FailWorkflow"
      }
      FailWorkflow = {
        Type  = "Fail"
        Error = "DRPhaseFailed"
        Cause = "See phase failure receipt and notification payload"
      }
    }
  })
  type = "STANDARD"
  tags = local.common_tags

  logging_configuration {
    include_execution_data = true
    level                  = "ALL"
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
  }

  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "AWS account mismatch for DR orchestrator apply"
    }
  }
}

resource "aws_iam_role" "events_start_execution" {
  name = "${local.name_prefix}-events-start-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "events_start_execution" {
  name = "${local.name_prefix}-events-start-policy"
  role = aws_iam_role.events_start_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "StartExecution"
        Effect = "Allow"
        Action = ["states:StartExecution"]
        Resource = [
          aws_sfn_state_machine.dr_orchestrator.arn
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${local.name_prefix}-schedule"
  description         = "SignalCraft DR health check and orchestration schedule"
  schedule_expression = var.schedule_expression
  is_enabled          = var.enable_triggers
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_target" "schedule" {
  rule      = aws_cloudwatch_event_rule.schedule.name
  arn       = aws_sfn_state_machine.dr_orchestrator.arn
  role_arn  = aws_iam_role.events_start_execution.arn
  target_id = "dr-orchestrator-sfn"
  input     = jsonencode(local.schedule_input)
}

resource "aws_cloudwatch_metric_alarm" "pipeline_freshness" {
  alarm_name          = "${local.name_prefix}-pipeline-freshness"
  alarm_description   = "No successful publish within freshness threshold"
  namespace           = var.metric_namespace
  metric_name         = "PipelineFreshnessHours"
  statistic           = "Maximum"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = var.max_freshness_hours
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  actions_enabled     = var.enable_triggers
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions = {
    Project  = var.project
    Provider = var.publish_provider
    Profile  = var.profile
  }
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "publish_correctness" {
  alarm_name          = "${local.name_prefix}-publish-correctness"
  alarm_description   = "Publish correctness failed (missing pointer/marker mismatch)"
  namespace           = var.metric_namespace
  metric_name         = "PublishCorrectness"
  statistic           = "Maximum"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = 0.5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  actions_enabled     = var.enable_triggers
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions = {
    Project  = var.project
    Provider = var.publish_provider
    Profile  = var.profile
  }
  tags = local.common_tags
}
