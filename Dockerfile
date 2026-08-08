FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --frozen --no-dev && rm -rf /root/.cache/uv

ENV PATH="/app/.venv/bin:$PATH" \
    SHERLOCK_BRAIN_DATA_DIR=/data \
    HOME=/data

RUN mkdir -p /data

CMD ["python", "-m", "sherlock_second_brain.server"]
