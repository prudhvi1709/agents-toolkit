#!/usr/bin/env python3
"""Incrementally index selected Claude/Codex project history, without model calls."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

MAX_RECORD_BYTES = 8 * 1024 * 1024
CHUNK_CHARS = 3000
APPLICATION = "agents-toolkit-history"
VERSION = "1"
KINDS = {"decision", "requirement", "correction", "question", "finding"}


class Envelope(BaseModel):
    """Validate the common envelope; provider adapters inspect relevant blocks."""

    type: str
    timestamp: str | None = None
    cwd: str | None = None
    session_id: str | None = Field(default=None, alias="sessionId")
    uuid: str | None = None
    parent_uuid: str | None = Field(default=None, alias="parentUuid")
    is_meta: bool = Field(default=False, alias="isMeta")
    is_compact_summary: bool = Field(default=False, alias="isCompactSummary")
    message: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None


def digest(data: bytes) -> str:
    """Return a stable content identity."""
    return hashlib.sha256(data).hexdigest()


def redact(text: str) -> str:
    """Remove common credential formats; this is not a complete DLP system."""
    text = re.sub(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
        "[REDACTED KEY]",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})\b",
        "[REDACTED TOKEN]",
        text,
    )
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*", "Bearer [REDACTED]", text)
    text = re.sub(
        r"(?im)(\b(?:api[_-]?key|access[_-]?token|password|client[_-]?secret|secret[_-]?key)\b\s*[=:]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        text,
    )
    return text


def extract_text(record: Envelope, provider: str) -> tuple[str, str] | None:
    """Keep conversation text only, never reasoning, tool arguments or outputs."""
    if record.is_meta:
        return None
    if provider == "claude":
        if record.type not in {"user", "assistant"} or record.message is None:
            return None
        role = record.type
        content = record.message.get("content")
    else:
        payload = record.payload or {}
        if record.type != "response_item" or payload.get("type") != "message":
            return None
        role_value = payload.get("role")
        if not isinstance(role_value, str) or role_value not in {"user", "assistant"}:
            return None
        role = role_value
        content = payload.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") in {"text", "input_text", "output_text"}
            and isinstance(block.get("text"), str)
        ]
        text = "\n".join(parts)
    else:
        return None
    # These injected instruction/context envelopes are not conversational evidence.
    if text.lstrip().startswith(
        (
            "<environment_context>",
            "<INSTRUCTIONS>",
            "# AGENTS.md instructions",
            "<system-reminder>",
        )
    ):
        return None
    if not text.strip():
        return None
    return ("summary" if record.is_compact_summary else role), redact(text)


def verify(connection: sqlite3.Connection) -> dict[str, str]:
    """Reject unrelated or incompatible databases."""
    try:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    except sqlite3.Error as error:
        raise ValueError("Unsupported history database") from error
    if metadata.get("application") != APPLICATION or metadata.get("version") != VERSION:
        raise ValueError("Unsupported history database")
    return metadata


def open_history(database: Path, *, writable: bool = False) -> sqlite3.Connection:
    """Default to read-only and keep private state out of repositories."""
    database = database.expanduser()
    if database.is_symlink():
        raise ValueError("History database must not be symlinked")
    if any((parent / ".git").exists() for parent in database.resolve().parents):
        raise ValueError("Keep history outside repositories")
    if writable:
        database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not database.exists():
            descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        connection = sqlite3.connect(database, timeout=10)
    else:
        connection = sqlite3.connect(
            f"{database.resolve().as_uri()}?mode=ro", uri=True, timeout=10
        )
    connection.row_factory = sqlite3.Row
    return connection


def initialize(connection: sqlite3.Connection, projects: list[str], home: Path) -> None:
    """Persist scope so later indexing cannot silently broaden it."""
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    if tables:
        metadata = verify(connection)
        if json.loads(metadata["projects"]) != projects or metadata["home"] != str(
            home
        ):
            raise ValueError("Scope changed; use a separate database for the new scope")
        return
    connection.executescript("""
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources(path TEXT PRIMARY KEY, provider TEXT NOT NULL, identity TEXT NOT NULL,
          offset INTEGER NOT NULL, prefix_hash TEXT NOT NULL, line INTEGER NOT NULL,
          project TEXT NOT NULL, session TEXT NOT NULL, size INTEGER NOT NULL, mtime INTEGER NOT NULL,
          state TEXT NOT NULL, counters TEXT NOT NULL);
        CREATE TABLE turns(id TEXT PRIMARY KEY, project TEXT NOT NULL, session TEXT NOT NULL,
          provider TEXT NOT NULL, role TEXT NOT NULL, timestamp TEXT, text TEXT NOT NULL, parent TEXT);
        CREATE TABLE evidence(turn_id TEXT NOT NULL, path TEXT NOT NULL, offset INTEGER NOT NULL,
          length INTEGER NOT NULL, line INTEGER NOT NULL, raw_hash TEXT NOT NULL,
          PRIMARY KEY(turn_id,path,offset));
        CREATE VIRTUAL TABLE chunks USING fts5(text, turn_id UNINDEXED, part UNINDEXED, tokenize='porter unicode61');
        CREATE TABLE memories(id TEXT PRIMARY KEY, project TEXT NOT NULL, kind TEXT NOT NULL,
          status TEXT NOT NULL, text TEXT NOT NULL, turn_id TEXT NOT NULL, supersedes TEXT, created_at TEXT NOT NULL);
        CREATE INDEX turns_project ON turns(project);
        CREATE INDEX evidence_turn ON evidence(turn_id);
    """)
    connection.executemany(
        "INSERT INTO metadata VALUES (?,?)",
        [
            ("application", APPLICATION),
            ("version", VERSION),
            ("projects", json.dumps(projects)),
            ("home", str(home)),
            ("updated_at", datetime.now(UTC).isoformat()),
        ],
    )
    connection.commit()


def prefix_hash(handle: Any, size: int) -> str:
    """Hash prior bytes to detect rewrites as well as truncation."""
    handle.seek(0)
    checksum = hashlib.sha256()
    remaining = size
    while remaining:
        block = handle.read(min(remaining, 1024 * 1024))
        if not block:
            break
        checksum.update(block)
        remaining -= len(block)
    return checksum.hexdigest()


def ingest_file(
    connection: sqlite3.Connection,
    path: Path,
    provider: str,
    projects: set[str],
    *,
    home: Path | None = None,
) -> str:
    """Commit each file and its cursor together; interruption safely resumes."""
    stat = path.stat()
    identity = f"{stat.st_dev}:{stat.st_ino}"
    previous = connection.execute(
        "SELECT * FROM sources WHERE path=?", (str(path),)
    ).fetchone()
    with path.open("rb") as handle:
        restart = (
            previous is None
            or previous["identity"] != identity
            or stat.st_size < previous["offset"]
        )
        if previous is not None and not restart:
            # Linear hash verification is deliberate for small local archives.
            # If disk I/O becomes costly, replace it with a tested block-hash manifest.
            restart = prefix_hash(handle, previous["offset"]) != previous["prefix_hash"]
        if previous is not None and not restart and stat.st_size == previous["offset"]:
            connection.execute(
                "UPDATE sources SET state='current' WHERE path=?", (str(path),)
            )
            return "unchanged"
        offset = 0 if restart else previous["offset"]
        line_number = 0 if restart else previous["line"]
        project = "" if restart else previous["project"]
        session = str(path) if restart else previous["session"]
        counters = {
            "records": 0,
            "malformed": 0,
            "unsupported": 0,
            "out_of_scope": 0,
            "oversized": 0,
        }
        if not restart:
            counters = json.loads(previous["counters"])
        if restart:
            connection.execute("DELETE FROM evidence WHERE path=?", (str(path),))
        handle.seek(offset)
        while True:
            start = handle.tell()
            raw = handle.readline(MAX_RECORD_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_RECORD_BYTES:
                while raw and not raw.endswith(b"\n"):
                    raw = handle.readline(MAX_RECORD_BYTES + 1)
                if not raw.endswith(b"\n"):
                    handle.seek(start)
                    break
                counters["oversized"] += 1
                line_number += 1
                continue
            if not raw.endswith(b"\n"):
                handle.seek(start)
                break
            line_number += 1
            counters["records"] += 1
            try:
                record = Envelope.model_validate_json(raw)
            except ValidationError:
                counters["malformed"] += 1
                continue
            payload = record.payload or {}
            if record.type == "session_meta" and isinstance(payload.get("id"), str):
                session = payload["id"]
            if record.session_id:
                session = record.session_id
            cwd = record.cwd or (
                payload.get("cwd")
                if record.type in {"session_meta", "turn_context"}
                else None
            )
            if isinstance(cwd, str) and Path(cwd).is_absolute():
                resolved = Path(cwd).resolve()
                project = next(
                    (
                        root
                        for root in sorted(projects, key=len, reverse=True)
                        if resolved.is_relative_to(Path(root))
                        and (home is None or Path(root) != home or resolved == home)
                    ),
                    "",
                )
            if project not in projects:
                counters["out_of_scope"] += 1
                continue
            extracted = extract_text(record, provider)
            if extracted is None:
                counters["unsupported"] += 1
                continue
            role, text = extracted
            original_id = record.uuid or payload.get("id") or str(start)
            identifier = digest(
                json.dumps(
                    [provider, session, original_id, role, text], ensure_ascii=True
                ).encode()
            )
            cursor = connection.execute(
                "INSERT OR IGNORE INTO turns VALUES (?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    project,
                    session,
                    provider,
                    role,
                    record.timestamp,
                    text,
                    record.parent_uuid,
                ),
            )
            if cursor.rowcount:
                for part, position in enumerate(range(0, len(text), CHUNK_CHARS)):
                    connection.execute(
                        "INSERT INTO chunks VALUES (?,?,?)",
                        (text[position : position + CHUNK_CHARS], identifier, part),
                    )
            connection.execute(
                "INSERT OR IGNORE INTO evidence VALUES (?,?,?,?,?,?)",
                (identifier, str(path), start, len(raw), line_number, digest(raw)),
            )
        offset = handle.tell()
        checksum = prefix_hash(handle, offset)
    connection.execute(
        "INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            str(path),
            provider,
            identity,
            offset,
            checksum,
            line_number,
            project,
            session,
            stat.st_size,
            stat.st_mtime_ns,
            "current",
            json.dumps(counters),
        ),
    )
    return "updated"


def ingest(
    database: Path, home: Path, projects: list[Path], *, max_files: int | None = None
) -> dict[str, Any]:
    """Inventory known agent roots and ingest only the selected project scope."""
    if not projects or any(
        not project.expanduser().is_absolute() for project in projects
    ):
        raise ValueError("Select at least one absolute project path")
    # Historical projects may have been moved or deleted. Scope selects log
    # metadata; it never grants permission to read files under a project path.
    selected = sorted({str(project.expanduser().resolve()) for project in projects})
    home = home.expanduser().resolve()
    roots = [
        ("claude", home / ".claude/projects"),
        ("codex", home / ".codex/sessions"),
        ("codex", home / ".codex/archived_sessions"),
    ]
    counts = {
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
        "remaining": 0,
        "symlinks_skipped": 0,
    }
    with closing(open_history(database, writable=True)) as connection:
        initialize(connection, selected, home)
        files = []
        for provider, root in roots:
            if root.is_dir() and not root.is_symlink():
                for path in sorted(root.rglob("*.jsonl")):
                    if any(
                        parent.is_symlink()
                        for parent in (path, *path.parents)
                        if parent.is_relative_to(root)
                    ):
                        counts["symlinks_skipped"] += 1
                        continue
                    if not path.is_symlink() and path.resolve().is_relative_to(
                        root.resolve()
                    ):
                        files.append((provider, path.resolve()))
        available = {str(path) for _, path in files}
        for row in connection.execute("SELECT path FROM sources").fetchall():
            if row["path"] not in available:
                connection.execute(
                    "UPDATE sources SET state='missing' WHERE path=?", (row["path"],)
                )
        connection.commit()
        for number, (provider, path) in enumerate(files):
            if max_files is not None and number >= max_files:
                counts["remaining"] = len(files) - number
                break
            try:
                with connection:
                    outcome = ingest_file(
                        connection, path, provider, set(selected), home=home
                    )
                counts[outcome] += 1
            except (OSError, ValueError, sqlite3.Error):
                counts["failed"] += 1
                continue
        connection.execute(
            "UPDATE metadata SET value=? WHERE key='updated_at'",
            (datetime.now(UTC).isoformat(),),
        )
        connection.commit()
        totals = dict(
            connection.execute(
                "SELECT provider, COUNT(*) FROM turns GROUP BY provider"
            ).fetchall()
        )
    return {
        **counts,
        "inventoried_files": len(files),
        "turns_by_provider": totals,
        "available_roots": sum(root.is_dir() for _, root in roots),
        "project_count": len(selected),
        "model_calls": 0,
        "limitation": "Only selected projects and conversation text are indexed; tool outputs and reasoning are excluded.",
    }


def evidence_status(row: sqlite3.Row) -> str:
    """Verify just the original record, not an entire multi-megabyte session."""
    path = Path(row["path"])
    try:
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            return "unavailable"
        with path.open("rb") as handle:
            handle.seek(row["offset"])
            raw = handle.read(row["length"])
        return "current" if digest(raw) == row["raw_hash"] else "changed"
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unavailable"


def locator(connection: sqlite3.Connection, turn_id: str) -> dict[str, Any]:
    """Choose a current original when replayed turns have multiple locators."""
    rows = connection.execute(
        "SELECT * FROM evidence WHERE turn_id=? ORDER BY path,offset", (turn_id,)
    ).fetchall()
    for row in rows:
        state = evidence_status(row)
        if state == "current":
            return {"source_status": state, "path": row["path"], "line": row["line"]}
    return {
        "source_status": "cached_only",
        "limitation": "Original record is missing or changed; cached conversation is historical evidence.",
    }


def status(database: Path) -> dict[str, Any]:
    """Return coverage without private contents or session identifiers."""
    if not database.expanduser().exists():
        return {"available": False}
    with closing(open_history(database)) as connection:
        metadata = verify(connection)
        coverage = {
            "records": 0,
            "malformed": 0,
            "unsupported": 0,
            "out_of_scope": 0,
            "oversized": 0,
        }
        sources = connection.execute(
            "SELECT offset,size,state,counters FROM sources"
        ).fetchall()
        for row in sources:
            for key, value in json.loads(row["counters"]).items():
                coverage[key] += value
        return {
            "available": True,
            "updated_at": metadata["updated_at"],
            "files": len(sources),
            "missing_files": sum(row["state"] == "missing" for row in sources),
            "pending_partial_files": sum(
                row["offset"] < row["size"] for row in sources
            ),
            "projects": len(json.loads(metadata["projects"])),
            "turns": connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0],
            "memories": connection.execute("SELECT COUNT(*) FROM memories").fetchone()[
                0
            ],
            **coverage,
        }


def selected_project(metadata: dict[str, str], project: Path) -> str:
    """Resolve a working subdirectory within the existing approved scope."""
    requested = project.expanduser().resolve()
    for root in sorted(json.loads(metadata["projects"]), key=len, reverse=True):
        if requested.is_relative_to(Path(root)) and (
            root != metadata["home"] or requested == Path(root)
        ):
            return str(root)
    raise ValueError("Project is outside the indexed scope")


def search(
    database: Path,
    query: str,
    *,
    project: Path,
    limit: int = 5,
    max_chars: int = 6000,
    excerpts: bool = False,
    match: Literal["all", "any"] = "all",
    role: Literal["all", "user", "assistant"] = "all",
) -> dict[str, Any]:
    """Rank by BM25; cap output and remove duplicate passages at retrieval time."""
    words = re.findall(r"\w+", query)
    if (
        not words
        or len(words) > 30
        or not 1 <= limit <= 20
        or not 500 <= max_chars <= 16000
        or match not in {"all", "any"}
        or role not in {"all", "user", "assistant"}
    ):
        raise ValueError("Invalid search limits or query")
    fts = (" AND " if match == "all" else " OR ").join(f'"{word}"' for word in words)
    with closing(open_history(database)) as connection:
        metadata = verify(connection)
        project_name = selected_project(metadata, project)
        rows = connection.execute(
            """
            SELECT t.id,t.role,t.provider,t.timestamp,c.part,c.text
            FROM chunks c JOIN turns t ON t.id=c.turn_id
            WHERE chunks MATCH ? AND t.project=? AND (?='all' OR t.role=?)
            ORDER BY bm25(chunks),t.timestamp DESC LIMIT 100
        """,
            (fts, project_name, role, role),
        ).fetchall()
        matches: list[dict[str, Any]] = []
        seen: set[str] = set()
        used = 0
        for row in rows:
            identity = digest(re.sub(r"\s+", " ", row["text"]).strip().encode())
            if identity in seen:
                continue
            seen.add(identity)
            item = {
                key: row[key] for key in ("id", "role", "provider", "timestamp", "part")
            }
            item.update(locator(connection, row["id"]))
            if excerpts:
                item["excerpt"] = row["text"]
            size = len(json.dumps(item, ensure_ascii=True))
            if used + size > max_chars:
                continue
            matches.append(item)
            used += size
            if len(matches) == limit:
                break
    return {
        "matches": matches,
        "returned_chars": used,
        "budget_chars": max_chars,
        "limitation": "Character budget, not an exact token count. User text may be a proposal; assistant text is unverified.",
    }


def read_turn(database: Path, identifier: str, *, part: int = 0) -> dict[str, Any]:
    """Read one bounded cached passage and report original-source freshness."""
    if not re.fullmatch(r"[a-f0-9]{64}", identifier) or part < 0:
        raise ValueError("Invalid turn locator")
    with closing(open_history(database)) as connection:
        verify(connection)
        row = connection.execute(
            "SELECT role,provider,timestamp,text FROM turns WHERE id=?", (identifier,)
        ).fetchone()
        if row is None:
            raise ValueError("Unknown turn")
        result = {key: row[key] for key in ("role", "provider", "timestamp")}
        result.update(locator(connection, identifier))
        result["text"] = row["text"][part * CHUNK_CHARS : (part + 1) * CHUNK_CHARS]
        result["part"] = part
        result["parts"] = (len(row["text"]) + CHUNK_CHARS - 1) // CHUNK_CHARS
    return result


def remember(
    database: Path,
    *,
    project: Path,
    kind: str,
    text: str,
    turn_id: str,
    confirmed: bool = False,
    supersedes: str | None = None,
) -> dict[str, str]:
    """Record reviewed memory with provenance; confirmation is always explicit."""
    if kind not in KINDS or not text.strip() or len(text) > 1000:
        raise ValueError("Invalid memory kind or length")
    project_name = str(project.expanduser().resolve())
    text = redact(text)
    identifier = digest(
        json.dumps([project_name, kind, text, turn_id, confirmed, supersedes]).encode()
    )
    with closing(open_history(database, writable=True)) as connection, connection:
        verify(connection)
        source = connection.execute(
            "SELECT role,project FROM turns WHERE id=?", (turn_id,)
        ).fetchone()
        if (
            source is None
            or source["project"] != project_name
            or (confirmed and source["role"] != "user")
        ):
            raise ValueError(
                "Confirmed memories require a user source in the same project"
            )
        if confirmed and locator(connection, turn_id)["source_status"] != "current":
            raise ValueError("Confirm only after reviewing a current original source")
        if supersedes:
            previous = connection.execute(
                "SELECT project FROM memories WHERE id=?", (supersedes,)
            ).fetchone()
            if previous is None or previous["project"] != project_name:
                raise ValueError("Superseded memory must belong to the same project")
        connection.execute(
            "INSERT OR IGNORE INTO memories VALUES (?,?,?,?,?,?,?,?)",
            (
                identifier,
                project_name,
                kind,
                "confirmed" if confirmed else "candidate",
                text,
                turn_id,
                supersedes,
                datetime.now(UTC).isoformat(),
            ),
        )
    return {"id": identifier, "status": "confirmed" if confirmed else "candidate"}


def briefing(database: Path, project: Path, *, max_chars: int = 6000) -> dict[str, Any]:
    """Prioritize reviewed memories, then offer clearly labeled recent user turns."""
    if not 500 <= max_chars <= 16000:
        raise ValueError("Invalid briefing budget")
    with closing(open_history(database)) as connection:
        metadata = verify(connection)
        project_name = selected_project(metadata, project)
        rows = connection.execute(
            """
            SELECT m.* FROM memories m WHERE m.project=? AND NOT EXISTS
              (SELECT 1 FROM memories n WHERE n.supersedes=m.id AND n.status='confirmed')
            ORDER BY CASE m.status WHEN 'confirmed' THEN 0 ELSE 1 END,m.created_at DESC LIMIT 30
        """,
            (project_name,),
        ).fetchall()
        memories = []
        recent = []
        used = 0
        for row in rows:
            item = {
                key: row[key] for key in ("id", "kind", "status", "text", "turn_id")
            }
            item.update(locator(connection, row["turn_id"]))
            size = len(json.dumps(item, ensure_ascii=True))
            if used + size <= max_chars:
                memories.append(item)
                used += size
        turns = connection.execute(
            "SELECT id,timestamp,text FROM turns WHERE project=? AND role='user' ORDER BY timestamp DESC LIMIT 30",
            (project_name,),
        ).fetchall()
        seen = set()
        for row in turns:
            text = row["text"][:700]
            if text in seen:
                continue
            seen.add(text)
            item = {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "text": text,
                "status": "unreviewed_user_turn",
            }
            size = len(json.dumps(item, ensure_ascii=True))
            if used + size <= max_chars:
                recent.append(item)
                used += size
            if len(recent) == 3:
                break
    return {
        "memories": memories,
        "recent_user_turns": recent,
        "updated_at": metadata["updated_at"],
        "returned_chars": used,
        "budget_chars": max_chars,
        "limitation": "Recent turns are activity, not accepted decisions. Confirmed memory is reviewed history, not proof of current implementation.",
    }


def main() -> int:
    """Provide local write commands and bounded read commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path.home() / ".local/share/agents-toolkit/history.sqlite",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index")
    index.add_argument("--home", type=Path, default=Path.home())
    index.add_argument("--project", type=Path, action="append", required=True)
    index.add_argument("--max-files", type=int)
    commands.add_parser("status")
    find = commands.add_parser("search")
    find.add_argument("query")
    find.add_argument("--project", type=Path, required=True)
    find.add_argument("--excerpts", action="store_true")
    find.add_argument("--match", choices=["all", "any"], default="all")
    find.add_argument("--role", choices=["all", "user", "assistant"], default="all")
    find.add_argument("--max-chars", type=int, default=6000)
    read = commands.add_parser("read")
    read.add_argument("id")
    read.add_argument("--part", type=int, default=0)
    brief = commands.add_parser("brief")
    brief.add_argument("--project", type=Path, required=True)
    brief.add_argument("--max-chars", type=int, default=6000)
    memory = commands.add_parser("remember")
    memory.add_argument("--project", type=Path, required=True)
    memory.add_argument("--kind", choices=sorted(KINDS), required=True)
    memory.add_argument("--text", required=True)
    memory.add_argument("--turn-id", required=True)
    memory.add_argument("--confirmed", action="store_true")
    memory.add_argument("--supersedes")
    args = parser.parse_args()
    try:
        match args.command:
            case "index":
                if args.max_files is not None and args.max_files < 1:
                    raise ValueError("max-files must be positive")
                result = ingest(
                    args.db, args.home, args.project, max_files=args.max_files
                )
            case "status":
                result = status(args.db)
            case "search":
                result = search(
                    args.db,
                    args.query,
                    project=args.project,
                    excerpts=args.excerpts,
                    match=args.match,
                    role=args.role,
                    max_chars=args.max_chars,
                )
            case "read":
                result = read_turn(args.db, args.id, part=args.part)
            case "brief":
                result = briefing(args.db, args.project, max_chars=args.max_chars)
            case "remember":
                result = remember(
                    args.db,
                    project=args.project,
                    kind=args.kind,
                    text=args.text,
                    turn_id=args.turn_id,
                    confirmed=args.confirmed,
                    supersedes=args.supersedes,
                )
            case _:
                raise ValueError("Unknown command")
    except (OSError, ValueError, sqlite3.Error) as error:
        print(
            f"History operation failed ({type(error).__name__}); check scope, source access and database.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
