# Version Extraction Stability Design

## Status

Approved design; implementation pending.

## Goal

Ensure module/component version changes consistently appear in the REST API's `customer_output` and therefore in the XLSX module column. The model remains responsible for customer-facing descriptions, while deterministic runtime post-processing provides a fallback when the model omits the version block.

## Current Problem

The service performs one model completion for the raw change point. MiniMax-M2.5 sometimes emits the required `版本变更：` block and sometimes drops version information entirely. The XLSX script writes the API response verbatim, so missing blocks are propagated to the workbook. Prompt and schema alignment improved the behavior but did not make it deterministic.

## Chosen Approach

Add a pure-function extractor in `runtime/version_extractor.py` and integrate it in `runtime/runtime.py` after model output validation.

### Extraction API

- `extract_version_changes(raw_text: str) -> list[str]`
  - Detect explicit version-change connectors, including `更新版本号至`, `版本号更新至`, `版本升级至`, `版本变更为`, `版本号变更为`, `升级至`, `升级到`, `更新至`, and `变更为`.
  - Recognize version tokens such as `NDK_V4.1.13`, `V1.1.21`, `2.0.47`, `020.057`, and `PaymentServer_V1.0.71T`.
  - Use a preceding version token when available: `<old> 升级至 <new>`.
  - Otherwise use a nearby component subject: `<component> 升级至 <new>`.
  - Skip ambiguous matches that have neither a usable old version nor a component subject.
  - Preserve source order and remove duplicate lines.

- `build_version_block(lines: list[str]) -> str | None`
  - Return `None` for no lines.
  - Otherwise return `版本变更：` followed by one extracted line per source occurrence.

### Runtime Integration

In both `ChangePilotRuntime.transform` and `transform_async`:

1. Build and validate the model result as today.
2. Extract deterministic version changes from the original `raw_text`.
3. If no deterministic lines are found, return the model result unchanged.
4. If the result description already contains `版本变更：`, preserve it and do not duplicate the block.
5. Otherwise append the deterministic block to `description` with newlines.
6. Rebuild `customer_line` with `build_customer_output_line` and return a new `TransformResult` preserving analysis, validation, and usage fields.

The API will therefore return a stable version block for recognized source patterns. The XLSX script requires no additional version logic because it writes the API's complete `customer_output` unchanged.

## Output Examples

Input:

```text
改进：MDB芯片，降低功耗，版本升级至V1.1.21，适用于U2000产品。
```

Output:

```text
MDB芯片功能优化：优化MDB芯片功耗，适用于U2000产品。
版本变更：
MDB芯片升级至 V1.1.21
```

Input:

```text
基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13。
```

Output fallback block:

```text
版本变更：
NDK_V4.1.12 升级至 NDK_V4.1.13
```

## Boundaries and Error Handling

- Do not scan arbitrary bare numeric strings; require an explicit version-change connector to avoid false positives from dates, ticket numbers, or unrelated component versions.
- Do not invent a version or infer an upgrade when the source does not state one.
- If extraction cannot identify a safe subject or old/new relationship, skip that occurrence rather than emit misleading output.
- If the model already supplied a version block, preserve it as requested by the hybrid strategy. This design does not remove version phrases accidentally left in the model's description; prompt rules continue to discourage that behavior.
- Extraction failures are non-fatal: an empty result leaves the validated model response unchanged.

## Testing

Add `server/tests/test_version_extractor.py` covering:

- `更新版本号至NDK_V4.1.13` with an old `NDK_V4.1.12`.
- `版本升级至V1.1.21` with a component subject.
- `配置文件版本号更新至020.057`.
- `版本变更为2.0.47` and `触屏驱动版本变更为2.0.46`.
- A bare compatibility dependency such as `PaymentServer_V1.0.71T及以上版本使用` is a compatibility note, NOT a version upgrade; it is intentionally excluded from the version block so the extractor never invents an upgrade relationship.
- Text without version changes returns no lines.
- Duplicate occurrences are de-duplicated while source order is retained.
- Existing `版本变更：` output is not duplicated by runtime integration.
- Both synchronous and asynchronous runtime paths return the appended block.

## Files

- Add: `runtime/version_extractor.py`
- Modify: `runtime/runtime.py`
- Add: `server/tests/test_version_extractor.py`
- Add or extend runtime integration tests as needed for sync and async behavior.

## Non-Goals

- No second model request.
- No XLSX-specific version parser.
- No broad refactor of prompt construction.
- No automatic rewriting of a model-generated version block unless it is absent.
