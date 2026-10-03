# Workflow companions

Three companions share one native Claude Code strip and detail pane. They use
no model calls, make no network requests, and never change tool calls or
permission decisions.

## When each appears

- Evidence Ghost starts tracking when Claude's foreground Bash tool runs a
  recognized check. It stays hidden until then.
- Benchmark Chai Stall stays hidden until a progress feed exists or you select
  one with `/chai watch`.
- Hero Fight Club stays hidden unless this project explicitly opts in. It is
  for active design comparisons, not every repository.

## Layout and interaction

See [the layout preview](preview.svg) for example states. It is a design
preview, not a screenshot of a live Claude session.

The compact strip uses a shared frame, six-cell icon column, eleven-cell label
column, and nine-cell status column. Detail text uses the remaining width. At
widths below 64 cells it moves below the label; `/companions` opens the details.
Color supplements words: green means a current check or a saved choice, yellow
means stale/unknown evidence or a silent feed, red means failure, and cyan marks
active work. Terminal and Desktop inherit the host's font and theme.

```text
+-----------------------------------------------------------------------+
| (o.o) Evidence   Haunted  2 stale checks. Boo.                    View |
| [~]   Chai stall Running  184/240 served, 12 retrying              View |
| [vs]  Hero club  Chosen   Centered hero                           View |
+-----------------------------------------------------------------------+
```

The third row appears only in opted-in projects. Idle rows disappear, with no
flashing or automatic focus changes. Token Weather must use this repository's
updated renderer so both mods can share the band. Surveys take precedence.

Open `/companions`, `/ghost`, `/chai`, or `/hero`. In the pane, Tab/Enter work
with the native controls. Focused-pane shortcuts: `g` for evidence, `c` for
Chai, `h` for Hero (when enabled), `r` to refresh, and `x` to close. Escape also
closes the pane. The strip's View buttons do not claim typing shortcuts.

## Source layout

Each companion has its own code, focused tests, examples, and illustrative
assets. The bundle keeps one plugin loader and one shared strip / pane:

```text
workflow-companions/
  evidence-ghost/
  benchmark-chai-stall/
  hero-fight-club/
  hooks/                  Shared SDK hooks and UI
  tests/                  Bundle integration tests
  types/                  Authored plugin state declarations
  .claude-plugin/         Bundle manifest
```

Install the bundle root, not an individual companion folder. Video production,
recordings, generated audio, renders, and social drafts stay local under the
Git-ignored `demo-video/` directory.

## Evidence Ghost

Keeps check results tied to the inputs that passed. No-op commands preserve
freshness; optional per-check file scopes avoid invalidating results after
unrelated edits. Unconfigured checks watch the whole worktree.

See [Evidence Ghost](evidence-ghost/README.md) for supported checks, scope
configuration, examples, and coverage limits.

## Benchmark Chai Stall

Shows completed, waiting, and retrying work, plus the runner's heartbeat.
Quiet runners are marked Silent; paused and finished jobs keep their own states.

See [Benchmark Chai Stall](benchmark-chai-stall/README.md) for the progress feed
schema, example JSON, and heartbeat rules.

## Hero Fight Club

Keeps project-opted-in design alternatives and a human-selected reason together.
Changes to the comparison or screenshots retire the saved choice.

See [Hero Fight Club](hero-fight-club/README.md) for opt-in configuration,
example comparisons, and screenshot handling.

## Install and verify

Copy this folder to `~/.claude/mods/workflow-companions`, add that absolute path
to the colon-separated `env.CLAUDE_CODE_PLUGIN_DIRS` in your local Claude
settings, and restart Claude Code. Also copy the updated `token-weather` source
to its installed folder. Keep unrelated settings intact.

Copy the runtime source without local video files or generated SDK declarations:

```bash
mkdir -p ~/.claude/mods/workflow-companions
rsync -a --exclude='/demo-video/' --exclude='/.claude-plugin/types/' mods/workflow-companions/ ~/.claude/mods/workflow-companions/
```

```bash
claude plugin validate mods/workflow-companions
claude plugin test mods/workflow-companions
claude plugin test mods/token-weather
git diff --check
```

Automated tests exercise real mod handlers and native UI trees at compact and
wide widths on terminal and Desktop. They do not verify native painting; check
the strip and pane in a live session after installation.

## Access

Reads the Git worktree, selected local progress files, opted-in design JSON,
and supplied screenshots. Runs only fixed read-only Git argv commands with
timeouts. Persists session receipts through Claude state and human choices in
the private plugin store. Clipboard writes happen only when you press Copy
decision. Makes no network or model calls; adds no automatic approvals.
