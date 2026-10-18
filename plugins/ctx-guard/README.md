# ctx-guard

Keeps long Claude Code sessions from silently growing. In a 30-day review, one
session reached 815k tokens of context over 2,882 calls, and every call
re-reads the whole window.

| Piece | Event | What it does |
| --- | --- | --- |
| Context watch | `UserPromptSubmit` | Warns once when context crosses 250k tokens and again at 500k; re-arms after `/clear` or compaction. |
| Checkpoint | `PreCompact` | Saves counts, git branch, changed file names and the last commit subject. No prompt text. |
| Restore | `SessionStart` | Injects the latest checkpoint (labeled as data, under 1,500 chars). Warns on resuming a large context. |
| `/ctx-guard:where` | skill | Ten-line status: context size, checkpoint, git state. |

State lives in `${CLAUDE_PLUGIN_DATA}` (owner-only permissions). The hooks
never block a prompt or a compaction, even when they fail.

## Install

```bash
claude plugin marketplace add ./   # run from the agents-toolkit checkout
claude plugin install ctx-guard@agents-toolkit
```

For a one-off trial: `claude --plugin-dir plugins/ctx-guard`.

## Thresholds

Set in the environment (for example in `~/.claude/settings.json` under `env`):

- `CTX_GUARD_WARN_TOKENS` (default 250000)
- `CTX_GUARD_CRITICAL_TOKENS` (default 500000)

## Compact instructions (manual step)

A plugin cannot ship `CLAUDE.md`, and a `PreCompact` hook cannot add summary
instructions (it can only observe or block). Add this block to the global or
project `CLAUDE.md` so every compaction keeps what matters:

```markdown
# Compact instructions

When compacting, keep: the user's current goal and confirmed decisions; file
paths touched and why; failing tests or errors with their exact messages;
commands that must be re-run; the next step. Drop: raw tool output, file
contents already on disk, exploration dead ends.
```

## Limits

- Context size is read from the transcript's newest assistant usage record,
  which can lag one turn behind.
- The checkpoint records no decisions or next action. For that, use the
  `project-checkpoint` skill; `/ctx-guard:where` says when none is recorded.

## Tests

```bash
python3 -m unittest discover -s plugins/ctx-guard/tests -v
```
