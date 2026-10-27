#!/usr/bin/env python3
"""Synchronize shared skills, MCP declarations, and hook adapters across agents."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
import tomllib
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
    data = read_json(MANIFEST)
    if data.get("version") != 1 or not isinstance(data.get("servers"), dict):
        raise ValueError(f"Invalid MCP manifest: {MANIFEST}")
    for name, server in data["servers"].items():
        if not name or not isinstance(server, dict):
            raise ValueError(f"Invalid MCP server declaration in {MANIFEST}")
        for client in ("claude_code", "claude_desktop", "codex"):
            config = server.get(client)
            if config is None:
                continue
            if not isinstance(config, dict):
                raise ValueError(f"Expected MCP client object in {MANIFEST}")
            if config.get("managed_by") == "official-plugin":
                continue
            transport = [key for key in ("command", "url") if key in config]
            if (
                len(transport) != 1
                or not isinstance(config[transport[0]], str)
                or not config[transport[0]].strip()
            ):
                raise ValueError(f"Expected one non-empty MCP command or URL in {MANIFEST}")
            if (
                client == "claude_code"
                and "url" in config
                and config.get("type") not in {"http", "sse"}
            ):
                raise ValueError(
                    f"Claude Code remote MCP '{name}' must declare type http or sse"
                )
            if "type" in config and config["type"] not in {"stdio", "http", "sse"}:
                raise ValueError(f"Invalid MCP transport type for '{name}' in {client}")
            if config.get("type") in {"http", "sse"} and "url" not in config:
                raise ValueError(f"Remote MCP '{name}' must use a URL in {client}")
            if config.get("type") == "stdio" and "command" not in config:
                raise ValueError(f"Stdio MCP '{name}' must use a command in {client}")
            if "args" in config and (
                not isinstance(config["args"], list)
                or any(not isinstance(arg, str) for arg in config["args"])
            ):
                raise ValueError(f"Expected MCP args to be a list of strings in {MANIFEST}")
    return data


def load_hook_manifest() -> dict:
    data = read_json(HOOK_MANIFEST)
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


def unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def reject_json_constant(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def parse_json(text: str, path: Path) -> dict:
    try:
        data = json.loads(
            text, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant
        )
    except ValueError as err:
        raise ValueError(f"Invalid or duplicate-key JSON in {path}") from err
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return parse_json(path.read_text(encoding="utf-8"), path)


def validate_toml(text: str, path: Path) -> None:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise ValueError(f"Invalid or conflicting TOML sections in {path}") from err


def write_config(path: Path, text: str) -> None:
    """Replace a validated config atomically, retaining existing permissions."""
    if path.is_symlink():
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        if path.exists():
            temporary.chmod(path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def render_json_servers(manifest: dict, client: str) -> dict:
    result = {}
    for name, server in manifest["servers"].items():
        config = server.get(client)
        if not config or config.get("managed_by") == "official-plugin":
            continue
        result[name] = resolve_runtime_paths(config)
        if client != "claude_code":
            result[name].pop("type", None)
    return result


def resolve_runtime_paths(value: object) -> object:
    """Expand the one portable checkout token used by local MCP commands."""
    if isinstance(value, str):
        return value.replace("${AGENTS_TOOLKIT_ROOT}", str(ROOT))
    if isinstance(value, list):
        return [resolve_runtime_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_runtime_paths(item) for key, item in value.items()}
    return value


def sync_json_config(path: Path, client: str, apply: bool) -> list[str]:
    data = read_json(path)
    current = data.setdefault("mcpServers", {})
    if not isinstance(current, dict):
        raise ValueError(f"Expected mcpServers object in {path}")
    desired = render_json_servers(load_manifest(), client)
    changes = []
    for name, config in desired.items():
        if current.get(name) == config:
            changes.append(f"OK MCP {path}: {name}")
        else:
            changes.append(f"SET MCP {path}: {name}")
            current[name] = config
    rendered = json.dumps(data, indent=2) + "\n"
    parse_json(rendered, path)
    if apply and desired:
        write_config(path, rendered)
    return changes


def render_codex_block(manifest: dict) -> str:
    lines = [MARKER_START]
    for name, server in manifest["servers"].items():
        config = server.get("codex")
        if not config:
            continue
        # Quoted keys keep dots and spaces inside a single server identifier.
        lines.append(f"[mcp_servers.{json.dumps(name, ensure_ascii=False)}]")
        if "url" in config:
            lines.append(f"url = {json.dumps(config['url'], ensure_ascii=False)}")
        else:
            lines.append(f"command = {json.dumps(config['command'], ensure_ascii=False)}")
            args = ", ".join(
                json.dumps(arg, ensure_ascii=False) for arg in config.get("args", [])
            )
            lines.append(f"args = [{args}]")
        lines.append("")
    lines.append(MARKER_END)
    return "\n".join(lines)


def sync_codex_config(apply: bool) -> list[str]:
    existing = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""
    validate_toml(existing, CODEX_CONFIG)
    block = render_codex_block(load_manifest())
    start, end = existing.find(MARKER_START), existing.find(MARKER_END)
    if (
        existing.count(MARKER_START) != existing.count(MARKER_END)
        or existing.count(MARKER_START) > 1
        or (start >= 0 and end < start)
    ):
        raise ValueError(f"Invalid managed MCP markers in {CODEX_CONFIG}")
    if start >= 0 and end >= start:
        end += len(MARKER_END)
        updated = existing[:start].rstrip() + "\n\n" + block + existing[end:]
    else:
        existing_servers = tomllib.loads(existing).get("mcp_servers", {})
        desired_servers = tomllib.loads(block).get("mcp_servers", {})
        if (
            isinstance(existing_servers, dict)
            and existing_servers.keys() & desired_servers.keys()
        ):
            raise ValueError(
                f"MCP declarations outside the managed block conflict in {CODEX_CONFIG}; "
                "reconcile ownership before syncing"
            )
        updated = existing.rstrip() + "\n\n" + block + "\n"
    validate_toml(updated, CODEX_CONFIG)
    if updated == existing:
        return [f"OK MCP {CODEX_CONFIG}"]
    if apply:
        write_config(CODEX_CONFIG, updated)
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
        if not isinstance(groups, list):
            raise ValueError(f"Expected hook event groups to be a list in {path}")
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
    rendered = json.dumps(data, indent=2) + "\n"
    parse_json(rendered, path)
    if apply:
        write_config(path, rendered)
    return [f"SET hooks {path}"]


def run(apply: bool, only: str, client: str = "all") -> int:
    # Preflight the whole selected category before any target is changed.
    # Writes are atomic per file, not a transaction across all clients.
    if client != "all" and only != "mcps":
        raise ValueError("--client can only be used with --only mcps")
    json_clients = {
        "claude_code": ("Claude Code", CLAUDE_JSON, "claude_code"),
        "claude_desktop": ("Claude Desktop", DESKTOP_JSON, "claude_desktop"),
    }
    selected_clients = (
        list(json_clients.values())
        if client == "all"
        else [json_clients[client]]
        if client in json_clients
        else []
    )
    include_codex = client in {"all", "codex"}
    if not selected_clients and not include_codex:
        raise ValueError(f"Unsupported MCP client: {client}")
    if only in {"all", "mcps"}:
        for _, path, client_name in selected_clients:
            sync_json_config(path, client_name, False)
        if include_codex:
            sync_codex_config(False)
    if only in {"all", "hooks"}:
        sync_hooks(CLAUDE_SETTINGS, "claude_code", False)
        sync_hooks(CODEX_HOOKS, "codex", False)
    if only in {"all", "skills"}:
        skills = source_skills()
        print(f"Source: {ROOT}\nSkills: {len(skills)}")
        for target in (CLAUDE_SKILLS, CODEX_SKILLS):
            print(f"\n[{ 'sync' if apply else 'audit' }] {target}")
            for line in sync_skill_target(target, skills, apply):
                print(line)
    if only in {"all", "mcps"}:
        print(f"Source: {ROOT}")
        for label, path, client_name in selected_clients:
            print(f"\n[{label}]")
            for line in sync_json_config(path, client_name, apply):
                print(line)
        if include_codex:
            print("\n[Codex]")
            for line in sync_codex_config(apply):
                print(line)
    if only in {"all", "hooks"}:
        print(f"Source: {ROOT}\n[Hooks]")
        hook_targets = (
            ("Claude Code", CLAUDE_SETTINGS, "claude_code"),
            ("Codex", CODEX_HOOKS, "codex"),
        )
        for label, path, hook_client in hook_targets:
            print(f"[{label}]")
            for line in sync_hooks(path, hook_client, apply):
                print(line)
    if not apply:
        client_option = "" if client == "all" else f" --client {client}"
        print(
            f"\nDry run only. Run `scripts/agent-sync.py sync --only {only}"
            f"{client_option}` to apply changes."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("audit", "diff", "sync", "validate"), nargs="?", default="audit"
    )
    parser.add_argument("--only", choices=("all", "skills", "mcps", "hooks"), default="all")
    parser.add_argument(
        "--client",
        choices=("all", "claude_code", "claude_desktop", "codex"),
        default="all",
        help="Limit MCP audit/sync to one client; valid only with --only mcps",
    )
    args = parser.parse_args()
    try:
        if args.command == "validate":
            manifest = load_manifest()
            load_hook_manifest()
            upstreams = read_json(ROOT / "agent-config" / "upstreams.json")
            if upstreams.get("version") != 1 or not isinstance(
                upstreams.get("sources"), list
            ):
                raise ValueError("Invalid upstream inventory")
            for source in upstreams["sources"]:
                if not isinstance(source, dict) or not all(
                    isinstance(source.get(key), str) and source[key]
                    for key in (
                        "name",
                        "repository",
                        "revision",
                        "license",
                        "form",
                        "boundary",
                    )
                ):
                    raise ValueError("Invalid upstream source entry")
                if (
                    not isinstance(source.get("adapted_files"), list)
                    or not source["adapted_files"]
                ):
                    raise ValueError("Upstream source must list adapted files")
                for relative in source["adapted_files"]:
                    relative_path = Path(relative) if isinstance(relative, str) else None
                    if (
                        relative_path is None
                        or relative_path.is_absolute()
                        or ".." in relative_path.parts
                        or not (ROOT / relative_path).exists()
                    ):
                        raise ValueError(f"Upstream source path does not exist: {relative}")
            for client in ("claude_code", "claude_desktop"):
                json.dumps({"mcpServers": render_json_servers(manifest, client)})
            validate_toml(render_codex_block(manifest), CODEX_CONFIG)
            for relative in (
                ".claude-plugin/marketplace.json",
                "desktop/local-context/plugin.json",
            ):
                if not (ROOT / relative).is_file():
                    raise ValueError(f"Required plugin manifest is missing: {relative}")
                read_json(ROOT / relative)
            print(
                f"Repository manifests valid: {len(source_skills())} canonical skills, "
                f"{len(upstreams['sources'])} tracked upstream sources"
            )
            return 0
        return run(args.command == "sync", args.only, args.client)
    except (ValueError, OSError) as err:
        print(f"Configuration sync failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
