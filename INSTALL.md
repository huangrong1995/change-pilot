# Installation

Change Pilot is a Claude Code / OpenClaw / DeepSeek Harness Skill. Pick the install scope that matches your use case.

## Quick reference

| Harness | Command | Default install path |
|---|---|---|
| Claude Code | `./install.sh --target=claude-code` | `~/.claude/skills/change-pilot/` |
| OpenClaw | `./install.sh --target=openclaw` | `~/.openclaw/skills/change-pilot/` |
| DeepSeek Harness | `./install.sh --target=dsh` | `./.dsh/skills/change-pilot/` |
| All three | `./install.sh --target=all` | (combined) |

## Options

```
--target=claude-code|openclaw|dsh|all   # required
--mode=copy|symlink                      # default: symlink (dev), copy (distribution)
--prefix=<dir>                           # override default target directory
--force                                  # overwrite existing install; backs up to .bak.<ts>
```

`symbolink` mode means source edits propagate to the installed skill immediately — useful for iterating on the skill itself. `copy` mode produces a standalone install that does not depend on the source repo location — useful for distribution.

## Per-harness detail

### Claude Code

The default location Claude Code auto-discovers is `~/.claude/skills/`.

```bash
./install.sh --target=claude-code
```

Verify with: invoke `/change-pilot` in any Claude Code session with a sample R&D change-point. Expected output is a single line in the form `title：description`.

### OpenClaw

OpenClaw auto-discovers skills from enterprise > personal > project layers. The default install path is `~/.openclaw/skills/`. If your OpenClaw setup uses a different personal-skill path, override with `--prefix`.

```bash
./install.sh --target=openclaw
```

Verify with: invoke the skill in OpenClaw with a sample R&D change-point and confirm the single-line customer-facing output.

### DeepSeek Harness (DSH)

DSH picks skills from four paths in priority order. The default install is at `./.dsh/skills/` (project scope, highest priority). For a personal global install, override with `--prefix=$HOME/.dsh/skills/`.

```bash
./install.sh --target=dsh
```

Verify with: list skills via DSH and confirm `change-pilot` appears, then invoke it with a sample R&D change-point.

## Verifying the install

Run the smoke test:

```bash
./tests/install-smoke.sh
```

Expected: eight `PASS:` lines, no `FAIL:`.

In a live harness session, type:

```
/change-pilot 修复扫码过程中图像数据未及时清理的问题，提升扫码稳定性。
```

Expected default output (single line, full-width Chinese colon):

```
扫码功能优化：优化扫码功能，提升扫码稳定性。
```

If you see that line, the skill is wired up correctly. If the harness produces verbose analysis or JSON, the skill is not loaded — re-check the install path.

## Updating

```bash
./install.sh --target=<harness> --force    # re-install with backup of existing
```

`--force` moves the existing install to `<path>.bak.<timestamp>` before installing fresh.

## Uninstall

```bash
rm -rf ~/.claude/skills/change-pilot
rm -rf ~/.openclaw/skills/change-pilot
rm -rf ./.dsh/skills/change-pilot
```

Adjust paths if you used `--prefix` to override.

## Frontmatter

The skill ships with a minimal frontmatter (`name: change-pilot` + `description:`) that all three SKILL.md-format harnesses accept. DSH-specific `whenToUse` and other optional fields are intentionally omitted — the `description` already covers trigger conditions for all targets.
