PY := backend/.venv/bin/python
UV := $(shell command -v uv 2>/dev/null)

.PHONY: install backend-deps frontend-deps test build seed reset start cli-status app bundle icon

install: backend-deps frontend-deps

backend-deps:
	@test -x $(PY) || ( [ -n "$(UV)" ] && uv venv backend/.venv --python 3.12 -q || python3 -m venv backend/.venv )
	@if [ -n "$(UV)" ]; then uv pip install -q --python $(PY) -r backend/requirements.txt; else $(PY) -m pip install -q -r backend/requirements.txt; fi

frontend-deps:
	cd frontend && npm install --no-audit --no-fund

test: backend-deps
	POLYA_LLM=deterministic POLYA_OFFLINE=1 $(PY) -m pytest backend/tests -q

build: frontend-deps
	cd frontend && npm run build

seed: backend-deps
	$(PY) -m backend.seed

reset:
	rm -f harness.db harness.db-wal harness.db-shm

start:
	./start.sh

cli-status:
	./polya status

# ---- Mac app (docs/specs/mac-app/SPEC.md, renamed per docs/specs/ui-simplify/SPEC.md) ----
APP_DIR := $(HOME)/Applications
APP_NAME := Pólya.app

icon: backend-deps
	$(PY) macos/make_icon.py

# Stage A: repo-backed Pólya.app (py2app alias mode) installed to ~/Applications
app: backend-deps build
	@test -f macos/Polya.icns || $(PY) macos/make_icon.py
	rm -rf build/app build/py2app
	$(PY) macos/setup_app.py py2app -A --dist-dir build/app --bdist-base build/py2app > build-app.log 2>&1 || (tail -30 build-app.log; exit 1)
	codesign --force --deep -s - "build/app/$(APP_NAME)"
	mkdir -p "$(APP_DIR)" && rm -rf "$(APP_DIR)/$(APP_NAME)" "$(APP_DIR)/LearnHarness.app" && cp -R "build/app/$(APP_NAME)" "$(APP_DIR)/"
	@rm -f build-app.log
	@echo "Installed $(APP_DIR)/$(APP_NAME) — open it from Spotlight or: open -a Pólya"

# Stage B: self-contained Pólya.app (PyInstaller, embedded Python) installed to /Applications.
# Replaces the stage A copy in ~/Applications so only one app owns the bundle id (rebuild it with `make app`),
# and removes the pre-rename LearnHarness.app.
bundle: backend-deps build
	@test -f macos/Polya.icns || $(PY) macos/make_icon.py
	rm -rf build/bundle build/pyinstaller
	$(PY) -m PyInstaller macos/Polya.spec --noconfirm --distpath build/bundle --workpath build/pyinstaller > build-bundle.log 2>&1 || (tail -40 build-bundle.log; exit 1)
	codesign --force --deep -s - "build/bundle/$(APP_NAME)"
	rm -rf "/Applications/$(APP_NAME)" /Applications/LearnHarness.app && cp -R "build/bundle/$(APP_NAME)" /Applications/
	@for old in "$(APP_DIR)/$(APP_NAME)" "$(APP_DIR)/LearnHarness.app"; do if [ -d "$$old" ]; then rm -rf "$$old"; echo "Removed $$old"; fi; done
	@rm -f build-bundle.log
	@du -sh "/Applications/$(APP_NAME)"
	@echo "Installed /Applications/$(APP_NAME) (self-contained) — open -a Pólya"
