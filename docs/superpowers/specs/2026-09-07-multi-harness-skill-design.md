# Multi-Harness Skill Compatibility — Design Spec

**Date:** 2026-09-07
**Status:** Approved (pending user review of this written spec)
**Scope:** Pilot — OpenClaw + DeepSeek Harness. Defer: OpenAI Codex CLI, Hermes Agent.

## Context

Change Pilot is currently distributed as a Claude Code skill — `SKILL.md` with YAML frontmatter plus a `prompts/` `rules/` `schemas/` `examples/` `tests/` tree, installed to `~/.claude/skills/change-pilot/`. The user wants the same skill loadable from other common AI harnesses so that teams using different harnesses can consume the same conversion logic.

Survey of target harnesses (2026-09-07):

| Harness | Format | Install convention |
|---|---|---|
| Claude Code | `SKILL.md` + frontmatter (`name`, `description`) | `~/.claude/skills/<name>/` |
| OpenClaw | `SKILL.md` + frontmatter (`name`, `description`) | auto-discovered, common path `~/.openclaw/skills/<name>/` |
| DeepSeek Harness (DSH) | `SKILL.md` + frontmatter (`name`, `description`, optional `whenToUse`, `provider`, `disable-model-invocation`, `user-invocable`) | `./.dsh/skills/` or `./.agents/skills/` or `~/.dsh/skills/` or `~/.agents/skills/` |
| Hermes Agent | `SKILL.md` + frontmatter (`name`, `description`, optional `metadata.hermes.*`) | managed by `tools/skill_manager_tool.py` |
| OpenAI Codex CLI | `AGENTS.md` (plain markdown, no frontmatter) | repo root, sub-folders, or `~/.codex/` |

**Key finding:** 4 of 5 target harnesses use the same `SKILL.md` + minimal frontmatter format. Only Codex uses `AGENTS.md`. This collapses the architectural problem to "where to install" rather than "how to translate formats".

## Goals

- Pilot install of the existing Change Pilot skill into OpenClaw and DeepSeek Harness with no source changes.
- Keep `SKILL.md` as the single source of truth — no parallel hand-maintained copies.
- Add an `install.sh` orchestrator that handles per-harness install paths and copy/symlink modes.
- Rewrite `INSTALL.md` to be multi-harness sectioned.

## Non-Goals (this pilot)

- Codex CLI support (different format — needs a generator step; defer).
- Hermes Agent support (path conventions not fully verified; defer).
- Harness-specific frontmatter (DSH `whenToUse`, Hermes `metadata.hermes.*`) — these are optional in both; the existing `description` already covers trigger conditions and is accepted by all four `SKILL.md` harnesses.
- Auto-discovery of all installed harnesses on a machine.
- Windows / WSL compatibility beyond what `bash` + standard POSIX tools already provide.

## Architecture

**Approach A — single source + per-harness install script.**

```
change-pilot/                          # repo root, GitHub-tracked
├── SKILL.md                           # single source of truth
├── prompts/  rules/  schemas/  examples/  tests/
├── install.sh                         # NEW — per-harness installer
├── README.md  INSTALL.md  LICENSE
└── docs/
    └── superpowers/specs/             # this file
```

`SKILL.md` and all supporting directories remain unchanged. `install.sh` is the only new code.

### install.sh interface

```bash
./install.sh --target=<harness>          # default mode = symlink
./install.sh --target=<harness> --mode=copy
./install.sh --target=all
./install.sh --target=<harness> --prefix=<dir>   # override default path
./install.sh --force                     # overwrite existing install, backup to .bak.<ts>
```

Valid `--target` values (pilot):
- `claude-code` — installs to `~/.claude/skills/change-pilot/`
- `openclaw` — installs to `~/.openclaw/skills/change-pilot/`
- `dsh` — installs to `./.dsh/skills/change-pilot/` (project scope, highest DSH priority)
- `all` — runs the three above in sequence

Defaults:
- `--mode` defaults to `symlink` (development-friendly; source edits propagate immediately).
- `--mode=copy` for distribution builds where the install must not depend on the source repo location.

Per-harness install function lives inside `install.sh` as `install_<target>()`, dispatched from a `case` on `$TARGET`. Each function:
1. Resolves the target directory (default or `--prefix` override).
2. Creates the directory if missing.
3. Either symlinks `SKILL.md` and each subdirectory, or copies them recursively.
4. Prints the resolved install path and a verify hint (per-harness invocation example).

## Components

**New file:** `install.sh` (POSIX bash, no external deps beyond `ln`/`cp`/`mkdir`/`find`).

**Modified file:** `INSTALL.md` — rewritten with one section per harness, common invocation table at the top, install verification per harness.

**Unchanged:** `SKILL.md`, all of `prompts/`, `rules/`, `schemas/`, `examples/`, `tests/`, `README.md`, `LICENSE`.

## Data Flow

