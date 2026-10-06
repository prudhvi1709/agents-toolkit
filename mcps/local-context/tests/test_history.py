"""Exercise incremental history indexing with synthetic provider records."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch


class HistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        path = (
            Path(__file__).resolve().parents[3]
            / "skills/local-context-search/scripts/history_search.py"
        )
        spec = importlib.util.spec_from_file_location("history_search_test", path)
        assert spec is not None and spec.loader is not None
        self.history = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.history)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.project = self.home / "project"
        self.project.mkdir()
        self.database = self.home / "private/history.sqlite"
        self.claude = self.home / ".claude/projects/project/a.jsonl"
        self.claude.parent.mkdir(parents=True)
        self.codex = self.home / ".codex/sessions/a.jsonl"
        self.codex.parent.mkdir(parents=True)

    def user(
        self, text: str, identifier: str = "u1", *, project: Path | None = None
    ) -> dict:
        return {
            "type": "user",
            "sessionId": "s1",
            "uuid": identifier,
            "cwd": str(project or self.project),
            "timestamp": "2026-10-06T12:00:00Z",
            "message": {"content": text},
        }

    def write(self, path: Path, records: list[dict], *, append: bool = False) -> None:
        with path.open("a" if append else "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

    def index(self) -> dict:
        return self.history.ingest(self.database, self.home, [self.project])

    def find(self, query: str, **kwargs: object) -> dict:
        return self.history.search(self.database, query, project=self.project, **kwargs)

    def test_home_history_does_not_grant_new_projects_and_deleted_paths_work(
        self,
    ) -> None:
        self.write(self.claude, [self.user("Home requirement", project=self.home)])
        self.history.ingest(self.database, self.home, [self.home, self.project])
        outside = self.home / "new-unregistered-project"
        outside.mkdir()
        self.write(
            self.claude,
            [self.user("Never adopt this new scope", "u2", project=outside)],
            append=True,
        )
        self.history.ingest(self.database, self.home, [self.home, self.project])
        with self.assertRaises(ValueError):
            self.history.search(self.database, "scope", project=outside)
        self.assertEqual(
            self.history.search(self.database, "adopt", project=self.home)["matches"],
            [],
        )
        self.project.rmdir()
        self.history.ingest(self.database, self.home, [self.home, self.project])
        with self.assertRaises(ValueError):
            self.history.ingest(
                self.home / "relative.sqlite", self.home, [Path("relative")]
            )

    def test_both_providers_source_links_privacy_and_no_tool_output(self) -> None:
        self.write(
            self.claude,
            [
                self.user("Preserve original brand fonts api_key=SECRET123"),
                {
                    "type": "assistant",
                    "sessionId": "s1",
                    "cwd": str(self.project),
                    "message": {
                        "content": [
                            {"type": "thinking", "thinking": "PRIVATE REASONING"},
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "input": {"command": "PRIVATE COMMAND"},
                            },
                            {
                                "type": "text",
                                "text": "Font proposal remains unverified.",
                            },
                        ]
                    },
                },
                {
                    "type": "user",
                    "cwd": str(self.project),
                    "message": {
                        "content": [
                            {"type": "tool_result", "content": "PRIVATE OUTPUT"}
                        ]
                    },
                },
            ],
        )
        self.write(
            self.codex,
            [
                {
                    "type": "session_meta",
                    "payload": {"id": "c1", "cwd": str(self.project)},
                },
                {
                    "type": "response_item",
                    "timestamp": "2026-10-06T13:00:00Z",
                    "payload": {
                        "id": "c-u1",
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Use bounded context retrieval",
                            }
                        ],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "output": "PRIVATE OUTPUT",
                    },
                },
            ],
        )
        result = self.index()
        self.assertEqual(result["turns_by_provider"], {"claude": 2, "codex": 1})
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)
        match = self.find("brand fonts")["matches"][0]
        self.assertNotIn("excerpt", match)
        source = self.history.read_turn(self.database, match["id"])
        self.assertEqual(source["source_status"], "current")
        self.assertNotIn("SECRET123", source["text"])
        for term in ["PRIVATE", "SECRET123"]:
            self.assertEqual(self.find(term)["matches"], [])
        self.assertEqual(len(self.find("bounded retrieval")["matches"]), 1)
        user_matches = self.find("fonts", role="user")["matches"]
        self.assertTrue(all(item["role"] == "user" for item in user_matches))
        subdirectory = self.project / "nested"
        subdirectory.mkdir()
        self.assertEqual(
            len(
                self.history.search(self.database, "brand fonts", project=subdirectory)[
                    "matches"
                ]
            ),
            1,
        )
        with self.assertRaises(ValueError):
            self.history.search(
                self.database, "fonts", project=self.home / "unapproved"
            )

    def test_append_resume_partial_record_and_replayed_dedup(self) -> None:
        record = self.user("approved fonts")
        self.write(self.claude, [record])
        self.index()
        self.write(
            self.claude, [record, self.user("bounded context", "u2")], append=True
        )
        with self.claude.open("ab") as handle:
            handle.write(json.dumps(self.user("partial message", "u3")).encode())
        self.index()
        self.assertEqual(self.history.status(self.database)["turns"], 2)
        self.assertEqual(self.history.status(self.database)["pending_partial_files"], 1)
        with self.claude.open("ab") as handle:
            handle.write(b"\n")
        self.index()
        self.assertEqual(self.history.status(self.database)["turns"], 3)
        with patch.object(
            self.history.Envelope,
            "model_validate_json",
            side_effect=AssertionError("unchanged files must not be parsed"),
        ):
            self.assertEqual(self.index()["updated"], 0)

    def test_rewrite_truncation_and_cached_source_status(self) -> None:
        self.write(self.claude, [self.user("first decision")])
        self.index()
        old = self.find("first")["matches"][0]["id"]
        self.write(self.claude, [self.user("next decision", "u2")])
        self.index()
        self.assertEqual(
            self.history.read_turn(self.database, old)["source_status"], "cached_only"
        )
        current = self.find("next")["matches"][0]["id"]
        self.claude.unlink()
        self.index()
        self.assertEqual(self.history.status(self.database)["missing_files"], 1)
        self.assertEqual(
            self.history.read_turn(self.database, current)["source_status"],
            "cached_only",
        )

    def test_project_isolation_and_scope_change_refused(self) -> None:
        other = self.home / "other"
        other.mkdir()
        self.write(
            self.claude,
            [
                self.user("private unrelated", project=other),
                self.user("allowed project"),
            ],
        )
        self.index()
        self.assertEqual(self.find("unrelated")["matches"], [])
        with self.assertRaises(ValueError):
            self.history.ingest(self.database, self.home, [self.project, other])

    def test_transaction_failure_rolls_back_cursor_and_evidence(self) -> None:
        self.write(self.claude, [self.user("original")])
        self.index()
        self.write(self.claude, [self.user("added", "u2")], append=True)
        original = self.history.extract_text
        with patch.object(
            self.history, "extract_text", side_effect=ValueError("private error")
        ):
            self.assertEqual(self.index()["failed"], 1)
        self.assertEqual(self.find("added")["matches"], [])
        self.assertIs(self.history.extract_text, original)
        self.index()
        self.assertEqual(len(self.find("added")["matches"]), 1)

    def test_budget_dedup_and_literal_queries(self) -> None:
        self.write(
            self.claude,
            [
                self.user("approved fonts " * 400),
                self.user("approved fonts " * 400, "u2"),
            ],
        )
        self.index()
        result = self.find("approved fonts", excerpts=True, max_chars=4000)
        self.assertLessEqual(result["returned_chars"], 4000)
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(self.find('approved " OR unrelated')["matches"], [])
        with self.assertRaises(ValueError):
            self.find("fonts", max_chars=1)

    def test_reviewed_memory_and_supersession_require_user_source(self) -> None:
        self.write(
            self.claude,
            [
                self.user("Use original fonts", "u1"),
                self.user("Use updated approved fonts", "u2"),
                {
                    "type": "assistant",
                    "cwd": str(self.project),
                    "uuid": "a1",
                    "message": {"content": "Maybe use other fonts"},
                },
            ],
        )
        self.index()
        first = self.find("original")["matches"][0]["id"]
        newer = self.find("updated")["matches"][0]["id"]
        assistant = self.find("other")["matches"][0]["id"]
        old = self.history.remember(
            self.database,
            project=self.project,
            kind="decision",
            text="Original fonts",
            turn_id=first,
            confirmed=True,
        )
        self.history.remember(
            self.database,
            project=self.project,
            kind="decision",
            text="Updated fonts",
            turn_id=newer,
            confirmed=True,
            supersedes=old["id"],
        )
        brief = self.history.briefing(self.database, self.project)
        self.assertEqual(
            [item["text"] for item in brief["memories"]], ["Updated fonts"]
        )
        with self.assertRaises(ValueError):
            self.history.remember(
                self.database,
                project=self.project,
                kind="decision",
                text="Assistant claim",
                turn_id=assistant,
                confirmed=True,
            )

    def test_symlinks_foreign_database_and_malformed_records(self) -> None:
        self.write(self.claude, [self.user("safe")])
        with self.claude.open("a", encoding="utf-8") as handle:
            handle.write("{bad json}\n")
        link = self.claude.parent / "link.jsonl"
        link.symlink_to(self.claude)
        result = self.index()
        self.assertEqual(result["symlinks_skipped"], 1)
        self.assertEqual(self.history.status(self.database)["malformed"], 1)
        foreign = self.home / "foreign.sqlite"
        with closing(sqlite3.connect(foreign)) as connection:
            connection.execute("CREATE TABLE foreign_data(secret TEXT)")
            connection.commit()
        with self.assertRaises(ValueError):
            self.history.ingest(foreign, self.home, [self.project])


if __name__ == "__main__":
    unittest.main()
