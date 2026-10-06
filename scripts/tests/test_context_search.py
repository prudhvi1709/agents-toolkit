"""Exercise private indexing and retrieval against temporary synthetic notes."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch


class ContextSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (Path(__file__).resolve().parents[2] /
                       "skills/local-context-search/scripts/context_search.py")
        spec = importlib.util.spec_from_file_location("context_search", self.script)
        assert spec is not None and spec.loader is not None
        self.context = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.context)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.notes = self.root / "notes"
        self.notes.mkdir()
        self.database = self.root / "private/context.sqlite"

    def note(self, name: str, content: str) -> Path:
        path = self.notes / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_locators_lines_private_permissions_and_read_only_search(self) -> None:
        path = self.note("decision.md", "\n".join(["padding"] * 80 + ["Approved logo uses the original asset."]))
        self.context.build_index(self.database, [self.notes])
        before = self.database.read_bytes()
        result = self.context.search_index(self.database, "approved logo")
        match = result["matches"][0]
        self.assertEqual(match["path"], str(path.resolve()))
        self.assertEqual((match["start_line"], match["end_line"]), (81, 81))
        self.assertEqual(match["source_status"], "current")
        self.assertNotIn("snippet", match)
        self.assertNotIn("original asset", json.dumps(result))
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.database.read_bytes(), before)

    def test_changed_and_missing_sources_are_not_presented_as_current(self) -> None:
        path = self.note("decision.md", "Approved logo original asset")
        self.context.build_index(self.database, [self.notes])
        self.assertIn("snippet", self.context.search_index(self.database, "logo", snippets=True)["matches"][0])
        path.write_text("Updated decision", encoding="utf-8")
        match = self.context.search_index(self.database, "logo", snippets=True)["matches"][0]
        self.assertEqual(match["source_status"], "changed")
        self.assertNotIn("snippet", match)
        path.unlink()
        self.assertEqual(self.context.search_index(self.database, "logo")["matches"][0]["source_status"], "missing")

    def test_rebuild_tracks_deletions_and_replaces_scope(self) -> None:
        old = self.note("old.md", "old decision")
        self.context.build_index(self.database, [self.notes])
        old.unlink()
        self.context.build_index(self.database, [self.notes])
        self.assertEqual(self.context.search_index(self.database, "old")["matches"], [])
        other = self.root / "other"
        other.mkdir()
        (other / "new.txt").write_text("new decision", encoding="utf-8")
        self.context.build_index(self.database, [other])
        self.assertEqual(len(self.context.search_index(self.database, "new")["matches"]), 1)

    def test_symlinks_excluded_directories_and_large_files_are_skipped(self) -> None:
        outside = self.root / "outside.md"
        outside.write_text("secret outside", encoding="utf-8")
        (self.notes / "link.md").symlink_to(outside)
        (self.notes / "linked-folder").symlink_to(self.root / "private", target_is_directory=True)
        self.note(".git/internal.md", "secret internal")
        self.note("node_modules/internal.md", "secret internal")
        self.note("large.txt", "x" * (self.context.MAX_BYTES + 1))
        self.note("safe.md", "approved note")
        result = self.context.build_index(self.database, [self.notes, self.notes])
        self.assertEqual(result["indexed_files"], 1)
        self.assertEqual(result["skipped_large_files"], 1)
        self.assertGreaterEqual(result["skipped_symlinks"], 1)
        self.assertEqual(self.context.search_index(self.database, "secret")["matches"], [])

    def test_failed_read_preserves_previous_snapshot_and_cleans_temporary_file(self) -> None:
        self.note("safe.md", "approved note")
        self.context.build_index(self.database, [self.notes])
        before = self.database.read_bytes()
        (self.notes / "invalid.md").write_bytes(b"\xffPRIVATE-SECRET")
        with self.assertRaises(UnicodeError):
            self.context.build_index(self.database, [self.notes])
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.database.parent.glob(".context-*")), [])

    def test_replace_failure_preserves_old_index(self) -> None:
        self.note("safe.md", "approved note")
        self.context.build_index(self.database, [self.notes])
        before = self.database.read_bytes()
        with patch.object(self.context.os, "replace", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                self.context.build_index(self.database, [self.notes])
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.database.parent.glob(".context-*")), [])

    def test_foreign_database_and_repository_destination_are_rejected(self) -> None:
        self.database.parent.mkdir()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE unrelated (id INTEGER)")
            connection.commit()
        before = self.database.read_bytes()
        with self.assertRaises(sqlite3.Error):
            self.context.build_index(self.database, [self.notes])
        self.assertEqual(self.database.read_bytes(), before)
        (self.notes / ".git").mkdir()
        with self.assertRaises(ValueError):
            self.context.build_index(self.notes / "context.sqlite", [self.notes])

    def test_missing_index_and_invalid_arguments_do_not_create_a_database(self) -> None:
        with self.assertRaises(sqlite3.Error):
            self.context.search_index(self.database, "decision")
        with self.assertRaises(ValueError):
            self.context.search_index(self.database, "---")
        with self.assertRaises(ValueError):
            self.context.search_index(self.database, "decision", limit=100)
        self.assertFalse(self.database.exists())

    def test_symlink_retarget_after_indexing_is_outside_scope(self) -> None:
        path = self.note("decision.md", "approved logo")
        self.context.build_index(self.database, [self.notes])
        outside = self.root / "outside.md"
        outside.write_text("private outside", encoding="utf-8")
        path.unlink()
        path.symlink_to(outside)
        match = self.context.search_index(self.database, "logo", snippets=True)["matches"][0]
        self.assertEqual(match["source_status"], "outside_scope")
        self.assertNotIn("snippet", match)

    def test_literal_query_and_cli_do_not_leak_invalid_source_text(self) -> None:
        self.note("safe.md", "approved logo")
        self.context.build_index(self.database, [self.notes])
        self.assertEqual(self.context.search_index(self.database, "approved OR missing")["matches"], [])
        (self.notes / "invalid.md").write_bytes(b"\xffPRIVATE-SECRET")
        result = subprocess.run([sys.executable, str(self.script), "rebuild", "--root", str(self.notes),
                                 "--db", str(self.database)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("PRIVATE-SECRET", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
