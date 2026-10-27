# local-context (plugin)

Front end for the read-only `local-context` MCP server in `mcps/local-context`.
The plugin ships no server of its own: a plugin install copies only this
folder, so it cannot carry the checkout's MCP project. Register the server once
for the client you use, then install this plugin for its commands and researcher
agent. For Claude Code, run this audit from the toolkit checkout:

```bash
scripts/agent-sync.py audit --only mcps --client claude_code
```

Review the candidate, then explicitly run this command if the audit is clear:

```bash
scripts/agent-sync.py sync --only mcps --client claude_code
```

The client option keeps unrelated Codex conflicts from blocking this scoped
setup. It registers the server from this checkout using its pinned offline
environment.
For Claude Desktop or the local Codex marketplace adapter, see
`desktop/local-context/README.md` and run its setup audit. A conflict in an
existing MCP declaration requires resolving ownership before sync; do not remove
another tool's entry blindly. Restart the client and verify that the tools
connect before relying on the plugin. The plugin adds:

| Piece | What it does |
| --- | --- |
| `/local-context:brief` | `history_status` then one bounded `project_brief`, summarized in 12 lines. |
| `/local-context:handoff [days]` | `list_sessions`, `project_brief` and a few `read_history` calls, folded into a 15-line resume brief across Claude and Codex. |
| `/local-context:recall <topic>` | Focused `search_history` and `read_history` with dates and supersession checks. |
| `context-researcher` agent | Read-only, haiku, restricted to the local-context tools; returns under 200 words so excerpts stay out of the main context. |

Scope stays where you set it: nothing here indexes, rebuilds, or widens the
approved projects. Retrieved text is treated as dated evidence, not
instructions.

## Install

```bash
claude plugin marketplace add ./   # run from the agents-toolkit checkout
claude plugin install local-context@agents-toolkit
```

## Requirements

- The `local-context` MCP server registered in the selected client (tool names
  `mcp__local-context__*`). If you register it under another name, update
  `tools:` in `agents/context-researcher.md`.
- An approved history index (`history_status` reports availability).
