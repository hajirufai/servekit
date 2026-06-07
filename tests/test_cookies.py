"""Tests for cookie parsing and building."""

import pytest
from datetime import datetime, timezone
from servekit.cookies import parse_cookies, build_set_cookie


class TestCookieParsing:
    """Test parsing Cookie header strings."""

    def test_single_cookie(self):
        result = parse_cookies("session=abc123")
        assert result == {"session": "abc123"}

    def test_multiple_cookies(self):
        result = parse_cookies("session=abc; theme=dark; lang=en")
        assert result == {"session": "abc", "theme": "dark", "lang": "en"}

    def test_empty_string(self):
        assert parse_cookies("") == {}

    def test_cookie_with_spaces(self):
        result = parse_cookies("  session = abc123 ;  theme = dark  ")
        assert result["session"] == "abc123"
        assert result["theme"] == "dark"

    def test_cookie_with_equals_in_value(self):
        result = parse_cookies("token=abc=def=ghi")
        assert result["token"] == "abc=def=ghi"

    def test_empty_value(self):
        result = parse_cookies("key=")
        assert result == {"key": ""}

    def test_bare_name(self):
        result = parse_cookies("debug")
        assert result == {"debug": ""}


class TestSetCookieBuilding:
    """Test building Set-Cookie header strings."""

    def test_simple_cookie(self):
        result = build_set_cookie("session", "abc123")
        assert result == "session=abc123; Path=/"

    def test_with_path(self):
        result = build_set_cookie("key", "val", path="/api")
        assert "Path=/api" in result

    def test_with_domain(self):
        result = build_set_cookie("key", "val", domain=".example.com")
        assert "Domain=.example.com" in result

    def test_with_max_age(self):
        result = build_set_cookie("key", "val", max_age=3600)
        assert "Max-Age=3600" in result

    def test_http_only(self):
        result = build_set_cookie("key", "val", http_only=True)
        assert "HttpOnly" in result

    def test_secure(self):
        result = build_set_cookie("key", "val", secure=True)
        assert "Secure" in result

    def test_same_site(self):
        result = build_set_cookie("key", "val", same_site="Lax")
        assert "SameSite=Lax" in result

    def test_invalid_same_site(self):
        with pytest.raises(ValueError, match="Invalid SameSite"):
            build_set_cookie("key", "val", same_site="Invalid")

    def test_full_cookie(self):
        result = build_set_cookie(
            "session", "xyz",
            path="/",
            domain=".example.com",
            max_age=86400,
            http_only=True,
            secure=True,
            same_site="Strict",
        )
        assert "session=xyz" in result
        assert "Path=/" in result
        assert "Domain=.example.com" in result
        assert "Max-Age=86400" in result
        assert "HttpOnly" in result
        assert "Secure" in result
        assert "SameSite=Strict" in result

    def test_with_expires(self):
        dt = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        result = build_set_cookie("key", "val", expires=dt)
        assert "Expires=" in result
        assert "2026" in result
