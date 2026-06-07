"""Static file serving with MIME type detection, ETag caching, and security.

Serves files from a directory on disk, mapping URL paths to file paths.
Prevents directory traversal attacks and supports conditional requests.
"""

import os
import hashlib
import mimetypes
from pathlib import Path
from servekit.request import Request
from servekit.response import Response
from servekit.errors import NotFound, Forbidden


# Extend mimetypes with common web types
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("application/wasm", ".wasm")


class StaticFileHandler:
    """Serves static files from a directory.

    Features:
        - MIME type detection
        - ETag-based caching (304 Not Modified)
        - Directory traversal prevention
        - Index file support
        - Configurable cache control

    Usage:
        handler = StaticFileHandler("./public")
        # Mount at /static/* in the router
    """

    def __init__(
        self,
        directory: str,
        index_file: str = "index.html",
        cache_max_age: int = 3600,
        show_directory: bool = False,
    ):
        self.root = Path(directory).resolve()
        self.index_file = index_file
        self.cache_max_age = cache_max_age
        self.show_directory = show_directory

        if not self.root.is_dir():
            raise ValueError(f"Static directory does not exist: {self.root}")

    def handle(self, request: Request, response: Response, url_prefix: str = "/") -> None:
        """Handle a request for a static file.

        The url_prefix is stripped from the request path to determine
        the file path relative to the root directory.
        """
        # Get file path relative to the URL prefix
        rel_path = request.params.get("path", "")
        if not rel_path:
            # Strip prefix from path manually
            path = request.path
            if path.startswith(url_prefix):
                rel_path = path[len(url_prefix):]
            rel_path = rel_path.lstrip("/")

        # Resolve to absolute path
        file_path = (self.root / rel_path).resolve()

        # Security: prevent directory traversal
        try:
            file_path.relative_to(self.root)
        except ValueError:
            raise Forbidden("Directory traversal is not allowed")

        # If it's a directory, look for index file
        if file_path.is_dir():
            index_path = file_path / self.index_file
            if index_path.is_file():
                file_path = index_path
            elif self.show_directory:
                self._serve_directory_listing(file_path, request, response)
                return
            else:
                raise NotFound(f"Not found: {request.path}")

        if not file_path.is_file():
            raise NotFound(f"File not found: {request.path}")

        self._serve_file(file_path, request, response)

    def _serve_file(self, file_path: Path, request: Request, response: Response) -> None:
        """Read and serve a single file with caching headers."""
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        # Read file
        content = file_path.read_bytes()

        # ETag: hash of file content
        etag = self._generate_etag(content)

        # Check If-None-Match for 304
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match.strip('"') == etag:
            response.status(304)
            response.header("ETag", f'"{etag}"')
            return

        # Serve file
        response.status(200)
        response.header("Content-Type", mime_type)
        response.header("Content-Length", str(len(content)))
        response.header("ETag", f'"{etag}"')
        response.header("Cache-Control", f"public, max-age={self.cache_max_age}")
        response._body = content

    def _serve_directory_listing(
        self, dir_path: Path, request: Request, response: Response
    ) -> None:
        """Serve a simple HTML directory listing."""
        entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        items = []
        for entry in entries:
            name = entry.name + ("/" if entry.is_dir() else "")
            href = request.path.rstrip("/") + "/" + entry.name
            size = entry.stat().st_size if entry.is_file() else "-"
            items.append(f'<li><a href="{href}">{name}</a> ({size})</li>')

        html = f"""<!DOCTYPE html>
<html>
<head><title>Index of {request.path}</title></head>
<body>
<h1>Index of {request.path}</h1>
<ul>{"".join(items)}</ul>
</body>
</html>"""
        response.html(html)

    @staticmethod
    def _generate_etag(content: bytes) -> str:
        """Generate an ETag from file content using MD5."""
        return hashlib.md5(content).hexdigest()
