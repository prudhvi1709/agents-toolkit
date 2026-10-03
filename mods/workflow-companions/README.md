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

## Evidence Ghost

Recognizes simple foreground pytest, npm/pnpm/yarn/bun test and lint commands,
ruff checks, mypy, ty, tsc, Cargo checks/tests, Go tests, Claude plugin
validation/tests, and `git diff --check`. It deliberately skips compound shell
commands, help/list/collection modes, and backgrounded commands.

The six most recent distinct commands get separate receipts. Command identity
is hashed; the UI shows check families rather than recording the raw command.
Failed checks stay failed until that same command succeeds. A successful tool
result is marked fresh only when before/after worktree fingerprints agree and
no observed edit intervened. Checks that change the worktree are stale.

Successful Edit/Write/NotebookEdit calls and Bash calls not marked read-only
invalidate existing passing receipts conservatively. The timer and each main
turn also inspect the Git worktree to catch external edits. Snapshots include
HEAD, staged and unstaged binary diffs, and untracked file contents. They cover
Git-visible files, not ignored dependencies, environment changes, remote
systems, or every possible input to a test. Reverting a file does not restore a
stale receipt; rerun the check.

Snapshots are bounded to 64 untracked files and 2 MiB of their content, with
three-second Git timeouts. Truncated diffs, unavailable Git, symlinks, or an
exceeded budget show unknown freshness instead of a green result. Raw source
contents are hashed in memory and never persisted by this mod. Check receipts
are session state; they are reset on clear/resume rather than borrowed from
another conversation. The ghost never runs tests itself.

## Benchmark Chai Stall

Have the runner write `.claude/companions/chai.progress.json`, or watch another
project-relative file:

```text
/chai watch output/evaluation/progress.json
/chai hide
/chai show
```

See `examples/chai.progress.example.json`. Required fields are `name`, `status`,
`completed`, `total`, and `heartbeat_at`. Optional `retrying` defaults to 0;
`stale_after_seconds` defaults to 300 and must be 10 to 86400. Counts must be
non-negative integers: completed cannot exceed total, and retrying cannot
exceed the unfinished count. `done` requires completed to equal total.

The runner supplies an actual UTC ISO timestamp ending in `Z`. Update it while
the worker is alive and write the file atomically, using a temporary file plus
rename. The example timestamp is illustrative; replace it with the current
time. A heartbeat reports liveness, not completed work. Chai shows both.

The feed refreshes every 15 seconds. A running job becomes Silent after the
configured heartbeat threshold. Paused, done, and failed jobs keep their own
states. A heartbeat over a minute into the future shows Clock? rather than
pretending the job is healthy. Invalid or missing watched feeds replace old
counts with a visible warning. The mod does not start, restart, or kill jobs.

For this repo, `.claude/companions/` is ignored. Add that ignore rule to other
repos using the default path, and ignore custom runtime output paths too.

## Hero Fight Club

Copy `examples/hero.example.json` to `.claude/companions/hero.json` in a project
that needs a comparison. Set `enabled` to false or remove that file to hide it.
Two to four variants require unique lowercase `id`, `label`, and `description`.
Optional `desktop` and `mobile` fields name project-relative PNG screenshot
paths. PNGs must be regular files within the project and at most 2 MiB each.

Terminal panes draw screenshots where the terminal supports images, with text
fallbacks otherwise. Desktop shows their file paths; open those files in your
usual image viewer. A supplied screenshot is not automatically reviewed or
scored. Use your existing capture/verification workflow to produce it.

In `/hero`, enter a short reason and press Enter, then choose a variant. The
choice and reason are saved to Claude's private plugin store per project.
They survive a new session, but changes to the comparison or screenshot
contents retire the choice. Copy decision puts the human-confirmed decision on
the clipboard for a handoff. It does not submit a prompt or edit the design.

## Install and verify

Copy this folder to `~/.claude/mods/workflow-companions`, add that absolute path
to the colon-separated `env.CLAUDE_CODE_PLUGIN_DIRS` in your local Claude
settings, and restart Claude Code. Also copy the updated `token-weather` source
to its installed folder. Keep unrelated settings intact.

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
