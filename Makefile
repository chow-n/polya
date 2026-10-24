PY := backend/.venv/bin/python
UV := $(shell command -v uv 2>/dev/null)

.PHONY: install backend-deps frontend-deps test build seed reset start cli-status

install: backend-deps frontend-deps

backend-deps:
	@test -x $(PY) || ( [ -n "$(UV)" ] && uv venv backend/.venv --python 3.12 -q || python3 -m venv backend/.venv )
	@if [ -n "$(UV)" ]; then uv pip install -q --python $(PY) -r backend/requirements.txt; else $(PY) -m pip install -q -r backend/requirements.txt; fi

frontend-deps:
	cd frontend && npm install --no-audit --no-fund

test: backend-deps
	LEARNHARNESS_LLM=deterministic LEARNHARNESS_OFFLINE=1 $(PY) -m pytest backend/tests -q

build: frontend-deps
	cd frontend && npm run build

seed: backend-deps
	$(PY) -m backend.seed

reset:
	rm -f harness.db harness.db-wal harness.db-shm

start:
	./start.sh

cli-status:
	./harness-cli status
