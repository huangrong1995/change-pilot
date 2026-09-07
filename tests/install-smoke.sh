#!/usr/bin/env bash
# tests/install-smoke.sh — smoke test for install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_SH="$REPO_ROOT/install.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

[[ -x "$INSTALL_SH" ]] || fail "install.sh not executable"

HELP=$("$INSTALL_SH" --help)
# Anchor to the target rows in the usage block: two leading spaces + name + space(s)
echo "$HELP" | grep -qE '^  claude-code  ' || fail "help missing claude-code row"
echo "$HELP" | grep -qE '^  openclaw  '    || fail "help missing openclaw row"
echo "$HELP" | grep -qE '^  dsh  '         || fail "help missing dsh row"
echo "$HELP" | grep -qE '^  all  '         || fail "help missing all row"

# Exit-code regression assertions (catch set -e / validation bugs).
# Use --prefix into a temp dir so assertions don't pollute real ~/.claude/ etc.
"$INSTALL_SH" --target=claude-code --prefix="$TMP/cc" --force >/dev/null 2>&1 || fail "valid target=claude-code should exit 0"
"$INSTALL_SH" --target=openclaw    --prefix="$TMP/oc" --mode=copy --force >/dev/null 2>&1 || fail "valid target=openclaw + mode=copy should exit 0"
"$INSTALL_SH" --target=dsh         --prefix="$TMP/dsh" --mode=symlink --force >/dev/null 2>&1 || fail "valid target=dsh + force should exit 0"

# Task 3: claude-code install content assertions
[[ -f "$TMP/cc/SKILL.md" ]]                                || fail "claude-code: SKILL.md missing"
[[ -d "$TMP/cc/prompts" ]]                                 || fail "claude-code: prompts/ missing"
[[ -d "$TMP/cc/rules" ]]                                   || fail "claude-code: rules/ missing"
[[ -d "$TMP/cc/schemas" ]]                                 || fail "claude-code: schemas/ missing"
[[ -d "$TMP/cc/examples" ]]                                || fail "claude-code: examples/ missing"
[[ -d "$TMP/cc/tests" ]]                                   || fail "claude-code: tests/ missing"
grep -q '^name: change-pilot' "$TMP/cc/SKILL.md"           || fail "claude-code: SKILL.md frontmatter name missing"
grep -q '^description:' "$TMP/cc/SKILL.md"                 || fail "claude-code: SKILL.md frontmatter description missing"
pass "claude-code install contents"

# Task 4: openclaw install content assertions
"$INSTALL_SH" --target=openclaw --prefix="$TMP/openclaw" --mode=copy --force >/dev/null
[[ -f "$TMP/openclaw/SKILL.md" ]]                            || fail "openclaw: SKILL.md missing"
[[ -d "$TMP/openclaw/prompts" ]]                             || fail "openclaw: prompts/ missing"
grep -q '^name: change-pilot' "$TMP/openclaw/SKILL.md"      || fail "openclaw: frontmatter name missing"

pass "openclaw install copies SKILL.md and all subdirs"

# Task 5: dsh install content assertions
"$INSTALL_SH" --target=dsh --prefix="$TMP/dsh-content" --mode=copy --force >/dev/null
[[ -f "$TMP/dsh-content/SKILL.md" ]]                            || fail "dsh: SKILL.md missing"
[[ -d "$TMP/dsh-content/rules" ]]                               || fail "dsh: rules/ missing"
grep -q '^name: change-pilot' "$TMP/dsh-content/SKILL.md"      || fail "dsh: frontmatter name missing"

pass "dsh install copies SKILL.md and all subdirs"

if "$INSTALL_SH" --target=bogus --prefix="$TMP/bogus" >/dev/null 2>&1; then
  fail "unknown target should exit non-zero"
fi
if "$INSTALL_SH" --mode=banana --target=claude-code --prefix="$TMP/banana" >/dev/null 2>&1; then
  fail "invalid --mode should exit non-zero"
fi
if "$INSTALL_SH" >/dev/null 2>&1; then
  fail "missing --target should exit non-zero"
fi

pass "exit-code regression assertions"
pass "help covers all targets"
