"""Subprocess wrapper around ``claude -p``.

The runner assembles a system prompt that points Claude at the installed
``change-pilot`` skill directory and forbids write/edit/bash tools. It
captures stdout (``--output-format json``) and parses the structured
result.

For tests, ``command_override`` lets the test inject a fake
(exit_code, stdout, stderr) tuple instead of spawning a real subprocess.
Production code uses ``run_subprocess`` (asyncio) to keep the event
loop unblocked; the test path is fully synchronous.
"""
from __future__ import annotations
import asyncio
import json
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.app.errors import AgentFailed, AgentStartFailed, AgentTimeout

@dataclass
class ClaudeRunResult:
    title: str | None
    description: str
    analysis: dict[str, Any] | None
    validation: dict[str, Any] | None
    raw_stdout: str
    exit_code: int

def build_system_prompt(skill_dir: Path, raw_text: str, context: dict | None = None) -> str:
    """Compose the full prompt sent to ``claude -p``.

    The system prompt tells Claude which skill directory to load and
    forbids destructive tools. The user-message portion is ``raw_text``
    plus optional context (passed verbatim, never invented from).
    """
    disallowed = (
        "Write, Edit, Bash, NotebookEdit, MultiEdit, WebFetch, WebSearch, "
        "git commit, git push"
    )
    ctx = context or {}
    ctx_block = json.dumps(ctx, ensure_ascii=False) if ctx else "{}"
    return (
        "You are the Change Pilot Agent.\n"
        "\n"
        "Skill location: {skill_dir}\n"
        "Read SKILL.md at that location and follow it exactly. Do not "
        "re-implement or paraphrase the skill rules; the skill is the "
        "single source of truth.\n"
        "\n"
        "Tool restrictions: you must NOT use {disallowed}. You may only "
        "Read files inside the skill directory to load rules, prompts, "
        "schemas, and examples.\n"
        "\n"
        "Input raw_text:\n"
        "{raw_text}\n"
        "\n"
        "Input context (disambiguation only — do not invent from):\n"
        "{ctx}\n"
        "\n"
        "Return a single JSON object matching the skill's "
        "schemas/output.schema.json. Do not emit any other text.\n"
    ).format(skill_dir=str(skill_dir), disallowed=disallowed, raw_text=raw_text, ctx=ctx_block)

def _parse_claude_result(stdout: str) -> dict[str, Any]:
    """Parse ``claude --output-format json`` payload.

    The wrapper may emit a top-level envelope with a ``result`` field
    holding a JSON string, or it may emit the inner JSON directly.
    """
    stdout = stdout.strip()
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AgentFailed(f"agent returned non-JSON output: {exc}") from exc
    inner = envelope.get("result")
    if isinstance(inner, str):
        try:
            return json.loads(inner)
        except json.JSONDecodeError as exc:
            raise AgentFailed(f"agent result is not parseable JSON: {exc}") from exc
    if isinstance(inner, dict):
        return inner
    raise AgentFailed("agent output envelope missing 'result' field")

def _extract_skill_output(parsed: dict[str, Any]) -> tuple[str | None, str, dict | None, dict | None]:
    co = parsed.get("customer_output")
    if not isinstance(co, dict):
        raise AgentFailed("agent output missing 'customer_output' object")
    title = co.get("title")
    description = co.get("description")
    if not isinstance(description, str) or not description:
        raise AgentFailed("agent output missing non-empty 'customer_output.description'")
    return title, description, parsed.get("analysis"), parsed.get("validation")

def _default_subprocess_run(args: list[str], stdin: str) -> tuple[int, str, str]:
    """Synchronous subprocess runner. Used by tests + sync entrypoint."""
    import subprocess
    proc = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=None, check=False)
    return proc.returncode, proc.stdout, proc.stderr

async def _async_subprocess_run(
    args: list[str], stdin: str, timeout_seconds: float | None = None
) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(stdin.encode("utf-8")), timeout=timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise AgentTimeout("agent subprocess timed out") from exc
    return proc.returncode or 0, stdout_b.decode("utf-8", errors="replace"), stderr_b.decode("utf-8", errors="replace")

class ClaudeRunner:
    def __init__(self, skill_dir: Path, timeout_seconds: int = 180, command_override=None):
        self.skill_dir = skill_dir
        self.timeout_seconds = timeout_seconds
        self._command_override = command_override
        self._claude_bin = shutil.which("claude")

    def _build_args(self, prompt: str) -> list[str]:
        if not self._claude_bin and not self._command_override:
            raise AgentStartFailed("claude CLI not found on PATH")
        binary = self._claude_bin or "claude"
        return [binary, "-p", prompt, "--output-format", "json", "--no-color"]

    def run(self, raw_text: str, context: dict | None, mode: str) -> ClaudeRunResult:
        """Synchronous entrypoint — used by tests + Phase 1–4 worker."""
        prompt = build_system_prompt(self.skill_dir, raw_text, context)
        args = self._build_args(prompt)
        runner = self._command_override or _default_subprocess_run
        exit_code, stdout, stderr = runner(args, prompt)
        if exit_code != 0:
            raise AgentFailed(f"claude exited {exit_code}: {stderr.strip()[:500]}")
        parsed = _parse_claude_result(stdout)
        title, description, analysis, validation = _extract_skill_output(parsed)
        return ClaudeRunResult(title=title, description=description, analysis=analysis, validation=validation, raw_stdout=stdout, exit_code=exit_code)

    async def run_async(self, raw_text: str, context: dict | None, mode: str) -> ClaudeRunResult:
        prompt = build_system_prompt(self.skill_dir, raw_text, context)
        args = self._build_args(prompt)
        if self._command_override:
            exit_code, stdout, stderr = await asyncio.to_thread(
                self._command_override, args, prompt
            )
        else:
            exit_code, stdout, stderr = await _async_subprocess_run(
                args, prompt, self.timeout_seconds
            )
        if exit_code != 0:
            raise AgentFailed(f"claude exited {exit_code}: {stderr.strip()[:500]}")
        parsed = _parse_claude_result(stdout)
        title, description, analysis, validation = _extract_skill_output(parsed)
        return ClaudeRunResult(title=title, description=description, analysis=analysis, validation=validation, raw_stdout=stdout, exit_code=exit_code)