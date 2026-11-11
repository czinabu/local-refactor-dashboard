import json

from refactor_dashboard.config import Settings
from refactor_dashboard.history import get_history_store


def events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_stream_done_has_summary_and_saves_history(client, ollama_stream, history):
    ollama_stream["chunks"][2] = {"response": "```\n\nSummary:\n- Fixed spacing.", "done": False}
    response = client.post(
        "/refactor/stream",
        json={"code": "print( 'hi' )", "language": "python", "preset": "simplify", "filename": "hi.py"},
    )
    done = events(response)[-1]
    assert done["type"] == "done"
    assert done["code"] == "print('hi')"
    assert done["summary"] == "- Fixed spacing."
    assert done["history_id"] == 1

    entry = history.get(1)
    assert entry.source == "web"
    assert entry.filename == "hi.py"
    assert entry.model == "test-model"
    assert entry.original_code == "print( 'hi' )"
    assert entry.refactored_code == "print('hi')"
    assert entry.summary == "- Fixed spacing."
    assert "Simplify" in entry.instruction


def test_prompt_asks_for_summary(client, ollama_calls):
    client.post("/refactor", json={"code": "x = 1", "language": "python"})
    assert "Summary:" in ollama_calls[0][1]["prompt"]


def test_save_history_false_skips_saving(client, history):
    response = client.post("/refactor", json={"code": "x = 1", "language": "python", "save_history": False})
    assert response.json()["history_id"] is None
    assert history.list() == []


def test_history_api(client):
    for _ in range(3):
        client.post("/refactor", json={"code": "x = 1", "language": "python"})

    items = client.get("/api/history", params={"limit": 2}).json()
    assert items["enabled"] is True
    assert [i["id"] for i in items["items"]] == [3, 2]
    assert "original_code" not in items["items"][0]

    entry = client.get("/api/history/1").json()
    assert entry["original_code"] == "x = 1"
    assert entry["refactored_code"] == "print('hi')"

    assert client.delete("/api/history/1").json() == {"deleted": 1}
    assert client.get("/api/history/1").status_code == 404
    assert client.delete("/api/history/1").status_code == 404
    assert client.delete("/api/history").json() == {"deleted": 2}
    assert client.get("/api/history").json()["items"] == []


def test_history_disabled(client):
    client.app.dependency_overrides[get_history_store] = lambda: None
    assert client.get("/api/history").json() == {"enabled": False, "items": []}
    assert client.get("/api/history/1").status_code == 404
    response = client.post("/refactor", json={"code": "x = 1", "language": "python"})
    assert response.json()["history_id"] is None


def test_get_history_store_respects_settings(tmp_path, monkeypatch):
    from refactor_dashboard import history as history_module

    monkeypatch.setattr(
        history_module,
        "get_settings",
        lambda: Settings(_env_file=None, data_dir=tmp_path, history_enabled=False),
    )
    assert get_history_store() is None
    monkeypatch.setattr(history_module, "get_settings", lambda: Settings(_env_file=None, data_dir=tmp_path))
    assert get_history_store().path == tmp_path / "history.db"
