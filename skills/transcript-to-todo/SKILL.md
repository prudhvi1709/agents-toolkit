---
name: transcript-to-todo
description: >
  Convert a conversation transcript (meeting, chat log, voice-note
  transcription, any pasted discussion) into a confirmed, action-oriented
  todo.md at the repo root. Runs a two-phase flow: (1) extract a structured
  understanding covering context, firm decisions, tentative directions,
  constraints, non-goals, action items, concerns/dissent, and open questions;
  (2) iterate section-by-section with the user via AskQuestion until every
  section is confirmed accurate and complete; then write todo.md. Preserves
  nuances (tentative vs firm decisions, dissent, verbatim constraints,
  unresolved threads, non-goals) rather than flattening to a bare task list.
  Never invents items. Use when the user asks to turn a transcript, meeting
  notes, chat log, or discussion into actionable todos, or names this skill
  explicitly.
disable-model-invocation: true
---

# transcript-to-todo

## When to use

The user provides a transcript (meeting, chat log, voice-note transcription, any recorded conversation) and wants a confirmed `todo.md` at the repo root that a future agent or human can execute against.

The skill's job stops when `todo.md` is written. Applying the todo is a separate action.

## Non-goals of this skill

- Do not commit or push `todo.md`. Only write the file and hand back a proposed commit message for the user to run.
- Do not fabricate items that are not in the transcript.
- Do not push back on decisions in the transcript. This is a capture skill, not a critique skill. If a decision looks wrong, mention it once at handoff, do not embed the critique in `todo.md`.

## Workflow

Copy this checklist and update it as you go:

```
Task Progress:
- [ ] 1. Ingest transcript
- [ ] 2. Extract structured understanding
- [ ] 3. Confirm each section with the user (iterate until locked)
- [ ] 4. Handle existing todo.md if present
- [ ] 5. Write todo.md
- [ ] 6. Hand off (proposed commit message, no commit)
```

## Step 1: Ingest

Accept the transcript from any of:

- Direct paste in the chat.
- File path the user provides (`.txt`, `.md`, `.vtt`, `.srt`, `.json`).
- Both: a file plus a scoping note like "focus on the second half".

If the input is short (roughly under 20 lines), lacks conversational structure (no speakers, turns, or topical shifts), or plausibly is not a transcript at all, stop and confirm with the user before processing. Do not guess through it.

Capture source metadata (kind of transcript, date if known, participants if named). You will cite this in the header of `todo.md`.

## Step 2: Extract structured understanding

Read the transcript end-to-end, not just scan. Fill this schema. Every item must trace to a specific part of the transcript; if you cannot trace it, drop it.

```
Context:              (2-4 sentences: why did this conversation happen?)
Firm decisions:       (explicit calls the participants made)
Tentative directions: (leaning toward X, "probably" or "we should", not yet firm)
Constraints:          (technical, timeline, non-negotiable; verbatim where phrasing matters)
Non-goals:            (explicitly out of scope, "we are NOT doing X")
Action items:         (concrete work; owner if named; acceptance if implied)
Concerns / dissent:   (disagreement, pushback, minority views raised, and the outcome)
Open questions:       (unresolved; needs a follow-up)
```

### Nuance preservation rules (do not skip)

1. Distinguish **firm** from **tentative**. "We will use Postgres" is firm; "leaning toward Postgres, need to check licensing" is tentative. Different section.
2. Preserve **verbatim** short quotes for constraints and strong positions when phrasing carries meaning (e.g. `"must not touch the auth layer"`).
3. Record **dissent**. If someone pushed back and was overruled, capture it in `Concerns / dissent` with the resolution. Future implementers need to know a decision was contested.
4. Record **non-goals** explicitly. Silent scope creep starts when non-goals are dropped from notes.
5. **Attribute** when attribution matters. "X insisted on Y" is different information from "we decided Y" when the insistence itself is a signal.
6. Flag **ambiguity** inline with `[?]`. Do not silently pick one interpretation.
7. Never invent an action item to make the list feel complete or "well rounded".
8. Do not deduplicate aggressively; two related items are usually two items, not one.
9. Do not compute or infer metrics the transcript does not support (deadlines, SLAs, headcount, cost). Quote what was said; do not clean it up.

