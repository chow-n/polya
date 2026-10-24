#!/usr/bin/env bash
# LearnHarness one-command launcher: FastAPI on :8000, Vite on :5173, health-checked.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="$ROOT/backend/.venv/bin/python"
LOGS="$ROOT/.logs"; mkdir -p "$LOGS"
API_PORT="${LEARNHARNESS_API_PORT:-8000}"; WEB_PORT="${LEARNHARNESS_WEB_PORT:-5173}"

c_ok=$'\033[32m'; c_dim=$'\033[2m'; c_b=$'\033[1m'; c_cy=$'\033[36m'; c_r=$'\033[0m'

if [ ! -x "$PY" ]; then
  echo "• creating backend/.venv"
  if command -v uv >/dev/null; then uv venv backend/.venv --python 3.12 -q; else python3 -m venv backend/.venv; fi
fi
if ! "$PY" -c "import fastapi, sympy, watchdog, pypdf" 2>/dev/null; then
  echo "• installing backend dependencies"
  if command -v uv >/dev/null; then uv pip install -q --python "$PY" -r backend/requirements.txt; else "$PY" -m pip install -q -r backend/requirements.txt; fi
fi
if [ ! -d frontend/node_modules ]; then
  echo "• installing frontend dependencies"; (cd frontend && npm install --no-audit --no-fund >"$LOGS/npm-install.log" 2>&1)
fi

for port in "$API_PORT" "$WEB_PORT"; do
  if lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✗ port $port is already in use (pid $(lsof -iTCP:"$port" -sTCP:LISTEN -t | head -1)). Stop it, or set LEARNHARNESS_API_PORT / LEARNHARNESS_WEB_PORT." >&2; exit 1
  fi
done

PIDS=()
cleanup() { echo; echo "• stopping LearnHarness"; for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM

"$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port "$API_PORT" >"$LOGS/backend.log" 2>&1 & PIDS+=($!)
(cd frontend && npx vite --port "$WEB_PORT" --strictPort --host 127.0.0.1 >"$LOGS/frontend.log" 2>&1) & PIDS+=($!)

wait_for() { # url name
  for _ in $(seq 1 120); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$1" || true)
    [ "$code" = "200" ] && { echo "${c_ok}✓${c_r} $2 ${c_dim}($1 → 200 OK)${c_r}"; return 0; }
    sleep 0.5
  done
  echo "✗ $2 did not become healthy; see $LOGS" >&2; tail -n 30 "$LOGS/backend.log" "$LOGS/frontend.log" >&2; exit 1
}
wait_for "http://127.0.0.1:$API_PORT/api/health" "backend  (FastAPI)"
wait_for "http://127.0.0.1:$WEB_PORT/" "frontend (Vite)"
ENGINE=$(curl -s "http://127.0.0.1:$API_PORT/api/health" | "$PY" -c "import sys,json;print(json.load(sys.stdin)['llm_engine'])")

cat <<DASH

${c_b}╭──────────────────────────────────────────────────────────────╮
│  LearnHarness · POMDP cognitive learning harness             │
╰──────────────────────────────────────────────────────────────╯${c_r}
  ${c_cy}UI${c_r}          http://localhost:$WEB_PORT
  ${c_cy}API${c_r}         http://localhost:$API_PORT/docs
  ${c_cy}LLM engine${c_r}  $ENGINE
  ${c_cy}Data home${c_r}   ${LEARNHARNESS_HOME:-$HOME/LearnHarness}  ${c_dim}(harness.db + workspace/)${c_r}
  ${c_cy}Scratchpad${c_r}  ${LEARNHARNESS_HOME:-$HOME/LearnHarness}/workspace/scratch.tex   ${c_dim}(./harness-cli scratch edit — saves stream live)${c_r}
  ${c_cy}Logs${c_r}        $LOGS/{backend,frontend}.log

  ${c_b}./harness-cli${c_r} status   ${c_dim}mastery, Bjork window, calibration${c_r}
  ${c_b}./harness-cli${c_r} due      ${c_dim}FSRS due list (desired retention 0.90)${c_r}
  ${c_b}./harness-cli${c_r} graph    ${c_dim}hypergraph by logical depth${c_r}
  ${c_b}./harness-cli${c_r} scratch  ${c_dim}print / open / watch scratch.tex${c_r}

  Ctrl+C to stop.
DASH
wait
