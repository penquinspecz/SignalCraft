# On-Prem Cloudflare Access Receipt Template

Use this template when validating a real deployment. Keep values concrete (hostnames, policy IDs, timestamps).

## Metadata
- Date (UTC):
- Operator:
- Cluster/context:
- Runbook version:

## Exposure Target
- Public hostname (Access-protected):
- Internal origin service:
- Tunnel name/UUID:

## DNS + Tunnel
- DNS record created:
- Tunnel created:
- Tunnel route created:
- Tunnel runtime location (host or k8s):

## Access Policy
- Access app name:
- Include rules (emails/groups):
- Exclude rules:
- MFA enforced:
- Session duration:

## Validation Evidence
- Unauthorized request result (expected deny/challenge):
- Authorized request result (expected dashboard/API access):
- Origin direct-WAN check (expected blocked):
- Artifact endpoint behavior check (expected constrained to indexed artifacts):

## Security Constraints Confirmation
- No in-app auth added:
- No resume/LinkedIn URL ingestion enabled:
- SSRF/egress constraints unchanged:

## Rollback Rehearsal
- Access disable step tested:
- Tunnel route removal tested:
- In-cluster tunnel rollback tested (if applicable):
- Fallback path used (`kubectl port-forward` from trusted host):

## Commands Run
```bash
# Fill with exact commands and outputs used during the rehearsal.
```
