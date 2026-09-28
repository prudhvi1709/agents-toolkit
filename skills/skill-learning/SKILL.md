---
name: skill-learning
description: Distill reusable lessons from completed agent work into the shared skill library. Use when the user asks to learn from a session, retain a workflow lesson, improve agent skills, or review repeated agent mistakes; skip one-off facts.
---

# Skill learning

Make useful lessons from real work available to both Claude Code and Codex. This adapts AutoHarness's distill, compare, consolidate, and usage-review loop as a portable skill: https://github.com/tigerless-labs/autoharness at `f74a9fb` (MIT). This skill has no automatic session hooks or MCP server.

## Decide whether a lesson belongs in a skill

1. Name the recurring task or failure, the behavior that should change, and the evidence from the current work. Prefer a corrected approach, a durable constraint, or a technique that would have prevented rework. Do not turn a single environment accident into a global rule.
2. Compare with existing `agents-toolkit/skills`, global skills, and relevant project instructions. Update a specific existing skill when it already owns the scenario; create a new skill only when the trigger and behavior are distinct. Consolidate near-duplicates.
3. Check whether a script, test, project rule, or ordinary documentation is a better home. A skill should carry decision guidance the agent will need at task time, not a transcript or a generic reminder.
4. State a narrow trigger and a concrete action. Keep the frontmatter description useful for discovery, and keep the body short enough to follow. Preserve explicit user instructions and existing approval boundaries.

Keep a concise decision record in the handoff: task class, observed friction, existing skill checked, chosen update or reason to skip, and what later usage would show that the change helped. Never use a synthetic benchmark alone as evidence that a skill is useful.

## Apply and review

- `agents-toolkit` is the source of truth for shared skills. When a change is requested or otherwise authorized, edit the canonical folder, inspect the diff, and sync only the intended skill links into `~/.claude/skills` and `~/.codex/skills`. Do not overwrite unrelated global folders or settings. Existing user-authored skills take priority.
- Do not store raw transcripts, client details, secrets, credentials, or local session paths in the repository. Record an abstract task scenario and a short reason for any substantive skill change.
- Revisit a learned rule after later use. Keep it when it changes outcomes; narrow, merge, or retire it when it causes misrouting, duplicates another skill, or adds cost without value. Explain the evidence behind a change.
- If no reusable lesson clears the bar, say so and leave the library unchanged.
