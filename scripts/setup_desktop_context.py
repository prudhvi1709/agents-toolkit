#!/usr/bin/env python3
"""Prepare the local-context desktop adapters without indexing or uploading notes."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_sync_helpers(repository: Path) -> Any:
    """Reuse validated JSON parsing and atomic configuration replacement."""
    spec = importlib.util.spec_from_file_location(
        "agent_sync", repository / "scripts/agent-sync.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load configuration helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(repository: Path, home: Path, *, apply: bool = False) -> dict[str, Any]:
    """Merge just this adapter, preserving unrelated client configuration."""
    sync = load_sync_helpers(repository)
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("uv is required; sync the MCP project dependencies first")
    project = repository / "mcps/local-context"
    server = {
        "command": uv,
        "args": [
            "run",
            "--frozen",
            "--offline",
            "--project",
            str(project),
            "python",
            str(project / "server.py"),
        ],
    }
    desktop_config = (
        home / "Library/Application Support/Claude/claude_desktop_config.json"
    )
    marketplace_path = home / ".agents/plugins/marketplace.json"
    plugin = home / ".codex/plugins/local-context"
    state = home / ".local/share/agents-toolkit/desktop-context"
    if any((parent / ".git").exists() for parent in state.resolve().parents):
        raise ValueError("Desktop output must stay outside a Git checkout")
    desktop = sync.read_json(desktop_config)
    servers = desktop.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise TypeError("Claude Desktop mcpServers must be an object")
    if "local-context" in servers and servers["local-context"] != server:
        raise ValueError(
            "An existing local-context server conflicts; reconcile it before setup"
        )
    servers["local-context"] = server
    marketplace = (
        sync.read_json(marketplace_path)
        if marketplace_path.exists()
        else {
            "name": "personal-toolkit",
            "interface": {"displayName": "Personal Toolkit"},
            "plugins": [],
        }
    )
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or any(
        not isinstance(entry, dict) for entry in entries
    ):
        raise ValueError("The personal marketplace must contain a plugins list")
    entry = {
        "name": "local-context",
        "source": {"source": "local", "path": "./.codex/plugins/local-context"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    existing = [item for item in entries if item.get("name") == "local-context"]
    if len(existing) > 1 or (existing and existing[0] != entry):
        raise ValueError(
            "An existing local-context marketplace entry conflicts; reconcile it before setup"
        )
    if not existing:
        entries.append(entry)
    manifest = sync.read_json(repository / "desktop/local-context/plugin.json")
    mcp = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {"local-context": {"type": "stdio", **server}},
    }
    files = {
        desktop_config: json.dumps(desktop, indent=2, ensure_ascii=True) + "\n",
        marketplace_path: json.dumps(marketplace, indent=2, ensure_ascii=True) + "\n",
        plugin / "plugin.json": json.dumps(manifest, indent=2, ensure_ascii=True)
        + "\n",
        plugin / "mcp.json": json.dumps(mcp, indent=2, ensure_ascii=True) + "\n",
    }
    skill = repository / "skills/local-context-search"
    skill_files = (
        "SKILL.md",
        "scripts/context_search.py",
        "scripts/history_search.py",
        "references/history-memory.md",
    )
    for relative in skill_files:
        files[plugin / "skills/local-context-search" / relative] = (
            skill / relative
        ).read_text(encoding="utf-8")
    changed = [
        path
        for path, text in files.items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    if apply:
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        for number, path in enumerate(changed):
            if path.exists():
                backup = state / f"{stamp}-{number}.backup"
                backup.write_bytes(path.read_bytes())
                backup.chmod(0o600)
            sync.write_config(path, files[path])
        with zipfile.ZipFile(
            state / "local-context-search.zip", "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for relative in skill_files:
                archive.write(skill / relative, f"local-context-search/{relative}")
    return {
        "applied": apply,
        "changed_files": len(changed),
        "indexed_notes": False,
        "claude_desktop": "configured" if apply else "candidate validated",
        "chatgpt": "personal marketplace prepared; app install and connectivity unverified",
        "skill_zip": str(state / "local-context-search.zip"),
    }


def main() -> None:
    """Audit first by default; --apply writes only the desktop adapter files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = prepare(Path(__file__).resolve().parents[1], Path.home(), apply=args.apply)
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
