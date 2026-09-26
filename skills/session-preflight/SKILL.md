---
name: session-preflight
description: Establish concise project context at the start of work or when entering an unfamiliar repository. Use when beginning substantial coding, after a context switch, or when status, test commands, services, or project constraints are unclear.
---

# Session preflight

Produce a short, evidence-backed project briefing before making substantial
changes. Inspect only what is needed:

1. repository root, branch, clean/dirty status, and recent relevant commits;
2. project instructions and agent configuration (`CLAUDE.md`, `.claude`,
   `.codex`, `.cursor`, `.mcp.json`), without exposing secrets;
3. stack, package manager, test/lint/type-check commands, and entry points;
4. active checkpoint, TODO, deployment manifest, and known limitations;
5. running local services and port ownership only when the task needs them.

Report facts separately from assumptions. If the repository has no reliable
test or run command, say so. Do not install dependencies, start services,
change settings, or modify files as part of preflight unless requested.

Keep the final briefing compact: current state, relevant constraints, command
to verify the work, likely risk, and the first action.
