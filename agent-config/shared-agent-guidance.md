## Shared agent toolkit

The agents-toolkit repository is the canonical source for shared skills, hook
implementations, MCP declarations, client adapters, and adaptation notes.

When a code change affects an agent-facing workflow, integration contract,
permission, or setup path, review the related skill, hook, MCP, adapter,
upstream note, example, and documentation. Update only assets whose behavior or
setup changed. Keep Claude-only and Codex-only instructions in their respective
global files.

Shared skills are linked into both clients. Run `agents-toolkit-sync` to sync
those links and this shared guidance, or `agents-toolkit-sync audit` to inspect
them without changing files. MCP and hook settings have separate sync commands
and should be changed only when explicitly requested.
