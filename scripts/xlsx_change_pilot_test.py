#!/usr/bin/env python3
"""Run a fixed-concurrency Change Pilot REST test from an XLSX change sheet.

The script reads raw change points, checks service health, then processes rows
in batches of five concurrent requests. Each row gets at most three retries
after its initial request. Credentials and provider payloads are never printed.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
import urllib.error
import threading
import urllib.request
import zipfile
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree

from openpyxl import load_workbook


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKERS = 5
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 120
RETRY_BACKOFF_SECONDS = 0.5
CHANGE_POINT_HEADERS = ("原始变更点", "变更点", "变更内容")


@dataclass(frozen=True)
class ChangePoint:
    row_number: int
    text: str


class InputError(Exception):
    """Raised when the XLSX cannot provide usable change points."""


class RequestFailure(Exception):
    """Raised for a failed health or transformation request."""


@dataclass
class ApiStats:
    """Thread-safe counters for transformation API attempts."""

    total_calls: int = 0
    failed_calls: int = 0
    _lock: threading.Lock = dataclass_field(default_factory=threading.Lock, repr=False)

    def record(self, failed: bool) -> None:
        with self._lock:
            self.total_calls += 1
            if failed:
                self.failed_calls += 1


def load_token() -> str:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CHANGE_PILOT_API_TOKEN="):
            return line.split("=", 1)[1].strip()
    return ""


def _normalise(value: Any) -> str:
    return "" if value is None else "".join(str(value).split())


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _column_index(reference: str) -> int:
    letters = "".join(char for char in reference if char.isalpha())
    index = 0
    for char in letters.upper():
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _xml_rows(path: Path) -> list[list[Any]]:
    """Read worksheet cells by coordinate when XLSX dimension metadata is wrong."""
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("main:si", namespace):
                shared.append("".join(item.itertext()))

        rows: dict[int, dict[int, Any]] = {}
        for name in archive.namelist():
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            for row in root.findall(".//main:row", namespace):
                row_number = int(row.attrib.get("r", "0"))
                if not row_number:
                    continue
                values = rows.setdefault(row_number, {})
                for cell in row.findall("main:c", namespace):
                    reference = cell.attrib.get("r", "")
                    if not reference:
                        continue
                    column = _column_index(reference)
                    kind = cell.attrib.get("t")
                    value_node = cell.find("main:v", namespace)
                    inline_node = cell.find("main:is", namespace)
                    if kind == "inlineStr" and inline_node is not None:
                        value: Any = "".join(inline_node.itertext())
                    elif value_node is None:
                        value = ""
                    elif kind == "s":
                        index = int(value_node.text or "0")
                        value = shared[index] if index < len(shared) else ""
                    else:
                        value = value_node.text or ""
                    values[column] = value

    if not rows:
        return []
    width = max(max(row) for row in rows.values()) + 1
    return [[row.get(column, "") for column in range(width)] for _, row in sorted(rows.items())]


def _extract_points_from_rows(rows: list[list[Any]]) -> list[ChangePoint]:
    candidates: list[tuple[int, int, list[ChangePoint]]] = []
    for header_row, row in enumerate(rows):
        for header_index, value in enumerate(row):
            if not any(name in _normalise(value) for name in CHANGE_POINT_HEADERS):
                continue
            points = []
            for row_number, data in enumerate(rows[header_row + 1:], start=header_row + 2):
                cell = _text(data[header_index] if header_index < len(data) else None)
                if cell:
                    points.append(ChangePoint(row_number, cell))
            if points:
                # Prefer the candidate yielding the most data rows. This
                # avoids treating a merged section title as the real header
                # in multi-level change-sheet layouts.
                candidates.append((len(points), header_row, points))
    if candidates:
        return max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]
    return []


def read_change_points(path: Path) -> list[ChangePoint]:
    """Extract one raw change point per data row from an XLSX workbook."""
    if not path.exists():
        raise InputError(f"XLSX 文件不存在: {path}")
    if not path.is_file():
        raise InputError(f"XLSX 路径不是文件: {path}")
    if path.suffix.lower() != ".xlsx":
        raise InputError(f"仅支持 .xlsx 文件: {path}")

    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - normalize library/parser errors
        raise InputError(f"XLSX 文件无法读取，可能已加密或损坏: {path}") from exc

    try:
        sheets = list(workbook.worksheets)
        if not sheets:
            raise InputError("XLSX 中没有工作表")

        # Prefer an explicitly named change-point column wherever it appears.
        for sheet in sheets:
            rows = sheet.iter_rows(values_only=True)
            header = next(rows, None)
            if header is None:
                continue
            header_index = next(
                (
                    index
                    for index, value in enumerate(header)
                    if any(name in _normalise(value) for name in CHANGE_POINT_HEADERS)
                ),
                None,
            )
            if header_index is None:
                # A header may not be on row 1 in a formatted change sheet.
                buffered = [header]
                buffered.extend(rows)
                for row_number, row in enumerate(buffered, start=1):
                    index = next(
                        (
                            i for i, value in enumerate(row)
                            if any(name in _normalise(value) for name in CHANGE_POINT_HEADERS)
                        ),
                        None,
                    )
                    if index is not None:
                        points = [
                            ChangePoint(row_number + offset, value)
                            for offset, data in enumerate(buffered[row_number:])
                            if (value := _text(data[index] if index < len(data) else None))
                        ]
                        if points:
                            return points
                        break
                continue

            points = []
            for row_number, row in enumerate(rows, start=2):
                value = _text(row[header_index] if header_index < len(row) else None)
                if value:
                    points.append(ChangePoint(row_number, value))
            if points:
                return points

        # Fallback for sheets without a recognizable header: use non-empty
        # text cells, but do not silently turn a blank/placeholder workbook
        # into a zero-row successful test.
        fallback: list[ChangePoint] = []
        for sheet in sheets:
            for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                values = [_text(value) for value in row]
                for value in values:
                    if value:
                        fallback.append(ChangePoint(row_number, value))
        if fallback:
            return fallback

        # Some workbooks contain valid worksheet cells but an incorrect
        # ``dimension ref="A1"``.  The read-only parser then sees only a
        # blank cell, so recover values from the worksheet XML directly.
        try:
            xml_points = _extract_points_from_rows(_xml_rows(path))
        except (OSError, KeyError, ValueError, ElementTree.ParseError) as exc:
            raise InputError(f"XLSX 结构异常，无法读取工作表数据: {path}") from exc
        if xml_points:
            return xml_points

        names = ", ".join(sheet.title for sheet in sheets)
        raise InputError(f"XLSX 中没有可用的原始变更点（工作表: {names}）")
    finally:
        workbook.close()


def _request_json(
    url: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if not 200 <= response.status < 300:
                raise RequestFailure(f"HTTP {response.status}")
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RequestFailure(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RequestFailure(exc.__class__.__name__) from exc
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError) as exc:
        raise RequestFailure("响应不是有效 JSON") from exc
    if not isinstance(parsed, dict):
        raise RequestFailure("响应 JSON 不是对象")
    return parsed


def health_check(base_url: str, token: str) -> None:
    try:
        result = _request_json(f"{base_url}/health", token)
        if result.get("status") != "ok":
            raise RequestFailure("health status 非 ok")
    except RequestFailure as exc:
        raise RequestFailure(f"健康检查失败: {exc}") from exc


def call_change_pilot(base_url: str, token: str, raw_text: str) -> str:
    result = _request_json(
        f"{base_url}/v1/change-pilot",
        token,
        method="POST",
        payload={"raw_text": raw_text, "mode": "default"},
    )
    output = result.get("customer_output")
    if result.get("success") is not True or not isinstance(output, str) or not output.strip():
        raise RequestFailure("接口返回失败")
    return output.strip()


def process_one(
    base_url: str,
    token: str,
    point: ChangePoint,
    stats: ApiStats,
    max_retries: int = MAX_RETRIES,
    progress: "Callable[[int], None] | None" = None,
) -> tuple[ChangePoint, str | None]:
    """Transform one point, retrying up to ``max_retries`` extra times.

    ``progress`` is an optional callback invoked as ``progress(attempt)``
    before each retry (attempt = 1-based retry count) so the caller can
    surface the retry in its progress view.
    """
    for attempt in range(max_retries + 1):
        if attempt and progress is not None:
            progress(attempt)
        try:
            output = call_change_pilot(base_url, token, point.text)
            stats.record(failed=False)
            return point, output
        except RequestFailure:
            stats.record(failed=True)
            if attempt >= max_retries:
                break
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    return point, None


def process_in_batches(
    base_url: str,
    token: str,
    points: list[ChangePoint],
    stats: ApiStats,
    workers: int = WORKERS,
    max_retries: int = MAX_RETRIES,
) -> list[tuple[ChangePoint, str | None]]:
    """Keep the configured number of requests in flight and refresh progress slots."""
    results: list[tuple[ChangePoint, str | None] | None] = [None] * len(points)
    slots: list[str] = []
    slot_futures: dict[concurrent.futures.Future, tuple[int, int]] = {}
    next_index = 0
    interactive = sys.stdout.isatty()
    block_rendered = False
    terminal_lock = threading.Lock()

    def paint() -> None:
        # Assumes terminal_lock is held. Rise back to the block's first line
        # only after it has been drawn once: on the first render the cursor is
        # already at the block start (just below the health-check log), so
        # rising early would climb into those logs and wipe them.
        nonlocal block_rendered
        if interactive:
            if block_rendered:
                sys.stdout.write(f"\033[{len(slots)}A")
            else:
                block_rendered = True
            for message in slots:
                sys.stdout.write(f"\033[2K{message}\n")
        else:
            for message in slots:
                print(message)
        sys.stdout.flush()

    def render() -> None:
        with terminal_lock:
            paint()

    def report_retry(slot: int, ordinal: int, attempt: int) -> None:
        """Flip a slot to its retry message and repaint immediately."""
        with terminal_lock:
            slots[slot] = f"正在处理第{ordinal}条数据，第{attempt}次重试中..."
            paint()

    def make_progress(slot: int, ordinal: int) -> "Callable[[int], None]":
        return lambda attempt: report_retry(slot, ordinal, attempt)

    def submit_one(point_index: int, slot: int) -> concurrent.futures.Future:
        point = points[point_index]
        return executor.submit(
            process_one, base_url, token, point, stats, max_retries,
            make_progress(slot, point_index + 1),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        while next_index < len(points) and len(slot_futures) < workers:
            slot = len(slot_futures)
            slots.append(f"正在处理第{next_index + 1}条数据...")
            slot_futures[submit_one(next_index, slot)] = (slot, next_index)
            next_index += 1
        render()

        while slot_futures:
            done, _ = concurrent.futures.wait(
                slot_futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                slot, point_index = slot_futures.pop(future)
                point, output = future.result()
                results[point_index] = (point, output)
                with terminal_lock:
                    if next_index < len(points):
                        slots[slot] = f"正在处理第{next_index + 1}条数据..."
                        slot_futures[submit_one(next_index, slot)] = (slot, next_index)
                        next_index += 1
                    else:
                        slots[slot] = "处理完成，等待其他任务..."
            render()

    if interactive and slots:
        with terminal_lock:
            sys.stdout.write(f"\033[{len(slots)}A")
            for _ in slots:
                sys.stdout.write("\033[2K\n")
            sys.stdout.write("处理进度完成\n")
            sys.stdout.flush()
    return [result for result in results if result is not None]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, required=True, help="原始变更单 .xlsx 路径")
    parser.add_argument("--base-url", required=True, help="Change Pilot 服务地址，例如 http://127.0.0.1:18081")
    parser.add_argument(
        "--concurrency", type=int, default=WORKERS,
        help=f"并发请求数（默认 {WORKERS}）",
    )
    parser.add_argument(
        "--retry", type=int, default=MAX_RETRIES,
        help=f"每条变更点最大重试次数，0 表示不重试（默认 {MAX_RETRIES}）",
    )
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        parser.error(f"--concurrency 必须 >= 1，received {args.concurrency}")
    if args.retry < 0:
        parser.error(f"--retry 必须 >= 0，received {args.retry}")
    base_url = args.base_url.rstrip("/")

    try:
        points = read_change_points(args.xlsx)
    except InputError as exc:
        print(f"文件校验失败: {exc}", file=sys.stderr)
        return 2
    print(f"文件校验通过: {args.xlsx}，读取到 {len(points)} 条原始变更点")

    token = load_token()
    if not token:
        print("服务检查失败: .env 中未找到 CHANGE_PILOT_API_TOKEN", file=sys.stderr)
        return 2
    try:
        health_check(base_url, token)
    except RequestFailure as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"健康检查通过: {base_url}/health")

    stats = ApiStats()
    started_at = time.perf_counter()
    results = process_in_batches(
        base_url, token, points, stats,
        workers=args.concurrency, max_retries=args.retry,
    )
    elapsed_seconds = time.perf_counter() - started_at
    success_count = 0
    for serial, (point, output) in enumerate(results, start=1):
        if output is None:
            print(f"{serial}. 大模型提炼失败")
        else:
            success_count += 1
            print(f"{serial}. {output}")
    print(f"成功数/总数: {success_count}/{len(results)}")
    print(f"总耗时: {elapsed_seconds:.2f} 秒")
    print(f"API 总调用次数: {stats.total_calls}")
    print(f"API 失败次数: {stats.failed_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
