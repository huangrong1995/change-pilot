# Installation

Change Pilot is a Claude Code Skill. Pick the install scope that matches your use case.

## Option A — User-level install (recommended for personal use)

The skill becomes available across every Claude Code project on this machine.

```bash
# Clone (or download) the repo
git clone https://github.com/<your-org>/change-pilot.git

# Copy into the Claude Code user skills directory
mkdir -p ~/.claude/skills
cp -r change-pilot ~/.claude/skills/change-pilot

# Verify
ls ~/.claude/skills/change-pilot
# Should list: SKILL.md  schemas/  rules/  prompts/  examples/  tests/
```

After this, every Claude Code session on this machine will trigger Change Pilot when you ask for R&D → customer rewrite.

## Option B — Project-level install (recommended for team / CI use)

The skill is scoped to a single project. Use this when a specific team owns the skill and wants it version-controlled with their codebase.

```bash
# From your project root
mkdir -p .claude/skills
cp -r /path/to/change-pilot .claude/skills/change-pilot

# Or, if you want the project to pin a specific version, add as a submodule:
git submodule add https://github.com/<your-org>/change-pilot.git .claude/skills/change-pilot
git submodule update --init --recursive
```

Commit `.gitmodules` and the submodule pointer. Team members run `git submodule update --init` after cloning.

## Option C — Direct invocation in a session

If you don't want to install system-wide, paste the contents of `SKILL.md` into a Claude Code session and ask Claude to follow its instructions for the current task. The skill is self-contained — no scripts, no dependencies.

## Verifying the install

In any Claude Code session, type:

```
/change-pilot 修复扫码过程中图像数据未及时清理的问题，提升扫码稳定性。
```

The expected default output is a single line:

```
扫码功能优化：优化扫码功能，提升扫码稳定性。
```

If you see that line, the skill is wired up correctly. If Claude produces verbose analysis or JSON, the skill is not loaded — re-check the path above.

## Uninstall

User-level: `rm -rf ~/.claude/skills/change-pilot`

Project-level: remove the `.claude/skills/change-pilot/` directory from the project.

Submodule: `git submodule deinit -f .claude/skills/change-pilot && git rm -f .claude/skills/change-pilot && rm -rf .git/modules/.claude/skills/change-pilot`

## Updating

```bash
cd ~/.claude/skills/change-pilot   # or wherever you cloned it
git pull
```

For project-level submodules: `git submodule update --remote .claude/skills/change-pilot` from the project root.
