"""Offline unit tests for foundry_client. Run: uv run pytest test_foundry_client.py"""

import os
import pytest

import foundry_client as fc


def test_endpoint_shape(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_TOKEN", "x")
    monkeypatch.delenv("LLMFOUNDRY_BASE_URL", raising=False)
    client = fc.FoundryClient(provider="openai")
    assert client._endpoint("v1/chat/completions") == (
        "https://llmfoundry.straive.com/openai/v1/chat/completions"
    )


def test_base_url_override(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_BASE_URL", "https://llmfoundry.straivedemo.com/")
    client = fc.FoundryClient(provider="gemini")
    assert client.base_url == "https://llmfoundry.straivedemo.com"
    assert client._endpoint("models").startswith("https://llmfoundry.straivedemo.com/gemini/")


def test_token_requires_env(monkeypatch):
    monkeypatch.delenv("LLMFOUNDRY_TOKEN", raising=False)
    with pytest.raises(EnvironmentError):
        fc._token()


def test_token_project_suffix(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_TOKEN", "tok")
    monkeypatch.setenv("LLMFOUNDRY_PROJECT", "proj")
    assert fc._token() == "tok:proj"


def test_headers_bearer(monkeypatch):
    monkeypatch.setenv("LLMFOUNDRY_TOKEN", "tok")
    monkeypatch.delenv("LLMFOUNDRY_PROJECT", raising=False)
    headers = fc.FoundryClient()._headers()
    assert headers["Authorization"] == "Bearer tok"
    assert headers["Content-Type"] == "application/json"
