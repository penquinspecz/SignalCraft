# M23 Entropy Reduction PR5: remove provably-unused direct dependencies (2026-02-19)

## Scope
Remove only direct runtime dependencies that are provably unused by repository imports.

Removed:
- `pandas`
- `python-dotenv`

Files changed:
- `pyproject.toml`
- `requirements.txt`

## Direct Dependency Before/After

Before (`pyproject.toml` direct `project.dependencies`):
- beautifulsoup4
- boto3>=1.34,<2
- faiss-cpu
- openai
- pandas
- python-dotenv
- pydantic
- requests

After (`pyproject.toml` direct `project.dependencies`):
- beautifulsoup4
- boto3>=1.34,<2
- faiss-cpu
- openai
- pydantic
- requests

## Dead-Usage Evidence (import scans)

Command:
```bash
rg -n --glob '*.py' "(^\\s*import\\s+pandas\\b)|(^\\s*from\\s+pandas\\b)|\\bpd\\." src scripts tests
```
Output:
```text
NO_MATCH:pandas
```

Command:
```bash
rg -n --glob '*.py' "(^\\s*import\\s+dotenv\\b)|(^\\s*from\\s+dotenv\\b)|python-dotenv" src scripts tests
```
Output:
```text
NO_MATCH:python-dotenv
```

Command:
```bash
rg -n "pandas|python-dotenv" pyproject.toml requirements.txt requirements-dev.txt
```
Output:
```text
NO_MATCH:dep-names-in-dependency-files
```

## Validation

Commands:
```bash
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make lint
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make ci-fast
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make gate
```

Results:
- `make lint`: pass (`ruff check`, all checks passed)
- `make ci-fast`: pass (`693 passed, 16 skipped`)
- `make gate`: pass (`693 passed, 16 skipped` + snapshot immutability pass + replay smoke pass)
