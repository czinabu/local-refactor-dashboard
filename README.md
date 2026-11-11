# Local AI Code Refactorer

[![CI](https://github.com/czinabu/local-refactor-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/czinabu/local-refactor-dashboard/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Paste in some code, pick a language, say what you want, and a large language model running **on your own machine** rewrites it to be cleaner, faster and easier to read. Nothing leaves your network: the app talks to a local [Ollama](https://ollama.com/) server, so it works offline and your code stays private.

<!--
  DEMO PLACEHOLDER: record a short GIF (paste code -> Refactor -> result) and save it as docs/demo.gif,
  then uncomment the line below.
  <p align="center"><img src="docs/demo.gif" alt="Refactoring a Python function in the dashboard" width="800"></p>
-->

## Features

- **Local-first refactoring.** Uses any Ollama model (default `qwen3:14b`), so no API keys, no cloud and no per-token cost.
- **Language aware.** Python, JavaScript, TypeScript, Go and Rust out of the box.
- **Custom instructions.** Ask for "simplify", "add type hints", "make it faster" or anything else.
- **Clean output.** Strips the model's markdown fences so you get code you can paste straight back in.
- **Configurable.** Point it at any Ollama server (localhost, LAN or Tailscale) with environment variables or a `.env` file.
- **One-command setup.** Docker Compose starts the app and Ollama together and downloads the model for you.

<!--
  SCREENSHOT PLACEHOLDER: save a full-page screenshot as docs/screenshot.png, then uncomment.
  <p align="center"><img src="docs/screenshot.png" alt="Dashboard showing original and refactored code" width="800"></p>
-->

## Quick start (Docker)

The easiest way to run everything. You need [Docker](https://docs.docker.com/get-docker/) with Compose v2.

```bash
git clone https://github.com/czinabu/local-refactor-dashboard.git
cd local-refactor-dashboard
docker compose up -d
```

Then open **http://localhost:8000**.

On the first run, the `ollama-pull` service downloads the model (about 9 GB for `qwen3:14b`). Refactor requests will fail until it finishes. Follow its progress with:

```bash
docker compose logs -f ollama-pull
```

The model is stored in a Docker volume, so later starts are instant.

**Using a smaller or different model.** Set `OLLAMA_MODEL` in your shell or in a `.env` file next to `docker-compose.yml`:

```bash
OLLAMA_MODEL=qwen2.5-coder:7b docker compose up -d
```

**Using an NVIDIA GPU.** Install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), then add the GPU override:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

On macOS, Docker can't use the Apple GPU, so for speed run Ollama natively and use the local setup below.

**Stopping.** `docker compose down` stops everything. Add `-v` to also delete the downloaded models.

## Local setup (without Docker)

1. Install [Ollama](https://ollama.com/download) and pull a model:
   ```bash
   ollama pull qwen3:14b
   ```
2. Clone the repo and install dependencies (Python 3.10+):
   ```bash
   git clone https://github.com/czinabu/local-refactor-dashboard.git
   cd local-refactor-dashboard
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure (optional). Copy `.env.example` to `.env` and adjust the values below.
4. Run the app:
   ```bash
   uvicorn refactor_dashboard.main:app --reload
   ```
   Then open **http://localhost:8000**.

## Configuration

Settings are read from environment variables or a `.env` file in the directory you start the app from.

| Variable          | Default                  | Description                                                                 |
| ----------------- | ------------------------ | --------------------------------------------------------------------------- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL, without a path. Use a LAN or Tailscale IP for a remote GPU box. |
| `OLLAMA_MODEL`    | `qwen3:14b`              | Model used for refactoring. Must be pulled in Ollama first.                 |
| `OLLAMA_TIMEOUT`  | `60`                     | Seconds to wait for the model to respond (Docker Compose uses `120`).       |

Docker Compose also reads `APP_PORT` (default `8000`) and `OLLAMA_PORT` (default `11434`) to change the published ports.

**Ollama on another machine?** Skip the bundled Ollama container and run just the app:

```bash
docker build -t local-refactor-dashboard .
docker run --rm -p 8000:8000 -e OLLAMA_BASE_URL=http://100.x.y.z:11434 local-refactor-dashboard
```

If Ollama runs on the same host as Docker, use `http://host.docker.internal:11434` (add `--add-host=host.docker.internal:host-gateway` on Linux), and make sure Ollama listens on all interfaces (`OLLAMA_HOST=0.0.0.0`).

## How it works

```
Browser ──POST /refactor──▶ FastAPI app ──/api/generate──▶ Ollama ──▶ local LLM
   ▲                          │  builds the prompt,
   └──────── refactored code ─┘  strips markdown fences
```

The FastAPI backend serves a single-page UI, wraps your code and instruction in a refactoring prompt, sends it to Ollama's `/api/generate` endpoint, and returns just the code block from the reply.

## API

The UI is a thin client over one JSON endpoint, so you can script it too:

```bash
curl -s http://localhost:8000/refactor \
  -H 'Content-Type: application/json' \
  -d '{"code": "def f(l):\n  r=[]\n  for i in l:\n    if i%2==0: r.append(i*i)\n  return r", "language": "python", "instruction": "Simplify and add type hints."}'
```

```json
{"status": "success", "code": "def square_evens(numbers: list[int]) -> list[int]:\n    ..."}
```

Interactive API docs are at **http://localhost:8000/docs**.

## Project layout

```
refactor_dashboard/
  main.py        # app factory and entry point
  config.py      # settings (env vars / .env)
  routes.py      # "/" page and POST /refactor
  ollama.py      # Ollama API client
  prompts.py     # prompt building and output cleanup
  schemas.py     # request models
  templates/     # index.html
  static/        # style.css, app.js
tests/
Dockerfile               # app image
docker-compose.yml       # app + Ollama + one-shot model download
docker-compose.gpu.yml   # optional NVIDIA GPU override
```

## Development

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

CI runs the same checks on every pull request.

## Tech stack

[FastAPI](https://fastapi.tiangolo.com/) · [Ollama](https://ollama.com/) · [httpx](https://www.python-httpx.org/) · [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) · [Jinja2](https://jinja.palletsprojects.com/) · Docker Compose

## License

MIT. See [LICENSE](LICENSE).
