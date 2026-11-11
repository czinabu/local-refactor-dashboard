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
def ollama_stream():
    """Mutable (status_code, chunks) the fake Ollama streams back as NDJSON for stream=True requests."""
    return {
        "status": 200,
        "chunks": [
            {"response": "```python\n", "done": False},
            {"response": "print('hi')\n", "done": False},
            {"response": "```", "done": False},
            {
                "response": "",
                "done": True,
                "eval_count": 12,
                "eval_duration": 2_000_000_000,
                "total_duration": 3_500_000_000,
            },
        ],
    }


@pytest.fixture
def ollama_tags():
    """Mutable (status_code, json body) the fake Ollama answers GET /api/tags with."""
    return {
        "status": 200,
        "body": {
            "models": [
                {"name": "test-model", "size": 1, "details": {"parameter_size": "7B", "family": "qwen"}},
                {"name": "another:3b", "size": 2, "details": {"parameter_size": "3B"}},
            ]
        },
    }


@pytest.fixture
def client(settings, ollama_calls, ollama_reply, ollama_stream, ollama_tags):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            ollama_calls.append((str(request.url), None))
            return httpx.Response(ollama_tags["status"], json=ollama_tags["body"])

        body = json.loads(request.content)
        ollama_calls.append((str(request.url), body))
        if body.get("stream"):
            ndjson = "".join(json.dumps(c) + "\n" for c in ollama_stream["chunks"])
            return httpx.Response(ollama_stream["status"], content=ndjson.encode())
        return httpx.Response(ollama_reply["status"], json=ollama_reply["body"])

    fake = OllamaClient(settings, transport=httpx.MockTransport(handler))
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: fake
    with TestClient(app) as c:
        yield c
