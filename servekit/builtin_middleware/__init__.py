"""Built-in middleware for ServeKit.

Available middleware:
    - logger:     Request/response logging
    - cors:       Cross-Origin Resource Sharing headers
    - compress:   Gzip response compression
    - rate_limit: In-memory rate limiting
    - auth:       Basic HTTP authentication
"""

from servekit.builtin_middleware.logger import LoggerMiddleware
from servekit.builtin_middleware.cors import CORSMiddleware
from servekit.builtin_middleware.compress import CompressMiddleware
from servekit.builtin_middleware.rate_limit import RateLimitMiddleware
from servekit.builtin_middleware.auth import BasicAuthMiddleware

__all__ = [
    "LoggerMiddleware",
    "CORSMiddleware",
    "CompressMiddleware",
    "RateLimitMiddleware",
    "BasicAuthMiddleware",
]
