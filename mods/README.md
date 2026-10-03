# Claude Code mods

Claude Code mods kept here for version control:

| Mod | Behavior |
| --- | --- |
| `token-weather` | Shows context usage, a 12-turn sparkline, and the last turn's token change above the prompt. |
| `cache-timer` | Shows a one-hour countdown, reset after a completed turn reports cache creation or reads. |
| `token-cost-status` | Shows session cost in USD and current context tokens after each completed turn. |
| `workflow-companions` | Evidence Ghost, Benchmark Chai Stall, and repo-opt-in Hero Fight Club in one aligned strip and detail pane. |

See [Workflow companions](workflow-companions/README.md) for activation rules,
progress feeds, design comparisons, and keyboard controls.

The cache countdown is a local estimate based on reported usage and a fixed
one-hour TTL. It does not query server-side cache expiry.

## Global setup

The installed folders live at:

```text
~/.claude/mods/token-weather
~/.claude/mods/cache-timer
~/.claude/mods/token-cost-status
~/.claude/mods/workflow-companions
```

Claude Code loads them through `env.CLAUDE_CODE_PLUGIN_DIRS` in
`~/.claude/settings.json`. Its value is the installed absolute folder paths joined
with `:` on macOS/Linux. Keep this setting and other personal settings local.
Inspect the configured paths with:

```bash
jq -r '.env.CLAUDE_CODE_PLUGIN_DIRS' ~/.claude/settings.json
```

## Updating the installed mods

Edit the source in this repository, then copy it to the permanent folders from
the repository root:

```bash
mkdir -p ~/.claude/mods
cp -R mods/token-weather mods/cache-timer mods/token-cost-status ~/.claude/mods/
cp -R mods/workflow-companions ~/.claude/mods/
```

Restart Claude Code to load the updated mods. This copy preserves generated
SDK declarations already present in the installed folders. The existing
`agent-sync.py` workflow manages skills, MCPs, and hooks; it does not sync mods.

If you edit an installed mod directly, copy its source changes back here before
updating Git. Keep `.claude-plugin/types/` out of version control: Claude Code
generates that directory for its installed version when it loads a mod.
The mod's own `types/` directory contains authored state declarations and is
included in Git.

## Validation

```bash
claude plugin validate mods/token-weather
claude plugin validate mods/cache-timer
claude plugin validate mods/token-cost-status
claude plugin validate mods/workflow-companions
claude plugin test mods/workflow-companions
claude plugin test mods/token-weather
git diff --check
```

The source uses Unicode escapes for the weather symbols so it stays ASCII
without changing the rendered display. The shared status-line behavior of
`cache-timer` and `token-cost-status` should also be checked together in a live
Claude Code session.

When first installing `workflow-companions`, add its absolute installed path
to the local `CLAUDE_CODE_PLUGIN_DIRS` value. Later copies need no setting
change. Hero Fight Club remains off until each project explicitly opts in.
