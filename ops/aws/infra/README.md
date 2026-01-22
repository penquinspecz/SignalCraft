# Terraform minimal ECS scheduled task

This directory contains minimal Terraform to run `scripts/run_daily.py` on ECS Fargate
and trigger it daily via EventBridge.

Populate `terraform.tfvars` with your values, then:
```bash
terraform init
terraform apply
```
