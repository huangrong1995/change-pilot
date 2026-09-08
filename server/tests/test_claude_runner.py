import json
from pathlib import Path

import pytest

from server.app.agent.runner import (
    ClaudeRunner,
    _async_subprocess_run,
    _parse_claude_result,
    build_system_prompt,
)
from server.app.errors import AgentFailed, AgentStartFailed, AgentTimeout


def test_prompt_includes_skill_dir_disallowed_tools_and_raw_text(tmp_path: Path):
    raw_text = "Please summarize this customer request."
    prompt = build_system_prompt(tmp_path, raw_text)

    assert str(tmp_path) in prompt
    assert "Write, Edit, Bash" in prompt
    assert "NotebookEdit" in prompt
    assert "MultiEdit" in prompt
    assert "WebFetch" in prompt
    assert "WebSearch" in prompt
    assert "git commit" in prompt
    assert "git push" in prompt
    assert raw_text in prompt


def test_prompt_excludes_business_rules(tmp_path: Path):
    prompt = build_system_prompt(tmp_path, "raw input")

    assert "保留业务事实" not in prompt
    assert "core rules" not in prompt


def test_parse_accepts_direct_inner_skill_dict():
    payload = {"customer_output": {"title": "direct", "description": "direct-description"}}
    assert _parse_claude_result(json.dumps(payload)) == payload


def test_command_override_parses_claude_result(tmp_path: Path):
    inner = {"customer_output": {"title": "t", "description": "d"}}
    stdout = json.dumps({"type": "result", "result": json.dumps(inner)})

    def fake_command(_args, _stdin):
        return 0, stdout, ""

    result = ClaudeRunner(tmp_path, command_override=fake_command).run(
        "raw text", None, "default"
    )

    assert result.title == "t"
    assert result.description == "d"
    assert result.analysis is None
    assert result.validation is None
    assert result.raw_stdout == stdout
    assert result.exit_code == 0


def test_nonzero_exit_raises_agent_failed_with_agent_message(tmp_path: Path):
    def failing_command(_args, _stdin):
        return 1, "", "agent subprocess failed"

    with pytest.raises(AgentFailed, match="agent"):
        ClaudeRunner(tmp_path, command_override=failing_command).run(
            "raw text", None, "default"
        )




async def test_run_async_honors_command_override(tmp_path: Path):
    inner = {"customer_output": {"title": "async-t", "description": "async-d"}}
    stdout = json.dumps({"type": "result", "result": json.dumps(inner)})

    def fake_command(_args, _stdin):
        return 0, stdout, ""

    result = await ClaudeRunner(tmp_path, command_override=fake_command).run_async(
        "raw text", None, "default"
    )

    assert result.title == "async-t"
    assert result.description == "async-d"
    assert result.raw_stdout == stdout
    assert result.exit_code == 0


async def test_async_subprocess_timeout_raises_agent_timeout():
    with pytest.raises(AgentTimeout):
        await _async_subprocess_run(["/bin/sleep", "5"], "", timeout_seconds=0.1)


def test_missing_claude_binary_raises_agent_start_failed(tmp_path: Path):
    runner = ClaudeRunner(tmp_path)
    runner._claude_bin = None
    runner._command_override = None

    with pytest.raises(AgentStartFailed):
        runner._build_args("prompt")
