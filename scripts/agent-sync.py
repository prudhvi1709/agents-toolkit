#!/usr/bin/env python3
"""Synchronize shared skills and MCP declarations across Claude and Codex."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "agent-config" / "mcps.json"
HOME = Path.home()
CLAUDE_SKILLS = HOME / ".claude" / "skills"
CODEX_SKILLS = HOME / ".codex" / "skills"
CLAUDE_JSON = HOME / ".claude.json"
DESKTOP_JSON = HOME / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
CODEX_CONFIG = HOME / ".codex" / "config.toml"
MARKER_START = "# BEGIN agents-toolkit managed MCP servers"
MARKER_END = "# END agents-toolkit managed MCP servers"


def load_manifest() -> dict:
    with MANIFEST.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("version") != 1 or not isinstance(data.get("servers"), dict):
        raise ValueError(f"Invalid MCP manifest: {MANIFEST}")
    return data


def source_skills() -> list[Path]:
    return sorted(path.parent for path in (ROOT / "skills").glob("*/SKILL.md"))


def backup_path(target: Path) -> Path:
    root = HOME / ".agent-sync-backups" / time.strftime("%Y%m%d-%H%M%S") / target.parent.name
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / target.name
    suffix = 1
    while candidate.exists():
        candidate = root / f"{target.name}-{suffix}"
        suffix += 1
    return candidate


def sync_skill_target(target_root: Path, skills: list[Path], apply: bool) -> list[str]:
    changes = []
    if apply:
        target_root.mkdir(parents=True, exist_ok=True)
    for source in skills:
        target = target_root / source.name
        if target.is_symlink() and target.resolve() == source.resolve():
            changes.append(f"OK skill {target}")
            continue
        if target.exists() or target.is_symlink():
            changes.append(f"BACKUP {target}")
            if apply:
                shutil.move(str(target), str(backup_path(target)))
        changes.append(f"LINK {target} -> {source}")
        if apply:
            target.symlink_to(source, target_is_directory=True)
    return changes


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def render_json_servers(manifest: dict, client: str) -> dict:
    result = {}
    for name, server in manifest["servers"].items():
        config = server.get(client)
        if not config or config.get("managed_by") == "official-plugin":
            continue
        result[name] = {key: value for key, value in config.items() if key != "type"}
    return result


def sync_json_config(path: Path, client: str, apply: bool) -> list[str]:
    data = read_json(path)
    current = data.setdefault("mcpServers", {})
    desired = render_json_servers(load_manifest(), client)
    changes = []
    for name, config in desired.items():
        if current.get(name) == config:
            changes.append(f"OK MCP {path}: {name}")
        else:
            changes.append(f"SET MCP {path}: {name}")
            if apply:
                current[name] = config
    if apply and desired:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
    return changes


def render_codex_block(manifest: dict) -> str:
    lines = [MARKER_START]
    for name, server in manifest["servers"].items():
        config = server.get("codex")
        if not config:
            continue
        lines.append(f"[mcp_servers.{name}]")
        if "url" in config:
            lines.append(f"url = {json.dumps(config['url'])}")
        else:
            lines.append(f"command = {json.dumps(config['command'])}")
            args = ", ".join(json.dumps(arg) for arg in config.get("args", []))
            lines.append(f"args = [{args}]")
        lines.append("")
    lines.append(MARKER_END)
    return "\n".join(lines)


def sync_codex_config(apply: bool) -> list[str]:
    existing = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""
    block = render_codex_block(load_manifest())
    start, end = existing.find(MARKER_START), existing.find(MARKER_END)
    if start >= 0 and end >= start:
        end += len(MARKER_END)
        updated = existing[:start].rstrip() + "\n\n" + block + existing[end:]
    else:
        updated = existing.rstrip() + "\n\n" + block + "\n"
    if updated == existing:
        return [f"OK MCP {CODEX_CONFIG}"]
    if apply:
        CODEX_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CODEX_CONFIG.write_text(updated, encoding="utf-8")
    return [f"SET MCP {CODEX_CONFIG}"]


def run(apply: bool) -> int:
    skills = source_skills()
    print(f"Source: {ROOT}\nSkills: {len(skills)}")
    for target in (CLAUDE_SKILLS, CODEX_SKILLS):
        print(f"\n[{ 'sync' if apply else 'audit' }] {target}")
        for line in sync_skill_target(target, skills, apply):
            print(line)
    for label, path, client in (("Claude Code", CLAUDE_JSON, "claude_code"), ("Claude Desktop", DESKTOP_JSON, "claude_desktop")):
        print(f"\n[{label}]")
        for line in sync_json_config(path, client, apply):
            print(line)
    print("\n[Codex]")
    for line in sync_codex_config(apply):
        print(line)
    if not apply:
        print("\nDry run only. Run `scripts/agent-sync.py sync` to apply changes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "diff", "sync"), nargs="?", default="audit")
    args = parser.parse_args()
    return run(args.command == "sync")


if __name__ == "__main__":
    sys.exit(main())
