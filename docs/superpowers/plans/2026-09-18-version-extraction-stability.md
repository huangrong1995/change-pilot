# Version Extraction Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make module/component version changes consistently appear in the REST API's `customer_output` (and therefore the XLSX module column) by adding a deterministic runtime extractor that appends a `版本变更：` block when the model omits it.

**Architecture:** Add a pure-function module `runtime/version_extractor.py` with `extract_version_changes(raw_text)` and `build_version_block(lines)`. Integrate it in `runtime/runtime.py` after model validation: both `transform` and `transform_async` pass the original `raw_text` into `_finish`, which appends a deterministic version block to `description` if one is not already present, then rebuilds `customer_line`. The model stays the author of the customer-facing prose; the extractor is the fallback for the version block.

**Tech Stack:** Python 3.10, `re` (stdlib), `openpyxl` (unchanged, downstream script untouched), `pytest` + `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-09-18-version-extraction-stability-design.md`

**Deviation from spec (intentional):** The spec names the test file `server/tests/test_version_extractor.py`, but the runtime module (`runtime/version_extractor.py`) and its integration live in `runtime/runtime.py`, whose tests follow the established convention under `tests_runtime/` (see `tests_runtime/test_runtime.py`). This plan places the new tests in `tests_runtime/test_version_extractor.py` to match the surrounding runtime tests. All test commands run from the repo root as `.venv/bin/python -m pytest` — the `-m` form puts the repo root on `sys.path`, which is what makes the `runtime.*` and `server.app.*` imports resolve.

---

### Task 1: `extract_version_changes` pure function + unit tests

**Files:**
- Test: `tests_runtime/test_version_extractor.py`
- Create: `runtime/version_extractor.py`

- [ ] **Step 1: Write the failing unit tests**

Create `tests_runtime/test_version_extractor.py`:

```python
"""Deterministic version-change extraction (runtime fallback for the model)."""
from runtime.version_extractor import extract_version_changes


def test_old_and_new_version_yield_upgrade_line():
    raw = "基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13。"
    assert extract_version_changes(raw) == ["NDK_V4.1.12 升级至 NDK_V4.1.13"]


def test_component_subject_with_connector():
    assert extract_version_changes("MDB芯片升级至V1.1.21") == ["MDB芯片升级至 V1.1.21"]


def test_config_file_version_update():
    assert extract_version_changes("配置文件版本号更新至020.057") == ["配置文件版本号更新至 020.057"]


def test_touchscreen_driver_version_change():
    assert extract_version_changes("触屏驱动版本变更为2.0.46") == ["触屏驱动版本变更为 2.0.46"]


def test_bare_version_change_without_subject_is_skipped():
    # No old version and no component subject directly before the connector →
    # ambiguous, intentionally skipped rather than inventing a subject.
    assert extract_version_changes("版本变更为2.0.47") == []


def test_compatibility_note_is_not_an_upgrade():
    # "及以上版本使用" is a compatibility dependency, not an upgrade; there is
    # no explicit version-change connector, so it must never yield a line.
    assert extract_version_changes("配置了PaymentServer_V1.0.71T及以上版本使用") == []


def test_no_version_change_returns_empty():
    assert extract_version_changes("优化扫码功能，提升扫码稳定性。") == []


def test_duplicates_removed_order_preserved():
    raw = ("NDK_V4.1.12 升级至 NDK_V4.1.13，"
           "同时NDK_V4.1.12 升级至 NDK_V4.1.13，"
           "MDB芯片升级至 V1.1.21")
    assert extract_version_changes(raw) == [
        "NDK_V4.1.12 升级至 NDK_V4.1.13",
        "MDB芯片升级至 V1.1.21",
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests_runtime/test_version_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'runtime.version_extractor'`

- [ ] **Step 3: Implement `extract_version_changes`**

Create `runtime/version_extractor.py`:

