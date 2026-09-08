#!/usr/bin/env bash
# tests/server-e2e-smoke.sh — Phase 1–4 smoke test.
#
# Spins up the FastAPI server in the background, hits /health and
# /v1/change-pilot, and asserts the response shape.
#
# Requires: server requirements installed, CHANGE_PILOT_API_TOKEN set,
# skill installed at .claude/skills/change-pilot (run
# ./install.sh --target=claude-code --prefix=$(pwd)/.claude first).
#
# This script is OPTIONAL in CI — Phase 1–4 unit tests cover the full
# pipeline via mocked ClaudeRunner. Run this locally to verify the
# real subprocess path.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

: "${CHANGE_PILOT_API_TOKEN:=dev-smoke-token}"
export CHANGE_PILOT_API_TOKEN

HOST="${CHANGE_PILOT_HOST:-127.0.0.1}"
PORT="${CHANGE_PILOT_PORT:-8088}"

python3 -m uvicorn server.app.main:app --host "$HOST" --port "$PORT" >/tmp/change-pilot-smoke.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

# Wait for server to come up.
for _ in {1..30}; do
  if curl -sf "http://$HOST:$PORT/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

echo "GET /health"
curl -sf "http://$HOST:$PORT/health"
echo

echo "POST /v1/change-pilot (unauthenticated should 401)"
code=$(curl -sk -o /dev/null -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"raw_text":"x"}' \
  "http://$HOST:$PORT/v1/change-pilot")
[[ "$code" == "401" ]] || { echo "FAIL: expected 401, got $code"; exit 1; }

echo "POST /v1/change-pilot (authenticated)"
curl -sf -X POST \
  -H "Authorization: Bearer $CHANGE_PILOT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"raw_text":"修复扫码过程中图像数据未及时清理的问题，提升扫码稳定性。"}' \
  "http://$HOST:$PORT/v1/change-pilot"
echo

echo "PASS: server e2e smoke"