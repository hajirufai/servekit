"""HTTP Response object — builds the outgoing response."""

import json as _json
from datetime import datetime
from servekit.utils import CaseInsensitiveDict, http_date
from servekit.cookies import build_set_cookie
from servekit.errors import STATUS_PHRASES


class Response:
    """Builds an HTTP response to send back to the client.

    Chain-friendly: most methods return self.
        res.status(201).header("X-Custom", "value").json({"ok": True})
    """

    __slots__ = (
        "status_code", "headers", "_body", "_cookies",
        "_sent", "_is_file",
    )

    def __init__(self):
        self.status_code: int = 200
        self.headers = CaseInsensitiveDict()
        self._body: bytes = b""
        self._cookies: list[str] = []
        self._sent: bool = False
        self._is_file: bool = False

        # Default headers
        self.headers["Server"] = "ServeKit/1.0"
        self.headers["Date"] = http_date()
        self.headers["Connection"] = "keep-alive"

    def status(self, code: int) -> "Response":
        """Set the HTTP status code."""
        self.status_code = code
        return self

    def header(self, name: str, value: str) -> "Response":
        """Set a response header."""
        self.headers[name] = value
        return self

    def json(self, data, indent: int | None = None) -> "Response":
        """Send a JSON response.

        Sets Content-Type to application/json and serializes the data.
        """
        body = _json.dumps(data, indent=indent, default=str)
        self._body = body.encode("utf-8")
        self.headers["Content-Type"] = "application/json; charset=utf-8"
        self.headers["Content-Length"] = str(len(self._body))
        return self

    def html(self, content: str) -> "Response":
        """Send an HTML response."""
        self._body = content.encode("utf-8")
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        self.headers["Content-Length"] = str(len(self._body))
        return self

    def text(self, content: str) -> "Response":
        """Send a plain text response."""
        self._body = content.encode("utf-8")
        self.headers["Content-Type"] = "text/plain; charset=utf-8"
        self.headers["Content-Length"] = str(len(self._body))
        return self

    def raw(self, data: bytes, content_type: str = "application/octet-stream") -> "Response":
        """Send raw bytes with a specified content type."""
        self._body = data
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(self._body))
        return self

    def redirect(self, url: str, code: int = 302) -> "Response":
        """Send a redirect response."""
        self.status_code = code
        self.headers["Location"] = url
        self._body = b""
        self.headers["Content-Length"] = "0"
        return self

    def cookie(
        self,
        name: str,
        value: str,
        path: str = "/",
        domain: str | None = None,
        expires: datetime | None = None,
        max_age: int | None = None,
        http_only: bool = False,
        secure: bool = False,
        same_site: str | None = None,
    ) -> "Response":
        """Set a cookie on the response."""
        cookie_str = build_set_cookie(
            name, value, path=path, domain=domain, expires=expires,
            max_age=max_age, http_only=http_only, secure=secure,
            same_site=same_site,
        )
        self._cookies.append(cookie_str)
        return self

    def no_content(self) -> "Response":
        """Send a 204 No Content response."""
        self.status_code = 204
        self._body = b""
        return self

    @property
    def body(self) -> bytes:
        return self._body

    def serialize(self) -> bytes:
        """Serialize the response to raw HTTP bytes for sending over TCP.

        Returns the complete HTTP response: status line + headers + body.
        """
        phrase = STATUS_PHRASES.get(self.status_code, "Unknown")
        status_line = f"HTTP/1.1 {self.status_code} {phrase}\r\n"

        header_lines = []
        for name, value in self.headers.items():
            header_lines.append(f"{name}: {value}\r\n")

        # Set-Cookie headers (can have multiple)
        for cookie in self._cookies:
            header_lines.append(f"Set-Cookie: {cookie}\r\n")

        # Build complete response
        response = status_line + "".join(header_lines) + "\r\n"
        return response.encode("utf-8") + self._body

    def __repr__(self) -> str:
        return f"<Response {self.status_code}>"
