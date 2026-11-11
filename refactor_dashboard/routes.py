"""HTTP routes: the dashboard page and the refactor API."""

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .ollama import OllamaClient, OllamaError, get_ollama_client
from .presets import presets_payload, resolve_instruction
from .prompts import ThinkSplitter, build_refactor_prompt, extract_code
from .schemas import DEFAULT_INSTRUCTION, RefactorRequest

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

router = APIRouter()


def _prompt_for(req: RefactorRequest) -> str:
    instruction = resolve_instruction(req.preset, req.instruction, DEFAULT_INSTRUCTION)
    return build_refactor_prompt(req.code, req.language, instruction)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get("/api/models")
async def models(ollama: OllamaClient = Depends(get_ollama_client)):
    """Installed Ollama models plus the configured default.

    Always returns 200 so the UI can fall back to the default model when Ollama is unreachable.
    """
    default = ollama.settings.ollama_model
    try:
        return {"models": await ollama.list_models(), "default": default, "error": None}
    except OllamaError as e:
        return {"models": [], "default": default, "error": str(e)}


@router.get("/api/presets")
async def presets():
    return presets_payload()


@router.post("/refactor", response_class=JSONResponse)
async def refactor_code(req: RefactorRequest, ollama: OllamaClient = Depends(get_ollama_client)):
    try:
        generated = await ollama.generate(_prompt_for(req), model=req.model)
        return JSONResponse(content={"status": "success", "code": extract_code(generated)})
    except Exception as e:  # OllamaError, network errors, bad JSON, etc.
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/refactor/stream")
async def refactor_stream(req: RefactorRequest, ollama: OllamaClient = Depends(get_ollama_client)):
    """Stream the refactor as newline-delimited JSON events.

    Events, one JSON object per line:
      {"type": "start", "model": ...}
      {"type": "thinking", "text": ...}   reasoning, for models that emit it
      {"type": "token", "text": ...}      answer text as it is generated
      {"type": "done", "code": ..., "raw": ..., "model": ..., "stats": {...}}
      {"type": "error", "message": ...}
    """
    model = req.model or ollama.settings.ollama_model
    prompt = _prompt_for(req)

    async def events() -> AsyncIterator[str]:
        def line(**event) -> str:
            return json.dumps(event) + "\n"

        yield line(type="start", model=model)
        splitter = ThinkSplitter()
        answer: list[str] = []
        started = time.monotonic()
        final: dict = {}

        def pieces(parts):
            for kind, text in parts:
                if kind == "token":
                    answer.append(text)
                yield line(type=kind, text=text)

        try:
            async for chunk in ollama.stream_generate(prompt, model=model):
                if chunk.get("thinking"):
                    yield line(type="thinking", text=chunk["thinking"])
                for out in pieces(splitter.feed(chunk.get("response", ""))):
                    yield out
                if chunk.get("done"):
                    final = chunk
            for out in pieces(splitter.flush()):
                yield out
        except OllamaError as e:
            yield line(type="error", message=str(e))
            return
        except Exception as e:  # malformed chunk, unexpected failure
            yield line(type="error", message=f"Unexpected error: {e}")
            return

        raw = "".join(answer)
        yield line(type="done", code=extract_code(raw), raw=raw, model=model, stats=_stats(final, started))

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        # Stop proxies (and uvicorn behind nginx) from buffering the stream.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _stats(final: dict, started: float) -> dict:
    eval_count = final.get("eval_count")
    eval_ns = final.get("eval_duration")
    total_ns = final.get("total_duration")
    return {
        "eval_count": eval_count,
        "duration_ms": round(total_ns / 1e6) if total_ns else round((time.monotonic() - started) * 1000),
        "tokens_per_second": round(eval_count / (eval_ns / 1e9), 1) if eval_count and eval_ns else None,
    }
