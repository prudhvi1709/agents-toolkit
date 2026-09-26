# Agents Toolkit

Reusable skills, hooks, scripts, and workflow accelerators for coding and
non-coding agents.

## Contents

- `skills/` contains task-specific agent instructions and supporting code.
- `hooks/` contains lifecycle hooks that can be adapted to an agent runtime.
- `scripts/` contains small utilities for agent status, workflow visibility, and
  validating skill folders against the spec.
- `agent-config/` contains the canonical shared skills/MCP synchronization
  manifest for Claude Code, Claude Desktop, and Codex.

Run `scripts/agent-sync.py audit` to inspect drift or
`scripts/agent-sync.py sync` to apply the shared configuration.

### Syncing agents

The repository is the source of truth for shared skills and MCPs:

```bash
./scripts/agent-sync.py audit  # read-only drift check
./scripts/agent-sync.py sync   # link skills and merge MCP entries
```

The sync command updates Claude Code, Claude Desktop, and Codex without
copying credentials. OAuth/API authentication remains local to each client.
Conflicting global skill folders are moved to `~/.agent-sync-backups/` before
they are replaced with links to this repository.

Before uploading changes to GitHub, run:

```bash
./scripts/agent-sync.py audit
python3 -m py_compile scripts/agent-sync.py
jq empty agent-config/mcps.json
git diff --check
git status --short
```

Review the final diff and confirm that reports, logs, credentials, local
settings, and backup directories are not included. Then commit and push from
the repository owner account.

## Skills

### Original

- `caffeinate` for unattended overnight runs, with power, disk, deadline, and
  process-tree guardrails.
- `foundry-client` for calling an OpenAI-compatible LLM proxy with retries,
  strict-JSON mode, and usage logging.
- `new-demo` for scaffolding a FastAPI and vanilla-JS LLM demo project.
- `transcript-to-todo` for turning a meeting transcript into a structured todo
  list that separates decisions from suggestions.

### Adapted from upstream workflows

- `decision-lens` for difficult decisions, reviews, diagnosis, and strategy.
- `agent-cli-design` for reliable tools, scripts, scaffolds, and hooks.
- `investigative-analysis` for evidence-backed data investigation.
- `decision-visualization` for honest charts, dashboards, tables, and maps.
- `playwright-verification` for console, network, accessibility, and responsive
  checks against a live page, with a bundled Playwright script that exits
  non-zero so a run can be gated.
- `document-pipeline` for PDF and document extraction, generation, and review.
- `delivery-review` for concise post-task learning after complex work.
- `interactive-explanation` for simulations, scrollytelling, and explorable stories.

These skills were inspired by the agent workflows in
[sanand0/scripts](https://github.com/sanand0/scripts/tree/live/agents), then
rewritten and adapted for this toolkit's preferences, workflows, and portability
requirements. They are not vendored copies of the upstream skills.

| Upstream concept | This toolkit |
| --- | --- |
| `expert-lens` | `decision-lens` |
| `agent-friendly-cli` | `agent-cli-design` |
| `data-analysis` | `investigative-analysis` |
| `data-viz` | `decision-visualization` |
| `devtools` | `playwright-verification` |
| `pdf` | `document-pipeline` |
| `post-mortem` | `delivery-review` |
| `interactive-storytelling` | `interactive-explanation` |

## Validating skills

`scripts/validate_skills.py` checks skill folders against the Agent Skills spec:
frontmatter, name and description shape, body length, layout, unreferenced
bundled files, and a signal-density heuristic that flags a skill made only of
advice a capable model already follows.

```bash
uv run scripts/validate_skills.py skills                 # findings
uv run scripts/validate_skills.py skills --score         # ranked against the guidance
uv run scripts/validate_skills.py skills --score --detail # per-criterion breakdown
uv run scripts/validate_skills.py skills --output json   # machine-readable
```

The scoring criteria come from the spec and Anthropic's authoring guidance; the
weights are a judgement call, so treat the numbers as relative rankings rather
than absolute grades. Exit codes: 0 clean, 1 findings at or above `--fail-on`,
2 usage error.

## Principles

- Keep secrets in environment variables, never in source or configuration files.
- Treat transcripts, session state, logs, caches, and local settings as private.
- Adapt paths and provider-specific settings before installing these tools.
- Review generated output before using it in client-facing or high-stakes work.

## License

MIT. See `LICENSE`.
