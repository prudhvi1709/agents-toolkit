#!/usr/bin/env python3
"""Synchronize shared skills, MCP declarations, and hook adapters across agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "agent-config" / "mcps.json"
HOOK_MANIFEST = ROOT / "agent-config" / "hooks.json"
HOME = Path.home()
CLAUDE_SKILLS = HOME / ".claude" / "skills"
CODEX_SKILLS = HOME / ".codex" / "skills"
CLAUDE_JSON = HOME / ".claude.json"
DESKTOP_JSON = HOME / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
CODEX_CONFIG = HOME / ".codex" / "config.toml"
CODEX_HOOKS = HOME / ".codex" / "hooks.json"
CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
MARKER_START = "# BEGIN agents-toolkit managed MCP servers"
MARKER_END = "# END agents-toolkit managed MCP servers"


def load_manifest() -> dict:
    with MANIFEST.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("version") != 1 or not isinstance(data.get("servers"), dict):
        raise ValueError(f"Invalid MCP manifest: {MANIFEST}")
    return data


def load_hook_manifest() -> dict:
    with HOOK_MANIFEST.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("version") != 1 or not isinstance(data.get("hooks"), dict):
        raise ValueError(f"Invalid hook manifest: {HOOK_MANIFEST}")
    for name, hook in data["hooks"].items():
        if not isinstance(hook, dict):
            raise ValueError(f"Invalid hook '{name}': expected an object")
        for client in ("claude_code", "codex"):
            adapters = hook.get(client, [])
            if not isinstance(adapters, list):
                raise ValueError(f"Invalid hook '{name}' {client}: expected a list")
            for adapter in adapters:
                if not isinstance(adapter, dict):
                    raise ValueError(f"Invalid hook '{name}' {client}: expected an object")
                if not isinstance(adapter.get("event"), str) or not adapter["event"].strip():
                    raise ValueError(f"Invalid hook '{name}' {client}: event must be a non-empty string")
                if not isinstance(adapter.get("script"), str) or not adapter["script"].strip():
                    raise ValueError(f"Invalid hook '{name}' {client}: script must be a non-empty path")
                script = Path(adapter["script"])
                if script.is_absolute() or ".." in script.parts or script.suffix not in {".py", ".sh"}:
                    raise ValueError(f"Hook '{name}' script must be a .py or .sh file under hooks/: {script}")
                if not (ROOT / "hooks" / script).is_file():
                    raise ValueError(f"Hook '{name}' script does not exist: {script}")
                if "matcher" in adapter and not isinstance(adapter["matcher"], str):
                    raise ValueError(f"Hook '{name}' matcher must be a string")
                if "timeout" in adapter and (
                    not isinstance(adapter["timeout"], (int, float)) or adapter["timeout"] <= 0
                ):
                    raise ValueError(f"Hook '{name}' timeout must be positive")
                if "async" in adapter and not isinstance(adapter["async"], bool):
                    raise ValueError(f"Hook '{name}' async must be a boolean")
                if "statusMessage" in adapter and not isinstance(adapter["statusMessage"], str):
                    raise ValueError(f"Hook '{name}' statusMessage must be a string")
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


def render_hook_groups(manifest: dict, client: str) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for hook in manifest["hooks"].values():
        for adapter in hook.get(client, []):
            script = (ROOT / "hooks" / adapter["script"]).resolve()
            if script.suffix == ".sh":
                command = f"/bin/bash {shlex.quote(str(script))}"
            else:
                command = f"python3 {shlex.quote(str(script))}"
            handler = {"type": "command", "command": command}
            for key in ("timeout", "async", "statusMessage"):
                if key in adapter:
                    handler[key] = adapter[key]
            group = {"hooks": [handler]}
            if adapter.get("matcher"):
                group["matcher"] = adapter["matcher"]
            groups.setdefault(adapter["event"], []).append(group)
    return groups


def is_toolkit_command(command: object) -> bool:
    root = str((ROOT / "hooks").resolve()) + "/"
    return isinstance(command, str) and root in command


def is_toolkit_hook(group: dict) -> bool:
    return any(
        isinstance(handler, dict) and is_toolkit_command(handler.get("command"))
        for handler in group.get("hooks", [])
    )


def sync_hooks(path: Path, client: str, apply: bool) -> list[str]:
    data = read_json(path)
    existing_hooks = data.get("hooks", {})
    if not isinstance(existing_hooks, dict):
        raise ValueError(f"Expected hooks object in {path}")
    desired = render_hook_groups(load_hook_manifest(), client)
    updated_hooks = {}
    for event, groups in existing_hooks.items():
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict) or not is_toolkit_hook(group):
                kept_groups.append(group)
                continue
            kept_handlers = [
                handler for handler in group.get("hooks", [])
                if not isinstance(handler, dict) or not is_toolkit_command(handler.get("command"))
            ]
            if kept_handlers:
                kept_groups.append({**group, "hooks": kept_handlers})
        if event in desired:
            kept_groups.extend(desired.pop(event))
        if kept_groups:
            updated_hooks[event] = kept_groups
    updated_hooks.update(desired)
    if updated_hooks == existing_hooks:
        return [f"OK hooks {path}"]
    data["hooks"] = updated_hooks
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
    return [f"SET hooks {path}"]


def run(apply: bool, only: str) -> int:
    if only in {"all", "skills"}:
        skills = source_skills()
        print(f"Source: {ROOT}\nSkills: {len(skills)}")
        for target in (CLAUDE_SKILLS, CODEX_SKILLS):
            print(f"\n[{ 'sync' if apply else 'audit' }] {target}")
            for line in sync_skill_target(target, skills, apply):
                print(line)
    if only in {"all", "mcps"}:
        print(f"Source: {ROOT}")
        for label, path, client in (("Claude Code", CLAUDE_JSON, "claude_code"), ("Claude Desktop", DESKTOP_JSON, "claude_desktop")):
            print(f"\n[{label}]")
            for line in sync_json_config(path, client, apply):
                print(line)
        print("\n[Codex]")
        for line in sync_codex_config(apply):
            print(line)
    if only in {"all", "hooks"}:
        print(f"Source: {ROOT}\n[Hooks]")
        hook_targets = (
            ("Claude Code", CLAUDE_SETTINGS, "claude_code"),
            ("Codex", CODEX_HOOKS, "codex"),
        )
        for label, path, client in hook_targets:
            print(f"[{label}]")
            for line in sync_hooks(path, client, apply):
                print(line)
    if not apply:
        print(f"\nDry run only. Run `scripts/agent-sync.py sync --only {only}` to apply changes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "diff", "sync"), nargs="?", default="audit")
    parser.add_argument("--only", choices=("all", "skills", "mcps", "hooks"), default="all")
    args = parser.parse_args()
    return run(args.command == "sync", args.only)


if __name__ == "__main__":
    sys.exit(main())
