"""Verify detection boundaries and privacy using synthetic agent logs."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path


class SkillUsageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script_root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("skill_usage", self.script_root / "skill_usage.py")
        assert spec is not None and spec.loader is not None
        self.usage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.usage)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)

    def write_log(self, relative: str, records: list[dict]) -> Path:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        return path

    def claude_call(self, name: str, arguments: dict, *, date: str | None = "2026-10-06T12:00:00Z") -> dict:
        return {"type": "assistant", "sessionId": "private-session", "timestamp": date,
                "message": {"content": [{"type": "tool_use", "name": name, "input": arguments}]}}

    def test_tool_input_detection_excludes_prose_and_examples(self) -> None:
        self.write_log(".claude/projects/example/session.jsonl", [
            {"type": "user", "message": {"content": "$brand-ui-prototyping"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "cat skills/fake/SKILL.md"}]}},
            self.claude_call("Bash", {"command": "echo cat skills/fake/SKILL.md"}),
            self.claude_call("Bash", {"command": "cat <<'EOF'\ncat skills/fake/SKILL.md\nEOF"}),
            self.claude_call("Skill", {"skill": "brand-ui-prototyping", "args": "PRIVATE-SECRET"}),
        ])
        result = self.usage.audit_skill_usage(self.home)
        self.assertEqual([row["skill"] for row in result["skills"]], ["brand-ui-prototyping"])
        rendered = json.dumps(result)
        for private in ("PRIVATE-SECRET", "private-session", str(self.home), "$brand-ui"):
            self.assertNotIn(private, rendered)

    def test_overlapping_evidence_and_repeated_calls_deduplicate_sessions(self) -> None:
        self.write_log(".claude/projects/example/session.jsonl", [
            self.claude_call("Skill", {"skill": "motion"}),
            self.claude_call("Skill", {"skill": "motion"}),
            self.claude_call("Read", {"file_path": "/private/.claude/skills/motion/SKILL.md"}),
        ])
        row = self.usage.audit_skill_usage(self.home)["skills"][0]
        self.assertEqual((row["invoked_sessions"], row["read_requested_sessions"], row["unique_sessions"]), (1, 1, 1))

    def test_codex_direct_and_orchestrated_literal_reads(self) -> None:
        self.write_log(".codex/sessions/example.jsonl", [
            {"type": "session_meta", "payload": {"id": "private-codex-session"}},
            {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command",
                "arguments": json.dumps({"cmd": "cat skills/skill-learning/SKILL.md"})}},
            {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "functions.exec",
                "input": 'await tools.exec_command({cmd:"cat /home/a/.codex/skills/.system/skill-creator/SKILL.md"})'}},
            {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "functions.exec",
                "input": 'await tools.exec_command({"cmd":"cat skills/motion/SKILL.md"})'}},
        ])
        self.assertEqual({row["skill"] for row in self.usage.audit_skill_usage(self.home)["skills"]},
                         {"skill-learning", "skill-creator", "motion"})

    def test_window_excludes_older_and_undated_calls(self) -> None:
        self.write_log(".claude/projects/example/session.jsonl", [
            self.claude_call("Skill", {"skill": "old"}, date="2026-09-01T00:00:00Z"),
            self.claude_call("Skill", {"skill": "undated"}, date=None),
            self.claude_call("Skill", {"skill": "current"}, date="2026-10-06T14:00:00+05:30"),
        ])
        result = self.usage.audit_skill_usage(self.home, since=datetime(2026, 10, 6, tzinfo=UTC))
        self.assertEqual([row["skill"] for row in result["skills"]], ["current"])
        self.assertEqual(result["coverage"]["claude"]["undated_records"], 1)

    def test_malformed_and_unavailable_sources_are_reported(self) -> None:
        path = self.write_log(".claude/projects/example/session.jsonl", [])
        path.write_text('{not json}\n[1]\n', encoding="utf-8")
        result = self.usage.audit_skill_usage(self.home)
        self.assertEqual(result["coverage"]["claude"]["malformed_records"], 2)
        self.assertFalse(result["coverage"]["codex"]["available"])

    def test_since_requires_timezone(self) -> None:
        with self.assertRaises(ValueError):
            self.usage.parse_since("2026-10-06")

    def test_orchestration_command_fields_without_a_tool_request_are_ignored(self) -> None:
        self.assertEqual(self.usage.call_skills("functions.exec", 'text({cmd:"cat skills/fake/SKILL.md"})'), set())

    def test_cli_skills_only_writes_nothing_and_rejects_invalid_window(self) -> None:
        command = [sys.executable, str(self.script_root / "audit_agent_activity.py"), "--home", str(self.home)]
        result = subprocess.run(command + ["--skills-only"], cwd=self.home, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["skills"], [])
        self.assertEqual(list(self.home.iterdir()), [])
        invalid = subprocess.run(command + ["--since", "2026-10-06T00:00:00Z"], cwd=self.home,
                                 capture_output=True, text=True, check=False)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
