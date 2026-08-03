---
name: foundry-client
description: >
  Use the shared Straive LLM Foundry client instead of hand-rolling a new proxy
  integration. Trigger whenever a project needs to call an LLM through Foundry
  (chat, JSON output, or streaming) with Bearer-token auth, retries, and cost
  logging. Use when you see LLMFOUNDRY_TOKEN, llmfoundry.straive.com, or a fresh
  httpx/requests call being written to an LLM endpoint.
---

# foundry-client

One tested client for the Straive LLM Foundry proxy. This exists because the same
integration was hand-rolled in ~67 files across projects. Do not write a new one;
import this.

## When to use

- A project needs to call an LLM through Foundry.
- You are about to write `httpx`/`requests` code that posts to an LLM endpoint.
- You see `LLMFOUNDRY_TOKEN`, `llmfoundry.straive.com`, or `llmfoundry.straivedemo.com`.

## Setup

Copy `foundry_client.py` into the project (or add this skill folder to the import
path). It needs only `httpx`.

```bash
uv add httpx
export LLMFOUNDRY_TOKEN="..."            # required
# optional:
export LLMFOUNDRY_BASE_URL="https://llmfoundry.straive.com"   # or the demo domain
export LLMFOUNDRY_PROJECT="my-project"   # appended as token:project
export LLMFOUNDRY_LOG="$HOME/.foundry/usage.jsonl"  # per-call cost/latency log
```

## Usage

```python
from foundry_client import chat, chat_json, stream, FoundryClient

# simple chat
print(chat("Summarize this in one line", model="gpt-4o-mini"))

# strict JSON (parses for you)
data = chat_json(
    'Return {"sentiment": "pos|neg|neu", "score": 0..1}',
    system="You are a strict JSON API.",
)

# streaming
for piece in stream("Tell me a short story"):
    print(piece, end="", flush=True)

# a configured client (e.g. the Gemini passthrough used by the video pipeline)
gem = FoundryClient(provider="gemini", timeout=600)
```

## What it gives you

- `chat()` single-turn, returns text.
- `chat_json()` strict JSON mode, returns parsed Python.
- `stream()` yields text pieces.
- Bounded exponential-backoff retries on 408/409/429/5xx and transport errors.
- Optional JSONL usage log (tokens + latency) when `LLMFOUNDRY_LOG` is set.
- Matches the existing house pattern: `Bearer $LLMFOUNDRY_TOKEN`, base
  `https://llmfoundry.straive.com/<provider>`, `httpx` transport.

## Conventions

- Never hard-code the token or base URL. Read them from env (the client does this).
- Default to a small model (`gpt-4o-mini`) unless the task needs more.
- Prefer `chat_json()` over manual JSON parsing of `chat()` output.
- If a project still has a bespoke Foundry call, replace it with this client.

## Verify

```bash
LLMFOUNDRY_TOKEN=... uv run foundry_client.py   # prints "ok"
```
