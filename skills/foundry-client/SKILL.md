---
name: foundry-client
description: Tested Python client for an OpenAI-compatible LLM proxy, providing chat, strict-JSON, and streaming calls with Bearer auth, backoff retries, and usage logging. Use when a project calls an LLM through a proxy or gateway, or when about to write httpx or requests code against an LLM endpoint, or on seeing LLMFOUNDRY_TOKEN or LLMFOUNDRY_BASE_URL.
---

# foundry-client

One client for the LLM proxy. The same integration was hand-rolled across
roughly 67 files before this existed. Import `scripts/foundry_client.py` instead
of writing a new one, and replace any bespoke proxy call found in a project.

## Use it

Copy `scripts/foundry_client.py` into the project, or add this folder to the
import path. It needs only `httpx`.

```python
from foundry_client import chat, chat_json, stream, FoundryClient

chat("Summarize this in one line", model="gpt-4o-mini")       # -> str
chat_json('Return {"sentiment": "pos|neg|neu"}')              # -> parsed Python
for piece in stream("Tell me a story"): ...                   # -> yields str
FoundryClient(provider="gemini", timeout=600)                 # configured client
```

Retries use bounded exponential backoff on 408, 409, 429, 5xx, and transport
errors. `chat_json()` enforces JSON mode and parses the result.

## Environment

`LLMFOUNDRY_TOKEN` and `LLMFOUNDRY_BASE_URL` are both required; the proxy host
is deliberately not baked into the file. Optional: `LLMFOUNDRY_PROJECT`
(appended as `token:project`) and `LLMFOUNDRY_LOG` (path for a per-call JSONL
log of tokens and latency).

```bash
export LLMFOUNDRY_TOKEN="..."
export LLMFOUNDRY_BASE_URL="https://llm-proxy.example.com"
```

Importing the module does not read the environment; the first call does. Never
hard-code the token or base URL.

## Defaults

- Default to `gpt-4o-mini` unless the task needs a larger model.
- Prefer `chat_json()` over parsing `chat()` output by hand.

## Verify

```bash
# offline, no credentials, leaves no cache or bytecode in the skill folder
PYTHONDONTWRITEBYTECODE=1 uv run pytest scripts/test_foundry_client.py -q -p no:cacheprovider
LLMFOUNDRY_TOKEN=... LLMFOUNDRY_BASE_URL=... uv run scripts/foundry_client.py   # prints "ok"
```
