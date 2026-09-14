#!/usr/bin/env python3
"""Run a child command while teeing its stdout/stderr into a size-capped log.

Usage:
    log_tee.py <log_file> <max_bytes> <backup_count> -- <child command...>

Runs the child (the uvicorn server), copies its combined output into
``log_file``, and rotates ``log_file`` -> ``log_file.1`` -> ``log_file.2`` ...
whenever it grows past ``max_bytes``, keeping ``backup_count`` old files.
SIGTERM/SIGINT are forwarded to the child, so stopping this wrapper's PID (the
one ``run.sh`` tracks) also stops the server. Everything is stdlib-only, so
the local ``.run/`` log is bounded without relying on logrotate/rotatelogs.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys


def _rotate(path: str, backup_count: int) -> None:
    for index in range(backup_count - 1, 0, -1):
        source = f"{path}.{index}"
        if os.path.exists(source):
            shutil.move(source, f"{path}.{index + 1}")
    if os.path.exists(path):
        shutil.move(path, f"{path}.1")


def main() -> int:
    if len(sys.argv) < 6 or sys.argv[4] != "--":
        print("usage: log_tee.py <log_file> <max_bytes> <backup_count> -- <cmd...>",
              file=sys.stderr)
        return 2
    log_file = sys.argv[1]
    max_bytes = int(sys.argv[2])
    backup_count = max(1, int(sys.argv[3]))
    child_args = sys.argv[5:]

    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    child = subprocess.Popen(
        child_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    signal.signal(signal.SIGTERM, lambda *_sig: child.terminate())
    signal.signal(signal.SIGINT, lambda *_sig: child.terminate())

    assert child.stdout is not None
    handle = open(log_file, "ab")
    while True:
        chunk = child.stdout.read(64 * 1024)
        if not chunk:
            break
        view = memoryview(chunk)
        while view:
            budget = max_bytes - handle.tell()
            if budget <= 0:
                handle.close()
                _rotate(log_file, backup_count)
                handle = open(log_file, "ab")
                budget = max_bytes
            take = min(len(view), budget)
            handle.write(view[:take])
            handle.flush()
            view = view[take:]
    handle.close()
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
