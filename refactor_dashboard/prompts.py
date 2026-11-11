"""Prompt construction and model output cleanup."""

import re

_FENCE_RUN = re.compile(r"`{3,}")
_CODE_BLOCK = re.compile(r"(`{3,})[^\n`]*\n(.*?)\1", re.DOTALL)
_THINK_BLOCK = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL)


def _fence_for(code: str) -> str:
    """A backtick fence longer than any backtick run in ``code``, so the code can't close it."""
    longest = max((len(m) for m in _FENCE_RUN.findall(code)), default=0)
    return "`" * max(3, longest + 1)


def build_refactor_prompt(code: str, language: str, instruction: str) -> str:
    """Build the prompt sent to the model for a refactor request."""
    fence = _fence_for(code)
    return f"""You are an expert {language} engineer.
Task: {instruction}

Language: {language}

Input code:
{fence}{language}
{code}
{fence}

Refactor the code according to the task.
Return ONLY the complete refactored code in a single fenced code block. Do not add explanations before or after it.
"""


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning that models such as qwen3 may emit inline."""
    return _THINK_BLOCK.sub("", text)


def extract_code(text: str) -> str:
    """Return the refactored code from a model response.

    Drops inline reasoning, then takes the longest fenced block (models sometimes
    add a short usage example). Falls back to the whole text when there is no fence.
    """
    text = strip_thinking(text).strip()
    blocks = [m.group(2) for m in _CODE_BLOCK.finditer(text)]
    if blocks:
        return max(blocks, key=len).strip()
    # An unterminated fence (e.g. generation cut off): drop the opening line.
    if text.startswith("```"):
        return text.split("\n", 1)[1].strip() if "\n" in text else ""
    return text


class ThinkSplitter:
    """Split a streamed response into reasoning and answer text.

    Models such as qwen3 wrap their reasoning in ``<think>...</think>``. Tags can be
    split across chunks, so text that might be the start of a tag is held back until
    the next chunk arrives.
    """

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self._buf = ""
        self._thinking = False

    def feed(self, chunk: str) -> list[tuple[str, str]]:
        """Return ``(kind, text)`` pieces, where kind is "thinking" or "token"."""
        self._buf += chunk
        out: list[tuple[str, str]] = []
        while self._buf:
            tag = self.CLOSE if self._thinking else self.OPEN
            kind = "thinking" if self._thinking else "token"
            idx = self._buf.find(tag)
            if idx >= 0:
                if idx:
                    out.append((kind, self._buf[:idx]))
                self._buf = self._buf[idx + len(tag) :]
                self._thinking = not self._thinking
                continue
            # Hold back a suffix that could be the beginning of the tag.
            keep = next((n for n in range(len(tag) - 1, 0, -1) if self._buf.endswith(tag[:n])), 0)
            emit = self._buf[: len(self._buf) - keep]
            if emit:
                out.append((kind, emit))
            self._buf = self._buf[len(emit) :]
            break
        return out

    def flush(self) -> list[tuple[str, str]]:
        rest, self._buf = self._buf, ""
        return [("thinking" if self._thinking else "token", rest)] if rest else []
