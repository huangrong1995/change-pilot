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

def build_system_prompt(skill_dir: Path) -> str:
    """Compose trusted instructions passed via Claude's system-prompt option."""
    return (
        "You are the Change Pilot Agent.\n"
        "\n"
        f"Skill location: {skill_dir}\n"
        "Read SKILL.md at that location and follow it exactly. Do not "
        "re-implement or paraphrase the skill rules; the skill is the "
        "single source of truth.\n"
        "\n"
        "Return a single JSON object matching the skill's "
        "schemas/output.schema.json. Do not emit any other text.\n"
    )


def build_user_prompt(raw_text: str, context: dict | None = None) -> str:
    """Compose the untrusted request sent only as the user prompt."""
    ctx_block = json.dumps(context or {}, ensure_ascii=False)
    return (
        "Input raw_text:\n"
        f"{raw_text}\n\n"
        "Input context (disambiguation only — do not invent from):\n"
        f"{ctx_block}\n"
    )

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
    if not isinstance(envelope, dict):
        raise AgentFailed("agent output is not a JSON object")
    inner = envelope.get("result")
    if inner is None:
        # Direct inner skill payload (e.g. {"customer_output": {...}}).
        return envelope
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

DISALLOWED_TOOLS = "Write, Edit, Bash, NotebookEdit, MultiEdit, WebFetch, WebSearch, GitCommit, GitPush"

class ClaudeRunner:
    def __init__(self, skill_dir: Path, timeout_seconds: int = 180, command_override=None):
        self.skill_dir = skill_dir
        self.timeout_seconds = timeout_seconds
        self._command_override = command_override
        self._claude_bin = shutil.which("claude")

    def _build_args(self, prompt: str) -> list[str]:
        """Build the ``claude -p`` invocation.

        Trusted instructions go via ``--system-prompt``; the untrusted
        request is the user prompt only (``-p``). The read-only restriction
        is enforced with ``--allowedTools Read`` plus an explicit
        ``--disallowedTools`` deny-list. ``--no-color`` is intentionally
        omitted — the installed CLI rejects it.
        """
        if not self._claude_bin and not self._command_override:
            raise AgentStartFailed("claude CLI not found on PATH")
        binary = self._claude_bin or "claude"
        return [
            binary,
            "-p",
            prompt,
            "--system-prompt",
            build_system_prompt(self.skill_dir),
            "--allowedTools",
            "Read",
            "--disallowedTools",
            DISALLOWED_TOOLS,
            "--output-format",
            "json",
        ]

    def run(self, raw_text: str, context: dict | None, mode: str) -> ClaudeRunResult:
        """Synchronous entrypoint — used by tests + Phase 1–4 worker."""
        prompt = build_user_prompt(raw_text, context)
        args = self._build_args(prompt)
        runner = self._command_override or _default_subprocess_run
        exit_code, stdout, stderr = runner(args, prompt)
        if exit_code != 0:
            raise AgentFailed(f"claude exited {exit_code}: {stderr.strip()[:500]}")
        parsed = _parse_claude_result(stdout)
        title, description, analysis, validation = _extract_skill_output(parsed)
        return ClaudeRunResult(title=title, description=description, analysis=analysis, validation=validation, raw_stdout=stdout, exit_code=exit_code)

    async def run_async(self, raw_text: str, context: dict | None, mode: str) -> ClaudeRunResult:
        prompt = build_user_prompt(raw_text, context)
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