```python
"""Deterministic version-change extraction from raw R&D change-point text.

The model may omit the ``版本变更：`` block even when the source upgrades a
module/component version. This module is the pure-function fallback: it
recognizes explicit version-change connectors and emits stable lines, so the
API response carries the version block regardless of model nondeterminism.
"""
from __future__ import annotations

import re

# A version token: an optional word prefix (component name or ``V``/``NDK_V``)
# followed by a dotted numeric version, plus an optional trailing suffix letter
# (e.g. ``NDK_V4.1.13``, ``V1.1.21``, ``020.057``, ``PaymentServer_V1.0.71T``).
# Requires at least one dot so plain ticket numbers / dates never match. The
# lookbehind excludes ASCII alnum / underscore / dot but NOT CJK, so ``至``
# before ``NDK_V...`` does not block the match.
_VERSION_TOKEN = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_]*\d+(?:\.\d+)+[A-Za-z0-9]*)")

# Explicit version-change connectors, longest-first so a longer phrase wins at
# a shared position (e.g. ``版本升级至`` beats ``升级至``).
_CONNECTORS = re.compile(
    r"更新版本号至|版本号更新至|版本升级至|版本变更为|版本号变更为|升级至|升级到|更新至|变更为"
)

# A contiguous component subject directly abutting the connector, e.g. the
# ``MDB芯片`` in ``MDB芯片升级至V1.1.21`` or ``触屏驱动`` in ``触屏驱动版本变更为2.0.46``.
# CJK punctuation (，。) is not in the class, so a cross-clause subject like
# ``功耗，版本升级至`` yields no subject and is safely skipped.
_SUBJECT_BEFORE = re.compile(r"([一-鿿A-Za-z0-9_]+)\s*$")

_OLD_WINDOW = 40  # chars to scan back for the previous version / subject
_NEW_WINDOW = 20  # chars to scan forward for the new version


def extract_version_changes(raw_text: str) -> list[str]:
    """Return one formatted ``版本变更`` line per recognized upgrade, in source
    order, de-duplicated. Empty when the source states no explicit upgrade."""
    lines: list[str] = []
    seen: set[str] = set()
    for m in _CONNECTORS.finditer(raw_text):
        connector = m.group(0)
        new = _new_version(raw_text, m.end())
        if new is None:
            continue  # e.g. ``更新至最新`` — no version, ambiguous, skip
        old = _old_version(raw_text, m.start())
        if old is not None:
            if old == new:
                continue  # same-version no-op; never invent an upgrade
            line = f"{old} 升级至 {new}"
        else:
            subject = _subject_before(raw_text, m.start())
            if not subject:
                continue  # no old version and no component subject → skip
            line = f"{subject}{connector} {new}"
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return lines


def _new_version(text: str, start: int) -> str | None:
    m = _VERSION_TOKEN.search(text[start:start + _NEW_WINDOW])
    return m.group(1) if m else None


def _old_version(text: str, end: int) -> str | None:
    matches = list(_VERSION_TOKEN.finditer(text[max(0, end - _OLD_WINDOW):end]))
    if not matches:
        return None
    return matches[-1].group(1)


def _subject_before(text: str, end: int) -> str | None:
    m = _SUBJECT_BEFORE.search(text[max(0, end - _OLD_WINDOW):end])
    return m.group(1) if m else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests_runtime/test_version_extractor.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add runtime/version_extractor.py tests_runtime/test_version_extractor.py
git commit -m "feat(runtime): deterministic version-change extraction

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: `build_version_block` + unit tests

**Files:**
- Modify: `tests_runtime/test_version_extractor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests_runtime/test_version_extractor.py`:

```python
from runtime.version_extractor import build_version_block


def test_build_version_block_none_for_empty():
    assert build_version_block([]) is None


def test_build_version_block_formats_lines():
    block = build_version_block(["NDK_V4.1.12 升级至 NDK_V4.1.13"])
    assert block == "版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests_runtime/test_version_extractor.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_version_block'`

- [ ] **Step 3: Implement `build_version_block`**

Add to `runtime/version_extractor.py` (before the `_new_version` helper):

