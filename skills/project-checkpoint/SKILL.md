---
name: project-checkpoint
description: Save or resume durable project state for long tasks, context compaction, model switches, handoffs, or long breaks. Use when the user asks where work stands, asks to save state, or a multi-step task has important decisions and a non-obvious next action. Do not use for trivial edits.
---

# Project checkpoint

Create a small, human-readable checkpoint in the project's established state
directory. If none exists, use `.agent-state/checkpoints/`, which works across
agents. Keep private machine state and transcripts out of the checkpoint.

Capture only information needed to resume:

- mission and success condition;
- current status: `in_progress`, `blocked`, `ready_to_verify`, or `done`;
- decisions and constraints that are not obvious from the diff;
- changed artifacts with paths and useful line references;
- blockers and open questions;
- the next 1-3 concrete actions;
- verification already run and what remains, with artifact revision and scope
  (journey, role, viewport or state) or a link to the detailed evidence record;
- for design work, selected reference locators and review status, governing
  token sources, confirmed corrections and unresolved approval decisions;
- the current iteration budget and stopping condition when a review loop is
  still active.

Before writing, inspect the current diff, status, and existing checkpoint so
the file reflects reality rather than the previous plan. Update the existing
checkpoint for the same workstream instead of creating duplicates. Keep it
short enough to read in under a minute.

When resuming, read the checkpoint first, verify that referenced files and
assumptions still exist, then continue from the next action. Mark stale items
instead of silently treating them as current.

Check whether changes since verification invalidate the evidence being relied
on. Identify the affected checks to rerun, preserve unaffected evidence with
its scope, and do not report an old pass as current. Link to the existing
handoff and requirement record rather than creating provider-specific copies;
another agent should be able to resume from the same decisions and next action.

Never record credentials, raw prompts, full transcripts, personal data, or
unverified claims. Ask before converting a tentative idea into a committed
project decision.
