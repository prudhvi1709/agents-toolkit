# Agents Toolkit

Reusable skills, hooks, scripts, and workflow accelerators for coding and
non-coding agents.

## Contents

- `skills/` contains task-specific agent instructions and supporting code.
- `hooks/` contains lifecycle hooks that can be adapted to an agent runtime.
- `scripts/` contains small utilities for agent status and workflow visibility.

## Principles

- Keep secrets in environment variables, never in source or configuration files.
- Treat transcripts, session state, logs, caches, and local settings as private.
- Adapt paths and provider-specific settings before installing these tools.
- Review generated output before using it in client-facing or high-stakes work.

## License

MIT. See `LICENSE`.

