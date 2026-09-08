"""Sensitive-pattern re-check for the agent's output.

Loads ``rules/sensitive-patterns.yaml`` from the installed skill and
runs every regex against the agent's ``customer_output.description``.

This is the Server's second line of defense (per spec section 40: "不要
把 Claude 的原始输出直接信任"). It does NOT replace the skill's own
checks — it re-verifies so a hallucinated output that bypassed the
skill still gets caught.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Iterable
import yaml

class SensitiveLeak(Exception):
    """Raised when the output contains a sensitive pattern match."""
    def __init__(self, matches: list[str]):
        super().__init__(sensitive_matches(matches))
        self.matches = matches

def sensitive_matches(matches: Iterable[str]) -> str:
    items = ", ".join(sorted(set(matches)))
    return f"customer_output contains sensitive patterns: {items}"

def load_patterns(yaml_path: Path) -> list[str]:
    """Flatten the YAML's grouped patterns into a single list of regex strings."""
    if not yaml_path.exists():
        return []
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    patterns = data.get("patterns", {})
    flat: list[str] = []
    for _, items in patterns.items():
        if isinstance(items, list):
            flat.extend(p for p in items if isinstance(p, str))
    return flat

def find_sensitive_matches(patterns: Iterable[str], text: str) -> list[str]:
    matches: list[str] = []
    for raw in patterns:
        try:
            regex = re.compile(raw)
        except re.error:
            continue
        for m in regex.finditer(text):
            matches.append(m.group(0))
    return matches

def check_description(text: str, yaml_path: Path) -> None:
    """Raise ``SensitiveLeak`` if ``text`` matches any pattern."""
    patterns = load_patterns(yaml_path)
    matches = find_sensitive_matches(patterns, text)
    if matches:
        raise SensitiveLeak(matches)