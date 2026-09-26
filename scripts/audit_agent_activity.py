#!/usr/bin/env python3
"""Build a privacy-preserving inventory of local coding-agent activity.

The report contains counts, paths, and broad recurring-work categories only.
It never writes transcript text, prompts, tool arguments, environment values, or
session contents to the output files.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CATEGORIES = {
    "status_and_polling": re.compile(r"\b(status|progress|where are we|check|poll|tail|log lines|process check)\b", re.I),
    "benchmarking_and_evaluation": re.compile(r"\b(benchmark|judge|evaluation|classif|ranking|retrieval|corpus|regression|test pipeline)\b", re.I),
    "design_and_ui_iteration": re.compile(r"\b(design|mockup|screenshot|UI|UX|frontend|layout|palette|screen|visual)\b", re.I),
    "handoff_and_documentation": re.compile(r"\b(handoff|DESIGN\.md|documentation|transcript|artifact|onepager|design\.md)\b", re.I),
    "deployment_and_release": re.compile(r"\b(deploy|deployment|commit|release|server|port|build|cache-bust|preflight)\b", re.I),
    "data_and_translation": re.compile(r"\b(translate|translation|Hindi|language|CSV|JSON|data|dataset|questions)\b", re.I),
}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield value
    except OSError:
        return


def strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def request_texts(path: Path) -> Iterable[str]:
    """Yield only request-like text from supported local log formats."""
    for record in iter_jsonl(path):
        record_type = record.get("type")
        if path.parts and ".claude" in path.parts:
            if record_type == "user":
                yield from strings(record.get("message", {}).get("content", ""))
            elif path.name == "timeline.jsonl":
                # Background-agent timelines are status updates, not transcripts.
                yield from strings(record.get("detail", ""))
                yield from strings(record.get("text", ""))
        elif ".codex" in path.parts:
            payload = record.get("payload", {})
            if isinstance(payload, dict) and payload.get("type") == "user_message":
                yield from strings(payload.get("message", ""))
                yield from strings(payload.get("text", ""))


def classify_file(path: Path) -> set[str]:
    found: set[str] = set()
    # Only use request text for in-memory classification; no text is emitted.
    for text in request_texts(path):
        for name, pattern in CATEGORIES.items():
            if pattern.search(text):
                found.add(name)
    return found


def project_label(path: Path, home: Path) -> str:
    relative = str(path.relative_to(home))
    if "/projects/" in relative:
        return relative.split("/projects/", 1)[1].rsplit("/", 1)[0]
    return relative.split("/", 1)[0]


def config_features(repo: Path) -> set[str]:
    features: set[str] = set()
    candidates = [
        repo / ".claude" / "settings.json",
        repo / ".claude" / "settings.local.json",
        repo / ".cursor" / "mcp.json",
        repo / ".codex" / "config.toml",
        repo / ".mcp.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        name = path.name
        if name == "mcp.json" or name == ".mcp.json":
            features.add("mcp_config")
        if name == "config.toml":
            features.add("codex_config")
        if name.startswith("settings"):
            features.add("claude_settings")
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            if isinstance(data, dict):
                if "hooks" in data:
                    features.add("hooks")
                if "enabledPlugins" in data:
                    features.add("plugins")
                if "permissions" in data:
                    features.add("permissions")
    for directory, feature in [
        (repo / ".claude" / "skills", "project_skills"),
        (repo / ".claude" / "hooks", "hooks"),
        (repo / ".claude" / "commands", "commands"),
        (repo / ".claude" / "agents", "agents"),
        (repo / ".codex", "codex_config"),
    ]:
        if directory.exists():
            features.add(feature)
    return features


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--desktop", type=Path, default=Path.home() / "Desktop")
    parser.add_argument("--output", type=Path, default=Path("reports/agent-activity-audit.md"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/agent-activity-audit.json"))
    args = parser.parse_args()

    home = args.home.expanduser().resolve()
    desktop = args.desktop.expanduser().resolve()
    claude_projects = home / ".claude" / "projects"
    claude_jobs = home / ".claude" / "jobs"
    codex_sessions = home / ".codex" / "sessions"
    desktop_claude_sessions = home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"

    source_counts: dict[str, int] = {}
    category_projects: dict[str, set[str]] = defaultdict(set)
    category_sessions: Counter[str] = Counter()

    claude_files = sorted(claude_projects.rglob("*.jsonl")) if claude_projects.exists() else []
    job_files = sorted(claude_jobs.glob("*/timeline.jsonl")) if claude_jobs.exists() else []
    codex_files = sorted(codex_sessions.rglob("*.jsonl")) if codex_sessions.exists() else []
    desktop_claude_files = sorted(desktop_claude_sessions.rglob("*.jsonl")) if desktop_claude_sessions.exists() else []
    source_counts["claude_session_logs"] = len(claude_files)
    source_counts["claude_background_timelines"] = len(job_files)
    source_counts["codex_session_logs"] = len(codex_files)
    source_counts["claude_desktop_session_logs"] = len(desktop_claude_files)

    for path in claude_files:
        label = project_label(path, home)
        categories = classify_file(path)
        for category in categories:
            category_projects[category].add(label)
            category_sessions[category] += 1
    for path in job_files:
        label = f"background-job:{path.parent.name}"
        categories = classify_file(path)
        for category in categories:
            category_projects[category].add(label)
            category_sessions[category] += 1
    for path in codex_files:
        label = f"codex:{path.parent.name}"
        categories = classify_file(path)
        for category in categories:
            category_projects[category].add(label)
            category_sessions[category] += 1
    for path in desktop_claude_files:
        label = f"claude-desktop:{project_label(path, desktop_claude_sessions)}"
        categories = classify_file(path)
        for category in categories:
            category_projects[category].add(label)
            category_sessions[category] += 1

    repos = []
    for git in desktop.rglob(".git") if desktop.exists() else []:
        if git.is_dir():
            repo = git.parent
            try:
                features = sorted(config_features(repo))
                if features:
                    repos.append({"repo": str(repo.relative_to(desktop)), "features": features})
            except (OSError, ValueError):
                continue
    repos.sort(key=lambda item: item["repo"])
    feature_counts = Counter(feature for item in repos for feature in item["features"])

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "desktop_root": str(desktop),
            "sources": ["~/.claude/projects", "~/.claude/jobs", "~/Library/Application Support/Claude/local-agent-mode-sessions", "~/.codex/sessions", "Desktop Git repositories"],
            "privacy": "Counts and broad categories only; raw transcript text is not written.",
        },
        "source_counts": source_counts,
        "recurring_categories": {
            category: {"session_count": category_sessions[category], "context_count": len(projects)}
            for category, projects in sorted(category_projects.items(), key=lambda item: (-category_sessions[item[0]], item[0]))
        },
        "repo_config_counts": dict(sorted(feature_counts.items())),
        "repos_with_agent_config": repos,
    }

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Local Agent Activity Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "> Privacy: this report contains counts, repository-relative paths, and broad categories only. Raw prompts, transcripts, tool arguments, environment values, and credentials are excluded.",
        "",
        "## Sources",
        "",
    ]
    for source, count in source_counts.items():
        lines.append(f"- `{source}`: **{count}** files")
    lines += ["", "## Recurring work categories", ""]
    for category, projects in sorted(category_projects.items(), key=lambda item: (-category_sessions[item[0]], item[0])):
        lines.append(f"- `{category}`: {category_sessions[category]} session/file matches across {len(projects)} log contexts")
    lines += ["", "## Agent configuration adoption", ""]
    for feature, count in sorted(feature_counts.items()):
        lines.append(f"- `{feature}`: {count} repositories")
    lines += ["", "## Repositories with agent configuration", ""]
    for item in repos:
        lines.append(f"- `{item['repo']}` — {', '.join(item['features'])}")
    lines += ["", "## Recommended next experiments", "", "1. Add a local project-state MCP or hook that records current status, next action, and blockers.", "2. Add resumable benchmark/evaluation workflows with checkpoints instead of repeated polling.", "3. Add a design-handoff skill that preserves decisions, screenshots, and implementation gaps.", "4. Add a deployment preflight hook for tests, process cleanup, ports, and commit readiness.", "5. Re-run this audit periodically and compare category counts before adding new skills or MCPs.", ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.output} and {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
