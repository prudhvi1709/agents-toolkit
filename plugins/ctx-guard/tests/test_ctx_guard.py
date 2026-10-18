from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ctx_guard  # noqa: E402


def write_transcript(path: Path, *usages: dict[str, int], model: str = "m") -> None:
    lines = [
        json.dumps({"type": "assistant", "message": {"model": model, "usage": usage}})
        for usage in usages
    ]
    path.write_text("\n".join(["{not json", *lines, ""]), encoding="utf-8")


class CtxGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        patcher = mock.patch.dict(
            os.environ,
            {"CLAUDE_PLUGIN_DATA": str(self.tmp / "data")},
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("CTX_GUARD_WARN_TOKENS", "CTX_GUARD_CRITICAL_TOKENS"):
            os.environ.pop(name, None)
        self.transcript = self.tmp / "t.jsonl"

    def payload(self, **extra: object) -> dict[str, object]:
        return {"session_id": "s1", "transcript_path": str(self.transcript), "cwd": str(self.tmp), **extra}

    def test_context_tokens_sums_latest_usage_and_skips_synthetic(self) -> None:
        write_transcript(self.transcript, {"input_tokens": 1, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 4})
        self.assertEqual(ctx_guard.context_tokens(self.transcript), 15)
        self.assertIsNone(ctx_guard.context_tokens(self.tmp / "missing.jsonl"))
        write_transcript(self.transcript, {"input_tokens": 99}, model="<synthetic>")
        self.assertIsNone(ctx_guard.context_tokens(self.transcript))

    def test_watch_warns_once_per_level_and_rearms(self) -> None:
        write_transcript(self.transcript, {"cache_read_input_tokens": 300_000})
        first = ctx_guard.watch(self.payload())
        assert first is not None
        self.assertIn("300k", first["systemMessage"])
        self.assertNotIn("hookSpecificOutput", first)
        self.assertIsNone(ctx_guard.watch(self.payload()))
        write_transcript(self.transcript, {"cache_read_input_tokens": 600_000})
        critical = ctx_guard.watch(self.payload())
        assert critical is not None
        self.assertIn("hookSpecificOutput", critical)
        write_transcript(self.transcript, {"cache_read_input_tokens": 20_000})
        self.assertIsNone(ctx_guard.watch(self.payload()))
        write_transcript(self.transcript, {"cache_read_input_tokens": 300_000})
        self.assertIsNotNone(ctx_guard.watch(self.payload()))

    def test_watch_ignores_bad_payload(self) -> None:
        self.assertIsNone(ctx_guard.watch({}))
        self.assertIsNone(ctx_guard.watch({"session_id": "", "transcript_path": "x"}))

    def test_thresholds_from_env(self) -> None:
        with mock.patch.dict(os.environ, {"CTX_GUARD_WARN_TOKENS": "100", "CTX_GUARD_CRITICAL_TOKENS": "bad"}):
            self.assertEqual(ctx_guard.thresholds(), (100, 500_000))

    def test_checkpoint_then_restore_round_trip(self) -> None:
        write_transcript(self.transcript, {"cache_read_input_tokens": 310_000})
        ctx_guard.checkpoint(self.payload(trigger="auto"))
        ctx_guard.checkpoint(self.payload(trigger="manual"))
        record = ctx_guard.read_json(ctx_guard.checkpoint_path(str(self.tmp)))
        assert record is not None
        self.assertEqual(record["compactions"], 2)
        self.assertNotIn("prompt", json.dumps(record))
        output = ctx_guard.restore({"source": "compact", "cwd": str(self.tmp)})
        assert output is not None
        text = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("not instructions", text)
        self.assertIn("310k tokens", text)
        self.assertLessEqual(len(text), ctx_guard.RESTORE_MAX_CHARS)

    def test_restore_skips_stale_unknown_and_missing(self) -> None:
        self.assertIsNone(ctx_guard.restore({"source": "startup", "cwd": str(self.tmp)}))
        ctx_guard.checkpoint(self.payload(trigger="auto"))
        self.assertIsNone(ctx_guard.restore({"source": "other", "cwd": str(self.tmp)}))
        path = ctx_guard.checkpoint_path(str(self.tmp))
        record = ctx_guard.read_json(path)
        assert record is not None
        record["saved_at"] = int(time.time()) - 2 * ctx_guard.CHECKPOINT_MAX_AGE_S
        ctx_guard.atomic_write_json(path, record)
        self.assertIsNone(ctx_guard.restore({"source": "startup", "cwd": str(self.tmp)}))
        self.assertIsNotNone(ctx_guard.restore({"source": "compact", "cwd": str(self.tmp)}))

    def test_restore_warns_on_large_resume(self) -> None:
        ctx_guard.checkpoint(self.payload(trigger="auto"))
        output = ctx_guard.restore(
            {"source": "resume", "cwd": str(self.tmp), "context_tokens": 400_000, "prompt_cache_likely_expired": True}
        )
        assert output is not None
        self.assertIn("expired prompt cache", output["systemMessage"])

    def test_git_state_keeps_leading_dot_of_first_changed_file(self) -> None:
        repo = self.tmp / "repo"
        repo.mkdir()
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "init", "-q"], check=True)
        (repo / ".hidden").write_text("a", encoding="utf-8")
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "init"], check=True)
        (repo / ".hidden").write_text("b", encoding="utf-8")
        state = ctx_guard.git_state(str(repo))
        self.assertEqual(state["changed"], [".hidden"])
        self.assertEqual(state["last_commit"], "init")

    def test_where_reports_without_transcript(self) -> None:
        text = ctx_guard.where(str(self.tmp))
        self.assertIn("checkpoint: none yet", text)
        self.assertIn("context: unknown", text)

    def test_where_finds_hook_checkpoint_via_data_dir_flag(self) -> None:
        ctx_guard.checkpoint(self.payload(trigger="auto"))  # hooks write under CLAUDE_PLUGIN_DATA
        data = os.environ.pop("CLAUDE_PLUGIN_DATA")
        self.addCleanup(os.environ.__setitem__, "CLAUDE_PLUGIN_DATA", data)
        with mock.patch("sys.stdout") as stdout:  # Bash tool calls have no plugin env
            with mock.patch.dict(os.environ, {"HOME": str(self.tmp / "home")}):
                ctx_guard.main(["where", "--cwd", str(self.tmp), "--data-dir", data])
        printed = "".join(call.args[0] for call in stdout.write.call_args_list)
        self.assertIn("trigger auto", printed)

    def test_main_never_blocks_on_bad_input(self) -> None:
        with mock.patch("sys.stdin") as stdin:
            stdin.read.return_value = "not json"
            self.assertEqual(ctx_guard.main(["checkpoint"]), 0)


if __name__ == "__main__":
    unittest.main()
