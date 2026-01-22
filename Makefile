.PHONY: test lint format-check gates docker-build docker-run-local report snapshot snapshot-openai smoke image smoke-fast smoke-ci image-ci

# Prefer repo venv if present; fall back to system python3.
PY ?= .venv/bin/python
ifeq ($(wildcard $(PY)),)
PY = python3
endif

PROFILE ?= cs
LIMIT ?= 15

define check_buildkit
	@if [ "$${DOCKER_BUILDKIT:-1}" = "0" ]; then \
		echo "BuildKit is required (Dockerfile uses RUN --mount=type=cache). Set DOCKER_BUILDKIT=1."; \
		exit 1; \
	fi
endef

define docker_diag
	@echo "Docker context: $$(docker context show 2>/dev/null || echo unknown)"; \
	context="$$(docker context show 2>/dev/null || echo default)"; \
	host="$$(docker context inspect "$$context" --format '{{json .Endpoints.docker.Host}}' 2>/dev/null || echo unknown)"; \
	echo "Docker host: $$host"
endef

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src

format-check:
	$(PY) -m ruff format --check src

gates: format-check lint test

docker-build:
	$(call check_buildkit)
	$(call docker_diag)
	docker build -t jobintel:local --build-arg RUN_TESTS=0 .

image: docker-build

image-ci:
	$(call check_buildkit)
	$(call docker_diag)
	docker build -t jobintel:local --build-arg RUN_TESTS=1 .

docker-run-local:
	docker run --rm \
		-v "$$PWD/data:/app/data" \
		-v "$$PWD/state:/app/state" \
		jobintel:local \
		--profiles cs --us_only --no_post --no_enrich

report:
	docker run --rm \
		-v "$$PWD/state:/app/state" \
		--entrypoint python \
		jobintel:local \
		-m scripts.report_changes --profile $(PROFILE) --limit $(LIMIT)

snapshot-openai:
	$(PY) scripts/update_snapshots.py --provider openai

snapshot:
	@if [ -z "$(provider)" ]; then echo "Usage: make snapshot provider=<name>"; exit 2; fi
	$(PY) scripts/update_snapshots.py --provider $(provider)

smoke:
	$(call check_buildkit)
	$(call docker_diag)
	$(MAKE) image
	SMOKE_SKIP_BUILD=1 ./scripts/smoke_docker.sh --skip-build

smoke-fast:
	$(call check_buildkit)
	$(call docker_diag)
	@docker image inspect jobintel:local >/dev/null 2>&1 || ( \
		echo "jobintel:local image missing; building with make image..."; \
		$(MAKE) image; \
	)
	SMOKE_SKIP_BUILD=1 ./scripts/smoke_docker.sh

smoke-ci:
	$(call check_buildkit)
	$(call docker_diag)
	$(MAKE) image-ci
	SMOKE_SKIP_BUILD=1 ./scripts/smoke_docker.sh --skip-build --providers openai --profiles cs
