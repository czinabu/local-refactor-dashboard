"""HTTP routes: the dashboard page and the refactor API."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .ollama import OllamaClient, get_ollama_client
from .prompts import build_refactor_prompt, extract_code
from .schemas import RefactorRequest

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.post("/refactor", response_class=JSONResponse)
async def refactor_code(req: RefactorRequest, ollama: OllamaClient = Depends(get_ollama_client)):
    try:
        prompt = build_refactor_prompt(req.code, req.language, req.instruction)
        generated = await ollama.generate(prompt)
        return JSONResponse(content={"status": "success", "code": extract_code(generated)})
    except Exception as e:  # OllamaError, network errors, bad JSON, etc.
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
