# local-context (plugin)

Front end for the read-only `local-context` MCP server in `mcps/local-context`.
The plugin ships no server of its own: a plugin install copies only this
folder, so it cannot carry the checkout's MCP project. Register the server
once (the toolkit's `scripts/agent-sync.py` or
`scripts/setup_desktop_context.py` do this), and the plugin adds:

| Piece | What it does |
| --- | --- |
| `/local-context:brief` | `history_status` then one bounded `project_brief`, summarized in 12 lines. |
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

- The `local-context` MCP server registered in Claude Code (tool names
  `mcp__local-context__*`). If you register it under another name, update
  `tools:` in `agents/context-researcher.md`.
- An approved history index (`history_status` reports availability).
