"""Request and response models for the HTTP API."""

from pydantic import BaseModel

DEFAULT_INSTRUCTION = (
    "Refactor this code to be cleaner, more efficient, and add comments. Output only the code."
)


class RefactorRequest(BaseModel):
    code: str
    language: str
    instruction: str = DEFAULT_INSTRUCTION
