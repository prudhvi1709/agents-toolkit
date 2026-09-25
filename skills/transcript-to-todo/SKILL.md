---
name: transcript-to-todo
description: Convert a meeting, chat, or voice transcript into a confirmed root-level todo.md through section-by-section user review. Preserve decisions, uncertainty, constraints, dissent, non-goals, and open questions without inventing work.
disable-model-invocation: true
---

# Transcript to TODO

Use only when the user provides a transcript or explicitly names this skill. The
skill ends after writing `todo.md`; executing the tasks is separate.

## Workflow

1. Read the complete transcript. Accept pasted text or a user-provided `.txt`,
   `.md`, `.vtt`, `.srt`, or `.json` file. If it is short, lacks speakers or
   turns, or looks like another document, ask before treating it as a transcript.
2. Extract this schema. Every item must trace to the source; otherwise omit it.

```text
Context: 2-4 sentences explaining why the conversation happened
Firm decisions: explicit calls made
Tentative directions: proposals or leanings not yet approved
Constraints: technical, timeline, or non-negotiable limits
Non-goals: explicitly out-of-scope work
Action items: concrete work, owner, and acceptance if stated
Concerns / dissent: objections and their resolution
Open questions: unresolved follow-ups
```

3. Preserve nuance: distinguish firm from tentative, attribute views when it
   matters, retain short consequential quotes, mark ambiguity with `[?]`, record
   non-goals and dissent, and never infer deadlines, metrics, owners, or tasks.
4. Confirm each section with the user before writing. Present the extracted
   section and ask: `Correct as-is`, `Edit`, or `Empty`. Apply edits and repeat
   until locked. After all sections, ask whether anything is missing.
5. Find the repository root with `git rev-parse --show-toplevel`. If that fails,
   ask for the target directory. Check for an existing `todo.md` and ask whether
   to overwrite, append a dated section, use another filename, or cancel.
6. Write the confirmed file from `assets/todo-template.md`, which carries the
   section order and formatting rules. Include every section, using
   `_None captured._` where a section is empty.

Use ASCII punctuation, one action per checkbox, and group actions by feature or
file surface. Keep the output factual and executable, not editorial.

## Handoff

Report the absolute output path, a one-line count of actions/questions/dissent,
and a proposed `DOC:` or `CHORE:` commit subject. Do not stage, commit, or push.

## Failure rules

- If there are no decisions, actions, or open questions, ask whether to save
  `notes.md` instead of writing an empty TODO.
- If topics are unrelated, offer separate TODO files.
- If a decision changes later, preserve the sequence and resolution under dissent.
- Keep private transcript content, credentials, and personal paths out of logs,
  commits, and public output.
