from refactor_dashboard.prompts import build_refactor_prompt, extract_code


def test_prompt_includes_inputs_and_escapes_backticks():
    prompt = build_refactor_prompt("s = `x`", "javascript", "make it shorter")
    assert "Task: make it shorter" in prompt
    assert "```javascript" in prompt
    assert "s = &#96;x&#96;" in prompt


def test_extract_code_from_fenced_block():
    text = "Here you go:\n```python\ndef f():\n    return 1\n```\nDone."
    assert extract_code(text) == "def f():\n    return 1"


def test_extract_code_passthrough_without_fence():
    assert extract_code("x = 1") == "x = 1"
