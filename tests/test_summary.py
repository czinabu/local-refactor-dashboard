from refactor_dashboard.languages import detect_language
from refactor_dashboard.prompts import split_code_and_summary


def test_split_code_and_summary():
    raw = "```python\nx = 1\n```\n\nSummary:\n- Added spaces around `=`.\n- Nothing else."
    assert split_code_and_summary(raw) == ("x = 1", "- Added spaces around `=`.\n- Nothing else.")


def test_split_handles_markdown_heading_and_think_block():
    raw = "<think>hmm ```not code```</think>\n```py\nx = 1\n```\n## Summary\n- Tidied."
    assert split_code_and_summary(raw) == ("x = 1", "- Tidied.")


def test_split_without_code_block():
    assert split_code_and_summary("x = 1") == ("x = 1", "")


def test_split_without_summary():
    assert split_code_and_summary("```python\nx = 1\n```") == ("x = 1", "")


def test_detect_language():
    assert detect_language("app.TSX") == "typescript"
    assert detect_language("main.rs") == "rust"
    assert detect_language("README") == "text"
    assert detect_language("notes.xyz", default="python") == "python"
