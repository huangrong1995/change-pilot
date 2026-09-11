import json
from pathlib import Path

from runtime.models import ModelReply

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    configured = True

    def __init__(self, **kwargs):
        pass

    def complete(self, messages):
        return ModelReply('{"customer_output": {"title": "扫码", "description": "提升稳定性"}}')


def run_main(monkeypatch, capsys, *args):
    import cli.main as m
    monkeypatch.setattr("cli.main.CompatibleClient", FakeClient)
    code = m.main(["--text", "x", "--skill-dir", str(ROOT), *args])
    return code, capsys.readouterr()


def test_cli_default_prints_only_customer_line(monkeypatch, capsys):
    code, out = run_main(monkeypatch, capsys)
    assert code == 0
    assert out.out.strip() == "扫码：提升稳定性"
    assert "analysis" not in out.out


def test_cli_debug_prints_structured_json(monkeypatch, capsys):
    code, out = run_main(monkeypatch, capsys, "--mode", "debug")
    assert code == 0
    payload = json.loads(out.out)
    assert payload["success"] is True
    assert payload["customer_output"] == "扫码：提升稳定性"