```python
def build_version_block(lines: list[str]) -> str | None:
    """Return the ``版本变更：`` block text, or ``None`` when there is nothing."""
    if not lines:
        return None
    return "版本变更：\n" + "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests_runtime/test_version_extractor.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add runtime/version_extractor.py tests_runtime/test_version_extractor.py
git commit -m "feat(runtime): build 版本变更 block from extracted lines

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: Integrate into `runtime/runtime.py` (sync + async) + integration tests

**Files:**
- Modify: `runtime/runtime.py:37-68` (`transform_async`, `transform`, `_finish`)
- Modify: `tests_runtime/test_version_extractor.py` (append integration tests)

- [ ] **Step 1: Write the failing integration tests**

Append to `tests_runtime/test_version_extractor.py`:

```python
import json
from pathlib import Path

import pytest

from runtime.models import ModelReply, ModelUsage
from runtime.prompt_builder import PromptBuilder
from runtime.runtime import ChangePilotRuntime
from runtime.skill_loader import load_skill
from runtime.validator import OutputValidator

ROOT = Path(__file__).resolve().parents[1]

RAW_WITH_VERSION = "基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13。"


class _FakeClient:
    configured = True
    _model = "test-model"

    def __init__(self, payload):
        self.payload = payload

    def complete(self, messages):
        return ModelReply(self.payload, ModelUsage(total_tokens=4))

    async def acomplete(self, messages):
        return ModelReply(self.payload, ModelUsage(total_tokens=4))


def _make_runtime(payload):
    bundle = load_skill(ROOT)
    return ChangePilotRuntime(
        bundle, PromptBuilder(), _FakeClient(payload),
        OutputValidator(bundle.output_schema, bundle.sensitive_patterns),
    )


def test_sync_appends_version_block_when_model_omits_it():
    payload = json.dumps({"customer_output": {"title": "扫码", "description": "优化NDK相关功能。"}})
    result = _make_runtime(payload).transform(RAW_WITH_VERSION, None, "default")
    expected = "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"
    assert result.description == expected
    assert result.customer_line == "扫码：" + expected


@pytest.mark.asyncio
async def test_async_appends_version_block_when_model_omits_it():
    payload = json.dumps({"customer_output": {"title": "扫码", "description": "优化NDK相关功能。"}})
    result = await _make_runtime(payload).transform_async(RAW_WITH_VERSION, None, "default")
    expected = "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"
    assert result.description == expected
    assert result.customer_line == "扫码：" + expected


def test_model_version_block_is_not_duplicated():
    payload = json.dumps({"customer_output": {
        "title": "扫码",
        "description": "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13",
    }})
    result = _make_runtime(payload).transform(RAW_WITH_VERSION, None, "default")
    assert result.description == "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"


def test_no_version_change_leaves_output_unchanged():
    payload = json.dumps({"customer_output": {"title": "扫码", "description": "优化扫码稳定性。"}})
    result = _make_runtime(payload).transform("修复扫码", None, "default")
    assert result.description == "优化扫码稳定性。"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests_runtime/test_version_extractor.py -v`
Expected: FAIL (the 4 integration tests) — the model output lacks the block and the runtime does not yet append it.

- [ ] **Step 3: Implement the runtime integration**

Modify `runtime/runtime.py`. Change `transform_async` and `transform` to forward `raw_text` into `_finish`, and rewrite `_finish` to append the deterministic block. Add the import at the top of the file (after the existing `from runtime.prompt_builder import PromptBuilder` line):

```python
from runtime.version_extractor import build_version_block, extract_version_changes
```

Replace the two call sites (lines 37-47):

```python
    async def transform_async(self, raw_text, context, mode) -> TransformResult:
        messages = self._messages(raw_text, context, mode)
        async with self._async_semaphore:
            reply = await self._client.acomplete(messages)
        return self._finish(reply, raw_text)

    def transform(self, raw_text, context, mode) -> TransformResult:
        messages = self._messages(raw_text, context, mode)
        with self._sync_semaphore:
            reply = self._client.complete(messages)
        return self._finish(reply, raw_text)
