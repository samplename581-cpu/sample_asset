# syntax=docker/dockerfile:1
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY backend/src ./backend/src
COPY frontend ./frontend
COPY data/seed ./data/seed

RUN uv sync --frozen --no-dev --extra watsonx \
    && mkdir -p /app/data/runtime \
    && chown -R app:app /app/data/runtime

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=3)"

CMD ["uvicorn", "helpdesk.main:app", "--app-dir", "backend/src", "--host", "0.0.0.0", "--port", "8000"]
