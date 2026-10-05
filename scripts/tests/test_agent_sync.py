"""Exercise configuration safety using temporary, credential-free fixtures."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch


class AgentSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "agent_sync", Path(__file__).resolve().parents[1] / "agent-sync.py"
        )
        assert spec is not None and spec.loader is not None
        self.sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.sync)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, filename in {
            "MANIFEST": "mcps.json",
            "HOOK_MANIFEST": "hook-manifest.json",
            "CLAUDE_JSON": "claude.json",
            "DESKTOP_JSON": "desktop.json",
            "CODEX_CONFIG": "codex.toml",
            "CLAUDE_SETTINGS": "claude-settings.json",
            "CODEX_HOOKS": "codex-hooks.json",
        }.items():
            setattr(self.sync, name, self.root / filename)
        self.sync.ROOT = self.root
        self.sync.CLAUDE_SKILLS = self.root / "claude-skills"
        self.sync.CODEX_SKILLS = self.root / "codex-skills"
        self.manifest = {
            "version": 1,
            "servers": {
                "example": {
                    "claude_code": {"command": "example", "args": ["serve"]},
                    "claude_desktop": {"url": "https://example.test/mcp"},
                    "codex": {"command": "example", "args": ["serve"]},
                }
            },
        }
        self.sync.MANIFEST.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.sync.HOOK_MANIFEST.write_text(
            '{"version": 1, "hooks": {}}', encoding="utf-8"
        )

    def test_json_rejects_malformed_duplicates_and_nonfinite_values(self) -> None:
        for text in ('{', '[]', '{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}', '{"x":NaN}'):
            with self.subTest(text=text):
                self.sync.CLAUDE_JSON.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.sync.sync_json_config(self.sync.CLAUDE_JSON, "claude_code", True)
                self.assertEqual(self.sync.CLAUDE_JSON.read_text(encoding="utf-8"), text)

    def test_invalid_mcp_container_is_not_overwritten(self) -> None:
        text = '{"mcpServers": []}'
        self.sync.CLAUDE_JSON.write_text(text, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.sync.sync_json_config(self.sync.CLAUDE_JSON, "claude_code", True)
        self.assertEqual(self.sync.CLAUDE_JSON.read_text(encoding="utf-8"), text)

    def test_json_preserves_unmanaged_provider_settings(self) -> None:
        existing = {"preferences": {"theme": "dark"}, "mcpServers": {"other": {"url": "https://other.test", "headers": {"custom": "fixture"}}}}
        self.sync.CLAUDE_JSON.write_text(json.dumps(existing), encoding="utf-8")
        self.sync.sync_json_config(self.sync.CLAUDE_JSON, "claude_code", True)
        result = json.loads(self.sync.CLAUDE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(result["preferences"], existing["preferences"])
        self.assertEqual(result["mcpServers"]["other"], existing["mcpServers"]["other"])

    def test_invalid_manifest_transport_is_rejected(self) -> None:
        for config in ({"command": "x", "url": "https://example.test"}, {"command": ""}, {"command": "x", "args": "serve"}, {"command": "x", "args": [1]}, "invalid"):
            with self.subTest(config=config):
                self.manifest["servers"]["example"]["codex"] = config
                self.sync.MANIFEST.write_text(json.dumps(self.manifest), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.sync.load_manifest()

    def test_codex_preserves_unmanaged_settings_and_is_idempotent(self) -> None:
        existing = 'model = "example-model"\n[mcp_servers.other]\nurl = "https://other.test"\ncustom = "keep"\n'
        self.sync.CODEX_CONFIG.write_text(existing, encoding="utf-8")
        self.sync.sync_codex_config(True)
        first = self.sync.CODEX_CONFIG.read_text(encoding="utf-8")
        parsed = tomllib.loads(first)
        self.assertEqual(parsed["model"], "example-model")
        self.assertEqual(parsed["mcp_servers"]["other"]["custom"], "keep")
        self.sync.sync_codex_config(True)
        self.assertEqual(self.sync.CODEX_CONFIG.read_text(encoding="utf-8"), first)

    def test_unmanaged_codex_collision_is_not_overwritten(self) -> None:
        existing = '[mcp_servers.example]\ncommand = "local"\n'
        self.sync.CODEX_CONFIG.write_text(existing, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "reconcile ownership"):
            self.sync.sync_codex_config(True)
        self.assertEqual(self.sync.CODEX_CONFIG.read_text(encoding="utf-8"), existing)

    def test_managed_block_collision_with_unmanaged_table_is_rejected(self) -> None:
        existing = '[mcp_servers.example]\ncommand = "local"\n' + self.sync.MARKER_START + '\n' + self.sync.MARKER_END + '\n'
        self.sync.CODEX_CONFIG.write_text(existing, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.sync.sync_codex_config(True)
        self.assertEqual(self.sync.CODEX_CONFIG.read_text(encoding="utf-8"), existing)

    def test_invalid_toml_and_markers_leave_original_intact(self) -> None:
        for existing in (
            'model = "unterminated',
            self.sync.MARKER_START + '\n',
            self.sync.MARKER_END + '\n' + self.sync.MARKER_START,
            (self.sync.MARKER_START + '\n' + self.sync.MARKER_END + '\n') * 2,
        ):
            with self.subTest(existing=existing):
                self.sync.CODEX_CONFIG.write_text(existing, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.sync.sync_codex_config(True)
                self.assertEqual(self.sync.CODEX_CONFIG.read_text(encoding="utf-8"), existing)

    def test_server_names_and_arguments_round_trip(self) -> None:
        name = 'example.with space"quote'
        self.manifest["servers"][name] = self.manifest["servers"].pop("example")
        arguments = ['path\\to\\file', 'quote"', 'line\nnext', chr(0x1F600)]
        self.manifest["servers"][name]["codex"]["args"] = arguments
        self.sync.MANIFEST.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.sync.sync_codex_config(True)
        parsed = tomllib.loads(self.sync.CODEX_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(parsed["mcp_servers"][name]["args"], arguments)

    def test_later_codex_conflict_prevents_earlier_client_writes(self) -> None:
        existing = '{"preferences": {"theme": "dark"}}'
        self.sync.CLAUDE_JSON.write_text(existing, encoding="utf-8")
        self.sync.CODEX_CONFIG.write_text('[mcp_servers.example]\ncommand="local"', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.sync.run(True, "all")
        self.assertEqual(self.sync.CLAUDE_JSON.read_text(encoding="utf-8"), existing)
        self.assertFalse(self.sync.DESKTOP_JSON.exists())
        self.assertFalse(self.sync.CLAUDE_SKILLS.exists())

    def test_audit_does_not_create_configs(self) -> None:
        with patch("sys.stdout"):
            self.sync.run(False, "mcps")
        self.assertFalse(self.sync.CLAUDE_JSON.exists())
        self.assertFalse(self.sync.DESKTOP_JSON.exists())
        self.assertFalse(self.sync.CODEX_CONFIG.exists())

    def test_hooks_preserve_unmanaged_handlers(self) -> None:
        data = {"otherSetting": True, "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "other-tool"}]}]}}
        self.sync.CLAUDE_SETTINGS.write_text(json.dumps(data), encoding="utf-8")
        self.sync.sync_hooks(self.sync.CLAUDE_SETTINGS, "claude_code", True)
        self.assertEqual(json.loads(self.sync.CLAUDE_SETTINGS.read_text(encoding="utf-8")), data)

    def test_invalid_hook_groups_are_not_overwritten(self) -> None:
        text = '{"hooks":{"SessionStart":null}}'
        self.sync.CLAUDE_SETTINGS.write_text(text, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.sync.sync_hooks(self.sync.CLAUDE_SETTINGS, "claude_code", True)
        self.assertEqual(self.sync.CLAUDE_SETTINGS.read_text(encoding="utf-8"), text)

    def test_atomic_write_retains_permissions_and_symlink(self) -> None:
        target = self.root / "actual.json"
        target.write_text('{}', encoding="utf-8")
        target.chmod(0o640)
        self.sync.CLAUDE_JSON.symlink_to(target)
        self.sync.sync_json_config(self.sync.CLAUDE_JSON, "claude_code", True)
        self.assertTrue(self.sync.CLAUDE_JSON.is_symlink())
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertIn("example", json.loads(target.read_text(encoding="utf-8"))["mcpServers"])

    def test_failed_replace_keeps_original_and_cleans_temporary(self) -> None:
        target = self.root / "actual.json"
        target.write_text('{}', encoding="utf-8")
        before = set(self.root.iterdir())
        with patch.object(self.sync.os, "replace", side_effect=PermissionError("fixture")):
            with self.assertRaises(PermissionError):
                self.sync.write_config(target, '{"changed":true}')
        self.assertEqual(target.read_text(encoding="utf-8"), '{}')
        self.assertEqual(set(self.root.iterdir()), before)

    def test_diagnostics_do_not_expose_values(self) -> None:
        marker = 'PRIVATE_FIXTURE_VALUE'
        self.sync.CLAUDE_JSON.write_text('{"x":"' + marker + '"', encoding="utf-8")
        with self.assertRaises(ValueError) as raised:
            self.sync.read_json(self.sync.CLAUDE_JSON)
        self.assertNotIn(marker, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
