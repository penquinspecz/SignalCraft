# Security Dependency Audit (M22) - 2026-02-17

## Scope
- Runtime dependency set from `requirements.txt`.
- Dev/tooling dependency set from `requirements-dev.txt`.
- CI dependency-audit behavior from `scripts/security_dependency_check.py` and `.github/workflows/ci.yml`.

## Inputs
```text
$ shasum -a 256 requirements.txt requirements-dev.txt
3feeb6ea8a0270c7530bba09ead9b54be259ebcb563f4071e31e3b8d4b3a3fd7  requirements.txt
6761d4c07a5b0f343974f4b52d21539485f2f581eeccbade53e91bc1a890fa99  requirements-dev.txt
```

## Runtime Dependencies (authoritative)
From `requirements.txt`:
- annotated-types==0.7.0
- anyio==4.12.1
- beautifulsoup4==4.14.3
- boto3==1.42.44
- botocore==1.42.44
- certifi==2026.1.4
- charset-normalizer==3.4.4
- distro==1.9.0
- faiss-cpu==1.13.2
- h11==0.16.0
- httpcore==1.0.9
- httpx==0.28.1
- idna==3.11
- jiter==0.13.0
- jmespath==1.1.0
- numpy==2.4.2
- openai==2.17.0
- packaging==26.0
- pandas==3.0.0
- pydantic==2.12.5
- pydantic-core==2.41.5
- python-dateutil==2.9.0.post0
- python-dotenv==1.2.1
- requests==2.32.5
- s3transfer==0.16.0
- six==1.17.0
- sniffio==1.3.1
- soupsieve==2.8.3
- tqdm==4.67.3
- typing-extensions==4.15.0
- typing-inspection==0.4.2
- urllib3==2.6.3

## Commands + Results

### 1) Runtime vulnerability audit (CI-aligned wrapper)
```text
$ .venv/bin/python scripts/security_dependency_check.py --requirements requirements.txt
dependency audit attempt 1/3
WARNING:pip_audit._cli:--no-deps is supported, but users are encouraged to fully hash their pinned dependencies
WARNING:pip_audit._cli:Consider using a tool like `pip-compile`: https://pip-tools.readthedocs.io/en/latest/#using-hashes
No known vulnerabilities found
dependency audit passed
```

### 2) Runtime+dev direct audit (pinned requirement files)
```text
$ .venv/bin/python -m pip_audit --cache-dir .cache/pip-audit --progress-spinner off --no-deps -r requirements.txt -r requirements-dev.txt
WARNING:pip_audit._cli:--no-deps is supported, but users are encouraged to fully hash their pinned dependencies
WARNING:pip_audit._cli:Consider using a tool like `pip-compile`: https://pip-tools.readthedocs.io/en/latest/#using-hashes
No known vulnerabilities found
```

### 3) Toolchain/environment audit (local venv)
```text
$ .venv/bin/python -m pip_audit --cache-dir .cache/pip-audit --progress-spinner off --local
Found 2 known vulnerabilities in 1 package
Name Version ID                  Fix Versions
---- ------- ------------------- ------------
pip  25.0.1  GHSA-4xh5-x5gv-qwph 25.3
pip  25.0.1  GHSA-6vgw-5pg2-w6jp 26.0
```
References:
- [GHSA-4xh5-x5gv-qwph](https://github.com/advisories/GHSA-4xh5-x5gv-qwph)
- [GHSA-6vgw-5pg2-w6jp](https://github.com/advisories/GHSA-6vgw-5pg2-w6jp)

### 4) Outdated package snapshot (local venv)
```text
$ .venv/bin/python -m pip list --outdated --format=json
bandit 1.8.6 -> 1.9.3
boto3 1.42.44 -> 1.42.50
botocore 1.42.44 -> 1.42.50
openai 2.17.0 -> 2.21.0
pip 25.0.1 -> 26.0.1
pip_audit 2.9.0 -> 2.10.0
pip-tools 7.4.1 -> 7.5.3
ruff 0.15.0 -> 0.15.1
```

## Findings
- P0: None.
- P1: No pinned runtime dependency vulnerabilities found on 2026-02-17; separate P1 application-control risk remains for runner redaction default mode.
- P2: `pip==25.0.1` in local/CI toolchain has known advisories (`GHSA-4xh5-x5gv-qwph`, `GHSA-6vgw-5pg2-w6jp`).
  - Impact: build/dependency-management plane, not runtime artifact/replay semantics.
  - Minimal fix path: bump bootstrap pip pin in CI and local setup from `25.0.1` to a fixed release (`>=25.3`), then re-run gate.

## Follow-on Issue Reference

- P1 redaction default-mode hardening: #167  
  https://github.com/penquinspecz/SignalCraft/issues/167

## Determinism Notes
- Added CI dependency audit wrapper is read-only with respect to repository artifacts.
- Wrapper retries transient advisory-service failures and soft-passes only when service availability is the failure mode.
- No runtime pipeline/output schema behavior changes are introduced by this audit artifact.
