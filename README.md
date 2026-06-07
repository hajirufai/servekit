# ServeKit 🔌

**A lightweight HTTP/1.1 server framework built from raw TCP sockets in Python.**

No Flask. No Express. No dependencies. Just `socket`, `select`, and hand-written HTTP parsing.

[![CI](https://github.com/hajirufai/servekit/actions/workflows/ci.yml/badge.svg)](https://github.com/hajirufai/servekit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Live Demo](https://hajirufai.github.io/servekit/) · [Documentation](#architecture) · [Examples](#examples)

---

## Why?

Because understanding *how* HTTP works — at the byte level — makes you a better engineer. ServeKit implements the HTTP/1.1 protocol from scratch: TCP socket binding, request parsing, response serialization, routing, middleware, static files, WebSocket upgrades, and more.

**Zero third-party dependencies.** The entire framework runs on Python's standard library.

## Quick Start

```python
from servekit import ServeKit

app = ServeKit()

@app.get("/")
def home(req, res):
    res.json({"message": "Hello from raw TCP sockets!"})

@app.get("/users/{id}")
def get_user(req, res):
    user_id = req.params["id"]
    res.json({"id": user_id, "name": "Haji Rufai"})

app.listen(8080)
```

```bash
$ python app.py
╔══════════════════════════════════════╗
║           ServeKit v1.0.0            ║
╠══════════════════════════════════════╣
║  → http://0.0.0.0:8080              ║
║  → 2 route(s) registered            ║
║  → 0 middleware(s) active            ║
║  → 4 worker thread(s)               ║
╚══════════════════════════════════════╝

$ curl localhost:8080/users/42
{"id": "42", "name": "Haji Rufai"}
```

## Features

### Core Protocol
- **Raw TCP sockets** — `socket.socket(AF_INET, SOCK_STREAM)`, no HTTP libraries
- **HTTP/1.1 parser** — Request line, headers, body, chunked transfer encoding
- **Response builder** — Status codes, headers, JSON/HTML/text/binary/redirect
- **Keep-alive** — Persistent connections (HTTP/1.1 default)
- **Non-blocking I/O** — `selectors.DefaultSelector` event loop
- **Thread pool** — Configurable worker threads for concurrent requests

### Routing
- **Exact matching** — `/users`, `/api/v1/health`
- **Path parameters** — `/users/{id}`, `/posts/{slug}/comments/{cid}`
- **Wildcards** — `/static/*path` catches `/static/css/app.css`
- **Method routing** — `@app.get`, `@app.post`, `@app.put`, `@app.delete`, `@app.patch`
- **Route groups** — `app.group("/api/v1")` for shared prefixes
- **Priority** — exact > parameterized > wildcard

### Middleware
- **Chain execution** — Ordered before/after hooks around handlers
- **Short-circuit** — Return 401/403 without hitting the handler
- **Built-in middleware:**
  - `LoggerMiddleware` — Colored request/response logging
  - `CORSMiddleware` — Cross-Origin Resource Sharing headers
  - `CompressMiddleware` — Gzip compression for large responses
  - `RateLimitMiddleware` — In-memory sliding window rate limiter
  - `BasicAuthMiddleware` — HTTP Basic authentication

### Static Files
- **MIME type detection** — Automatic Content-Type from file extension
- **ETag caching** — 304 Not Modified for unchanged files
- **Directory traversal prevention** — `../` paths blocked
- **Index files** — Serve `index.html` for directory requests
- **Cache-Control** — Configurable max-age headers

### WebSocket
- **RFC 6455 handshake** — HTTP upgrade with SHA-1 accept key
- **Frame parsing** — Text, binary, ping, pong, close opcodes
- **Masking/unmasking** — Client mask handling per spec
- **Extended payloads** — 16-bit and 64-bit payload lengths

### Extras
- **Cookie handling** — Parse `Cookie` header, build `Set-Cookie` with all options
- **Query parameters** — Automatic parsing of `?key=value&foo=bar`
- **Form data** — URL-encoded POST body parsing
- **Error handling** — Typed HTTP errors (400, 401, 403, 404, 405, 500)
- **Graceful shutdown** — SIGINT/SIGTERM handlers
- **Case-insensitive headers** — Per HTTP spec

## Architecture

```
                                   ServeKit Architecture
┌─────────────────────────────────────────────────────────────────────┐
│                           TCP Server                                │
│  socket.bind() → selectors.DefaultSelector → ThreadPoolExecutor     │
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────┐       │
│  │ Accept   │───→│  HTTP Parser │───→│   Middleware Chain   │       │
│  │ (select) │    │  (raw bytes  │    │                     │       │
│  │          │    │   → Request) │    │  Logger → CORS →    │       │
│  └──────────┘    └──────────────┘    │  Compress → Auth →  │       │
│                                      │  RateLimit → ...    │       │
│                                      └────────┬────────────┘       │
│                                               │                     │
│                  ┌────────────────────────────┬┘                    │
│                  ▼                            ▼                      │
│         ┌──────────────┐            ┌──────────────┐               │
│         │    Router     │            │   WebSocket   │               │
│         │              │            │   Upgrade     │               │
│         │ /users/{id}  │            │              │               │
│         │ /static/*    │            │   Frame I/O  │               │
│         └──────┬───────┘            └──────────────┘               │
│                │                                                    │
│                ▼                                                    │
│         ┌──────────────┐    ┌──────────────┐                       │
│         │   Handler    │───→│  Response     │──→ raw bytes → client │
│         │  (user code) │    │  Builder     │                       │
│         └──────────────┘    └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Examples

### REST API with CRUD

```python
from servekit import ServeKit
from servekit.builtin_middleware import LoggerMiddleware, CORSMiddleware

app = ServeKit()
app.use(LoggerMiddleware())
app.use(CORSMiddleware(allow_origins=["*"]))

books = {}

@app.get("/api/books")
def list_books(req, res):
    res.json({"books": list(books.values())})

@app.post("/api/books")
def create_book(req, res):
    book = req.json()
    books[book["id"]] = book
    res.status(201).json(book)

@app.get("/api/books/{id}")
def get_book(req, res):
    book_id = req.params["id"]
    if book_id in books:
        res.json(books[book_id])
    else:
        res.status(404).json({"error": "Not found"})

app.listen(8080)
```

### Static File Server

```python
from servekit import ServeKit

app = ServeKit()
app.static("/", "./public")
app.listen(8080)
```

### Middleware Chain

```python
from servekit import ServeKit

app = ServeKit()

@app.use
def timer(req, res, next_handler):
    import time
    start = time.monotonic()
    next_handler(req, res)
    elapsed = (time.monotonic() - start) * 1000
    res.header("X-Response-Time", f"{elapsed:.1f}ms")

@app.get("/")
def home(req, res):
    res.json({"fast": True})

app.listen(8080)
```

### WebSocket Echo

```python
from servekit import ServeKit
from servekit.websocket import parse_frame, encode_text

app = ServeKit()

@app.websocket("/ws")
def echo(sock, request):
    buffer = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buffer += chunk
        frame, consumed = parse_frame(buffer)
        if frame and frame.is_text:
            sock.sendall(encode_text(f"Echo: {frame.text}"))
            buffer = buffer[consumed:]

app.listen(8080)
```

## What's Inside

```
servekit/
├── __init__.py              # Package exports
├── app.py                   # ServeKit application (user-facing API)
├── server.py                # TCP server, event loop, thread pool
├── http_parser.py           # HTTP/1.1 request parser (bytes → Request)
├── request.py               # Request object
├── response.py              # Response builder (Response → bytes)
├── router.py                # URL routing (exact, params, wildcards)
├── middleware.py             # Middleware chain engine
├── static.py                # Static file serving
├── websocket.py             # WebSocket protocol (RFC 6455)
├── cookies.py               # Cookie parsing & Set-Cookie building
├── errors.py                # HTTP error hierarchy
├── utils.py                 # URL encoding, dates, CaseInsensitiveDict
└── builtin_middleware/
    ├── logger.py            # Request logging
    ├── cors.py              # CORS headers
    ├── compress.py          # Gzip compression
    ├── rate_limit.py        # Rate limiting
    └── auth.py              # Basic HTTP auth
```

## Running Tests

```bash
pip install pytest
pytest -v
```

## Docker

```bash
docker build -t servekit .
docker run -p 8080:8080 servekit
```

## How It Works

1. **TCP Server** binds a socket, uses `selectors` for non-blocking I/O
2. **HTTP Parser** reads raw bytes, extracts method/path/headers/body
3. **Router** matches the path against registered routes
4. **Middleware Chain** wraps the handler with before/after hooks
5. **Handler** receives Request + Response objects, sets the response
6. **Response** serializes back to HTTP bytes and sends over TCP

Every step is hand-written. No third-party HTTP libraries involved.

## License

MIT — see [LICENSE](LICENSE).

## Author

**Haji Rufai** — [GitHub](https://github.com/hajirufai) · [LinkedIn](https://linkedin.com/in/hajirufai) · [dev.to](https://dev.to/hajirufai)
