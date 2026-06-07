"""Utility functions for URL handling, date formatting, and encoding."""

from datetime import datetime, timezone
from urllib.parse import unquote, quote


def url_decode(s: str) -> str:
    """Decode a percent-encoded URL string."""
    return unquote(s)


def url_encode(s: str) -> str:
    """Percent-encode a string for use in URLs."""
    return quote(s)


def parse_query_string(qs: str) -> dict[str, str]:
    """Parse a query string into a dict.

    Handles: key=value&foo=bar&empty=&bare
    """
    if not qs:
        return {}

    params = {}
    for pair in qs.split("&"):
        if not pair:
            continue
        if "=" in pair:
            key, _, value = pair.partition("=")
            params[url_decode(key)] = url_decode(value)
        else:
            params[url_decode(pair)] = ""
    return params


def parse_form_data(body: str) -> dict[str, str]:
    """Parse URL-encoded form body (same format as query strings)."""
    return parse_query_string(body)


def http_date(dt: datetime | None = None) -> str:
    """Format a datetime as an HTTP date string (RFC 7231).

    Example: Thu, 29 May 2026 06:30:00 GMT
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def parse_http_date(date_str: str) -> datetime | None:
    """Parse an HTTP date string back to datetime."""
    formats = [
        "%a, %d %b %Y %H:%M:%S GMT",     # RFC 7231
        "%A, %d-%b-%y %H:%M:%S GMT",      # RFC 850
        "%a %b %d %H:%M:%S %Y",           # asctime
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def normalize_path(path: str) -> str:
    """Normalize a URL path: decode, collapse slashes, ensure leading slash."""
    path = url_decode(path)

    # Collapse multiple slashes
    while "//" in path:
        path = path.replace("//", "/")

    # Ensure leading slash
    if not path.startswith("/"):
        path = "/" + path

    # Remove trailing slash (except root)
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return path


class CaseInsensitiveDict:
    """A dict that treats header names as case-insensitive.

    Preserves original casing on iteration but normalizes for lookup.
    """

    def __init__(self, data: dict[str, str] | None = None):
        self._store: dict[str, tuple[str, str]] = {}  # lower -> (original_key, value)
        if data:
            for key, value in data.items():
                self[key] = value

    def __setitem__(self, key: str, value: str):
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key: str) -> str:
        return self._store[key.lower()][1]

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._store

    def __delitem__(self, key: str):
        del self._store[key.lower()]

    def get(self, key: str, default: str | None = None) -> str | None:
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        return [(orig, val) for orig, val in self._store.values()]

    def keys(self):
        return [orig for orig, _ in self._store.values()]

    def values(self):
        return [val for _, val in self._store.values()]

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        items = ", ".join(f"{k!r}: {v!r}" for k, v in self.items())
        return f"CaseInsensitiveDict({{{items}}})"

    def __iter__(self):
        return iter(self.keys())

    def copy(self) -> "CaseInsensitiveDict":
        new = CaseInsensitiveDict()
        for key, value in self.items():
            new[key] = value
        return new
