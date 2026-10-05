# Shared agent configuration

`agents-toolkit` is the only source of truth for shared skills, MCP declarations,
and reusable hook implementations. Claude Code, Claude Desktop, and Codex read
their generated runtime locations; those are not copies to edit by hand.

```bash
scripts/agent-sync.py audit   # inspect drift; changes nothing
scripts/agent-sync.py diff    # same drift report
scripts/agent-sync.py sync --only skills  # link skills only
scripts/agent-sync.py sync --only mcps    # apply MCP declarations only
scripts/agent-sync.py sync --only hooks   # apply hook adapters only
```

Skills are linked into each client. Existing conflicting skill directories are
moved to `~/.agent-sync-backups/` before linking. Unrelated settings remain
untouched. MCP entries are merged into each native config; credentials and
OAuth state are never stored here.

## Where each change goes

- Skill content: `skills/<name>/SKILL.md`. Keep shared instructions portable.
  Put Codex UI or invocation policy in `skills/<name>/agents/openai.yaml`;
  use Claude-specific frontmatter only when Claude needs a behavior Codex can
  configure separately.
- MCP servers: add one entry to `mcps.json`. The sync command renders each
  client's native config while preserving unrelated servers and credentials.
- Hooks: keep reusable scripts under `hooks/` and event/handler adapters in
  `agent-config/hooks.json`. Add an adapter for each client because hook event schemas and
  execution behavior differ. The sync command only manages entries pointing
  to this toolkit's `hooks/` directory; it preserves hooks owned by other
  tools. Claude Code and Codex are supported; Claude Desktop has no hook
  adapter. Add a hook to the manifest only after reviewing its behavior and
  data written, because syncing the manifest activates it.

Hook `script` paths are relative to `hooks/`. The same implementation can map
to different events or matchers per client:

```json
{
  "version": 1,
  "hooks": {
    "example": {
      "claude_code": [{"event": "SessionStart", "matcher": "startup", "script": "example.py"}],
      "codex": [{"event": "SessionStart", "matcher": "startup", "script": "example.py"}]
    }
  }
}
```

Use `.py` scripts with Python 3 or `.sh` scripts with Bash. Optional adapter
fields are `timeout`, `async`, and `statusMessage`.

After a change, audit and sync that category with `--only`. This avoids
applying unrelated MCP or hook declarations. Skill edits appear through the
existing symlinks; a new skill needs the skill-only sync once.

Audits and syncs validate the selected category before changing any target.
Malformed or duplicate-key JSON, conflicting TOML sections, malformed managed
MCP markers, and invalid manifest transports stop the command. Diagnostics
identify the affected file without printing configuration values. Existing
MCP declarations outside Codex's managed block must have their ownership
reconciled before sync can append that block; they are not silently replaced.
Run `uv run scripts/agent-sync.py audit --only mcps` to check MCP candidates.

Validated settings are replaced atomically per file with existing permissions
and symlinks preserved. This is not a transaction across clients: an I/O failure
after an earlier replacement can still leave a partially applied sync. Audits
check serialization and basic manifest structure, not client runtime support,
server connectivity, or OAuth readiness.

Run the configuration regression tests with:

```bash
uv run --no-project python -m unittest discover -s scripts/tests -v
```

## Supported configuration

The manifest currently manages:

- CodeGraphContext through `uvx` on all three clients.
- Postman Minimal through its remote URL on all three clients.
- Figma through the official Claude Code plugin, the Claude Desktop remote
  server, and the Codex remote server.

Existing MCP servers and hooks that are not owned by this toolkit are
preserved. Restart each client after syncing, then complete any first-use OAuth
or login flow. The Figma Claude Code plugin remains managed by Claude's plugin
system; this manifest records it but does not replace or uninstall the plugin.

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
