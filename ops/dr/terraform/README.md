# DR Terraform (Cold Standby Runner)

This Terraform module provisions a temporary ARM EC2 instance with k3s for DR drills.

## Required inputs

- `vpc_id`
- `subnet_id`

## Optional inputs

- `region` (default `us-east-1`)
- `instance_type` (default `t4g.small`)
- `ami_id` (if empty, latest Ubuntu 24.04 ARM is selected)
- `key_name`
- `allowed_cidr` (SSH + k3s API access)

## Usage

```bash
cd ops/dr/terraform
terraform init
terraform plan
terraform apply
terraform output
```
