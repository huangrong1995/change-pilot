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
_SUBJECT_BEFORE = re.compile(r"([一-鿿A-Za-z0-9_.]+)\s*$")

_OLD_WINDOW = 40  # chars to scan back for the previous version / subject
_NEW_GAP = 8  # max chars between the connector and the new version (allows whitespace)


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
        subject = _subject_before(raw_text, m.start())
        if subject and _VERSION_TOKEN.search(subject) is None:
            # A non-version component subject abuts the connector (e.g. ``MDB芯片``)
            # → prefer the subject form over a version from a prior clause.
            line = f"{subject}{connector} {new}"
        else:
            if old is None:
                continue  # no old version and no component subject → skip
            if old == new:
                continue  # same-version no-op; never invent an upgrade
            line = f"{old} 升级至 {new}"
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return lines


def build_version_block(lines: list[str]) -> str | None:
    """Return the ``版本变更：`` block text, or ``None`` when there is nothing."""
    if not lines:
        return None
    return "版本变更：\n" + "\n".join(lines)


def _new_version(text: str, start: int) -> str | None:
    m = _VERSION_TOKEN.search(text, start)
    if m is None or m.start() > start + _NEW_GAP:
        return None
    return m.group(1)


def _old_version(text: str, end: int) -> str | None:
    matches = list(_VERSION_TOKEN.finditer(text[max(0, end - _OLD_WINDOW):end]))
    if not matches:
        return None
    return matches[-1].group(1)


def _subject_before(text: str, end: int) -> str | None:
    m = _SUBJECT_BEFORE.search(text[max(0, end - _OLD_WINDOW):end])
    return m.group(1) if m else None
