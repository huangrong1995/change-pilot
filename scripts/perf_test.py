#!/usr/bin/env python3
"""Measure Change Pilot runtime latency without logging input or provider payloads.

Mock mode is the default and is safe for local/CI smoke checks. Live mode is
explicitly opt-in with ``--live`` and uses the configured OpenAI-compatible
provider environment variables.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.compatible_client import CompatibleClient
from runtime.models import ModelReply, ModelUsage
from runtime.prompt_builder import PromptBuilder
from runtime.runtime import ChangePilotRuntime
from runtime.skill_loader import load_skill
from runtime.validator import OutputValidator
from server.app.config import load_settings


class MockClient:
    configured = True
    _model = "mock"

    def complete(self, messages):
        return ModelReply(
            json.dumps({"customer_output": {"title": "功能优化", "description": "优化相关功能。"}}, ensure_ascii=False),
            ModelUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )


def build_runtime(live: bool) -> ChangePilotRuntime:
    settings = load_settings()
    bundle = load_skill(settings.skill_dir)
    if live:
        client = CompatibleClient(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            max_tokens=settings.max_tokens,
            timeout_seconds=settings.provider_timeout_seconds,
            max_retries=settings.retry_count,
        )
    else:
        client = MockClient()
    return ChangePilotRuntime(
        bundle,
        PromptBuilder(),
        client,
        OutputValidator(bundle.output_schema, bundle.sensitive_patterns),
        max_concurrency=settings.max_concurrency,
    )


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--live", action="store_true", help="use the configured provider; never enabled by default")
    parser.add_argument("--skill-dir", type=Path)
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    if args.skill_dir:
        import os
        os.environ["CHANGE_PILOT_SKILL_DIR"] = str(args.skill_dir.resolve())

    runtime = build_runtime(args.live)
    durations = []
    total_tokens = 0
    for _ in range(args.iterations):
        started = time.perf_counter()
        result = runtime.transform("优化扫码功能", None, "default")
        durations.append(time.perf_counter() - started)
        total_tokens += result.usage.total_tokens

    elapsed = sum(durations)
    report = {
        "mode": "live" if args.live else "mock",
        "iterations": args.iterations,
        "p50_ms": round(percentile(durations, 0.50) * 1000, 3),
        "p95_ms": round(percentile(durations, 0.95) * 1000, 3),
        "throughput_per_second": round(args.iterations / elapsed, 3) if elapsed else 0.0,
        "total_tokens": total_tokens,
        "model": runtime.model,
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
