#!/usr/bin/env python3
"""Measure live Change Pilot HTTP latency and concurrent throughput.

The script reads ``CHANGE_PILOT_API_TOKEN`` from the local ``.env`` file
without printing it, then runs fixed concurrency scenarios against the local
service. It reports only aggregate timing, success, and sanitized error data.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:18081/v1/change-pilot"
PAYLOAD = json.dumps(
    {"raw_text": "优化扫码功能稳定性", "mode": "default"},
    ensure_ascii=False,
).encode()


def load_token() -> str:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text().splitlines():
        if line.startswith("CHANGE_PILOT_API_TOKEN="):
            return line.split("=", 1)[1].strip()
    return ""


TOKEN = load_token()


def one_call(_: int) -> tuple[float | None, bool, int | None, str | None]:
    request = urllib.request.Request(
        BASE_URL,
        data=PAYLOAD,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode()
        duration_ms = (time.perf_counter() - started) * 1000
        success = response.status == 200 and '"success":true' in body
        try:
            processing_time_ms = json.loads(body).get("processing_time_ms")
        except (TypeError, ValueError):
            processing_time_ms = None
        return duration_ms, success, processing_time_ms, None
    except Exception as exc:  # noqa: BLE001 - report only a sanitized class/message
        return None, False, None, f"{exc.__class__.__name__}: {exc}"


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 1)


def run_scenario(concurrency: int, total: int) -> dict:
    latencies: list[float] = []
    processing_times: list[float] = []
    errors: list[str] = []
    successes = 0
    started = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        for duration, success, processing_time, error in executor.map(
            one_call, range(total)
        ):
            if duration is not None:
                latencies.append(duration)
            if processing_time is not None:
                processing_times.append(processing_time)
            if success:
                successes += 1
            elif error:
                errors.append(error)

    wall_seconds = time.perf_counter() - started
    return {
        "concurrency": concurrency,
        "total": total,
        "success": successes,
        "failed": total - successes,
        "error_samples": errors[:3],
        "client_latency_p50_ms": percentile(latencies, 0.50),
        "client_latency_p95_ms": percentile(latencies, 0.95),
        "client_latency_p99_ms": percentile(latencies, 0.99),
        "server_proc_p50_ms": percentile(processing_times, 0.50),
        "server_proc_p95_ms": percentile(processing_times, 0.95),
        "wall_s": round(wall_seconds, 2),
        "throughput_rps": round(total / wall_seconds, 2) if wall_seconds else 0,
    }


def main() -> int:
    for concurrency, total in ((1, 10), (5, 20), (10, 30)):
        print(
            json.dumps(
                run_scenario(concurrency, total),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
