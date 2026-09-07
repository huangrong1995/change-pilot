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
  case "$TARGET" in
    claude-code|openclaw|dsh|all) ;;
    *) usage; die "unknown target: $TARGET (valid: claude-code, openclaw, dsh, all)" ;;
  esac
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

install_skill() {
  local target="$1" mode="$2" target_dir="$3" force="$4"
  if [[ ! -f "$REPO_ROOT/SKILL.md" ]]; then
    die "SKILL.md not found at $REPO_ROOT — run install.sh from the change-pilot repo root"
  fi
  if [[ -e "$target_dir" ]]; then
    if [[ "$force" -ne 1 ]]; then
      die "$target_dir already exists. Re-run with --force to overwrite (will backup to .bak.<ts>)"
    fi
    local ts backup
    ts="$(date +%Y%m%d%H%M%S)"
    backup="${target_dir}.bak.${ts}"
    mv "$target_dir" "$backup"
    echo "backed up existing install to $backup"
  fi
  mkdir -p "$target_dir"
  if [[ "$mode" == "symlink" ]]; then
    for f in "${SKILL_FILES[@]}"; do
      ln -sfn "$REPO_ROOT/$f" "$target_dir/$f"
    done
  else
    for f in "${SKILL_FILES[@]}"; do
      cp -R "$REPO_ROOT/$f" "$target_dir/$f"
    done
  fi
  echo "installed to $target_dir (mode=$mode)"
}

run_target() {
  local target="$1" target_dir
  if [[ -n "$PREFIX" ]]; then
    target_dir="$PREFIX"
  else
    target_dir="$(resolve_default_prefix "$target")"
  fi
  install_skill "$target" "$MODE" "$target_dir" "$FORCE"
}

main() {
  parse_args "$@"
  case "$TARGET" in
    claude-code|openclaw|dsh) run_target "$TARGET" ;;
    all)
      for t in claude-code openclaw dsh; do
        local saved_prefix="$PREFIX"
        PREFIX=""
        run_target "$t"
        PREFIX="$saved_prefix"
      done
      ;;
    *) die "unknown target: $TARGET (valid: claude-code, openclaw, dsh, all)" ;;
  esac
}

main "$@"
