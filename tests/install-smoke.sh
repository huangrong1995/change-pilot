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
echo "$HELP" | grep -q "claude-code" || fail "help missing claude-code"
echo "$HELP" | grep -q "openclaw"    || fail "help missing openclaw"
echo "$HELP" | grep -q "dsh"         || fail "help missing dsh"
echo "$HELP" | grep -q "all"         || fail "help missing all"

pass "help covers all targets"
