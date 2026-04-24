# ── Builder Stage ─────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN groupadd -r appgroup -g 1001 && \
    useradd -r -u 1001 -g appgroup appuser

COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY static/ static/

RUN uv sync --frozen --no-dev

# ── Runtime Stage ─────────────────────────────────────────────────────
FROM python:3.13-slim

COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/static /app/static

RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

USER appuser

ENV PATH="/app/.venv/bin:$PATH"
ENV HOOKBOX_DATABASE_URL="sqlite+aiosqlite:////app/data/hookbox.db"

EXPOSE 8080

ENTRYPOINT ["python", "-m", "hookbox"]
