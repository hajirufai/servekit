"""Cross-Origin Resource Sharing (CORS) middleware.

Adds CORS headers to responses and handles preflight OPTIONS requests.
"""


class CORSMiddleware:
    """CORS middleware with configurable origins, methods, and headers.

    Usage:
        app.use(CORSMiddleware(allow_origins=["https://example.com"]))
        # or allow everything:
        app.use(CORSMiddleware(allow_origins=["*"]))
    """

    def __init__(
        self,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        expose_headers: list[str] | None = None,
        allow_credentials: bool = False,
        max_age: int = 86400,
    ):
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        self.allow_headers = allow_headers or ["Content-Type", "Authorization", "Accept"]
        self.expose_headers = expose_headers or []
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    def __call__(self, req, res, next_handler):
        origin = req.headers.get("Origin", "")

        # Determine the allowed origin to send back
        if "*" in self.allow_origins:
            res.header("Access-Control-Allow-Origin", "*")
        elif origin in self.allow_origins:
            res.header("Access-Control-Allow-Origin", origin)
            res.header("Vary", "Origin")

        if self.allow_credentials:
            res.header("Access-Control-Allow-Credentials", "true")

        if self.expose_headers:
            res.header("Access-Control-Expose-Headers", ", ".join(self.expose_headers))

        # Handle preflight OPTIONS
        if req.method == "OPTIONS":
            res.header("Access-Control-Allow-Methods", ", ".join(self.allow_methods))
            res.header("Access-Control-Allow-Headers", ", ".join(self.allow_headers))
            res.header("Access-Control-Max-Age", str(self.max_age))
            res.status(204)
            res.header("Content-Length", "0")
            return  # Short-circuit — don't call next handler

        next_handler(req, res)
