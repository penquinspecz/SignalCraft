provider "aws" {
  region = var.region
}

data "aws_ami" "ubuntu_arm64" {
  count       = var.ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  selected_ami = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu_arm64[0].id
}

data "aws_iam_policy_document" "dr_runner_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dr_runner_ssm" {
  name               = "${var.name_prefix}-runner-ssm-role"
  assume_role_policy = data.aws_iam_policy_document.dr_runner_assume_role.json

  tags = {
    Name      = "${var.name_prefix}-runner-ssm-role"
    ManagedBy = "terraform"
    Purpose   = "jobintel-dr"
  }
}

resource "aws_iam_role_policy_attachment" "dr_runner_ssm_core" {
  role       = aws_iam_role.dr_runner_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "dr_runner" {
  name = "${var.name_prefix}-runner-instance-profile"
  role = aws_iam_role.dr_runner_ssm.name

  tags = {
    Name      = "${var.name_prefix}-runner-instance-profile"
    ManagedBy = "terraform"
    Purpose   = "jobintel-dr"
  }
}

resource "aws_security_group" "dr_runner" {
  name        = "${var.name_prefix}-sg"
  description = "JobIntel DR runner access"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  ingress {
    description = "k3s API"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name      = "${var.name_prefix}-sg"
    ManagedBy = "terraform"
    Purpose   = "jobintel-dr"
  }
}

resource "aws_instance" "dr_runner" {
  ami                         = local.selected_ami
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  iam_instance_profile        = aws_iam_instance_profile.dr_runner.name
  vpc_security_group_ids      = [aws_security_group.dr_runner.id]
  key_name                    = var.key_name != "" ? var.key_name : null
  associate_public_ip_address = true

  user_data = <<-EOT
    #!/usr/bin/env bash
    set -euo pipefail
    apt-get update
    apt-get install -y curl ca-certificates
    curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.31.5+k3s1 sh -
  EOT

  tags = {
    Name      = "${var.name_prefix}-runner"
    ManagedBy = "terraform"
    Purpose   = "jobintel-dr"
  }
}