```
User runs ./install.sh --target=openclaw --mode=symlink
        │
        ▼
Parse args (target, mode, prefix, force)
        │
        ▼
Validate source SKILL.md exists at repo root
        │
        ▼
Dispatch to install_openclaw()
        │
        ▼
  Resolve target = ${PREFIX:-$HOME/.openclaw/skills/change-pilot}
  Check existing → if present and ! --force, exit 1
  mkdir -p target
  For each of {SKILL.md, prompts, rules, schemas, examples, tests}:
      symlink or copy into target/
        │
        ▼
Print: "Installed to <path>. Verify with: <harness-specific command>"
exit 0
```

## Error Handling

| Condition | Behavior | Exit code |
|---|---|---|
| Source `SKILL.md` missing (not in repo root) | Error: "请在 change-pilot 仓库根目录运行 install.sh" | 1 |
| Unknown `--target` value | Error: "unknown target '<x>'. valid: claude-code, openclaw, dsh, all" | 1 |
| Target path not writable | Error: "cannot write to <path> — check permissions" | 1 |
| Existing install + no `--force` | Error: "<path> already exists. Re-run with --force to overwrite (will backup to .bak.<ts>)" | 1 |
| Existing install + `--force` | Move existing to `<path>.bak.<timestamp>` before installing | 0 |
| Symlink target source deleted | Symlink broken silently; user can rerun install to fix | n/a |

## Testing

**`tests/install-smoke.sh`** — POSIX bash, exercises the install path against a temp directory:

1. `TMP=$(mktemp -d)`
2. Run `../install.sh --target=_smoke --prefix="$TMP/change-pilot" --mode=copy`. `install.sh` accepts a private `_smoke` target (undocumented in INSTALL.md) that performs the copy/symlink step against an arbitrary `--prefix` directory, skipping the post-install verification hint. Used only by the smoke test.
3. Assert:
   - `$TMP/change-pilot/SKILL.md` exists
   - `SKILL.md` frontmatter contains `name: change-pilot`
   - `SKILL.md` frontmatter `description:` is non-empty
   - Subdirs present: `prompts/`, `rules/`, `schemas/`, `examples/`, `tests/`
   - Each subdir has at least one file (non-empty)
4. `rm -rf "$TMP"`

Add a manual runbook entry in `INSTALL.md` instructing users to execute the smoke test before reporting install issues.

CI integration is deferred — smoke test runs locally for now. GitHub Actions hook can be added later.

## INSTALL.md Rewrite Plan

Restructure into:

```
# Installation

## Quick reference

| Harness | Command | Default install path |
|---|---|---|
| Claude Code | ./install.sh --target=claude-code | ~/.claude/skills/change-pilot/ |
| OpenClaw | ./install.sh --target=openclaw | ~/.openclaw/skills/change-pilot/ |
| DeepSeek Harness | ./install.sh --target=dsh | ./.dsh/skills/change-pilot/ |
| All three | ./install.sh --target=all | (combined) |

## Per-harness detail
### Claude Code
... (current content, condensed)

### OpenClaw
... install path, invocation pattern in OpenClaw, verify command

### DeepSeek Harness
... install path, invocation pattern in DSH, verify command

## Options
--target, --mode, --prefix, --force

## Verification
Per-harness verify snippet (one short example each).

## Uninstall
Per-harness rm paths.

## Updating
./install.sh --force (or git pull in source + reinstall)
```

## Open Items / Future Work

- **Codex CLI support** — needs a generator step that emits `AGENTS.md` from `SKILL.md` body. Add `harnesses/codex/AGENTS.md.tmpl` and a `build_codex()` function. Frontmatter (none in Codex format) gets stripped.
- **Hermes Agent support** — confirm canonical skill directory path with the user once verified, then add `install_hermes()`.
- **DSH `whenToUse` and Hermes `metadata.hermes.*` precision** — only needed if the shared `description` proves insufficient for trigger accuracy in production. Reassess after pilot usage.
- **CI smoke test** — wire `tests/install-smoke.sh` into GitHub Actions once a CI config exists.
- **Auto-discovery of harnesses** — `install.sh --auto` could probe for `.claude/` `.openclaw/` `.dsh/` directories and install to whichever exists. Defer.

## Risks

- **OpenClaw install path is best-effort.** My web search surfaced `~/.openclaw/skills/` as the conventional user-scope path but the official docs emphasize auto-discovery with project/personal/enterprise layers. If users hit a different default, they can use `--prefix` to override. Documented in INSTALL.md.
- **Symlink mode assumes the source repo stays in place.** If the user moves the repo, all symlinked installs break. `--mode=copy` is the safe alternative for distribution. Documented.
- **DSH project-scope default** means `./.dsh/skills/` is the default, which gets committed to the repo if version-controlled. Matches the user's existing pattern of installing Change Pilot into the test project (per memory note `change-pilot-customer-setup`). Acceptable; documented in INSTALL.md.