```

Replace `_finish` (lines 55-68):

```python
    def _finish(self, reply: ModelReply, raw_text: str) -> TransformResult:
        try:
            parsed = json.loads(_extract_json(reply.text))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise OutputInvalidError("model output is not valid JSON") from exc
        verified = self._validator.process(parsed)
        description = verified.description
        if "版本变更：" not in description:
            block = build_version_block(extract_version_changes(raw_text))
            if block:
                description = description.rstrip() + "\n" + block
        return TransformResult(
            title=verified.title,
            description=description,
            customer_line=build_customer_output_line(verified.title, description),
            analysis=verified.analysis,
            validation=verified.validation,
            usage=reply.usage,
        )
```

- [ ] **Step 4: Run the full runtime + extractor test files to verify they pass**

Run: `.venv/bin/python -m pytest tests_runtime/test_version_extractor.py tests_runtime/test_runtime.py -v`
Expected: PASS — the 4 new integration tests, the 10 extractor unit tests, and all existing `test_runtime.py` tests (their raw inputs like `"修复扫码"` have no version connector, so their assertions are unchanged).

- [ ] **Step 5: Commit**

```bash
git add runtime/runtime.py tests_runtime/test_version_extractor.py
git commit -m "feat(runtime): append deterministic 版本变更 block when model omits it

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: Full test suite + final commit

**Files:** none new.

- [ ] **Step 1: Run the whole test suite**

Run: `.venv/bin/python -m pytest tests_runtime/ server/tests/ -q`
Expected: PASS. No existing behavior changes: runtime clients whose source text carries no version connector produce identical output to before.

- [ ] **Step 2: (Optional) Live smoke check against the local API**

If the local server is reachable, send one request whose `raw_text` contains a version upgrade and confirm `customer_output` carries the `版本变更：` block even when the model would have dropped it. Example request against `POST http://localhost:18081/v1/change-pilot` with `Authorization: Bearer <token from .env>` and body `{"raw_text": "基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13。", "mode": "default"}`.

- [ ] **Step 3: Commit any remaining changes and confirm the working tree is clean**

```bash
git add -A
git status
```

Expected: clean tree (or only intentional pre-existing uncommitted prompt/SKILL edits, which are out of scope for this plan).
```

## Self-Review

**Spec coverage:**
- `extract_version_changes` / `build_version_block` API → Task 1 & 2. ✓
- Runtime integration in both sync and async paths, rebuild `customer_line`, preserve analysis/validation/usage, skip when `版本变更：` already present → Task 3. ✓
- All 9 concrete test requirements from the spec's Testing section → Tasks 1 & 3 (old→new; subject+connector; 配置文件版本号更新至; 触屏驱动版本变更为; bare `版本变更为2.0.47` skipped as ambiguous per the spec's boundary rule; compatibility note excluded; no-change → empty; de-dup + order; no duplication; sync + async). ✓
- Non-goals honored: no second model call, no XLSX parser, no prompt refactor, no rewriting of a model-provided block. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; every test step shows a full test and its exact command + expected output. ✓

**Type consistency:** `extract_version_changes(raw_text: str) -> list[str]`, `build_version_block(lines: list[str]) -> str | None`, `_finish(reply, raw_text)` — consistent across all three tasks. The `build_version_block` import and the `extract_version_changes` import both come from `runtime.version_extractor`. ✓

**One known boundary (documented, not a gap):** The deterministic subject-only form requires the component subject to directly abut the connector (`MDB芯片升级至V1.1.21`). A cross-clause subject such as `MDB芯片，降低功耗，版本升级至V1.1.21` yields no old version and a non-contiguous subject, so the extractor deliberately skips it — the model remains the fallback for that shape. The spec's headline example renders via the model path, not the deterministic one; this is the intended "deterministic-first, model-assisted" split and avoids inventing a subject.
