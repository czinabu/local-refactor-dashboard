# Local AI Code Refactorer

A simple web app that uses AI to refactor code for better readability, efficiency, and maintainability. Built with FastAPI, Ollama, and Python.

## 🚀 Features
- Refactor code using AI (powered by Qwen3)
- Simple and clean UI
- Works locally with minimal setup

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
  routes.py      # "/" page and POST /refactor
  ollama.py      # Ollama API client
  prompts.py     # prompt building and output cleanup
  schemas.py     # request models
  templates/     # index.html
  static/        # style.css, app.js
tests/
```

## 🧪 Development
```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

## 📝 License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.