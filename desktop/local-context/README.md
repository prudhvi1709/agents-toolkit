# Desktop local context

This adapter shares approved local notes and automatic coding-agent project
knowledge with desktop apps. The
canonical skill remains in `skills/local-context-search`; the read-only MCP
server lives in `mcps/local-context`. It exposes `context_status`,
`search_context`, and `read_context` for approved notes, plus `history_status`,
`search_history`, `read_history`, and `project_brief` for approved coding-agent
history. See the canonical skill's `references/history-memory.md` for CLI scope
and indexing commands. It cannot rebuild an index, run commands,
write files, or retrieve arbitrary paths. Reads require an unchanged indexed
source and return at most 80 lines / 16 KiB. Search excerpts are opt-in.

## Setup and updates on this Mac

```bash
uv sync --frozen --project mcps/local-context
uv run --no-project python scripts/setup_desktop_context.py
uv run --no-project python scripts/setup_desktop_context.py --apply
```

The first setup command installs the pinned official MCP SDK. The setup script
audits by default. `--apply` adds only the `local-context` Claude Desktop server,
creates a personal ChatGPT marketplace entry and plugin, and prepares a Claude
skill ZIP. It preserves unrelated settings, rejects conflicting entries, and
backs up replaced files outside the repository. It does not restart apps,
install the plugin in the app, upload the ZIP, index notes, or create a tunnel.
The generated plugin references this checkout and requires it to remain here.
Re-run setup after skill changes to refresh the desktop copies.

- Claude Desktop: restart when convenient, then check `local-context` under
  Connectors. Upload the generated skill ZIP through Customize > Skills when
  that feature is available. Server instructions already describe proactive
  retrieval, but hosts decide when tools run.
- ChatGPT Desktop: restart when convenient, open Plugins Directory in Work or
  Codex, select Personal Toolkit, and install Local Context if exposed by the
  account. The bundled stdio server requires a local execution surface;
  registration alone does not establish ordinary ChatGPT access.
- Ordinary ChatGPT or a cloud Work surface: use an OpenAI Secure MCP Tunnel
  with this same stdio server, then register the tunnel as a custom MCP plugin.
  This requires a tunnel ID, runtime API key, and account/workspace permission.
  Do not publish a public endpoint or put keys in this repository. Once the
  custom plugin exists, its technical ID can be mapped into the local plugin.

The index stays at `~/.local/share/agents-toolkit/context.sqlite`. No index is
created during setup. Select only approved note roots using the existing skill's
local rebuild command. Include all desired roots on each rebuild. Retrieved
paths and excerpts enter the receiving app's conversation; local storage does
not make the model interaction offline. Treat retrieved text as evidence,
check source freshness, and check for superseding decisions.

## Optional Obsidian review

The same history database can generate a private linked review vault through
`scripts/obsidian_memory.py`. See the canonical history reference for export,
hourly refresh and edit protection. Desktop retrieval still uses the read-only
MCP; annotations in the vault are not automatically accepted as memory.

## Validation

```bash
uv run --project mcps/local-context python -m unittest discover -s mcps/local-context/tests -v
uv run --project mcps/local-context ruff check mcps/local-context scripts/setup_desktop_context.py
uv run --project mcps/local-context mypy --strict mcps/local-context/server.py scripts/setup_desktop_context.py scripts/obsidian_memory.py
```

Official integration references: [Claude local MCP](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop),
[OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins),
[OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
