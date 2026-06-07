"""Gzip compression middleware.

Compresses responses when the client supports gzip encoding
and the response body is large enough to benefit.
"""

import gzip


class CompressMiddleware:
    """Gzip compression for responses.

    Only compresses if:
        - Client sends Accept-Encoding: gzip
        - Response body exceeds min_size bytes
        - Content-Type is compressible (text, json, xml, etc.)

    Usage:
        app.use(CompressMiddleware(min_size=1024))
    """

    COMPRESSIBLE_TYPES = {
        "text/html", "text/css", "text/plain", "text/xml",
        "application/json", "application/javascript",
        "application/xml", "image/svg+xml",
    }

    def __init__(self, min_size: int = 1024, level: int = 6):
        self.min_size = min_size
        self.level = level  # gzip compression level (1-9)

    def __call__(self, req, res, next_handler):
        next_handler(req, res)

        # Check if client accepts gzip
        accept_encoding = req.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding.lower():
            return

        # Check body size
        body = res._body
        if len(body) < self.min_size:
            return

        # Check content type
        content_type = res.headers.get("Content-Type", "")
        base_type = content_type.split(";")[0].strip().lower()
        if base_type not in self.COMPRESSIBLE_TYPES:
            return

        # Compress
        compressed = gzip.compress(body, compresslevel=self.level)

        # Only use if actually smaller
        if len(compressed) < len(body):
            res._body = compressed
            res.header("Content-Encoding", "gzip")
            res.header("Content-Length", str(len(compressed)))
            # Remove ETag since content changed
            if "ETag" in res.headers:
                del res.headers["ETag"]
