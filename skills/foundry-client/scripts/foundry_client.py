"""
foundry_client: one shared client for an OpenAI-compatible LLM proxy.

Replaces roughly 67 hand-rolled proxy integrations across projects with a single,
tested entry point. Expected URL and auth shape:
    base = $LLMFOUNDRY_BASE_URL/<provider>
    auth = Authorization: Bearer $LLMFOUNDRY_TOKEN
    transport = httpx

Design goals:
- Resilient: bounded retries with exponential backoff on transient errors.
- Useful: chat(), chat_json() (strict JSON mode), and stream() helpers.
- Observable: optional per-call cost/latency logging to a JSONL file.
- Portable: the proxy host is configuration, never baked into this file.

Dependencies: httpx only. No openai SDK required.

Env vars:
    LLMFOUNDRY_TOKEN        required. Bearer token for the proxy.
    LLMFOUNDRY_BASE_URL     required. Proxy root, e.g. https://llm-proxy.example.com
    LLMFOUNDRY_PROJECT      optional. Appended to token as "<token>:<project>" if set.
    LLMFOUNDRY_LOG          optional. Path to a JSONL usage log. Logging off if unset.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import httpx

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
TRANSIENT_STATUS = {408, 409, 429, 500, 502, 503, 504}


class FoundryError(RuntimeError):
    """Raised when the proxy returns a non-recoverable error."""


def _token() -> str:
    token = os.getenv("LLMFOUNDRY_TOKEN")
    if not token:
        raise EnvironmentError("LLMFOUNDRY_TOKEN not set")
    project = os.getenv("LLMFOUNDRY_PROJECT")
    return f"{token}:{project}" if project else token


def _base_url() -> str:
    base = os.getenv("LLMFOUNDRY_BASE_URL")
    if not base:
        raise EnvironmentError(
            "LLMFOUNDRY_BASE_URL not set. Export the proxy root, e.g. "
            "export LLMFOUNDRY_BASE_URL=https://llm-proxy.example.com"
        )
    return base.rstrip("/")


@dataclass
class FoundryClient:
    """Thin, retrying client for an OpenAI-compatible proxy endpoint.

    Usage:
        fc = FoundryClient()
        text = fc.chat("Summarize this in one line", model="gpt-4o-mini")
        data = fc.chat_json("Return {\\"sentiment\\": ...}", system="You are strict.")
        for piece in fc.stream("Tell me a story"):
            print(piece, end="", flush=True)
    """

    base_url: str = field(default_factory=_base_url)
    provider: str = "openai"            # path segment: openai, gemini, anthropic, ...
    timeout: float = 120.0
    max_retries: int = 5
    backoff_base: float = 1.5
    log_path: str | None = field(default_factory=lambda: os.getenv("LLMFOUNDRY_LOG"))

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}

    def _endpoint(self, path: str) -> str:
        return f"{self.base_url}/{self.provider}/{path.lstrip('/')}"

    # ---- core request with retry ----------------------------------------
    def _post(self, path: str, payload: dict[str, Any], *, stream: bool = False):
        url = self._endpoint(path)
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = httpx.Client(timeout=self.timeout)
                if stream:
                    return client, client.stream("POST", url, headers=self._headers(), json=payload)
                resp = client.post(url, headers=self._headers(), json=payload)
                if resp.status_code in TRANSIENT_STATUS:
                    raise httpx.HTTPStatusError("transient", request=resp.request, response=resp)
                if resp.status_code >= 400:
                    client.close()
                    raise FoundryError(f"{resp.status_code}: {resp.text[:500]}")
                client.close()
                return resp
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.backoff_base ** attempt)
        raise FoundryError(f"request failed after {self.max_retries} attempts: {last_exc}")

    def _log(self, model: str, usage: dict[str, Any], latency: float, kind: str) -> None:
        if not self.log_path:
            return
        rec = {
            "ts": time.time(),
            "id": uuid.uuid4().hex[:8],
            "kind": kind,
            "model": model,
            "latency_s": round(latency, 3),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        p = Path(self.log_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")

    # ---- public helpers --------------------------------------------------
    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> str:
        """Single-turn chat. Returns the assistant text."""
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        payload = {"model": model, "messages": messages, "temperature": temperature, **kwargs}
        t0 = time.time()
        resp = self._post("v1/chat/completions", payload)
        data = resp.json()
        self._log(model, data.get("usage", {}), time.time() - t0, "chat")
        return data["choices"][0]["message"]["content"]

    def chat_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Any:
        """Chat with strict JSON output. Returns parsed Python data."""
        text = self.chat(
            prompt,
            system=system,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            **kwargs,
        )
        return json.loads(text)

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Yield assistant text pieces as they arrive."""
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }
        client, ctx = self._post("v1/chat/completions", payload, stream=True)
        try:
            with ctx as resp:
                if resp.status_code >= 400:
                    raise FoundryError(f"{resp.status_code}: stream error")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    chunk = line[len("data: "):]
                    if chunk.strip() == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta
        finally:
            client.close()


# Module-level conveniences, so callers can do:
#   from foundry_client import chat, chat_json
# Built lazily: constructing a client reads the environment, and importing this
# module must not require it to be configured yet. Cached for the process, so a
# mid-run env change needs _client.cache_clear().
@lru_cache(maxsize=1)
def _client() -> FoundryClient:
    return FoundryClient()


def chat(*args: Any, **kwargs: Any) -> str:
    return _client().chat(*args, **kwargs)


def chat_json(*args: Any, **kwargs: Any) -> Any:
    return _client().chat_json(*args, **kwargs)


def stream(*args: Any, **kwargs: Any) -> Iterator[str]:
    return _client().stream(*args, **kwargs)


if __name__ == "__main__":
    # Smoke test: requires LLMFOUNDRY_TOKEN and LLMFOUNDRY_BASE_URL.
    print(chat("Reply with the single word: ok", model=DEFAULT_CHAT_MODEL))
