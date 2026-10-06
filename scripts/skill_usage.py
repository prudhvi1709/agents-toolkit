"""Count explicit skill invocations and read requests without exporting log text."""

from __future__ import annotations

import json
import re
import shlex
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SKILL_NAME = re.compile(r"[a-z0-9][a-z0-9:_-]{0,127}\Z")
SKILL_PATH = re.compile(r"(?:^|[/\\])skills[/\\](?:[a-zA-Z0-9_.-]+[/\\])*([a-z0-9_-]+)[/\\]SKILL\.md\Z")
READ_TOOLS = frozenset({"Read", "read_file"})
SHELL_TOOLS = frozenset({"Bash", "exec_command", "functions.exec_command"})
READ_COMMANDS = frozenset({"cat", "head", "tail", "sed", "rg", "bat", "less"})


def parse_since(value: str) -> datetime:
    """Require an ISO timestamp with an explicit timezone."""
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("--since requires an ISO timestamp with a timezone")
    return result


def command_skills(command: str) -> set[str]:
    """Recognize direct shell reads, excluding echoed examples and heredoc bodies."""
    found: set[str] = set()
    # Deliberately conservative: shell aliases, expansions and dynamic paths are
    # missed. Add fixture-backed adapters rather than interpreting arbitrary shell.
    for line in command.splitlines():
        if "<<" in line:
            break
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue
        if not tokens or Path(tokens[0]).name not in READ_COMMANDS:
            continue
        for token in tokens[1:]:
            match = SKILL_PATH.search(token)
            if match:
                found.add(match[1])
    return found


def call_skills(name: str, arguments: Any) -> set[tuple[str, str]]:
    """Extract evidence from actual tool call inputs, never ordinary prose."""
    if name in {"functions.exec", "exec"} and isinstance(arguments, str):
        found: set[tuple[str, str]] = set()
        # Codex orchestration embeds commands in JavaScript. Only decode JSON
        # string literals immediately following cmd; do not execute the source.
        for match in re.finditer(r'tools\.exec_command\(\s*\{\s*(?:"cmd"|cmd)\s*:\s*("(?:\\.|[^"\\])*")', arguments):
            try:
                command = json.loads(match[1])
            except json.JSONDecodeError:
                continue
            found.update((skill, "read_requested") for skill in command_skills(command))
        return found
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return set()
    if not isinstance(arguments, dict):
        return set()
    if name == "Skill":
        skill = arguments.get("skill")
        return {(skill, "invoked")} if isinstance(skill, str) and SKILL_NAME.fullmatch(skill) else set()
    if name in READ_TOOLS:
        path = arguments.get("file_path", arguments.get("path"))
        match = SKILL_PATH.search(path) if isinstance(path, str) else None
        return {(match[1], "read_requested")} if match else set()
    if name in SHELL_TOOLS:
        command = arguments.get("command", arguments.get("cmd"))
        if isinstance(command, str):
            return {(skill, "read_requested") for skill in command_skills(command)}
    return set()


def record_calls(record: dict[str, Any]) -> list[tuple[str, Any]]:
    """Support Claude assistant tool blocks and Codex response-item calls."""
    calls: list[tuple[str, Any]] = []
    if record.get("type") == "assistant":
        message = record.get("message")
        content = message.get("content", []) if isinstance(message, dict) else []
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                calls.append((block["name"], block.get("input")))
    payload = record.get("payload")
    if record.get("type") == "response_item" and isinstance(payload, dict):
        if payload.get("type") in {"function_call", "custom_tool_call"} and isinstance(payload.get("name"), str):
            calls.append((payload["name"], payload.get("arguments", payload.get("input"))))
    return calls


def audit_skill_usage(home: Path, *, since: datetime | None = None) -> dict[str, Any]:
    """Return aggregate session counts and explicit coverage gaps only."""
    roots = {
        "claude": home / ".claude/projects",
        "codex": home / ".codex/sessions",
        "codex_archive": home / ".codex/archived_sessions",
        "claude_desktop": home / "Library/Application Support/Claude/local-agent-mode-sessions",
    }
    coverage: dict[str, dict[str, Any]] = {}
    found: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    all_sessions: dict[tuple[str, str], set[str]] = defaultdict(set)
    for provider, root in roots.items():
        stats = {"available": root.is_dir(), "files": 0, "read_errors": 0,
                 "malformed_records": 0, "undated_records": 0, "records_in_window": 0}
        coverage[provider] = stats
        for path in sorted(root.rglob("*.jsonl")) if stats["available"] else []:
            stats["files"] += 1
            session = str(path)
            try:
                with path.open(encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            stats["malformed_records"] += 1
                            continue
                        if not isinstance(record, dict):
                            stats["malformed_records"] += 1
                            continue
                        if record.get("type") == "session_meta" and isinstance(record.get("payload"), dict):
                            session = str(record["payload"].get("id") or session)
                        session = str(record.get("sessionId") or session)
                        raw_timestamp = record.get("timestamp")
                        try:
                            timestamp = parse_since(raw_timestamp) if isinstance(raw_timestamp, str) else None
                        except ValueError:
                            timestamp = None
                        if timestamp is None:
                            stats["undated_records"] += 1
                            if since is not None:
                                continue
                        if since is not None and timestamp is not None and timestamp < since:
                            continue
                        stats["records_in_window"] += 1
                        for name, arguments in record_calls(record):
                            for skill, kind in call_skills(name, arguments):
                                found[provider, skill, kind].add(session)
                                all_sessions[provider, skill].add(session)
            except (OSError, UnicodeError):
                stats["read_errors"] += 1
    rows = [{"provider": provider, "skill": skill,
             "invoked_sessions": len(found[provider, skill, "invoked"]),
             "read_requested_sessions": len(found[provider, skill, "read_requested"]),
             "unique_sessions": len(sessions)}
            for (provider, skill), sessions in sorted(all_sessions.items())]
    return {"since": since.isoformat() if since else None, "coverage": coverage,
            "skills": rows, "limitations": [
                "Invocation and read requests do not establish successful loading or useful outcomes.",
                "Counts deduplicate each skill within a session; evidence kinds overlap.",
                "Only supported tool-call formats and literal read commands are detected.",
                "Logs can be incomplete; undated records are excluded when --since is supplied.",
                "No prompts, transcripts, arguments, paths or session identifiers are exported.",
            ]}
