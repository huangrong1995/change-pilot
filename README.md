# Change Pilot

> Convert R&D technical change-point descriptions into customer-facing release notes.

A Claude Code Skill that turns raw engineering change logs into clean, customer-readable change descriptions. Strips implementation detail, hides internal IDs and version numbers, and abstracts technical mechanisms into product capabilities — without fabricating benefits the source does not support.

## The problem

R&D writes change points like this:

> commit 8f3a21c，修复 scan_service.cpp 中的图像缓存问题。
> 基于 NDK_V4.1.44T18 修改，需同步更新 master (3.5.02.29)。
> 优化读取 adb 值的代码。

Customers need to read this:

> 扫码功能优化：优化扫码功能，提升扫码稳定性。
> 安全模块版本更新：升级内部基础组件版本。
> 开发工具优化：优化内部开发调试功能。

Change Pilot does that conversion automatically, following a strict set of rules so the output never invents benefits, never leaks internal IDs, and never exaggerates.

## Quick start

### 1. Install

See [INSTALL.md](./INSTALL.md) for user-level, project-level, and submodule setups.

```bash
# user-level (Linux/macOS)
git clone https://github.com/<your-org>/change-pilot.git
mkdir -p ~/.claude/skills
cp -r change-pilot ~/.claude/skills/change-pilot
```

### 2. Try it

In any Claude Code session:

```
/change-pilot 修复扫码过程中图像数据未及时清理的问题，提升扫码稳定性。
```

Output:

```
扫码功能优化：优化扫码功能，提升扫码稳定性。
```

For multiple changes in one entry:

```
/change-pilot 1. 修复扫码稳定性问题；2. 修复默认数据卡切换问题；3. 增加系统日志广播功能。
```

Output (one line per change, in source order):

```
扫码功能优化：优化扫码功能，提升扫码稳定性。
移动网络功能优化：优化移动网络切换功能，解决特定场景下数据卡切换异常的问题。
系统日志功能扩展：新增系统日志广播功能。
```

To see the structured analysis (change types, hidden terms, abstractions, validation flags), append `--debug` or say "用 debug 模式".

## How it works

Every input flows through a 5-stage pipeline:

```
Raw R&D change point
       │
       ▼
┌──────────────────┐
│ 1. Understand    │  Identify the product capability, problem, customer value
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. Classify      │  Split into business facts / technical details / internal info
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. Abstract      │  Promote tech to product capability (L1 → L2 → L3)
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. Express       │  Compose customer-facing title + description
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 5. Validate      │  10-point audit (no leakage, no fabrication, no exaggeration)
└────────┬─────────┘
         ▼
   customer_output
```

### The 10 core rules

1. **Retain business facts** — keep purpose, functional change, problem, customer value.
2. **Hide internal details** — file names, code paths, IDs, `.so`/`.jar`, commits, branches, internal IDs, internal config, testers, test environments.
3. **Abstract technical info** — never expose L1 implementation; default to L3 product capability. Never invent L4 benefits.
4. **Recognize change type** — `new_feature` / `optimization` / `bug_fix` / `compatibility` / `security_compliance` / `version_component`. Weave into narrative, don't label explicitly.
5. **Detail by complexity** — simple: 1 sentence. Normal: title + 1 sentence. Complex: title + 1–2 sentences. Length follows comprehension, not source length.
6. **Technical terms** — see `rules/terminology.yaml` for retain / abstract / hide lists.
7. **No exaggeration** — every claim traces to source. Forbidden without source support: 显著 / 大幅 / 极大 / 全面 / 彻底 / 完全 / 明显; "性能提升"; "稳定性提升"; "用户体验提升"; "速度提升".
8. **Multiple changes** — merge if same business purpose / capability / scenario; split if distinct business purposes.
9. **IDs and versions** — hide BUG / 需求 / 0A / Jira / Commit / Git / Patch / Branch IDs; hide internal component versions (`NDK_V*`, `kernel_*`); product-facing versions may stay if customers need them.
10. **Output format** — default `{title}：{description}` as a single line. Simple change: 1 sentence only.

Full rules with examples: [`rules/core-rules.md`](./rules/core-rules.md).

## Project structure

```
change-pilot/
├── SKILL.md                  # Skill entry — Claude reads this when the skill triggers
├── INSTALL.md                # Install instructions (user / project / submodule)
├── LICENSE                   # MIT
├── README.md                 # This file
│
├── schemas/
│   ├── input.schema.json     # raw_text + optional context + mode
│   └── output.schema.json    # customer_output + analysis + validation
│
├── rules/
│   ├── core-rules.md         # 10 core rules with examples
│   ├── terminology.yaml      # retain / abstract / hide per term
│   └── sensitive-patterns.yaml  # regex patterns for internal-info detection
│
├── prompts/
│   ├── analyze.md            # Stage 1: structured analysis
│   ├── transform.md          # Stage 2: customer-language rewrite
│   └── validate.md           # Stage 3: 10-check audit
│
├── examples/                 # Worked YAML examples by category
│   ├── basic.yaml
│   ├── security.yaml
│   ├── system.yaml
│   ├── network.yaml
│   ├── application.yaml
│   └── multiple-changes.yaml
│
└── tests/
    └── cases.yaml            # Regression cases (positive + negative + boundary)
```

## Default vs debug output

| Mode       | Output                                                  |
|------------|---------------------------------------------------------|
| `default`  | Single line: `{title}：{description}`                   |
| `debug`    | Above + `analysis` block + `validation` flags           |

Default mode never emits JSON, analysis tables, stage labels, or commentary — the customer-facing line is the entire response. Debug mode is for harness / test use only; never for end customers.

## Extending the skill

- **New term to handle?** Edit `rules/terminology.yaml` (retain / abstract / hide). Don't hardcode it in prompts.
- **New sensitive pattern?** Edit `rules/sensitive-patterns.yaml`.
- **New test case?** Append to `tests/cases.yaml` with `name`, `input`, and `expected` (or `forbidden` for negative checks, `expected_count` for multi-change, `expect_error` for boundary cases).
- **Tweak a rule?** Edit `rules/core-rules.md` and propagate to `SKILL.md` if the rule summary in the skill entry needs to stay in sync.

## V1 scope

**In scope**: single-point transformation, multi-change identification, technical abstraction, internal-info hiding, customer language expression, fact validation.

**Out of scope** (intentional): Git analysis, code review, risk analysis, RAG, automated Excel editing, Jenkins integration, automatic code analysis, test plan generation.

## License

[MIT](./LICENSE)
