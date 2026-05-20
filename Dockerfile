FROM projectdiscovery/subfinder:latest AS subfinder

FROM ghcr.io/astral-sh/uv:python3.13-alpine AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY subdomain_watcher/ ./subdomain_watcher/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.13-alpine AS final

COPY --from=subfinder /usr/local/bin/subfinder /usr/local/bin/subfinder

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "subdomain_watcher.main"]
