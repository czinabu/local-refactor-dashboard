# Local AI Code Refactorer

A simple web app that uses AI to refactor code for better readability, efficiency, and maintainability. Built with FastAPI, Ollama, and Python.

## 🚀 Features
- Refactor code using a local model through Ollama (Qwen3 by default)
- Output streams in as the model writes it, with the model's reasoning tucked into a collapsible section
- Side-by-side diff of original vs refactored code with syntax highlighting, plus a one-click copy button
- Model picker that lists the models installed in your Ollama (remembers your choice)
- Instruction presets: Simplify, Optimize performance, Add types/docs, or a Custom instruction
- Works fully offline: front-end libraries are bundled in `static/vendor/`

## 🛠️ Technologies Used
- [FastAPI](https://fastapi.tiangolo.com/)
- [Ollama](https://ollama.ai/)
- [Python](https://www.python.org/)

## 📦 Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/czinabu/local-refactor-dashboard.git
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure Ollama (optional). Copy `.env.example` to `.env` and set `OLLAMA_BASE_URL` if Ollama
   isn't on `http://localhost:11434` (for example, another machine on your Tailscale network), and
   `OLLAMA_MODEL` to change the model (default `qwen3:14b`).
4. Run the app:
   ```bash
   uvicorn refactor_dashboard.main:app --reload
   ```
   Then open http://localhost:8000.

## 🗂️ Project layout
```
refactor_dashboard/
  main.py        # app factory and entry point
  config.py      # settings (env vars / .env)
  routes.py      # "/" page and the API below
  ollama.py      # Ollama API client (generate, streaming, installed models)
  presets.py     # instruction presets
  prompts.py     # prompt building and output cleanup
  schemas.py     # request models
  templates/     # index.html
  static/        # style.css, app.js, vendor/ (jsdiff, highlight.js)
tests/
```

## 🔌 API
| Method & path | What it does |
| --- | --- |
| `GET /api/models` | Installed Ollama models, the configured default, and an `error` if Ollama is unreachable |
| `GET /api/presets` | Instruction presets and the default preset |
| `POST /refactor/stream` | Streams the refactor as NDJSON events: `start`, `thinking`, `token`, then `done` (with the extracted `code`, `raw` text and `stats`) or `error` |
| `POST /refactor` | Same request, non-streaming JSON response |

Request body for both refactor endpoints: `{"code": "...", "language": "python", "model": "qwen3:14b", "preset": "simplify", "instruction": null}`.
`model`, `preset` and `instruction` are optional; a non-empty `instruction` overrides the preset.

## 🧪 Development
```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

## 📝 License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.