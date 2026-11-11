"""Request and response models for the HTTP API."""

from pydantic import BaseModel, Field

DEFAULT_INSTRUCTION = "Refactor this code to be cleaner, more efficient, and add comments."


class RefactorRequest(BaseModel):
    code: str = Field(min_length=1)
    language: str
    # Free-text instruction. When empty, the preset's instruction is used.
    instruction: str | None = None
    # One of the ids from GET /api/presets (e.g. "simplify").
    preset: str | None = None
    # Ollama model name; defaults to the configured OLLAMA_MODEL.
    model: str | None = None
    # Name of the uploaded file, if any; kept in the history.
    filename: str | None = Field(default=None, max_length=255)
    # Set to false to skip saving this run to the local history.
    save_history: bool = True
