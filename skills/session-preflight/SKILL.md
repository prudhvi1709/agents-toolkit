---
name: session-preflight
description: Establish concise project context at the start of work or when entering an unfamiliar repository. Use when beginning substantial coding, after a context switch, or when status, test commands, services, or project constraints are unclear.
---

# Session preflight

Produce a short, evidence-backed project briefing before making substantial
changes. Inspect only what is needed:

1. repository root, branch, clean/dirty status, and recent relevant commits;
2. project instructions and agent configuration (`AGENTS.md`, `CLAUDE.md`,
   `.agents`, `.claude`, `.codex`, `.cursor`, `.mcp.json`), without exposing
   secrets;
3. stack, package manager, test/lint/type-check commands, and entry points;
4. active checkpoint, TODO, deployment manifest, and known limitations;
5. automatic project knowledge through `local-context-search`, if an approved
   history index covers the project and earlier context matters: check status,
   retrieve a bounded project briefing, and verify relevant sources before use;
6. running local services and port ownership only when the task needs them.

For configuration sync work, run the project's read-only audit for the selected
category before applying changes. A valid existing config can still conflict
with generated sections. Resolve duplicate declarations and managed-block
ownership explicitly; an audit's pending entries do not authorize enabling
additional tools. Validate generated candidates before writing runtime settings.

Report facts separately from assumptions. If the repository has no reliable
test or run command, say so. Do not install dependencies, start services,
change settings, or modify files as part of preflight unless requested.

Keep the final briefing compact: current state, relevant constraints, command
to verify the work, likely risk, and the first action.
