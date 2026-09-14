#!/usr/bin/env python3
"""Run a child command while directing its output into a size-capped log.

Usage:
    log_tee.py <log_file> <max_bytes> <backup_count> -- <child command...>

Runs the child (the uvicorn server) with its stdout/stderr pointed straight at
``log_file`` — no pipe round-trip. A supervisor loop watches the live file
size and, once it passes ``max_bytes``, does a copytruncate rotation: the
current ``log_file`` is copied to ``log_file.1`` (older backups are copied to
``log_file.2`` ... ``log_file.N``), then ``log_file`` is truncated *in place*.
Truncating the same inode keeps the child's already-open fd valid, so the
child keeps appending to the fresh ``log_file`` rather than to a renamed-away
file. SIGTERM/SIGINT are forwarded to the child, so stopping this wrapper's
PID (the one ``run.sh`` tracks) also stops the server. Everything is
stdlib-only, so the local ``.run/`` log is bounded without relying on
logrotate/rotatelogs.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time


def _shift_backups(path: str, backup_count: int) -> None:
    """Copy current/older logs up one slot (copy, not rename).

    ``shutil.move`` would unlink the live inode away from ``path``; the child
    still holds that inode and would keep writing to a renamed-away file,
    leaving a fresh-but-empty ``log_file``. Copying keeps the live inode at
    ``path``, so only copy-based shifting is safe here.
    """
    for index in range(backup_count - 1, 0, -1):
        source = f"{path}.{index}"
        if os.path.exists(source):
            shutil.copyfile(source, f"{path}.{index + 1}")
    if os.path.exists(path) and os.path.getsize(path):
        shutil.copyfile(path, f"{path}.1")


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

    log_fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)

    child = subprocess.Popen(
        child_args,
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        # Reuse the inherited (already "clean") file descriptor for stdout so
        # subprocess does not run the output through an interaction wrapper.
        close_fds=True,
    )
    signal.signal(signal.SIGTERM, lambda *_sig: child.terminate())
    signal.signal(signal.SIGINT, lambda *_sig: child.terminate())

    try:
        while True:
            if child.poll() is not None:
                break
            try:
                size = os.fstat(log_fd).st_size
            except OSError:
                size = os.path.getsize(log_file)
            if size > max_bytes:
                # copytruncate: snapshot current contents to .1 (and bump older
                # backups), then shrink the live file in place so the child's
                # open fd keeps pointing at the same (now empty) inode.
                _shift_backups(log_file, backup_count)
                os.ftruncate(log_fd, 0)
            time.sleep(1)
    finally:
        try:
            os.close(log_fd)
        except OSError:
            pass
    try:
        return child.wait()
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())