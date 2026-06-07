"""
ServeKit — A lightweight HTTP/1.1 server framework built from raw TCP sockets.

No dependencies. No magic. Just socket, select, and hand-written HTTP parsing.

Usage:
    from servekit import ServeKit

    app = ServeKit()

    @app.get("/")
    def home(req, res):
        res.json({"message": "Hello, World!"})

    app.listen(8080)
"""

from servekit.app import ServeKit
from servekit.request import Request
from servekit.response import Response
from servekit.errors import (
    HTTPError,
    BadRequest,
    Unauthorized,
    Forbidden,
    NotFound,
    MethodNotAllowed,
    InternalServerError,
)

__version__ = "1.0.0"
__all__ = [
    "ServeKit",
    "Request",
    "Response",
    "HTTPError",
    "BadRequest",
    "Unauthorized",
    "Forbidden",
    "NotFound",
    "MethodNotAllowed",
    "InternalServerError",
]
