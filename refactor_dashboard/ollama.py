"""Minimal async client for the Ollama HTTP API."""

import httpx

from .config import Settings, get_settings


class OllamaError(RuntimeError):
    """Raised when Ollama returns a non-200 response."""


class OllamaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport

    async def generate(self, prompt: str, model: str | None = None) -> str:
        """Run a single non-streaming generation and return the response text."""
        async with httpx.AsyncClient(transport=self._transport) as client:
            response = await client.post(
                self.settings.ollama_generate_url,
                json={
                    "model": model or self.settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=self.settings.ollama_timeout,
            )
        if response.status_code != 200:
            raise OllamaError("Ollama API Error")
        return response.json().get("response", "")


def get_ollama_client() -> OllamaClient:
    """FastAPI dependency; override in tests to inject a fake transport."""
    return OllamaClient(get_settings())
