#!/usr/bin/env python3
"""
scaffold.py: stand up a new LLM demo in the house style.

Generates: FastAPI backend wired to the Foundry client, a light vanilla-JS SPA,
a thin CLAUDE.md, a GitLab CI file, todo.md / changelog.md, pyproject.toml, and
.gitignore. Conventions are baked in so every demo starts consistent.

Usage:
    python scaffold.py my-demo
    python scaffold.py my-demo --dir ~/Desktop/gitlab --title "My Demo"
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def w(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"))
    print(f"  + {path}")


def pyproject(name: str) -> str:
    return f"""
[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["fastapi>=0.110", "uvicorn>=0.29", "httpx>=0.27"]

[dependency-groups]
dev = ["pytest>=8"]
"""


def main_py() -> str:
    return '''
"""FastAPI app: serves a small SPA and a /api/chat endpoint backed by Foundry."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .foundry_client import chat

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="demo")


class Ask(BaseModel):
    prompt: str
    model: str = "gpt-4o-mini"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
def api_chat(ask: Ask) -> dict:
    return {"reply": chat(ask.prompt, model=ask.model)}


app.mount("/", StaticFiles(directory=STATIC), name="static")
'''


def index_html(title: str) -> str:
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
  <main class="container py-5" style="max-width:720px">
    <h1 class="h3 mb-1">{title}</h1>
    <p class="text-muted">FastAPI + Foundry demo. THIS IS A DEMO.</p>
    <div class="input-group my-3">
      <input id="prompt" class="form-control" placeholder="Ask something...">
      <button id="send" class="btn btn-primary">Send</button>
    </div>
    <pre id="out" class="p-3 bg-white border rounded" style="white-space:pre-wrap"></pre>
  </main>
  <script src="/app.js"></script>
</body>
</html>
'''


def app_js() -> str:
    return '''
const $ = (id) => document.getElementById(id);
async function ask() {
  const prompt = $("prompt").value.trim();
  if (!prompt) return;
  $("out").textContent = "...";
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const data = await r.json();
    $("out").textContent = data.reply ?? JSON.stringify(data);
  } catch (e) {
    $("out").textContent = "Error: " + e;
  }
}
$("send").addEventListener("click", ask);
$("prompt").addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
'''


def claude_md(title: str) -> str:
    return f"""
# {title}

LLM demo: FastAPI backend, vanilla-JS + Bootstrap SPA, Foundry for inference.

## Conventions
- Never use em dashes or en dashes. Use commas, colons, periods, or a plain hyphen.
- Python: uv only. Run with `uv run`. No bare pip.
- All LLM calls go through `foundry_client` (do not hand-roll a Foundry call).
- Secrets (LLMFOUNDRY_TOKEN) come from env, never committed.
- Keep this thin. Only project-specific notes here; global rules live in ~/.claude/CLAUDE.md.

## Discipline
- Keep todo.md and changelog.md current.
- Never run `git commit` or `git push` unless explicitly asked.

## Run
```bash
uv run uvicorn app.main:app --reload
```
"""


def gitlab_ci() -> str:
    return """
stages: [test]
smoke:
  stage: test
  image: python:3.11-slim
  script:
    - pip install uv
    - uv run pytest -q
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH'
"""


def test_smoke() -> str:
    return '''
"""Smoke test: app imports and health endpoint responds. No network/LLM call."""
import os
os.environ.setdefault("LLMFOUNDRY_TOKEN", "test")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
'''


def gitignore() -> str:
    return """
__pycache__/
*.pyc
.venv/
.env
*.jsonl
.DS_Store
"""


def readme(title: str) -> str:
    return f"""
# {title}

A small LLM demo: FastAPI + a vanilla-JS SPA, inference via the Straive Foundry proxy.

## Setup
```bash
uv sync
export LLMFOUNDRY_TOKEN="..."
uv run uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

## Test
```bash
uv run pytest -q
```
"""


def vendor_foundry(dest_app: Path) -> None:
    """Copy foundry_client.py from the sibling foundry-client skill if present."""
    candidates = [
        HERE.parent / "foundry-client" / "foundry_client.py",
        HERE / "foundry_client.py",
    ]
    for src in candidates:
        if src.exists():
            shutil.copy(src, dest_app / "foundry_client.py")
            print(f"  + {dest_app / 'foundry_client.py'} (from {src.name})")
            return
    w(
        dest_app / "foundry_client.py",
        '# Install the foundry-client skill and copy its foundry_client.py here.\n'
        'def chat(*a, **k):\n    raise NotImplementedError("Add foundry_client from the foundry-client skill")\n',
    )
    print("  ! foundry-client skill not found next to scaffold; wrote a stub. Replace it.")


def build(name: str, base: Path, title: str) -> Path:
    root = base.expanduser() / name
    if root.exists():
        sys.exit(f"refusing to overwrite existing path: {root}")
    print(f"Scaffolding {root}")
    w(root / "pyproject.toml", pyproject(name))
    w(root / "README.md", readme(title))
    w(root / "CLAUDE.md", claude_md(title))
    w(root / "todo.md", f"# todo\n\n- [ ] First task for {title}\n")
    w(root / "changelog.md", f"# changelog\n\n## {date.today().isoformat()}\n- Scaffolded {title}.\n")
    w(root / ".gitlab-ci.yml", gitlab_ci())
    w(root / ".gitignore", gitignore())
    w(root / "app" / "__init__.py", "")
    w(root / "app" / "main.py", main_py())
    w(root / "app" / "static" / "index.html", index_html(title))
    w(root / "app" / "static" / "app.js", app_js())
    w(root / "tests" / "test_smoke.py", test_smoke())
    vendor_foundry(root / "app")
    print("\nNext:")
    print(f"  cd {root}")
    print("  uv sync && export LLMFOUNDRY_TOKEN=... && uv run uvicorn app.main:app --reload")
    return root


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("name", help="project folder name (kebab-case)")
    p.add_argument("--dir", default=".", help="parent directory (default: current)")
    p.add_argument("--title", help="human title (default: derived from name)")
    return p.parse_args()


if __name__ == "__main__":
    args = cli()
    title = args.title or args.name.replace("-", " ").replace("_", " ").title()
    build(args.name, Path(args.dir), title)
