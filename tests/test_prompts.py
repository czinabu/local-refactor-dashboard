from refactor_dashboard.presets import resolve_instruction
from refactor_dashboard.prompts import ThinkSplitter, build_refactor_prompt, extract_code


def test_prompt_includes_inputs():
    prompt = build_refactor_prompt("s = `x`", "javascript", "make it shorter")
    assert "Task: make it shorter" in prompt
    assert "```javascript\ns = `x`\n```" in prompt


def test_prompt_uses_longer_fence_when_code_contains_one():
    code = 'doc = """\n```py\nx\n```\n"""'
    prompt = build_refactor_prompt(code, "python", "tidy")
    assert f"````python\n{code}\n````" in prompt


def test_extract_code_from_fenced_block():
    text = "Here you go:\n```python\ndef f():\n    return 1\n```\nDone."
    assert extract_code(text) == "def f():\n    return 1"


def test_extract_code_passthrough_without_fence():
    assert extract_code("x = 1") == "x = 1"


def test_extract_code_prefers_longest_block_and_drops_thinking():
    text = "<think>```py\nnot this\n```</think>```py\ndef f():\n    return 1\n```\nUsage:\n```py\nf()\n```"
    assert extract_code(text) == "def f():\n    return 1"


def test_extract_code_handles_unterminated_fence():
    assert extract_code("```python\nx = 1\n") == "x = 1"


def test_extract_code_keeps_inner_fences_with_longer_outer_fence():
    text = '````python\ns = """\n```\n"""\n````'
    assert extract_code(text) == 's = """\n```\n"""'


def test_think_splitter_handles_split_tags():
    s = ThinkSplitter()
    out = []
    for chunk in ["a<", "think>b</thi", "nk>c<", "d"]:
        out += s.feed(chunk)
    out += s.flush()
    joined = {"thinking": "", "token": ""}
    for kind, text in out:
        joined[kind] += text
    assert joined == {"thinking": "b", "token": "ac<d"}


def test_resolve_instruction():
    assert resolve_instruction("simplify", "  mine  ", "fb") == "mine"
    assert resolve_instruction("simplify", None, "fb").startswith("Simplify")
    assert resolve_instruction("custom", "", "fb") == "fb"
    assert resolve_instruction(None, None, "fb") == "fb"
    assert resolve_instruction("unknown", None, "fb") == "fb"
