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
