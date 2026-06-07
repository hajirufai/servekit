"""Middleware demo — shows how to chain middleware for logging, auth, CORS,
rate limiting, and custom middleware functions."""

import sys
sys.path.insert(0, "..")

from servekit import ServeKit
from servekit.builtin_middleware import (
    LoggerMiddleware,
    CORSMiddleware,
    CompressMiddleware,
    RateLimitMiddleware,
    BasicAuthMiddleware,
)

app = ServeKit()

# Stack middleware (order matters!)
app.use(LoggerMiddleware())
app.use(CORSMiddleware(allow_origins=["*"]))
app.use(CompressMiddleware(min_size=512))
app.use(RateLimitMiddleware(max_requests=10, window_seconds=60))


# Custom middleware via decorator
@app.use
def add_request_id(req, res, next_handler):
    """Add a unique request ID header to every response."""
    import time
    req_id = f"req-{int(time.time() * 1000)}"
    res.header("X-Request-ID", req_id)
    next_handler(req, res)


@app.get("/")
def home(req, res):
    res.json({
        "message": "Middleware demo",
        "middleware_count": 5,
        "tip": "Try hitting this endpoint rapidly to trigger rate limiting!",
    })


@app.get("/public")
def public_route(req, res):
    res.json({"access": "public", "data": "Anyone can see this"})


# Protected route group with basic auth
api = app.group("/admin")
auth = BasicAuthMiddleware({"admin": "secret"}, realm="Admin Area")


@api.get("/dashboard")
def admin_dashboard(req, res):
    # Note: in a real app, you'd apply auth as route-level middleware
    # For demo, we show it can be used globally or per-group
    res.json({
        "dashboard": "Admin panel",
        "stats": {"users": 42, "requests_today": 1337},
    })


if __name__ == "__main__":
    app.listen(8080)
