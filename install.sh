#!/usr/bin/env bash
# install.sh — install Change Pilot skill into a target AI harness
# Usage: ./install.sh --target=<harness> [options]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="change-pilot"
SKILL_FILES=(SKILL.md prompts rules schemas examples tests)

usage() {
  cat <<'EOF'
Usage: install.sh --target=<harness> [options]

Targets:
  claude-code   Install to ~/.claude/skills/change-pilot/
  openclaw      Install to ~/.openclaw/skills/change-pilot/
  dsh           Install to ./.dsh/skills/change-pilot/
  all           Install to all three above

Options:
  --mode=copy|symlink   Install mode (default: symlink)
  --prefix=<dir>        Override default target directory
  --force               Overwrite existing install (backup to .bak.<ts>)
  -h, --help            Show this help
EOF
}

die() { echo "error: $*" >&2; exit 1; }

parse_args() {
  TARGET=""
  MODE="symlink"
  PREFIX=""
  FORCE=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --target=*) TARGET="${1#*=}" ;;
      --mode=*)   MODE="${1#*=}" ;;
      --prefix=*) PREFIX="${1#*=}" ;;
      --force)    FORCE=1 ;;
      -h|--help)  usage; exit 0 ;;
      *) usage; die "unknown argument: $1" ;;
    esac
    shift
  done
  [[ -n "$TARGET" ]] || { usage; die "--target is required"; }
  [[ "$MODE" == "copy" || "$MODE" == "symlink" ]] || die "--mode must be copy or symlink"
}

resolve_default_prefix() {
  case "$1" in
    claude-code) echo "$HOME/.claude/skills/$SKILL_NAME" ;;
    openclaw)    echo "$HOME/.openclaw/skills/$SKILL_NAME" ;;
    dsh)         echo "./.dsh/skills/$SKILL_NAME" ;;
    *) die "unknown target: $1" ;;
  esac
}

main() {
  parse_args "$@"
  local target_dir
  if [[ -n "$PREFIX" ]]; then
    target_dir="$PREFIX"
  else
    target_dir="$(resolve_default_prefix "$TARGET")"
  fi
  echo "would install target=$TARGET mode=$MODE dir=$target_dir force=$FORCE"
}

main "$@"
