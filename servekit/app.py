"""ServeKit application — the main user-facing API.

Ties together the router, middleware chain, static file handler,
and TCP server into a clean, Flask-like interface.
"""

import json
import traceback
from servekit.server import TCPServer
from servekit.router import Router
from servekit.middleware import MiddlewareChain
from servekit.static import StaticFileHandler
from servekit.request import Request
from servekit.response import Response
from servekit.errors import HTTPError, MethodNotAllowed, STATUS_PHRASES


class ServeKit:
    """The main ServeKit application.

    Usage:
        app = ServeKit()

        @app.get("/")
        def home(req, res):
            res.json({"message": "Hello, World!"})

        app.listen(8080)
    """

    def __init__(self):
        self._router = Router()
        self._middleware = MiddlewareChain()
        self._static_handlers: list[tuple[str, StaticFileHandler]] = []
        self._websocket_handlers: dict[str, callable] = {}
        self._error_handler = None
        self._server: TCPServer | None = None

    # === Route decorators ===

    def get(self, pattern: str):
        """Register a GET route."""
        return self._router.get(pattern)

    def post(self, pattern: str):
        """Register a POST route."""
        return self._router.post(pattern)

    def put(self, pattern: str):
        """Register a PUT route."""
        return self._router.put(pattern)

    def delete(self, pattern: str):
        """Register a DELETE route."""
        return self._router.delete(pattern)

    def patch(self, pattern: str):
        """Register a PATCH route."""
        return self._router.patch(pattern)

    def options(self, pattern: str):
        """Register an OPTIONS route."""
        return self._router.options(pattern)

    def any(self, pattern: str):
        """Register a route matching any method."""
        return self._router.any(pattern)

    def route(self, method: str, pattern: str, handler: callable):
        """Register a route programmatically."""
        self._router.add_route(method, pattern, handler)

    def group(self, prefix: str):
        """Create a route group with a shared URL prefix."""
        return self._router.group(prefix)

    # === Middleware ===

    def use(self, middleware):
        """Add middleware to the chain.

        Can be used as a decorator:
            @app.use
            def my_middleware(req, res, next_handler):
                ...

        Or called directly with a middleware instance:
            app.use(CORSMiddleware())
        """
        if callable(middleware):
            self._middleware.add(middleware)
            return middleware
        raise TypeError(f"Middleware must be callable, got {type(middleware)}")

    # === Static files ===

    def static(self, url_path: str, directory: str, **kwargs):
        """Serve static files from a directory.

        Args:
            url_path:  URL prefix (e.g. "/static")
            directory: Local directory path
            **kwargs:  Passed to StaticFileHandler (index_file, cache_max_age, etc.)
        """
        handler = StaticFileHandler(directory, **kwargs)
        self._static_handlers.append((url_path.rstrip("/"), handler))

        # Register a wildcard route for this path
        wildcard_pattern = url_path.rstrip("/") + "/*path"

        def serve_static(req, res, _handler=handler, _prefix=url_path.rstrip("/")):
            _handler.handle(req, res, url_prefix=_prefix)

        self._router.add_route("GET", wildcard_pattern, serve_static)

        # Also serve the root (e.g., /static → index.html)
        def serve_static_root(req, res, _handler=handler, _prefix=url_path.rstrip("/")):
            req.params["path"] = ""
            _handler.handle(req, res, url_prefix=_prefix)

        self._router.add_route("GET", url_path.rstrip("/"), serve_static_root)

    # === WebSocket ===

    def websocket(self, path: str):
        """Register a WebSocket handler.

        @app.websocket("/ws")
        def handle_ws(sock, request):
            ...
        """
        def decorator(fn):
            self._websocket_handlers[path] = fn
            return fn
        return decorator

    # === Error handling ===

    def on_error(self, handler: callable):
        """Register a custom error handler.

        @app.on_error
        def handle_error(req, res, error):
            res.status(error.status_code).json({"custom_error": str(error)})
        """
        self._error_handler = handler
        return handler

    # === Request dispatch ===

    def _handle_request(self, request: Request) -> Response:
        """Core request handling: middleware → router → handler → response."""
        response = Response()

        try:
            # Resolve the route
            handler, params = self._router.resolve(request.method, request.path)
            request.params.update(params)

            # Execute middleware chain + handler
            self._middleware.execute(request, response, handler)

        except HTTPError as exc:
            self._handle_http_error(request, response, exc)
        except Exception as exc:
            # Unexpected error → 500
            error = HTTPError(500, f"Internal Server Error")
            self._handle_http_error(request, response, error)
            traceback.print_exc()

        return response

    def _handle_http_error(self, request: Request, response: Response, error: HTTPError):
        """Handle an HTTP error, using custom handler if registered."""
        if self._error_handler:
            try:
                self._error_handler(request, response, error)
                return
            except Exception:
                pass  # Fall through to default

        # Check for route-level error handler
        route_handler = self._router.get_error_handler(error.status_code)
        if route_handler:
            try:
                route_handler(request, response, error)
                return
            except Exception:
                pass

        # Default error response
        response.status(error.status_code)
        if isinstance(error, MethodNotAllowed) and error.allowed_methods:
            response.header("Allow", ", ".join(error.allowed_methods))
        response.json(error.to_dict())

    def _handle_websocket(self, sock, request: Request):
        """Handle a WebSocket connection."""
        handler = self._websocket_handlers.get(request.path)
        if handler:
            try:
                handler(sock, request)
            except Exception as exc:
                print(f"WebSocket error: {exc}")
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

    # === Server lifecycle ===

    def listen(self, port: int = 8080, host: str = "0.0.0.0", workers: int = 4, **kwargs):
        """Start the HTTP server.

        Args:
            port:    Port to listen on
            host:    Host to bind to
            workers: Number of worker threads
        """
        self._server = TCPServer(
            host=host, port=port, workers=workers, **kwargs,
        )
        self._server.on_request = self._handle_request
        if self._websocket_handlers:
            self._server.on_websocket = self._handle_websocket

        print(f"""
╔══════════════════════════════════════╗
║           ServeKit v1.0.0            ║
╠══════════════════════════════════════╣
║  → http://{host}:{port:<5}              ║
║  → {len(self._router)} route(s) registered         ║
║  → {len(self._middleware)} middleware(s) active        ║
║  → {workers} worker thread(s)               ║
╚══════════════════════════════════════╝
""")
        self._server.start()

    def stop(self):
        """Stop the server."""
        if self._server:
            self._server.stop()

    @property
    def router(self) -> Router:
        """Access the underlying router."""
        return self._router

    @property
    def routes(self):
        """List all registered routes."""
        return self._router.routes
