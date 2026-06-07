"""Cookie parsing and Set-Cookie header building."""

from datetime import datetime
from servekit.utils import http_date


def parse_cookies(cookie_header: str) -> dict[str, str]:
    """Parse a Cookie header string into a dict.

    Input:  "session=abc123; theme=dark; lang=en"
    Output: {"session": "abc123", "theme": "dark", "lang": "en"}
    """
    cookies = {}
    if not cookie_header:
        return cookies

    for pair in cookie_header.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            name, _, value = pair.partition("=")
            cookies[name.strip()] = value.strip()
        else:
            cookies[pair.strip()] = ""
    return cookies


def build_set_cookie(
    name: str,
    value: str,
    path: str = "/",
    domain: str | None = None,
    expires: datetime | None = None,
    max_age: int | None = None,
    http_only: bool = False,
    secure: bool = False,
    same_site: str | None = None,
) -> str:
    """Build a Set-Cookie header value.

    Returns something like:
        session=abc123; Path=/; HttpOnly; Secure; SameSite=Lax
    """
    parts = [f"{name}={value}"]

    if path:
        parts.append(f"Path={path}")
    if domain:
        parts.append(f"Domain={domain}")
    if expires:
        parts.append(f"Expires={http_date(expires)}")
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    if http_only:
        parts.append("HttpOnly")
    if secure:
        parts.append("Secure")
    if same_site:
        if same_site not in ("Strict", "Lax", "None"):
            raise ValueError(f"Invalid SameSite value: {same_site}")
        parts.append(f"SameSite={same_site}")

    return "; ".join(parts)
