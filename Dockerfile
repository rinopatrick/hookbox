# ── Builder Stage ─────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --frozen --no-dev && \
    uv run ruff check --fix src/ && \
    uv run ruff format src/

# ── Runtime Stage ─────────────────────────────────────────────────────
FROM gcr.io/distroless/python3-debian12

COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group

RUN ["/busybox/sh", "-c", "addgroup --system --gid 1001 appgroup && adduser --system --uid 1001 --ingroup appgroup appuser"]

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/static /app/static

USER 1001

ENV PATH="/app/.venv/bin:$PATH"
ENV HOOKBOX_DATABASE_URL="sqlite+aiosqlite:///./hookbox.db"

EXPOSE 8080

ENTRYPOINT ["/app/.venv/bin/python", "-m", "hookbox"]
