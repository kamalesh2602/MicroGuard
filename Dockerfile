FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project --python 3.12

COPY gateway ./gateway
COPY services ./services

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]