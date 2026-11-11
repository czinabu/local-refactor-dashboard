from refactor_dashboard.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_model == "qwen3:14b"
    assert s.ollama_generate_url == "http://localhost:11434/api/generate"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://100.64.0.1:11434/")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    s = Settings(_env_file=None)
    assert s.ollama_generate_url == "http://100.64.0.1:11434/api/generate"
    assert s.ollama_model == "qwen2.5-coder:7b"
