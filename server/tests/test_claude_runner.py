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


def test_system_and_user_prompts_are_separate_and_tools_are_disallowed(tmp_path: Path):
    raw_text = "Please summarize this customer request."
    system_prompt = build_system_prompt(tmp_path)
    user_prompt = "Input raw_text:\n" + raw_text

    assert str(tmp_path) in system_prompt
    assert raw_text not in system_prompt
    assert raw_text in user_prompt


def test_command_args_use_separate_system_prompt_and_forbid_tools(tmp_path: Path):
    runner = ClaudeRunner(tmp_path, command_override=lambda *_: (0, "", ""))
    args = runner._build_args("untrusted")

    assert args[args.index("-p") + 1] == "untrusted"
    assert args[args.index("--system-prompt") + 1] == build_system_prompt(tmp_path)
    assert args[args.index("--allowedTools") + 1] == "Read"
    forbidden = args[args.index("--disallowedTools") + 1]
    assert all(tool in forbidden for tool in ("Write", "Edit", "Bash", "WebFetch", "WebSearch"))
    assert "--no-color" not in args
    assert args[args.index("--output-format") + 1] == "json"


def test_prompt_excludes_business_rules(tmp_path: Path):
    prompt = build_system_prompt(tmp_path)

    assert "保留业务事实" not in prompt
    assert "core rules" not in prompt


def test_parse_normalizes_fenced_string_customer_output():
    inner = "```json\n{\"customer_output\": \"扫码功能优化：优化扫码功能，提升扫码稳定性。\", \"validation\": {}}\n```"
    stdout = json.dumps({"type": "result", "result": inner}, ensure_ascii=False)

    parsed = _parse_claude_result(stdout)

    assert parsed["customer_output"] == {
        "title": "扫码功能优化",
        "description": "优化扫码功能，提升扫码稳定性。",
    }


def test_parse_normalizes_string_without_colon_as_description_only():
    stdout = json.dumps({"type": "result", "result": json.dumps({"customer_output": "仅描述，无标题"})})

    parsed = _parse_claude_result(stdout)

    assert parsed["customer_output"] == {"title": None, "description": "仅描述，无标题"}


def test_parse_preserves_object_customer_output():
    inner = {"customer_output": {"title": "t", "description": "d"}, "analysis": {"business_intent": "x"}}
    stdout = json.dumps({"type": "result", "result": json.dumps(inner)})

    parsed = _parse_claude_result(stdout)

    assert parsed == inner


def test_parse_malformed_fenced_result_fails_safely():
    stdout = json.dumps({"type": "result", "result": "```json\n{not json\n```"})

    with pytest.raises(AgentFailed, match="not parseable JSON"):
        _parse_claude_result(stdout)


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
