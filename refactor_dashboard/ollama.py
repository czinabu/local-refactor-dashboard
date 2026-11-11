"""Minimal async client for the Ollama HTTP API."""

import json
from collections.abc import AsyncIterator

import httpx

from .config import Settings, get_settings


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns an error."""


class OllamaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport

    def _url(self, path: str) -> str:
        return f"{self.settings.ollama_base_url.rstrip('/')}{path}"

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

    async def stream_generate(self, prompt: str, model: str | None = None) -> AsyncIterator[dict]:
        """Yield Ollama's streamed /api/generate chunks as dicts.

        Each chunk carries a ``response`` text fragment (and ``thinking`` on Ollama
        versions that separate reasoning); the last one has ``done: true`` plus
        timing stats. ``ollama_timeout`` applies to the wait between chunks, so a
        long generation is fine as long as tokens keep arriving.
        """
        payload = {"model": model or self.settings.ollama_model, "prompt": prompt, "stream": True}
        timeout = httpx.Timeout(self.settings.ollama_timeout, connect=10.0)
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=timeout) as client:
                async with client.stream("POST", self.settings.ollama_generate_url, json=payload) as resp:
                    if resp.status_code != 200:
                        raise OllamaError(_error_detail(resp.status_code, await resp.aread()))
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        if chunk.get("error"):
                            raise OllamaError(chunk["error"])
                        yield chunk
        except httpx.TimeoutException as exc:
            raise OllamaError(
                f"Ollama stopped responding (no output for {self.settings.ollama_timeout:g}s)"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"Could not reach Ollama at {self.settings.ollama_base_url}: {exc}") from exc

    async def list_models(self) -> list[dict]:
        """Return the models installed in Ollama (from /api/tags), sorted by name."""
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=5.0) as client:
                response = await client.get(self._url("/api/tags"))
        except httpx.HTTPError as exc:
            raise OllamaError(f"Could not reach Ollama at {self.settings.ollama_base_url}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(_error_detail(response.status_code, response.content))

        models = []
        for m in response.json().get("models", []):
            details = m.get("details") or {}
            models.append(
                {
                    "name": m.get("name") or m.get("model"),
                    "size": m.get("size"),
                    "parameter_size": details.get("parameter_size"),
                    "family": details.get("family"),
                    "quantization": details.get("quantization_level"),
                }
            )
        return sorted(models, key=lambda m: m["name"] or "")


def _error_detail(status: int, body: bytes) -> str:
    text = body.decode(errors="replace").strip()
    try:
        text = json.loads(text).get("error", text)
    except (ValueError, AttributeError):
        pass
    return f"Ollama returned {status}: {text}" if text else f"Ollama returned {status}"


def get_ollama_client() -> OllamaClient:
    """FastAPI dependency; override in tests to inject a fake transport."""
    return OllamaClient(get_settings())