## Step 3: Confirm with user (section by section)

Ask the user with structured multiple-choice questions. Use the `AskQuestion` tool if the host provides it (Cursor); otherwise present the same options as a numbered list the user can reply to.

For each of the eight schema sections in order, present the section's extracted content in the prompt (so the user can see exactly what you have) with these options:

- `Correct as-is`
- `Edit / add / remove specific items` (user replies freeform; you update; re-present the same section)
- `This section should be empty`

Move to the next section only after the current is locked. If a user edit is cross-cutting (e.g. "move that from Action items to Open questions"), apply it and re-confirm both affected sections.

After the last section, ask one final structured question:

- Prompt: "Anything from the transcript still missing or misrepresented?"
- Options: `Nothing missing, proceed to write todo.md` / `Yes, I want to add or fix ...`

Only proceed to Step 4 after that final confirmation.

## Step 4: Handle existing todo.md

Determine the repo root:

- If `git rev-parse --show-toplevel` succeeds, use it.
- If not, ask the user for a target directory before writing anything.

Then check whether `todo.md` exists at that root.

- If it does not: proceed.
- If it does: ask the user (structured question) with options:
  - `Overwrite (existing content is lost)`
  - `Append a new dated section to the existing file`
  - `Write to a different filename I will name`
  - `Cancel`

Never silently overwrite.

## Step 5: Write todo.md

Use this template. Include every section even when empty (write `_None captured._` rather than omitting the section; future readers should see what was considered and found absent).

```markdown
# TODO: <short title derived from context>

_Generated <YYYY-MM-DD> from <source description, e.g. "product sync meeting, 2026-07-22, participants: A, B, C">_

## Context

<2-4 sentences>

## Constraints

- <item, verbatim where phrasing matters>

## Non-goals

- <explicitly out of scope>

## Action items

### <Group / feature area>

- [ ] <task>
      - Acceptance: <what "done" looks like, if implied by the transcript>
      - Owner: <if named in the transcript>
      - Depends on: <if applicable>

## Tentative (not yet firm)

- <"leaning toward X"; needs confirmation before acting>

## Open questions

- <unresolved; needs follow-up>

## Concerns / dissent

- <who pushed back, on what, and the outcome>
```

Formatting rules for the output file (match the user's global typography rules):

- Plain ASCII only. No em-dashes, en-dashes (outside numeric ranges), curly quotes, or the ellipsis character. Use `-`, `"`, `'`, `...`.
- Use `- [ ]` checkboxes only inside `## Action items`. Other sections use plain `-` bullets.
- Group action items by feature area, subsystem, or file surface, not by owner or urgency. Grouping should help the executor find related work.
- One task per checkbox. If you catch yourself writing "and" between two verbs in a task, split it into two tasks.
- No emoji or decorative glyphs.

## Step 6: Hand off

Tell the user:

1. Path of the file you wrote (absolute).
2. A one-line summary, e.g. "12 action items across 3 groups, 3 open questions, 1 recorded dissent".
3. Proposed commit message using the user's `PREFIX: imperative summary` style, e.g. `DOC: Capture <topic> discussion in todo.md` or `CHORE: Add todo.md from <source>`.
4. Explicit note that you have not staged, committed, or pushed anything.

Do not run `git add`, `git commit`, or `git push`. Ever, even if the user says "commit it" in passing. That is their action.

## Failure modes

- **Empty extract**: If no firm decisions, no action items, and no clear open questions emerged, do not write an empty `todo.md`. Report what you found (usually just context) and ask whether to save it as a `notes.md` instead or discard.
- **Non-transcript input**: If the input looks like a spec, a bug report, a code paste, or an arbitrary document, say so and ask for confirmation before treating it as a transcript.
- **Contradictions in the transcript**: If the same decision is made and reversed later in the conversation, capture both events in `Concerns / dissent` with the resolution order, not just the final position.
- **Unverifiable specifics**: Numbers, dates, SLAs, cost figures - include them verbatim in the relevant section, tagged as reported. Do not present them as verified facts.
- **Multiple simultaneous topics**: If the transcript covers two clearly separate initiatives, offer to produce two `todo.md` files (or one with two top-level titled blocks) rather than mixing action items.
