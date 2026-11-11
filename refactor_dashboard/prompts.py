"""Prompt construction and model output cleanup."""

import re

_CODE_BLOCK = re.compile(r"```[\w]*\n?(.*?)```", re.DOTALL)


def build_refactor_prompt(code: str, language: str, instruction: str) -> str:
    """Build the prompt sent to the model for a refactor request."""
    # Escape backticks so user code can't close the fenced block early.
    safe_code = code.replace("`", "&#96;")
    return f"""
You are an expert software engineer.
Task: {instruction}

Language: {language}

Input Code:
```{language}
{safe_code}
```

Act as an expert programmer. Observe the following program and refactor it according to the task description.
Return ONLY the refactored code block. Do not include explanations or markdown text outside the code block unless necessary for clarity.
"""


def extract_code(text: str) -> str:
    """Return the contents of the first fenced code block, or the text unchanged."""
    if "```" in text:
        match = _CODE_BLOCK.search(text)
        if match:
            return match.group(1).strip()
    return text
