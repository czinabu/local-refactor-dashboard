"""Request and response models for the HTTP API."""

from pydantic import BaseModel, Field

DEFAULT_INSTRUCTION = (
    "Refactor this code to be cleaner, more efficient, and add comments. Output only the code."
)


class RefactorRequest(BaseModel):
    code: str = Field(min_length=1)
    language: str
    # Free-text instruction. When empty, the preset's instruction is used.
    instruction: str | None = None
    # One of the ids from GET /api/presets (e.g. "simplify").
    preset: str | None = None
    # Ollama model name; defaults to the configured OLLAMA_MODEL.
    model: str | None = None
