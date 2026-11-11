# Local AI Refactor Dashboard: FastAPI app image.
# Ollama runs in its own container (see docker-compose.yml) or on your host.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY refactor_dashboard ./refactor_dashboard

# Run as an unprivileged user. /data holds the refactor history (mount a volume there).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir /data && chown appuser:appuser /data
USER appuser
ENV DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=3)" || exit 1

CMD ["uvicorn", "refactor_dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"]
