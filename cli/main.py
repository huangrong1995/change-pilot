"""CLI entry point backed by the same runtime as FastAPI."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from runtime.compatible_client import CompatibleClient
from runtime.models import ChangePilotRuntimeError
from runtime.prompt_builder import PromptBuilder
from runtime.runtime import ChangePilotRuntime
from runtime.skill_loader import load_skill
from runtime.validator import OutputValidator
from server.app.config import load_settings


def build_runtime(settings) -> ChangePilotRuntime:
    bundle = load_skill(settings.skill_dir)
    client = CompatibleClient(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model,
        max_tokens=settings.max_tokens,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.retry_count,
    )
    return ChangePilotRuntime(
        bundle, PromptBuilder(), client,
        OutputValidator(bundle.output_schema, bundle.sensitive_patterns),
        max_concurrency=settings.max_concurrency,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="change-pilot")
    parser.add_argument("--text", help="raw change description; otherwise read stdin")
    parser.add_argument("--context", help="context JSON object")
    parser.add_argument("--mode", choices=("default", "debug"), default="default")
    parser.add_argument("--skill-dir", help="override the configured skill directory")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        if args.skill_dir:
            settings = replace(settings, skill_dir=Path(args.skill_dir).resolve())
        context = None
        if args.context:
            context = json.loads(args.context)
            if not isinstance(context, dict):
                raise ValueError("--context must be a JSON object")
        raw_text = args.text if args.text is not None else sys.stdin.read()
        if not raw_text.strip():
            raise ValueError("input text must not be empty")
        result = build_runtime(settings).transform(raw_text, context, args.mode)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ChangePilotRuntimeError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    if args.mode == "debug":
        print(json.dumps({
            "success": True,
            "customer_output": result.customer_line,
            "analysis": result.analysis,
            "validation": result.validation,
        }, ensure_ascii=False))
    else:
        print(result.customer_line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
