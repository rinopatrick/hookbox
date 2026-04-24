# Hookbox

![License](https://img.shields.io/badge/license-MIT-green)
![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Vanilla%20JS-orange)
![Python](https://img.shields.io/badge/python-3.13-blue)

Self-hosted webhook inspector — catch, inspect, and debug webhooks in real-time. The free, open-source alternative to webhook.site and RequestBin.

> **What does this do, in plain English?**  
> When apps like Stripe, GitHub, or Shopify need to tell *your* app that something happened ("someone paid", "code was pushed", "an order came in"), they send a **webhook**. Hookbox gives you a temporary URL, catches whatever those apps send, and shows you the full data — headers, body, query params — live in your browser. No accounts, no cloud, no subscriptions. Perfect for debugging integrations.

> **Self-hosted by design.** Hookbox runs on your own machine. It is NOT a public SaaS. There is no auth, no rate limiting, and no multi-user isolation — because it is intended to run locally or behind your own firewall.

---

## Features

- **One command deploy** — `docker run hookbox` and you're running
- **Real-time inspection** — WebSocket-powered live request streaming
- **Any HTTP method** — GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD
- **Full request details** — headers, body, query params, source IP
- **Auto-cleanup** — TTL-based request expiry (default 24h)
- **Zero dependencies** — just SQLite, no Redis/Postgres needed
- **Dark mode UI** — built-in web interface for inspecting requests

---

## Quick Start

### Docker

```bash
docker run -p 8080:8080 hookbox
```

Open `http://localhost:8080`, create a hook, and start sending webhooks to it.

### Docker Compose

```bash
docker compose up -d
```

### From Source

```bash
git clone https://github.com/rinopatrick/hookbox.git
cd hookbox
uv sync
uv run python -m hookbox
```

---

## API

### Create a Hook

```bash
curl -X POST http://localhost:8080/hook
```

Response:
```json
{
  "id": "a1b2c3d4e5f6",
  "url": "http://localhost:8080/hook/a1b2c3d4e5f6"
}
```

### Send Webhooks

Any HTTP request to `/hook/{id}` is captured:

```bash
curl -X POST http://localhost:8080/hook/a1b2c3d4e5f6 \
  -H "Content-Type: application/json" \
  -d '{"event": "user.created", "data": {"id": 123}}'
```

Sub-paths work too:
```bash
curl http://localhost:8080/hook/a1b2c3d4e5f6/github/webhook
```

### List Requests

```bash
curl http://localhost:8080/hook/a1b2c3d4e5f6
```

### Delete a Hook

```bash
curl -X DELETE http://localhost:8080/hook/a1b2c3d4e5f6
```

### Health Check

```bash
curl http://localhost:8080/health
```

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/hook` | Create a new hook |
| POST | `/hook/{id}` | Catch a webhook (any HTTP method works) |
| GET | `/hook/{id}` | List stored requests (paginated) |
| DELETE | `/hook/{id}` | Delete a hook and its requests |
| WS | `/hook/{id}/ws` | Real-time request stream |
| DELETE | `/hook/{id}/{req}` | Delete a specific request |
| GET | `/health` | Service health check |

---

## Configuration

All settings are configurable via environment variables with the `HOOKBOX_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOOKBOX_HOST` | `0.0.0.0` | Server bind address |
| `HOOKBOX_PORT` | `8080` | Server bind port |
| `HOOKBOX_DEBUG` | `false` | Enable debug mode |
| `HOOKBOX_DATABASE_URL` | `sqlite+aiosqlite:///./hookbox.db` | SQLite database URL |
| `HOOKBOX_REQUEST_TTL_HOURS` | `24` | Hours before requests auto-delete |
| `HOOKBOX_CLEANUP_INTERVAL_SECONDS` | `300` | Background cleanup interval |
| `HOOKBOX_MAX_BODY_SIZE` | `1048576` | Max stored body size in bytes (1MB) |
| `HOOKBOX_CORS_ORIGINS` | `` | Comma-separated allowed CORS origins |

---

## Tech Stack

- **Backend:** Python 3.13 + FastAPI + WebSocket + SQLite (aiosqlite)
- **Frontend:** Vanilla JS + Tailwind CSS
- **Docker:** Multi-stage build (slim runtime)
- **Testing:** pytest + pytest-asyncio + httpx

---

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/
```

---

## Support

If this tool saves you time, consider giving it a ⭐ on GitHub and supporting its development:

| Platform | Link | Payment Methods |
|----------|------|----------------|
| **Saweria** (Indonesia) | [saweria.co/rinopatrick](https://saweria.co/rinopatrick) | QRIS, GoPay, OVO, Dana, LinkAja |
| **Ko-fi** (International) | [ko-fi.com/rinopatrick](https://ko-fi.com/rinopatrick) | PayPal, Credit Card |

Every cup of coffee helps keep this project alive and growing.

---

## License

MIT

---

**Hookbox** — *Debug webhooks without leaving your machine.*
