terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  log_group_name = "/ecs/${var.project}"
  task_family    = "${var.project}-daily"
}

resource "aws_cloudwatch_log_group" "jobintel" {
  name              = local.log_group_name
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "task_role" {
  name = "${var.project}-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "task_policy" {
  name = "${var.project}-task-policy"
  role = aws_iam_role.task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Publish"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket}",
          "arn:aws:s3:::${var.s3_bucket}/${var.s3_prefix}/*"
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.jobintel.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role" "execution_role" {
  name = "${var.project}-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "execution_role" {
  role       = aws_iam_role.execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_task_definition" "jobintel" {
  family                   = local.task_family
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name      = "jobintel"
      image     = var.container_image
      essential = true
      command   = ["python", "scripts/run_daily.py", "--profiles", "cs", "--providers", "openai", "--no_post"]
      secrets   = var.container_secrets
      environment = [
        { name = "JOBINTEL_S3_BUCKET", value = var.s3_bucket },
        { name = "JOBINTEL_S3_PREFIX", value = var.s3_prefix },
        { name = "S3_PUBLISH_ENABLED", value = "1" },
        { name = "DISCORD_WEBHOOK_URL", value = var.discord_webhook_url },
        { name = "JOBINTEL_DASHBOARD_URL", value = var.jobintel_dashboard_url }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.jobintel.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = var.project
        }
      }
    }
  ])
}

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.project}-daily"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "ecs" {
  rule      = aws_cloudwatch_event_rule.schedule.name
  target_id = "ecs-task"
  arn       = var.ecs_cluster_arn
  role_arn  = aws_iam_role.task_role.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.jobintel.arn
    task_count          = 1
    launch_type         = "FARGATE"
    network_configuration {
      subnets         = var.subnet_ids
      security_groups = var.security_group_ids
      assign_public_ip = true
    }
  }
}
