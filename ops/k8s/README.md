# Kubernetes Manifests

SignalCraft has two Kustomize-based manifest stacks:

## `ops/k8s/` (Base Stack — Development/Offline)

- Mode: `CAREERS_MODE=SNAPSHOT` (offline, no live scraping)
- Image: `ghcr.io/yourorg/jobintel:sha-REPLACE_WITH_COMMIT_SHA`
- Flags: `--profiles cs --us_only --no_post --snapshot-only --offline`
- Use case: Local development, CI, offline testing

## `ops/k8s/jobintel/` (Production Stack — Live)

- Mode: `CAREERS_MODE=AUTO` (attempts live, falls back to snapshot)
- Image: ECR-pinned (`048622080012.dkr.ecr.us-east-1.amazonaws.com/jobintel`)
- Flags: `--profiles cs --us_only --no_post`
- Includes: S3 publish requirement, dashboard deployment
- Use case: Production AWS EKS deployment

## Overlays

Both stacks have environment-specific overlays:

- `overlays/aws-eks/` — AWS EKS with IAM service account
- `overlays/eks/` — Generic EKS
- `overlays/live/` — Live mode patches (enables live scraping)
- `overlays/onprem/` — On-premises k3s with local PVCs
- `overlays/onprem-pi/` — Pi cluster with Traefik ingress

## Canonical Source of Truth

For production deployments, use `ops/k8s/jobintel/` as the canonical base.
The root `ops/k8s/` stack is for development and CI only.

Environment configuration should be managed via ConfigMap (`jobintel-config`)
and Secrets (`jobintel-secrets`), not hardcoded in manifests.
