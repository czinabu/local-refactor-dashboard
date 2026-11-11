"""Application settings, read from environment variables or a local .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Base URL of the Ollama server, without a path (e.g. http://localhost:11434).
    ollama_base_url: str = "http://localhost:11434"
    # Model used for refactoring requests.
    ollama_model: str = "qwen3:14b"
    # Seconds to wait for Ollama before giving up.
    ollama_timeout: float = 60.0
    # Folder for local data such as the refactor history database.
    data_dir: Path = Path.home() / ".local-refactor-dashboard"
    # Set to false to stop saving refactors to the local history.
    history_enabled: bool = True

    @property
    def ollama_generate_url(self) -> str:
        return f"{self.ollama_base_url.rstrip('/')}/api/generate"

    @property
    def history_db_path(self) -> Path:
        return self.data_dir.expanduser() / "history.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
