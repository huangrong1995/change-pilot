# Core Rules

The 10 rules that govern every change-pilot transformation. Read these before processing input.

## Priority Order

When rules conflict, follow this priority:

1. Fact accuracy
2. No internal-info leakage
3. Preserve business change
4. Preserve customer-perceivable value
5. Concise expression
6. Professional, natural language

> Preserve business facts. Drop internal implementation with no customer value.

> AI should say less, not more.

---

## Rule 1 — Retain Business Facts

**Keep**:
- Business purpose
- Functional change
- Problem improvement
- Customer-perceivable value

**Do not keep** internal implementation info that has no customer value.

## Rule 2 — Hide Internal Details

**Default hide**:
- File names (`*.cpp`, `*.java`, `*.so`, `*.jar`, `*.xml`, `*.mk`, `*.bp`, `*.h`, `*.c`)
- Code paths (`vendor/`, `frameworks/`, `packages/`, `system/`, `device/`, `hardware/`)
- Class / function / variable names
- Git commit, branch, patch IDs
- BUG ID, requirement ID, 0A ID, Jira ID
- Internal property names (`set_xxx_property()`, `ro.xxx`)
- Internal config keys
- Testers, test environment, internal problem-localization notes

Internal info is only retained when it is itself part of the product information customers need to understand.

## Rule 3 — Abstract Technical Information

Do not just delete technical info with business meaning — abstract it.

Default transformation ladder:

```
L1 Implementation detail
       ↓
L2 Technical mechanism
       ↓
L3 Product capability        ← default target
       ↓
L4 Customer value            ← only if source supports it
```

Default to L3. **Never invent L4 benefits** to make the description sound better.

Example:

| Source (L1)                  | Customer output (L3)                          |
|------------------------------|------------------------------------------------|
| 增加 P2P/AP/DHCP/IP 配置     | 优化无线扩展坞相关功能，提升设备与无线扩展设备的连接支持能力。 |
| 修改 PackageManager 相关代码 | 优化应用管理功能，支持相关应用的静默卸载。    |

## Rule 4 — Change Type

Recognize the change type:

- `new_feature` — 新增功能
- `optimization` — 功能优化
- `bug_fix` — 问题修复
- `compatibility` — 兼容性调整
- `security_compliance` — 安全/合规变更
- `version_component` — 版本/基础组件变更

Change type guides expression. Unless the user explicitly asks, do not output labels like "变更类型：功能优化" — weave the type into the narrative naturally.

## Rule 5 — Output Detail

| Change complexity | Format                          |
|-------------------|---------------------------------|
| Simple            | 1 sentence                      |
| Normal            | title + 1 sentence              |
| Complex           | title + 1–2 sentences           |

Length follows comprehension, not source length. A long R&D note can yield a 1-sentence customer description.

## Rule 6 — Technical Terms

Three buckets — see `terminology.yaml` for the canonical lists:

- **Retain** (customer already knows them): WiFi, Bluetooth, NFC, PIN, 扫码, 移动网络, 无线扩展坞, 密钥管理, 安全认证, OTA.
- **Abstract** (replace with business language): P2P, AP, DHCP, IP, CCID.
- **Hide** (always remove): `*.cpp`, `*.so`, commit hashes, branch names, patch IDs.

When unsure about a term, look it up — do not guess.

## Rule 7 — No Exaggeration

Every claim in customer output must trace to the source. Forbidden without explicit source support:

- Strength words: 显著, 大幅, 极大, 全面, 彻底, 完全, 明显, 极大改善.
- Benefit claims: "性能提升", "安全性提升", "兼容性提升", "稳定性提升", "用户体验提升", "效率提升", "速度提升".

Allowed:

- "修复 WiFi 连接异常" — source explicitly described the issue.
- "优化 WiFi 连接能力" — reasonable business abstraction of the source.

Forbidden:

- "显著提升 WiFi 连接速度" — source did not mention speed.
- "全面提升系统稳定性" — source only touches 扫码.
- "大幅提升用户体验" — no source support.

## Rule 8 — Multiple Changes

Do not split mechanically by technical edit count. Decide:

- Same business purpose? Same product capability? Same customer scenario? One concept covers them all?
- If yes → merge.
- If distinct business purposes → split.

Examples:

| Source                                                                | Action       |
|-----------------------------------------------------------------------|--------------|
| 修改 P2P / 增加 AP / 增加 DHCP / 调整 IP                              | Merge → 无线扩展坞能力 |
| 优化扫码稳定性 / 修复移动网络异常 / 增加系统日志广播                   | Split into 3 |

## Rule 9 — IDs and Versions

**Always hide**: BUG ID, requirement ID, 0A ID, Jira ID, Commit ID, Git ID, Patch ID, Branch, internal component versions.

**Product versions** depend on customer need:

- `NDK_V4.1.44T18 → NDK_V4.1.44T19` — internal component → hide.
- 产品版本 `V4.1.44T18 → V4.1.44T19` — product-facing → may retain if customers need to identify the product.

Core test: would the customer need this identifier to understand what changed?

## Rule 10 — Output Format

Default format: `title` + `description`. Simple change may be 1 sentence only.

Examples:

```
扫码功能优化
优化扫码功能，提升扫码稳定性。
```

```
安全模块功能优化
优化 PIN 操作及密钥管理等相关功能，提升特定业务场景下的支持能力和兼容性。
```

Do not label the change type explicitly. Do not expose the analysis. Output must read as a finished customer-facing artifact.
