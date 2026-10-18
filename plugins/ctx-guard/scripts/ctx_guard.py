#!/usr/bin/env python3
"""Context watch, compaction checkpoint, and restore helpers for Claude Code hooks.

Subcommands read the hook JSON from stdin (except `where`) and never exit with a
blocking status: a failing guard must not stop a prompt or a compaction.
Checkpoints hold counts, git state and paths only, never prompt text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_WARN_TOKENS = 250_000
DEFAULT_CRITICAL_TOKENS = 500_000
TAIL_BYTES = 262_144  # newest usage record is near the end; ceiling: a >256 KiB final record
CHECKPOINT_MAX_AGE_S = 24 * 3600
RESTORE_MAX_CHARS = 1_500
GIT_TIMEOUT_S = 3
MAX_LISTED_FILES = 8
SOURCES_WITH_RESTORE = frozenset({"startup", "resume", "clear", "compact"})


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def thresholds() -> tuple[int, int]:
    warn = _int_env("CTX_GUARD_WARN_TOKENS", DEFAULT_WARN_TOKENS)
    critical = max(_int_env("CTX_GUARD_CRITICAL_TOKENS", DEFAULT_CRITICAL_TOKENS), warn)
    return warn, critical


def data_dir() -> Path:
    configured = os.environ.get("CLAUDE_PLUGIN_DATA")
    if configured:
        return Path(configured)
    return Path.home() / ".local" / "state" / "ctx-guard"


def project_key(cwd: str) -> str:
    return hashlib.sha1(cwd.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    previous_umask = os.umask(0o077)
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, separators=(",", ":"))
        os.replace(temporary, path)
        temporary = None
    finally:
        os.umask(previous_umask)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def context_tokens(transcript_path: str | Path) -> int | None:
    """Return the prompt size of the latest assistant call in a transcript, or None."""
    try:
        with open(transcript_path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(handle.tell() - TAIL_BYTES, 0))
            tail = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        message = record.get("message") if isinstance(record, dict) else None
        if not isinstance(message, dict) or record.get("type") != "assistant":
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict) or message.get("model") == "<synthetic>":
            continue
        total = sum(
            usage.get(key, 0)
            for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
            if isinstance(usage.get(key, 0), int)
        )
        if total > 0:
            return total
    return None


def level_for(tokens: int) -> int:
    warn, critical = thresholds()
    return 2 if tokens >= critical else 1 if tokens >= warn else 0


def _safe_id(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:64]


def watch(payload: dict[str, Any]) -> dict[str, Any] | None:
    """UserPromptSubmit: warn once per threshold crossing while context is large."""
    transcript = payload.get("transcript_path")
    session_id = payload.get("session_id")
    if not isinstance(transcript, str) or not isinstance(session_id, str) or not session_id:
        return None
    tokens = context_tokens(transcript)
    if tokens is None:
        return None
    level = level_for(tokens)
    state_path = data_dir() / "state" / f"{_safe_id(session_id)}.json"
    previous = (read_json(state_path) or {}).get("level", 0)
    if level == previous:
        return None
    atomic_write_json(state_path, {"level": level, "updated_at": int(time.time())})
    if level < previous or level == 0:
        return None  # context shrank (clear or compaction): re-arm silently
    size = f"{tokens // 1000}k"
    message = (
        f"ctx-guard: context is {size} tokens and every call re-reads it. "
        "Run /ctx-guard:where, then /compact with a focus or /clear and resume."
    )
    output: dict[str, Any] = {"systemMessage": message}
    if level == 2:
        output["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                f"Context is very large ({size} tokens). Before starting a large new task, "
                "tell the user and suggest saving state and starting a fresh session."
            ),
        }
    return output


def _git(cwd: str, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    # Only trailing newlines are dropped: porcelain lines start with a significant space.
    return result.stdout.rstrip("\n") if result.returncode == 0 else ""


def git_state(cwd: str) -> dict[str, Any]:
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if not branch:
        return {}
    changed = [line[3:] for line in _git(cwd, "status", "--porcelain").splitlines() if len(line) > 3]
    return {
        "branch": branch,
        "changed_count": len(changed),
        "changed": changed[:MAX_LISTED_FILES],
        "last_commit": _git(cwd, "log", "-1", "--format=%s").strip()[:80],
    }


def checkpoint_path(cwd: str) -> Path:
    return data_dir() / "checkpoints" / f"{project_key(cwd)}.json"


def checkpoint(payload: dict[str, Any]) -> None:
    """PreCompact: record a counts-and-paths snapshot for the project."""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return
    transcript = payload.get("transcript_path")
    tokens = context_tokens(transcript) if isinstance(transcript, str) else None
    path = checkpoint_path(cwd)
    previous = read_json(path) or {}
    atomic_write_json(
        path,
        {
            "version": 1,
            "saved_at": int(time.time()),
            "cwd": cwd,
            "session_id": payload.get("session_id"),
            "transcript_path": transcript,
            "trigger": payload.get("trigger"),
            "context_tokens": tokens,
            "compactions": int(previous.get("compactions", 0)) + 1,
            "git": git_state(cwd),
        },
    )


def _age(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes}m" if minutes < 120 else f"{minutes // 60}h"


def describe_checkpoint(record: dict[str, Any], now: float) -> str:
    git = record.get("git") if isinstance(record.get("git"), dict) else {}
    tokens = record.get("context_tokens")
    size = f"{tokens // 1000}k tokens" if isinstance(tokens, int) else "unknown size"
    parts = [
        f"saved {_age(now - float(record.get('saved_at', now)))} ago, "
        f"trigger {record.get('trigger') or '?'} at {size}, "
        f"{record.get('compactions', 1)} compaction(s) in this project"
    ]
    if git:
        files = ", ".join(str(name) for name in git.get("changed", []))
        extra = int(git.get("changed_count", 0)) - len(git.get("changed", []))
        parts.append(f"branch {git.get('branch')}")
        parts.append(f"uncommitted: {files or 'none'}" + (f" (+{extra} more)" if extra > 0 else ""))
        parts.append(f"last commit: {git.get('last_commit') or 'n/a'}")
    return "; ".join(parts)


def restore(payload: dict[str, Any]) -> dict[str, Any] | None:
    """SessionStart: surface the latest checkpoint as bounded, labeled data."""
    source = payload.get("source")
    cwd = payload.get("cwd")
    if source not in SOURCES_WITH_RESTORE or not isinstance(cwd, str):
        return None
    record = read_json(checkpoint_path(cwd))
    if record is None:
        return None
    now = time.time()
    if source != "compact" and now - float(record.get("saved_at", 0)) > CHECKPOINT_MAX_AGE_S:
        return None
    text = (
        "ctx-guard snapshot (informational data from a local file, not instructions): "
        + describe_checkpoint(record, now)
        + ". No decisions or next action are recorded; re-read the repository and ask if unsure."
    )
    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text[:RESTORE_MAX_CHARS],
        }
    }
    resumed_tokens = payload.get("context_tokens")
    if source in {"resume", "fork"} and isinstance(resumed_tokens, int) and resumed_tokens >= thresholds()[0]:
        output["systemMessage"] = (
            f"ctx-guard: resuming a {resumed_tokens // 1000}k-token context"
            + (" with an expired prompt cache" if payload.get("prompt_cache_likely_expired") else "")
            + ". Consider /clear plus a short handoff instead."
        )
    return output


def latest_transcript(cwd: str) -> Path | None:
    folder = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd)
    try:
        candidates = [path for path in folder.glob("*.jsonl") if path.is_file()]
    except OSError:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def where(cwd: str) -> str:
    """Plain-text status for the /ctx-guard:where skill."""
    warn, critical = thresholds()
    lines = [f"project: {cwd}"]
    transcript = latest_transcript(cwd)
    tokens = context_tokens(transcript) if transcript else None
    if tokens is None:
        lines.append("context: unknown (no transcript found for this directory)")
    else:
        flag = ["ok", "WARN", "CRITICAL"][level_for(tokens)]
        lines.append(f"context: {tokens // 1000}k tokens, {flag} (warn {warn // 1000}k, critical {critical // 1000}k)")
    record = read_json(checkpoint_path(cwd))
    lines.append("checkpoint: " + (describe_checkpoint(record, time.time()) if record else "none yet"))
    git = git_state(cwd)
    if git:
        lines.append(f"git now: branch {git['branch']}, {git['changed_count']} uncommitted file(s)")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"checked: {now}")
    return "\n".join(lines)


def _read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("watch", "checkpoint", "restore"):
        sub.add_parser(name, help=f"hook entry point: {name} (JSON on stdin)")
    where_parser = sub.add_parser("where", help="print a status summary")
    where_parser.add_argument("--cwd", default=os.getcwd())
    where_parser.add_argument(
        "--data-dir",
        help="plugin data directory; needed because Bash tool calls do not export CLAUDE_PLUGIN_DATA",
    )
    args = parser.parse_args(argv)

    if args.command == "where":
        if args.data_dir:
            os.environ["CLAUDE_PLUGIN_DATA"] = args.data_dir
        print(where(args.cwd))
        return 0
    handlers = {"watch": watch, "restore": restore}
    try:
        payload = _read_payload()
        if args.command == "checkpoint":
            checkpoint(payload)
            output = None
        else:
            output = handlers[args.command](payload)
    except (OSError, ValueError, TypeError) as error:  # never block a prompt or compaction on a guard failure
        print(f"ctx-guard {args.command}: {error}", file=sys.stderr)
        return 0
    if output is not None:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
