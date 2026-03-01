FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md
RUN pip install --no-cache-dir uv && uv sync --no-dev

COPY backend /app/backend

WORKDIR /app/backend
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
