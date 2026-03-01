# Dashboard Modes

This repo supports two dashboard workflows:

## 1) Minimal Mode (offline sanity only)

Use this mode in CI and in local environments where dashboard extras are not installed.

```bash
make dashboard-sanity
```

What it does:
- Runs deterministic artifact contract sanity checks only.
- Does not start FastAPI/Uvicorn.
- Does not require network installs.

## 2) Full Dashboard Mode (FastAPI + Uvicorn)

Install local extras once:

```bash
pip install -e ".[dashboard]"
```

Then run the dashboard:

```bash
make dashboard
```

If extras are missing, `make dashboard` fails fast with exit code `2` and prints:

```text
Dashboard deps missing (fastapi, uvicorn). Install with: pip install -e '.[dashboard]'
```

This failure is intentional and deterministic.

## CI Policy

- CI fast job runs `make dashboard-sanity` only.
- CI does not install dashboard extras dynamically.

## Authentication

Dashboard authentication is disabled by default (localhost-only access).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_HOST` | `127.0.0.1` | Bind address. Set to `0.0.0.0` for non-local access. |
| `DASHBOARD_PORT` | `8080` | Listen port. |
| `DASHBOARD_AUTH_ENABLED` | `false` | Enable bearer token authentication. |
| `DASHBOARD_AUTH_TOKEN` | (none) | Required when auth is enabled. |

### Production Deployment

When deploying outside localhost, enable authentication:

```bash
DASHBOARD_HOST=0.0.0.0
DASHBOARD_AUTH_ENABLED=true
DASHBOARD_AUTH_TOKEN=<secure-random-token>
```

Health and version endpoints (`/health`, `/healthz`, `/version`, `/v1/version`) are always
accessible without authentication.
