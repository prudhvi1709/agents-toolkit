"""Verify generated review ownership, recovery, scope and scheduling."""

import importlib.util
import json
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ObsidianTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "obsidian_test", self.repository / "scripts/obsidian_memory.py"
        )
        assert spec is not None and spec.loader is not None
        self.exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.exporter)
        self.history = self.exporter.load_history(self.repository)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.project = self.home / "project"
        self.project.mkdir()
        self.database = self.home / "private/history.sqlite"
        self.vault = self.home / "vault"
        self.log = self.home / ".claude/projects/project/session.jsonl"
        self.log.parent.mkdir(parents=True)
        self.append("Use original fonts and caf\u00e9 labels", "first")
        self.history.ingest(self.database, self.home, [self.project])
        turn = self.history.search(self.database, "fonts", project=self.project)[
            "matches"
        ][0]
        self.first = self.history.remember(
            self.database,
            project=self.project,
            kind="requirement",
            text="Use original fonts",
            turn_id=turn["id"],
            confirmed=True,
        )

    def append(self, text: str, identifier: str) -> None:
        record = {
            "type": "user",
            "sessionId": "session",
            "uuid": identifier,
            "cwd": str(self.project),
            "timestamp": "2026-10-06T12:00:00Z",
            "message": {"content": text},
        }
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def export(self, *, apply: bool = True) -> dict:
        return self.exporter.export_vault(
            self.repository, self.database, self.vault, apply=apply
        )

    def snapshot(self) -> dict[str, bytes]:
        return {
            str(path.relative_to(self.vault)): path.read_bytes()
            for path in self.vault.rglob("*.md")
        }

    def test_preview_private_graph_and_read_only_index(self) -> None:
        before = self.database.read_bytes()
        preview = self.export(apply=False)
        self.assertFalse(self.vault.exists())
        self.assertGreater(preview["changed_notes"], 0)
        self.export()
        self.assertEqual(self.database.read_bytes(), before)
        notes = self.snapshot()
        self.assertEqual(len(notes), 5)
        self.assertTrue(all(value.isascii() for value in notes.values()))
        self.assertIn(
            b"status: confirmed", notes[f"Memories/memory-{self.first['id']}.md"]
        )
        self.assertTrue(any(b"\\xe9" in content for content in notes.values()))
        self.assertIn(b"[[Projects/", notes["Home.md"])
        self.assertTrue(any(b"[[Evidence/" in value for value in notes.values()))
        self.assertFalse(list(self.vault.rglob("*.jsonl")))
        for path in self.vault.rglob("*.md"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_idempotence_review_preservation_and_conflict_preflight(self) -> None:
        self.export()
        review = self.vault / "Reviews/my correction.md"
        review.write_text("Keep this personal review", encoding="utf-8")
        self.assertEqual(self.export()["changed_notes"], 0)
        self.assertEqual(
            review.read_text(encoding="utf-8"), "Keep this personal review"
        )
        home = self.vault / "Home.md"
        home.write_text("My edited generated home", encoding="utf-8")
        self.append("Another user instruction", "second")
        self.history.ingest(self.database, self.home, [self.project])
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.snapshot(), before)

    def test_interrupted_export_resumes_and_protects_edits(self) -> None:
        original = self.exporter.atomic_write
        written = 0

        def interrupted(path: Path, text: str) -> None:
            nonlocal written
            if path.suffix == ".md":
                written += 1
                if written == 3:
                    raise OSError("simulated interrupted write")
            original(path, text)

        with (
            patch.object(self.exporter, "atomic_write", side_effect=interrupted),
            self.assertRaises(OSError),
        ):
            self.export()
        self.assertTrue((self.vault / ".agent-memory/pending.json").exists())
        edited = next(self.vault.rglob("*.md"))
        generated = edited.read_text(encoding="utf-8")
        edited.write_text("User correction after interruption", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.snapshot(), before)
        edited.write_text(generated, encoding="utf-8")
        self.export()
        self.assertFalse((self.vault / ".agent-memory/pending.json").exists())
        self.assertEqual(self.export()["changed_notes"], 0)

    def test_supersession_retains_both_records_and_stale_sources(self) -> None:
        self.append("Replace original fonts with approved new fonts", "second")
        self.history.ingest(self.database, self.home, [self.project])
        turn = self.history.search(self.database, "Replace", project=self.project)[
            "matches"
        ][0]
        replacement = self.history.remember(
            self.database,
            project=self.project,
            kind="correction",
            text="Use approved new fonts",
            turn_id=turn["id"],
            confirmed=True,
            supersedes=self.first["id"],
        )
        self.export()
        old = self.vault / f"Memories/memory-{self.first['id']}.md"
        new = self.vault / f"Memories/memory-{replacement['id']}.md"
        self.assertIn("active: false", old.read_text(encoding="utf-8"))
        self.assertIn(replacement["id"], old.read_text(encoding="utf-8"))
        self.assertIn(self.first["id"], new.read_text(encoding="utf-8"))
        self.log.unlink()
        self.export()
        self.assertIn("source_status: cached_only", new.read_text(encoding="utf-8"))

    def test_git_symlink_and_unowned_file_refused(self) -> None:
        self.vault.mkdir()
        (self.vault / ".git").mkdir()
        with self.assertRaises(ValueError):
            self.export()
        (self.vault / ".git").rmdir()
        (self.vault / "Home.md").symlink_to(self.log)
        with self.assertRaises(ValueError):
            self.export()
        (self.vault / "Home.md").unlink()
        (self.vault / "Home.md").write_text("Existing personal vault", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(
            (self.vault / "Home.md").read_text(encoding="utf-8"),
            "Existing personal vault",
        )

    def test_refresh_uses_only_persisted_scope(self) -> None:
        other = self.home / "unapproved"
        other.mkdir()
        record = {
            "type": "user",
            "cwd": str(other),
            "uuid": "other",
            "message": {"content": "Unapproved project"},
        }
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        self.exporter.refresh(self.repository, self.database, self.vault, apply=True)
        self.assertEqual(self.history.status(self.database)["projects"], 1)
        self.assertFalse(
            any(b"Unapproved project" in text for text in self.snapshot().values())
        )

    def test_schedule_is_hourly_private_and_preserves_conflicting_jobs(self) -> None:
        args = (self.repository, self.database, self.vault)
        self.exporter.schedule(*args, home=self.home)
        path = (
            self.home
            / "Library/LaunchAgents/local.agents-toolkit.obsidian-memory.plist"
        )
        self.assertFalse(path.exists())
        with patch.object(
            self.exporter.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0),
        ) as run:
            self.exporter.schedule(*args, home=self.home, apply=True)
            self.assertEqual(run.call_count, 1)
        settings = plistlib.loads(path.read_bytes())
        self.assertEqual(settings["StartInterval"], 3600)
        self.assertIn("--offline", settings["ProgramArguments"])
        self.assertEqual(settings["ProgramArguments"][-2:], ["refresh", "--apply"])
        for log in (self.home / ".local/share/agents-toolkit/obsidian-state").glob(
            "*.log"
        ):
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        path.write_text("Existing unrelated schedule", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.exporter.schedule(*args, home=self.home, apply=True)
        self.assertEqual(
            path.read_text(encoding="utf-8"), "Existing unrelated schedule"
        )


if __name__ == "__main__":
    unittest.main()
