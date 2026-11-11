import json

import httpx
import pytest
from fastapi.testclient import TestClient

from refactor_dashboard.config import Settings
from refactor_dashboard.main import create_app
from refactor_dashboard.ollama import OllamaClient, get_ollama_client


@pytest.fixture
def settings():
    return Settings(_env_file=None, ollama_base_url="http://ollama.test:11434", ollama_model="test-model")


@pytest.fixture
def ollama_calls():
    """Requests the fake Ollama received, as (url, json body) pairs."""
    return []


@pytest.fixture
def ollama_reply():
    """Mutable (status_code, json body) the fake Ollama answers with."""
    return {"status": 200, "body": {"response": "```python\nprint('hi')\n```"}}


@pytest.fixture
def client(settings, ollama_calls, ollama_reply):
    def handler(request: httpx.Request) -> httpx.Response:

        ollama_calls.append((str(request.url), json.loads(request.content)))
        return httpx.Response(ollama_reply["status"], json=ollama_reply["body"])

    fake = OllamaClient(settings, transport=httpx.MockTransport(handler))
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: fake
    with TestClient(app) as c:
        yield c
