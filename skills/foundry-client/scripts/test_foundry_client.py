"""Offline unit tests for foundry_client. Run: uv run pytest test_foundry_client.py"""

import pytest

import foundry_client as fc

PROXY = "https://llm-proxy.example.com"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_TOKEN", "x")
    monkeypatch.setenv("LLMFOUNDRY_BASE_URL", PROXY)
    monkeypatch.delenv("LLMFOUNDRY_PROJECT", raising=False)
    monkeypatch.delenv("LLMFOUNDRY_LOG", raising=False)


def test_endpoint_shape():
    client = fc.FoundryClient(provider="openai")
    assert client._endpoint("v1/chat/completions") == f"{PROXY}/openai/v1/chat/completions"


def test_base_url_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_BASE_URL", "https://other-proxy.example.com/")
    client = fc.FoundryClient(provider="gemini")
    assert client.base_url == "https://other-proxy.example.com"
    assert client._endpoint("models").startswith("https://other-proxy.example.com/gemini/")


def test_base_url_requires_env(monkeypatch):
    monkeypatch.delenv("LLMFOUNDRY_BASE_URL", raising=False)
    with pytest.raises(EnvironmentError, match="LLMFOUNDRY_BASE_URL"):
        fc._base_url()


def test_token_requires_env(monkeypatch):
    monkeypatch.delenv("LLMFOUNDRY_TOKEN", raising=False)
    with pytest.raises(EnvironmentError, match="LLMFOUNDRY_TOKEN"):
        fc._token()


def test_token_project_suffix(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_TOKEN", "tok")
    monkeypatch.setenv("LLMFOUNDRY_PROJECT", "proj")
    assert fc._token() == "tok:proj"


def test_headers_bearer(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_TOKEN", "tok")
    headers = fc.FoundryClient()._headers()
    assert headers["Authorization"] == "Bearer tok"
    assert headers["Content-Type"] == "application/json"
