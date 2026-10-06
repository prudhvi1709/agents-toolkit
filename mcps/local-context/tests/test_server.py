"""Verify bounded retrieval and the actual stdio protocol with synthetic notes."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from mcp.client import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = Path(__file__).resolve().parents[3]
        self.module = load_module(
            self.repository / "mcps/local-context/server.py", "context_server"
        )
        self.search = self.module.load_search_module()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.notes = self.root / "notes"
        self.notes.mkdir()
        self.source = self.notes / "decision.md"
        self.source.write_text(
            "Approved logo uses original asset.\nLater approval needs review.\n",
            encoding="utf-8",
        )
        self.database = self.root / "private/context.sqlite"
        self.search.build_index(self.database, [self.notes])
        self.server = self.module.create_server(self.database)

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self.server.call_tool(name, arguments)
        if result.structured_content is not None:
            return dict(result.structured_content)
        return dict(json.loads(result.content[0].text))

    async def test_scope_freshness_and_read_only_snapshot(self) -> None:
        before = self.database.read_bytes()
        found = await self.call("search_context", {"query": "approved logo"})
        self.assertNotIn("snippet", found["matches"][0])
        read = await self.call(
            "read_context", {"path": str(self.source), "line_count": 1}
        )
        self.assertEqual(read["content"], "Approved logo uses original asset.")
        beyond = await self.call(
            "read_context", {"path": str(self.source), "start_line": 99}
        )
        self.assertEqual(beyond["error"], "line_out_of_range")
        outside = self.root / "private.txt"
        outside.write_text("PRIVATE SECRET", encoding="utf-8")
        rejected = await self.call("read_context", {"path": str(outside)})
        self.assertEqual(rejected["error"], "outside_scope")
        self.source.write_text("Superseding decision", encoding="utf-8")
        stale = await self.call("read_context", {"path": str(self.source)})
        self.assertEqual(stale["error"], "stale_source")
        snippets = await self.call(
            "search_context", {"query": "logo", "snippets": True}
        )
        self.assertNotIn("snippet", snippets["matches"][0])
        self.assertEqual(self.database.read_bytes(), before)

    async def test_symlink_replacement_and_output_limit(self) -> None:
        copy = self.notes / "copy.md"
        copy.write_bytes(self.source.read_bytes())
        self.source.unlink()
        self.source.symlink_to(copy)
        self.assertEqual(
            (await self.call("read_context", {"path": str(self.source)}))["error"],
            "stale_source",
        )
        self.source.unlink()
        self.source.write_text("logo " + "x" * 17000, encoding="utf-8")
        self.search.build_index(self.database, [self.notes])
        self.assertEqual(
            (await self.call("read_context", {"path": str(self.source)}))["error"],
            "response_too_large",
        )

    async def test_missing_index_and_private_error_redaction(self) -> None:
        self.database.unlink()
        status = await self.call("context_status", {})
        self.assertFalse(status["available"])
        result = await self.call("search_context", {"query": "SECRET QUERY"})
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn(str(self.database), json.dumps(result))
        self.assertFalse(self.database.exists())

    async def test_stdio_handshake_tools_and_validation(self) -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[
                str(self.repository / "mcps/local-context/server.py"),
                "--db",
                str(self.database),
            ],
        )
        async with asyncio.timeout(20):
            async with (
                stdio_client(parameters) as (reader, writer),
                ClientSession(reader, writer) as client,
            ):
                await client.initialize()
                tools = await client.list_tools()
                self.assertEqual(
                    {tool.name for tool in tools.tools},
                    {
                        "context_status",
                        "search_context",
                        "read_context",
                        "history_status",
                        "search_history",
                        "read_history",
                        "project_brief",
                    },
                )
                self.assertTrue(
                    all(tool.annotations.read_only_hint for tool in tools.tools)
                )
                status = await client.call_tool("context_status", {})
                self.assertEqual(status.structured_content["indexed_files"], 1)
                found = await client.call_tool("search_context", {"query": "logo"})
                self.assertEqual(len(found.structured_content["matches"]), 1)
                invalid = await client.call_tool(
                    "read_context", {"path": str(self.source), "line_count": 81}
                )
                self.assertTrue(invalid.is_error)


class SetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Path(__file__).resolve().parents[3]
        self.setup = load_module(
            self.repository / "scripts/setup_desktop_context.py", "desktop_setup"
        )
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)

    def test_audit_preservation_idempotence_and_package_contents(self) -> None:
        path = (
            self.home / "Library/Application Support/Claude/claude_desktop_config.json"
        )
        path.parent.mkdir(parents=True)
        original = {
            "preferences": {"example": True},
            "mcpServers": {"existing": {"command": "example"}},
        }
        path.write_text(json.dumps(original), encoding="utf-8")
        self.setup.prepare(self.repository, self.home)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)
        self.setup.prepare(self.repository, self.home, apply=True)
        updated = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(updated["preferences"], original["preferences"])
        self.assertEqual(
            updated["mcpServers"]["existing"], original["mcpServers"]["existing"]
        )
        self.assertEqual(
            self.setup.prepare(self.repository, self.home)["changed_files"], 0
        )
        self.assertFalse(
            (self.home / ".local/share/agents-toolkit/context.sqlite").exists()
        )
        import zipfile

        with zipfile.ZipFile(
            self.home
            / ".local/share/agents-toolkit/desktop-context/local-context-search.zip"
        ) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    "local-context-search/SKILL.md",
                    "local-context-search/scripts/context_search.py",
                    "local-context-search/scripts/history_search.py",
                    "local-context-search/references/history-memory.md",
                },
            )

    def test_conflicting_server_and_invalid_config_fail_without_writes(self) -> None:
        path = (
            self.home / "Library/Application Support/Claude/claude_desktop_config.json"
        )
        path.parent.mkdir(parents=True)
        original = '{"mcpServers": {"local-context": {"command": "different"}}}'
        path.write_text(original, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.setup.prepare(self.repository, self.home, apply=True)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        path.write_text('{"preferences": {}, "preferences": {}}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.setup.prepare(self.repository, self.home, apply=True)
        self.assertFalse((self.home / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
