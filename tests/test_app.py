def test_home_serves_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Local AI Code Refactorer" in response.text
    assert "/static/app.js" in response.text
    assert "/static/style.css" in response.text


def test_static_assets_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_refactor_success(client, ollama_calls):
    response = client.post(
        "/refactor", json={"code": "print( 'hi' )", "language": "python", "instruction": "tidy"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success", "code": "print('hi')"}

    url, body = ollama_calls[0]
    assert url == "http://ollama.test:11434/api/generate"
    assert body["model"] == "test-model"
    assert body["stream"] is False
    assert "tidy" in body["prompt"]


def test_refactor_ollama_error(client, ollama_reply):
    ollama_reply["status"] = 500
    ollama_reply["body"] = {"error": "boom"}
    response = client.post("/refactor", json={"code": "x = 1", "language": "python"})
    assert response.status_code == 500
    assert response.json() == {"status": "error", "message": "Ollama API Error"}


def test_refactor_requires_code(client):
    response = client.post("/refactor", json={"language": "python"})
    assert response.status_code == 422
