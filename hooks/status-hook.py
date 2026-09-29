#!/usr/bin/env python3
"""Write a privacy-conscious snapshot from an agent lifecycle event."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def _string_field(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    return value if isinstance(value, str) else ""


def _events_dir() -> Path:
    configured = os.environ.get("AGENT_EVENTS_DIR")
    if configured:
        return Path(configured).expanduser()
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else Path.home() / ".local/state"
    return base / "agents-toolkit" / "events"


def _write_snapshot(directory: Path, process_id: int, record: dict[str, Any]) -> None:
    # Event files contain local project and transcript paths, so keep them owner-only.
    previous_umask = os.umask(0o077)
    temporary_path: Path | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{process_id}.", suffix=".tmp", dir=directory
        )
        temporary_path = Path(temporary_name)
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, directory / f"{process_id}.json")
    finally:
        os.umask(previous_umask)
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    event = _string_field(payload, "hook_event_name")
    session_id = _string_field(payload, "session_id")
    if not event or not session_id:
        return 0

    record = {
        "event": event,
        "session_id": session_id,
        "cwd": _string_field(payload, "cwd"),
        "transcript_path": _string_field(payload, "transcript_path"),
        "ts": int(time.time()),
    }
    try:
        _write_snapshot(_events_dir(), os.getppid(), record)
    except OSError:
        # Status collection is best-effort and must not interrupt an agent turn.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
