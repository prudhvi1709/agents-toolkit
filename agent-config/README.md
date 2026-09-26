# Shared agent configuration

`agents-toolkit` is the source of truth for shared skills and MCP declarations
used by Claude Code, Claude Desktop, and Codex.

```bash
scripts/agent-sync.py audit   # inspect drift; changes nothing
scripts/agent-sync.py diff    # same drift report
scripts/agent-sync.py sync    # apply links and merge MCP entries
```

Skills are linked into each client. Existing conflicting skill directories are
moved to `~/.agent-sync-backups/` before linking. Unrelated settings remain
untouched. MCP entries are merged into each native config; credentials and
OAuth state are never stored here.

## Supported configuration

The manifest currently manages:

- CodeGraphContext through `uvx` on all three clients.
- Postman Minimal through its remote URL on all three clients.
- Figma through the official Claude Code plugin, the Claude Desktop remote
  server, and the Codex remote server.

Existing MCP servers that are not in `mcps.json` are preserved. Restart each
client after syncing, then complete any first-use OAuth or login flow. The
Figma Claude Code plugin remains managed by Claude's plugin system; this
manifest records it but does not replace or uninstall the plugin.

## Publishing this repository

Only this repository's canonical skills, scripts, documentation, and manifest
belong in Git. Never commit `~/.claude`, `~/.codex`, OAuth data, backups,
session logs, reports, or generated local settings. From the repository root:

```bash
./scripts/agent-sync.py audit
git diff --check
git status --short
git add README.md agent-config scripts skills .gitignore
git diff --cached --check
git commit -m "Add shared Claude and Codex sync"
git push origin Main
```
