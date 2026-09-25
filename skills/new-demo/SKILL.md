---
name: new-demo
description: Scaffolds a new LLM demo in the house stack via scripts/scaffold.py - uv project, FastAPI backend wired to foundry-client, vanilla-JS Bootstrap SPA, thin CLAUDE.md, GitLab CI, todo and changelog. Use when starting a demo, POC, prototype, or small LLM web app, or when about to create a fresh FastAPI project with an LLM call and a simple UI.
---

# new-demo

The "Foundry plus FastAPI plus dashboard" stack has been reassembled by hand
roughly 16 times. Run the scaffold instead.

```bash
uv run scripts/scaffold.py my-demo --dir ~/projects --title "My Demo"
```

It refuses to overwrite an existing folder. It vendors `foundry_client.py` from
the sibling `foundry-client` skill; if that skill is missing it writes a stub
that raises `NotImplementedError`, which must then be replaced.

## What it produces

```
pyproject.toml          uv project, pinned fastapi, uvicorn, httpx
app/main.py             GET /, GET /api/health, POST /api/chat
app/static/             Bootstrap SPA calling /api/chat
app/foundry_client.py   vendored from the foundry-client skill
tests/test_smoke.py     imports the app and hits /api/health, no network
.gitlab-ci.yml          smoke test on branches and MRs
CLAUDE.md               thin, defers to ~/.claude/CLAUDE.md
todo.md changelog.md    pre-seeded, expected to stay current
```

## Conventions the scaffold assumes

- Every LLM call goes through `foundry_client`. No bespoke Foundry calls.
- uv only, Python >=3.11, FastAPI plus a light vanilla-JS SPA.
- Plain ASCII typography in generated files.
- `todo.md` and `changelog.md` stay current as the demo evolves.

## Verify

```bash
cd ~/projects/my-demo && uv sync && uv run pytest -q
uv run uvicorn app.main:app --reload   # /api/chat needs LLMFOUNDRY_TOKEN and _BASE_URL
```
