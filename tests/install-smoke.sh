#!/usr/bin/env bash
# tests/install-smoke.sh — smoke test for install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_SH="$REPO_ROOT/install.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

[[ -x "$INSTALL_SH" ]] || fail "install.sh not executable"

HELP=$("$INSTALL_SH" --help)
# Anchor to the target rows in the usage block: two leading spaces + name + space(s)
echo "$HELP" | grep -qE '^  claude-code  ' || fail "help missing claude-code row"
echo "$HELP" | grep -qE '^  openclaw  '    || fail "help missing openclaw row"
echo "$HELP" | grep -qE '^  dsh  '         || fail "help missing dsh row"
echo "$HELP" | grep -qE '^  all  '         || fail "help missing all row"

# Exit-code regression assertions (catch set -e / validation bugs)
"$INSTALL_SH" --target=claude-code >/dev/null 2>&1 || fail "valid target=claude-code should exit 0"
"$INSTALL_SH" --target=openclaw --mode=copy >/dev/null 2>&1 || fail "valid target=openclaw + mode=copy should exit 0"
"$INSTALL_SH" --target=dsh --mode=symlink --force >/dev/null 2>&1 || fail "valid target=dsh + force should exit 0"

if "$INSTALL_SH" --target=bogus >/dev/null 2>&1; then
  fail "unknown target should exit non-zero"
fi
if "$INSTALL_SH" --mode=banana --target=claude-code >/dev/null 2>&1; then
  fail "invalid --mode should exit non-zero"
fi
if "$INSTALL_SH" >/dev/null 2>&1; then
  fail "missing --target should exit non-zero"
fi

pass "exit-code regression assertions"
pass "help covers all targets"
