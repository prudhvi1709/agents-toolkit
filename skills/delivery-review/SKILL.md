---
name: delivery-review
description: A short blameless review capturing intended versus actual outcome, the blockers and rework encountered, and the one to three changes that would prevent recurrence. Use when a complex, failure-prone, or multi-step task has just finished and it is worth deciding what should change before the next similar task.
---

# Delivery Review

Run a short blameless review when work involved retries, blockers, rework,
multiple tools, external dependencies, or meaningful risk. Skip it for trivial
successful edits.

## Review

Capture:

- intended outcome and actual outcome;
- failures, retries, permissions, network, or environment blockers;
- wasted steps, unclear assumptions, and avoidable rework;
- scope changes or user-impacting compromises;
- evidence that supports the completion claim;
- one to three changes that would prevent recurrence.

For each recurring issue, write:

`I did X. This caused Y. Next time, change Z.`

Focus on system and process improvements, not blame. Distinguish a one-off
failure from a pattern worth encoding in a skill, script, test, or project rule.

## Privacy and storage

- Do not include secrets, private transcripts, credentials, personal paths, or
  client identifiers.
- Prefer a project-local `docs/agent-reviews/` or an explicitly requested output
  path. Do not assume a personal home-directory location.
- Keep the review concise enough to be useful during the next task.

## Completion

End with the highest-value change to make next: a prompt improvement, preflight
check, deterministic test, tool wrapper, or documentation update. Do not create a
review merely to satisfy the skill.

