"""Tests for the HTTP response builder."""

import json
import pytest
from servekit.response import Response


class TestResponseBasics:
    """Test basic response construction."""

    def test_default_status(self):
        res = Response()
        assert res.status_code == 200

    def test_set_status(self):
        res = Response()
        result = res.status(404)
        assert res.status_code == 404
        assert result is res  # chain-friendly

    def test_default_headers(self):
        res = Response()
        assert "Server" in res.headers
        assert res.headers["Server"] == "ServeKit/1.0"
        assert "Date" in res.headers

    def test_set_header(self):
        res = Response()
        result = res.header("X-Custom", "value")
        assert res.headers["X-Custom"] == "value"
        assert result is res

    def test_repr(self):
        res = Response()
        assert repr(res) == "<Response 200>"
        res.status(404)
        assert repr(res) == "<Response 404>"


class TestResponseBody:
    """Test response body methods."""

    def test_json_response(self):
        res = Response()
        res.json({"message": "hello"})
        assert res.status_code == 200
        assert "application/json" in res.headers["Content-Type"]
        body = json.loads(res.body.decode())
        assert body == {"message": "hello"}

    def test_json_with_indent(self):
        res = Response()
        res.json({"key": "val"}, indent=2)
        body_str = res.body.decode()
        assert "  " in body_str  # indented

    def test_html_response(self):
        res = Response()
        res.html("<h1>Hello</h1>")
        assert "text/html" in res.headers["Content-Type"]
        assert res.body == b"<h1>Hello</h1>"

    def test_text_response(self):
        res = Response()
        res.text("Hello, World!")
        assert "text/plain" in res.headers["Content-Type"]
        assert res.body == b"Hello, World!"

    def test_raw_response(self):
        data = b"\x00\x01\x02"
        res = Response()
        res.raw(data, "application/octet-stream")
        assert res.body == data

    def test_no_content(self):
        res = Response()
        res.no_content()
        assert res.status_code == 204
        assert res.body == b""

    def test_content_length_set(self):
        res = Response()
        res.text("12345")
        assert res.headers["Content-Length"] == "5"


class TestRedirect:
    """Test redirect responses."""

    def test_redirect_302(self):
        res = Response()
        res.redirect("https://example.com")
        assert res.status_code == 302
        assert res.headers["Location"] == "https://example.com"

    def test_redirect_301(self):
        res = Response()
        res.redirect("/new-path", code=301)
        assert res.status_code == 301
        assert res.headers["Location"] == "/new-path"


class TestCookies:
    """Test cookie setting on responses."""

    def test_simple_cookie(self):
        res = Response()
        res.cookie("session", "abc123")
        serialized = res.serialize().decode()
        assert "Set-Cookie: session=abc123" in serialized

    def test_cookie_with_options(self):
        res = Response()
        res.cookie("token", "xyz", http_only=True, secure=True, same_site="Lax")
        serialized = res.serialize().decode()
        assert "HttpOnly" in serialized
        assert "Secure" in serialized
        assert "SameSite=Lax" in serialized

    def test_multiple_cookies(self):
        res = Response()
        res.cookie("a", "1").cookie("b", "2")
        serialized = res.serialize().decode()
        assert "Set-Cookie: a=1" in serialized
        assert "Set-Cookie: b=2" in serialized

    def test_cookie_chaining(self):
        res = Response()
        result = res.cookie("key", "val")
        assert result is res  # chain-friendly


class TestSerialization:
    """Test serializing a response to raw HTTP bytes."""

    def test_simple_serialize(self):
        res = Response()
        res.text("Hello")
        raw = res.serialize()

        assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
        assert b"Content-Type: text/plain; charset=utf-8\r\n" in raw
        assert b"Content-Length: 5\r\n" in raw
        assert raw.endswith(b"Hello")

    def test_404_serialize(self):
        res = Response()
        res.status(404).json({"error": "Not found"})
        raw = res.serialize()
        assert b"HTTP/1.1 404 Not Found\r\n" in raw

    def test_header_body_separator(self):
        res = Response()
        res.text("ok")
        raw = res.serialize()
        # Headers and body are separated by \r\n\r\n
        assert b"\r\n\r\n" in raw
        parts = raw.split(b"\r\n\r\n", 1)
        assert parts[1] == b"ok"

    def test_empty_body(self):
        res = Response()
        res.status(204)
        raw = res.serialize()
        assert raw.endswith(b"\r\n\r\n")

    def test_chained_operations(self):
        res = Response()
        res.status(201).header("X-Custom", "test").json({"created": True})
        raw = res.serialize()
        assert b"HTTP/1.1 201 Created\r\n" in raw
        assert b"X-Custom: test\r\n" in raw
        body = json.loads(raw.split(b"\r\n\r\n", 1)[1])
        assert body == {"created": True}
