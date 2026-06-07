"""HTTP Request object — the parsed representation of an incoming request."""

import json as _json
from servekit.utils import CaseInsensitiveDict, parse_query_string, parse_form_data
from servekit.cookies import parse_cookies


class Request:
    """Represents an incoming HTTP request.

    Attributes:
        method:      HTTP method (GET, POST, PUT, etc.)
        path:        URL path, decoded (e.g. /users/42)
        query:       Dict of query parameters
        headers:     Case-insensitive header dict
        body:        Raw bytes body
        params:      Route parameters extracted by the router
        client_addr: Tuple of (host, port) for the client
        http_version: HTTP version string (e.g. "1.1")
    """

    __slots__ = (
        "method", "path", "raw_path", "query", "query_string",
        "headers", "body", "params", "client_addr", "http_version",
        "_json_cache", "_form_cache", "_cookies_cache",
    )

    def __init__(
        self,
        method: str = "GET",
        path: str = "/",
        headers: CaseInsensitiveDict | None = None,
        body: bytes = b"",
        query_string: str = "",
        client_addr: tuple[str, int] = ("127.0.0.1", 0),
        http_version: str = "1.1",
    ):
        self.method = method.upper()
        self.path = path
        self.raw_path = path
        self.query_string = query_string
        self.query = parse_query_string(query_string)
        self.headers = headers or CaseInsensitiveDict()
        self.body = body
        self.params: dict[str, str] = {}
        self.client_addr = client_addr
        self.http_version = http_version
        self._json_cache = None
        self._form_cache = None
        self._cookies_cache = None

    def json(self) -> dict | list:
        """Parse the request body as JSON.

        Raises ValueError if the body isn't valid JSON.
        """
        if self._json_cache is None:
            try:
                self._json_cache = _json.loads(self.body.decode("utf-8"))
            except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid JSON body: {exc}") from exc
        return self._json_cache

    def form(self) -> dict[str, str]:
        """Parse the body as URL-encoded form data."""
        if self._form_cache is None:
            try:
                self._form_cache = parse_form_data(self.body.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ValueError(f"Invalid form body: {exc}") from exc
        return self._form_cache

    @property
    def cookies(self) -> dict[str, str]:
        """Parsed cookies from the Cookie header."""
        if self._cookies_cache is None:
            cookie_header = self.headers.get("Cookie", "")
            self._cookies_cache = parse_cookies(cookie_header)
        return self._cookies_cache

    @property
    def content_type(self) -> str:
        """The Content-Type header value, or empty string."""
        return self.headers.get("Content-Type", "")

    @property
    def content_length(self) -> int:
        """The Content-Length header as int, or 0."""
        try:
            return int(self.headers.get("Content-Length", "0"))
        except (ValueError, TypeError):
            return 0

    @property
    def is_json(self) -> bool:
        """True if Content-Type indicates JSON."""
        ct = self.content_type.lower()
        return "application/json" in ct

    @property
    def host(self) -> str:
        """The Host header value."""
        return self.headers.get("Host", "")

    @property
    def user_agent(self) -> str:
        """The User-Agent header value."""
        return self.headers.get("User-Agent", "")

    @property
    def is_keep_alive(self) -> bool:
        """Whether the connection should be kept alive."""
        conn = self.headers.get("Connection", "").lower()
        if self.http_version == "1.1":
            return conn != "close"
        return conn == "keep-alive"

    def __repr__(self) -> str:
        return f"<Request {self.method} {self.path}>"
