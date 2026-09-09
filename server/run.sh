#!/usr/bin/env bash
# Manage the local Change Pilot Agent Server.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${CHANGE_PILOT_VENV_DIR:-$REPO_ROOT/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON="$VENV_DIR/bin/python"
RUN_DIR="${CHANGE_PILOT_RUN_DIR:-$REPO_ROOT/.run}"
PID_FILE="$RUN_DIR/change-pilot.pid"
LOG_FILE="$RUN_DIR/change-pilot.log"
REQUIREMENTS_FILE="$REPO_ROOT/server/requirements.txt"
DEPS_STAMP="$RUN_DIR/.requirements-installed"

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

load_dotenv() {
  local env_file="$REPO_ROOT/.env"
  [[ -f "$env_file" ]] || return 0

  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim "$line")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" == export\ * ]] && line="${line#export }"
    [[ "$line" == *=* ]] || continue

    key="$(trim "${line%%=*}")"
    value="$(trim "${line#*=}")"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue

    # Explicitly exported environment variables have precedence over .env.
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done < "$env_file"
}

configure_environment() {
  load_dotenv

  export CHANGE_PILOT_API_TOKEN="${CHANGE_PILOT_API_TOKEN:-dev-token}"
  if [[ -z "${CHANGE_PILOT_SKILL_DIR:-}" ]]; then
    if [[ -d "$HOME/.claude/skills/change-pilot" ]]; then
      export CHANGE_PILOT_SKILL_DIR="$HOME/.claude/skills/change-pilot"
    else
      export CHANGE_PILOT_SKILL_DIR="$REPO_ROOT/.claude/skills/change-pilot"
    fi
  fi

  CHANGE_PILOT_HOST="${CHANGE_PILOT_HOST:-0.0.0.0}"
  CHANGE_PILOT_PORT="${CHANGE_PILOT_PORT:-8080}"
  export CHANGE_PILOT_HOST CHANGE_PILOT_PORT
}

ensure_dependencies() {
  mkdir -p "$RUN_DIR"
  if [[ ! -x "$PYTHON" ]]; then
    echo "Creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  local install=0
  [[ -f "$DEPS_STAMP" ]] || install=1
  [[ "$REQUIREMENTS_FILE" -nt "$DEPS_STAMP" ]] && install=1
  if ! "$PYTHON" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
    install=1
  fi

  if [[ "$install" -eq 1 ]]; then
    echo "Installing server dependencies"
    "$PYTHON" -m pip install -r "$REQUIREMENTS_FILE"
    touch "$DEPS_STAMP"
  fi
}

read_pid() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(tr -d '[:space:]' < "$PID_FILE")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  printf '%s' "$pid"
}

process_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

clear_stale_pid() {
  local pid
  if pid="$(read_pid)" && ! process_running "$pid"; then
    rm -f "$PID_FILE"
  fi
}

server_command() {
  printf '%s\n' "$PYTHON" -m uvicorn server.app.main:app \
    --host "$CHANGE_PILOT_HOST" --port "$CHANGE_PILOT_PORT"
}

start_server() {
  ensure_dependencies
  clear_stale_pid

  local pid
  if pid="$(read_pid)" && process_running "$pid"; then
    echo "Change Pilot server is already running (pid $pid)"
    return 1
  fi

  mkdir -p "$RUN_DIR"
  nohup "$PYTHON" -m uvicorn server.app.main:app \
    --host "$CHANGE_PILOT_HOST" \
    --port "$CHANGE_PILOT_PORT" \
    >>"$LOG_FILE" 2>&1 &
  pid=$!
  printf '%s\n' "$pid" > "$PID_FILE"

  sleep 1
  if ! process_running "$pid"; then
    rm -f "$PID_FILE"
    echo "Change Pilot server failed to start; see $LOG_FILE" >&2
    return 1
  fi
  echo "Change Pilot server started (pid $pid)"
  echo "Log: $LOG_FILE"
}

stop_server() {
  local pid
  if ! pid="$(read_pid)"; then
    echo "Change Pilot server is not running"
    return 0
  fi
  if ! process_running "$pid"; then
    rm -f "$PID_FILE"
    echo "Removed stale server PID file"
    return 0
  fi

  kill "$pid"
  for _ in {1..30}; do
    process_running "$pid" || break
    sleep 0.2
  done
  if process_running "$pid"; then
    echo "Change Pilot server did not stop (pid $pid)" >&2
    return 1
  fi
  rm -f "$PID_FILE"
  echo "Change Pilot server stopped"
}

status_server() {
  local pid
  if pid="$(read_pid)" && process_running "$pid"; then
    echo "Change Pilot server is running (pid $pid)"
    echo "Log: $LOG_FILE"
    return 0
  fi
  if [[ -f "$PID_FILE" ]]; then
    rm -f "$PID_FILE"
    echo "Change Pilot server is stopped (removed stale PID file)"
  else
    echo "Change Pilot server is stopped"
  fi
  return 1
}

foreground_server() {
  ensure_dependencies
  exec "$PYTHON" -m uvicorn server.app.main:app \
    --host "$CHANGE_PILOT_HOST" \
    --port "$CHANGE_PILOT_PORT"
}

usage() {
  cat <<'EOF'
Usage: ./server/run.sh <command>

Commands:
  start       Start in the background (default)
  stop        Stop the background server
  restart     Restart the background server
  status      Show whether the background server is running
  logs        Follow the server log
  foreground  Run in the current shell for debugging

Configuration:
  Copy .env.example to .env and customize it. Explicitly exported
  environment variables take precedence over .env values.
EOF
}

main() {
  configure_environment
  local command="${1:-start}"
  case "$command" in
    start)      start_server ;;
    stop)       stop_server ;;
    restart)    stop_server; start_server ;;
    status)     status_server ;;
    logs)
      if [[ -f "$LOG_FILE" ]]; then
        tail -f "$LOG_FILE"
      else
        echo "No server log exists yet: $LOG_FILE" >&2
        return 1
      fi
      ;;
    foreground) foreground_server ;;
    -h|--help|help) usage ;;
    *) echo "Unknown command: $command" >&2; usage >&2; return 2 ;;
  esac
}

main "$@"
