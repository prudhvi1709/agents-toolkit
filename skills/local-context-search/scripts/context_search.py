#!/usr/bin/env python3
"""Search an explicitly scoped, private SQLite snapshot of local text notes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_BYTES = 2 * 1024 * 1024
CHUNK_LINES = 80
EXCLUDED_DIRS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__", "secrets", "credentials"})
SCHEMA_VERSION = "1"


def verify_database(connection: sqlite3.Connection) -> dict[str, str]:
    """Refuse unrelated or unsupported databases before using them."""
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    if metadata.get("application") != "agents-toolkit-context" or metadata.get("version") != SCHEMA_VERSION:
        raise ValueError("Not a supported agents-toolkit context index")
    if not {"roots", "built_at"}.issubset(metadata):
        raise ValueError("Incomplete context index metadata")
    roots = json.loads(metadata["roots"])
    if not isinstance(roots, list) or not roots or any(not isinstance(root, str) or not Path(root).is_absolute() for root in roots):
        raise ValueError("Invalid context index roots")
    return metadata


def open_database(path: Path) -> sqlite3.Connection:
    """Open read-only without silently creating a missing index."""
    if path.is_symlink():
        raise ValueError("The database path must not be a symlink")
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def check_destination(path: Path) -> None:
    """Keep private index files out of repositories and preserve foreign data."""
    if path.is_symlink():
        raise ValueError("The database path must not be a symlink")
    if any((parent / ".git").exists() for parent in path.resolve().parents):
        raise ValueError("Keep the private index outside a Git checkout")
    if path.exists():
        connection = open_database(path)
        try:
            verify_database(connection)
        finally:
            connection.close()


def normalize_roots(roots: list[Path]) -> list[Path]:
    """Require explicit existing directories and remove duplicate roots."""
    normalized = sorted({root.expanduser().resolve(strict=True) for root in roots})
    if not normalized or any(not root.is_dir() for root in normalized):
        raise ValueError("Supply at least one existing note directory with --root")
    return normalized


def build_index(database: Path, roots: list[Path]) -> dict[str, Any]:
    """Build a complete snapshot in a temporary file, then replace atomically."""
    selected = normalize_roots(roots)
    database = database.expanduser()
    check_destination(database)
    database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".context-", suffix=".sqlite", dir=database.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    counts = {"indexed_files": 0, "chunks": 0, "skipped_symlinks": 0, "skipped_large_files": 0}
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript("""
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE documents (id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, digest TEXT NOT NULL);
            CREATE VIRTUAL TABLE chunks USING fts5(content, document_id UNINDEXED, start_line UNINDEXED, end_line UNINDEXED);
        """)
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", [
            ("application", "agents-toolkit-context"), ("version", SCHEMA_VERSION),
            ("roots", json.dumps([str(root) for root in selected])),
            ("built_at", datetime.now(UTC).isoformat()),
        ])
        seen: set[Path] = set()
        # Full rebuild is intentional for small note collections. If this becomes
        # expensive, add a content-hash incremental updater with deletion tracking.
        for root in selected:
            def walk_error(error: OSError) -> None:
                raise error

            for folder, directories, filenames in root.walk(on_error=walk_error, follow_symlinks=False):
                directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
                for name in sorted(filenames):
                    path = folder / name
                    if path.is_symlink():
                        counts["skipped_symlinks"] += 1
                        continue
                    if path.suffix.lower() not in {".md", ".txt"} or not path.is_file():
                        continue
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(root):
                        raise ValueError("A note escaped its selected root")
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    if path.stat().st_size > MAX_BYTES:
                        counts["skipped_large_files"] += 1
                        continue
                    with path.open("rb") as handle:
                        data = handle.read(MAX_BYTES + 1)
                    if len(data) > MAX_BYTES:
                        counts["skipped_large_files"] += 1
                        continue
                    lines = data.decode("utf-8").splitlines()
                    cursor = connection.execute("INSERT INTO documents(path, digest) VALUES (?, ?)",
                                                (str(resolved), hashlib.sha256(data).hexdigest()))
                    for offset in range(0, len(lines), CHUNK_LINES):
                        part = lines[offset:offset + CHUNK_LINES]
                        connection.execute("INSERT INTO chunks VALUES (?, ?, ?, ?)",
                                           ("\n".join(part), cursor.lastrowid, offset + 1, offset + len(part)))
                        counts["chunks"] += 1
                    counts["indexed_files"] += 1
        connection.commit()
        connection.close()
        os.replace(temporary, database)
    finally:
        connection.close()
        temporary.unlink(missing_ok=True)
    return {"roots": len(selected), **counts, "snapshot": "replaced"}


def source_status(path: Path, digest: str, roots: list[Path]) -> str:
    """Check original bytes and scope before declaring a locator current."""
    try:
        resolved = path.resolve(strict=True)
        if not any(resolved.is_relative_to(root) for root in roots):
            return "outside_scope"
        if path.stat().st_size > MAX_BYTES:
            return "changed"
        with path.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        return "current" if hashlib.sha256(data).hexdigest() == digest else "changed"
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"


def search_index(database: Path, query: str, *, limit: int = 10, snippets: bool = False) -> dict[str, Any]:
    """AND-match literal words and return source locators, optionally excerpts."""
    words = re.findall(r"\w+", query)
    if not words or not 1 <= limit <= 50:
        raise ValueError("Use a nonempty word query and a limit between 1 and 50")
    fts_query = " AND ".join(f'"{word}"' for word in words)
    connection = open_database(database.expanduser())
    try:
        metadata = verify_database(connection)
        roots = [Path(root) for root in json.loads(metadata["roots"])]
        rows = connection.execute("""
            SELECT d.path, d.digest, c.start_line, c.end_line,
                   snippet(chunks, 0, '[', ']', '...', 24)
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE chunks MATCH ? ORDER BY bm25(chunks), d.path, c.start_line LIMIT ?
        """, (fts_query, limit)).fetchall()
    finally:
        connection.close()
    matches = []
    statuses: dict[str, str] = {}
    for path, digest, start, end, excerpt in rows:
        if path not in statuses:
            statuses[path] = source_status(Path(path), digest, roots)
        match = {"path": path, "start_line": int(start), "end_line": int(end), "source_status": statuses[path]}
        if snippets and statuses[path] == "current":
            match["snippet"] = excerpt
        matches.append(match)
    return {"built_at": metadata["built_at"], "matches": matches,
            "limitation": "Matches are candidates; read original sources and check superseding decisions."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    default_database = Path.home() / ".local/share/agents-toolkit/context.sqlite"
    rebuild = commands.add_parser("rebuild", help="Replace the snapshot using exactly the selected roots")
    rebuild.add_argument("--root", type=Path, action="append", required=True)
    rebuild.add_argument("--db", type=Path, default=default_database)
    search = commands.add_parser("search", help="Return source-linked candidates")
    search.add_argument("query")
    search.add_argument("--db", type=Path, default=default_database)
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--snippets", action="store_true")
    args = parser.parse_args()
    try:
        result = (build_index(args.db, args.root) if args.command == "rebuild" else
                  search_index(args.db, args.query, limit=args.limit, snippets=args.snippets))
    except (OSError, UnicodeError, ValueError, sqlite3.Error) as error:
        # Do not echo exception messages: SQLite and decoding errors can include
        # private source/query text. The error class distinguishes failure kinds.
        print(f"Context search failed ({type(error).__name__}); check roots, UTF-8 files, index and FTS5 support.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
