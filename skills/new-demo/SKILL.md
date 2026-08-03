---
name: new-demo
description: >
  Scaffold a new LLM demo or POC in the house style: FastAPI backend wired to the
  Foundry client, a light vanilla-JS + Bootstrap SPA, a thin CLAUDE.md, GitLab CI,
  and todo/changelog. Use whenever starting a new demo, POC, prototype, or small
  LLM web app, instead of rebuilding the stack from scratch. Pairs with the
  foundry-client skill.
---

# new-demo

Stand up a new LLM demo with one command instead of reassembling the same
"Foundry + FastAPI + dashboard" stack by hand (it has been rebuilt ~16 times).

## When to use

- Starting any new demo, POC, prototype, or small LLM-backed web app.
- You are about to create a fresh FastAPI project with an LLM call and a simple UI.

## Usage

```bash
# from this skill folder, or with scaffold.py on PATH
python scaffold.py my-demo --dir ~/Desktop/gitlab --title "My Demo"
```

This creates `~/Desktop/gitlab/my-demo/` with:

```
pyproject.toml          uv project, pinned deps (fastapi, uvicorn, httpx)
README.md               setup + run + test
CLAUDE.md               thin, project-specific; defers to global ~/.claude/CLAUDE.md
todo.md  changelog.md   discipline files, pre-seeded
.gitlab-ci.yml          smoke test on MRs and branches
.gitignore
app/main.py             FastAPI: GET /, /api/health, POST /api/chat
app/static/index.html   Bootstrap SPA
app/static/app.js       fetch -> /api/chat
app/foundry_client.py   copied from the foundry-client skill if present
tests/test_smoke.py     app imports + health endpoint (no network)
```

## After scaffolding

```bash
cd ~/Desktop/gitlab/my-demo
uv sync
export LLMFOUNDRY_TOKEN="..."
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000
uv run pytest -q                         # smoke test
```

## Conventions baked in

- All LLM calls go through `foundry_client` (the foundry-client skill). No bespoke
  Foundry calls.
- uv only, Python >=3.11, FastAPI + light vanilla-JS SPA.
- No em dashes anywhere in generated files.
- todo.md and changelog.md created and expected to stay current.
- CLAUDE.md stays thin and defers global rules to `~/.claude/CLAUDE.md`.
- The scaffold refuses to overwrite an existing folder.

## Dependency

Install the `foundry-client` skill alongside this one (or keep both in the same
skills directory) so `scaffold.py` can vendor `foundry_client.py` automatically.
If it is missing, the scaffold writes a stub and tells you to replace it.
```
