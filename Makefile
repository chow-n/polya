PY := backend/.venv/bin/python
UV := $(shell command -v uv 2>/dev/null)

.PHONY: install backend-deps frontend-deps test build seed reset start cli-status app icon

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

# ---- Mac app (docs/specs/mac-app/SPEC.md) ----
APP_DIR := $(HOME)/Applications

icon: backend-deps
	$(PY) macos/make_icon.py

# Stage A: repo-backed LearnHarness.app (py2app alias mode) installed to ~/Applications
app: backend-deps build
	@test -f macos/LearnHarness.icns || $(PY) macos/make_icon.py
	rm -rf build/app build/py2app
	$(PY) macos/setup_app.py py2app -A --dist-dir build/app --bdist-base build/py2app > build-app.log 2>&1 || (tail -30 build-app.log; exit 1)
	codesign --force --deep -s - build/app/LearnHarness.app
	mkdir -p "$(APP_DIR)" && rm -rf "$(APP_DIR)/LearnHarness.app" && cp -R build/app/LearnHarness.app "$(APP_DIR)/"
	@rm -f build-app.log
	@echo "Installed $(APP_DIR)/LearnHarness.app — open it from Launchpad/Spotlight or: open -a LearnHarness"
