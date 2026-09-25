---
name: agent-cli-design
description: Design rules for command-line tools that both people and agents can drive reliably, covering explicit help, structured output, boundary validation, dry-run before writes, safe re-execution, and meaningful exit codes. Use when creating or changing command-line tools, scripts, scaffolds, hooks, or automation that an agent or unattended process will operate.
---

# Agent CLI Design

Design command-line tools as reliable interfaces for both humans and agents.

## Contract

- Provide explicit `--help` with examples and exit behavior.
- Support structured output such as `--output json` or `--format json` for
  machine consumers. Keep human output readable when attached to a terminal.
- Validate inputs at the boundary and report the invalid field plus a correction.
- Prefer environment variables for secrets and deployment-specific values.
- Provide `--dry-run` before writes, network calls, migrations, or destructive
  actions when the operation can change state.
- Make repeated execution safe. Inspect existing state before overwriting it.
- Exit non-zero on failure and preserve the underlying cause in the message.
- Emit progress before slow or consequential actions so an agent can observe
  what is happening.

## Data and context

- Accept JSON input when the command has more than a few structured arguments.
- Support filters, field selection, bounded output, and pagination for large data.
- Keep logs free of tokens, private paths, transcript content, and personal data.
- Use stable keys and schemas rather than parsing human-oriented output.
- Include a `--describe` or equivalent machine-readable contract when the tool
  exposes multiple operations.

## Implementation preferences

- Python: use `uv`, typed functions, `pathlib`, standard-library solutions first,
  and a small PEP 723 script when a standalone utility is enough.
- Shell: quote variables, use strict mode, avoid fragile text parsing for JSON,
  and make the default operation non-destructive.
- Keep the happy path linear. Extract an abstraction only when it removes real
  duplication or makes a contract easier to verify.

## Verification

Test help, valid input, malformed input, empty input, repeated execution,
`--dry-run`, and failure exit codes. Verify JSON output parses as JSON and that
no secret or absolute workstation path appears in output.

