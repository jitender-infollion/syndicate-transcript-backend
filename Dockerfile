# syntax=docker/dockerfile:1.7
FROM python:3.13.5-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pinned Astral uv binary for fast, hash-verified installs.
COPY --from=ghcr.io/astral-sh/uv:0.11.27@sha256:4d01caf3b22dfd11003455e2e68153da08c4ee1fa54fdbd166c6282d22693419 /uv /usr/local/bin/uv

COPY requirements.lock.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --require-hashes -r requirements.lock.txt

COPY --chown=1001:1001 src ./src

USER 1001
WORKDIR /app/src
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
