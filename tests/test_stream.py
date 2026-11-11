import json

import httpx

from refactor_dashboard.ollama import OllamaClient, get_ollama_client
from refactor_dashboard.presets import PRESETS_BY_ID


def events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_stream_emits_tokens_then_done(client, ollama_calls):
    response = client.post("/refactor/stream", json={"code": "print( 'hi' )", "language": "python"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")

    evts = events(response)
    assert evts[0] == {"type": "start", "model": "test-model"}
    assert "".join(e["text"] for e in evts if e["type"] == "token") == "```python\nprint('hi')\n```"
    done = evts[-1]
    assert done["type"] == "done"
    assert done["code"] == "print('hi')"
    assert done["raw"] == "```python\nprint('hi')\n```"
    assert done["stats"] == {"eval_count": 12, "duration_ms": 3500, "tokens_per_second": 6.0}

    url, body = ollama_calls[0]
    assert url == "http://ollama.test:11434/api/generate"
    assert body["stream"] is True
    assert body["model"] == "test-model"


def test_stream_uses_requested_model_and_preset(client, ollama_calls):
    client.post(
        "/refactor/stream",
        json={"code": "x = 1", "language": "python", "model": "another:3b", "preset": "optimize"},
    )
    _, body = ollama_calls[0]
    assert body["model"] == "another:3b"
    assert PRESETS_BY_ID["optimize"].instruction in body["prompt"]


def test_custom_instruction_overrides_preset(client, ollama_calls):
    client.post(
        "/refactor/stream",
        json={"code": "x = 1", "language": "python", "preset": "custom", "instruction": "use walrus"},
    )
    assert "Task: use walrus" in ollama_calls[0][1]["prompt"]


def test_stream_separates_inline_thinking(client, ollama_stream):
    ollama_stream["chunks"] = [
        {"response": "<thi"},
        {"response": "nk>plan it</th"},
        {"response": "ink>\n```python\ny = 2\n```"},
        {"response": "", "done": True},
    ]
    evts = events(client.post("/refactor/stream", json={"code": "y=2", "language": "python"}))
    assert "".join(e["text"] for e in evts if e["type"] == "thinking") == "plan it"
    assert "<think>" not in "".join(e["text"] for e in evts if e["type"] == "token")
    assert evts[-1]["code"] == "y = 2"


def test_stream_passes_through_separate_thinking_field(client, ollama_stream):
    ollama_stream["chunks"] = [
        {"response": "", "thinking": "hmm"},
        {"response": "```python\nz = 3\n```", "done": True},
    ]
    evts = events(client.post("/refactor/stream", json={"code": "z=3", "language": "python"}))
    assert {"type": "thinking", "text": "hmm"} in evts
    assert evts[-1]["code"] == "z = 3"


def test_stream_reports_ollama_http_error(client, ollama_stream):
    ollama_stream["status"] = 404
    ollama_stream["chunks"] = [{"error": "model 'nope' not found"}]
    evts = events(client.post("/refactor/stream", json={"code": "x", "language": "python"}))
    assert evts[-1] == {"type": "error", "message": "Ollama returned 404: model 'nope' not found"}


def test_stream_reports_midstream_error(client, ollama_stream):
    ollama_stream["chunks"] = [{"response": "```py"}, {"error": "out of memory"}]
    evts = events(client.post("/refactor/stream", json={"code": "x", "language": "python"}))
    assert evts[-1] == {"type": "error", "message": "out of memory"}
    assert not any(e["type"] == "done" for e in evts)


def test_stream_reports_unreachable_ollama(client, settings):
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    client.app.dependency_overrides[get_ollama_client] = lambda: OllamaClient(
        settings, transport=httpx.MockTransport(refuse)
    )
    evts = events(client.post("/refactor/stream", json={"code": "x", "language": "python"}))
    assert evts[-1]["type"] == "error"
    assert "Could not reach Ollama at http://ollama.test:11434" in evts[-1]["message"]


def test_stream_rejects_empty_code(client):
    assert client.post("/refactor/stream", json={"code": "", "language": "python"}).status_code == 422


def test_models_lists_installed(client):
    data = client.get("/api/models").json()
    assert data["default"] == "test-model"
    assert data["error"] is None
    assert [m["name"] for m in data["models"]] == ["another:3b", "test-model"]
    assert data["models"][1]["parameter_size"] == "7B"


def test_models_reports_error_with_default(client, ollama_tags):
    ollama_tags["status"] = 500
    ollama_tags["body"] = {"error": "boom"}
    data = client.get("/api/models").json()
    assert data == {"models": [], "default": "test-model", "error": "Ollama returned 500: boom"}


def test_presets(client):
    data = client.get("/api/presets").json()
    assert data["default"] == "simplify"
    assert [p["label"] for p in data["presets"]] == [
        "Simplify",
        "Optimize performance",
        "Add types/docs",
        "Custom",
    ]


def test_vendor_assets_served(client):
    for path in (
        "/static/vendor/diff-5.2.0.min.js",
        "/static/vendor/highlight-11.9.0.min.js",
        "/static/vendor/hljs-github-dark.min.css",
    ):
        assert client.get(path).status_code == 200
