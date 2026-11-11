import pytest

from refactor_dashboard import cli
from refactor_dashboard.config import Settings
from refactor_dashboard.history import HistoryStore

REPLY = "```python\nx = 1\n```\nSummary:\n- Added spaces."


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", ollama_model="test-model")
    prompts = []

    async def fake_generate(self, prompt, model=None):
        prompts.append((prompt, model))
        return REPLY

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.OllamaClient, "generate", fake_generate)
    src = tmp_path / "thing.py"
    src.write_text("x=1\n")
    return settings, src, prompts


def test_prints_code_and_summary_and_saves_history(cli_env, capsys):
    settings, src, prompts = cli_env
    assert cli.main([str(src), "-i", "tidy"]) == 0
    out, err = capsys.readouterr()
    assert out == "x = 1\n"
    assert "- Added spaces." in err
    assert "tidy" in prompts[0][0] and "python" in prompts[0][0]
    assert src.read_text() == "x=1\n"  # untouched without --write

    [row] = HistoryStore(settings.history_db_path).list()
    assert row["source"] == "cli"
    assert row["filename"].endswith("thing.py")
    assert row["model"] == "test-model"


def test_write_and_no_history(cli_env, capsys):
    settings, src, _ = cli_env
    assert cli.main([str(src), "--write", "--no-history", "-q"]) == 0
    assert src.read_text() == "x = 1\n"
    assert capsys.readouterr() == ("", "")
    assert HistoryStore(settings.history_db_path).list() == []


def test_diff(cli_env, capsys):
    _, src, _ = cli_env
    assert cli.main([str(src), "--diff", "-q"]) == 0
    out = capsys.readouterr().out
    assert "-x=1" in out and "+x = 1" in out


def test_history_and_show(cli_env, capsys):
    _, src, _ = cli_env
    cli.main([str(src), "-q"])
    capsys.readouterr()
    assert cli.main(["--history"]) == 0
    assert "thing.py" in capsys.readouterr().out
    assert cli.main(["--show", "1"]) == 0
    assert capsys.readouterr().out == "x = 1\n"
    assert cli.main(["--show", "99"]) == 1


def test_missing_file(cli_env, capsys):
    assert cli.main(["nope.py"]) == 1
    assert "not a file" in capsys.readouterr().err


def test_ollama_failure(cli_env, monkeypatch, capsys):
    _, src, _ = cli_env

    async def boom(self, prompt, model=None):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(cli.OllamaClient, "generate", boom)
    assert cli.main([str(src)]) == 1
    assert "connection refused" in capsys.readouterr().err
