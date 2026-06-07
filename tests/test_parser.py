"""Tests for the HTTP/1.1 request parser."""

import pytest
from servekit.http_parser import HTTPParser, find_request_boundary
from servekit.errors import BadRequest, PayloadTooLarge


@pytest.fixture
def parser():
    return HTTPParser(max_body_size=1_000_000)


class TestRequestLineParsing:
    """Test parsing of the HTTP request line."""

    def test_simple_get(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.method == "GET"
        assert req.path == "/"
        assert req.http_version == "1.1"

    def test_get_with_path(self, parser):
        raw = b"GET /users/42 HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.path == "/users/42"

    def test_post_method(self, parser):
        raw = b"POST /api/data HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n"
        req = parser.parse(raw)
        assert req.method == "POST"

    def test_all_methods(self, parser):
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            raw = f"{method} / HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
            req = parser.parse(raw)
            assert req.method == method

    def test_http_10(self, parser):
        raw = b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.http_version == "1.0"

    def test_unknown_method_raises(self, parser):
        raw = b"FOOBAR / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        with pytest.raises(BadRequest, match="Unknown HTTP method"):
            parser.parse(raw)

    def test_invalid_version_raises(self, parser):
        raw = b"GET / HTTTPS/1.1\r\nHost: localhost\r\n\r\n"
        with pytest.raises(BadRequest):
            parser.parse(raw)

    def test_malformed_request_line(self, parser):
        raw = b"GETHTTP/1.1\r\nHost: localhost\r\n\r\n"
        with pytest.raises(BadRequest):
            parser.parse(raw)

    def test_empty_request(self, parser):
        with pytest.raises(BadRequest, match="Empty request"):
            parser.parse(b"")


class TestQueryStringParsing:
    """Test query string extraction and parsing."""

    def test_simple_query(self, parser):
        raw = b"GET /search?q=hello HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.path == "/search"
        assert req.query == {"q": "hello"}

    def test_multiple_params(self, parser):
        raw = b"GET /search?q=hello&page=2&sort=date HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.query == {"q": "hello", "page": "2", "sort": "date"}

    def test_empty_value(self, parser):
        raw = b"GET /search?q=&debug= HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.query == {"q": "", "debug": ""}

    def test_no_query(self, parser):
        raw = b"GET /page HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.query == {}

    def test_url_encoded_values(self, parser):
        raw = b"GET /search?q=hello%20world HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.query == {"q": "hello world"}

    def test_bare_key(self, parser):
        raw = b"GET /search?debug HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.query == {"debug": ""}


class TestHeaderParsing:
    """Test HTTP header parsing."""

    def test_basic_headers(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: example.com\r\nAccept: text/html\r\n\r\n"
        req = parser.parse(raw)
        assert req.headers["Host"] == "example.com"
        assert req.headers["Accept"] == "text/html"

    def test_case_insensitive(self, parser):
        raw = b"GET / HTTP/1.1\r\nhost: example.com\r\nCONTENT-TYPE: text/html\r\n\r\n"
        req = parser.parse(raw)
        assert req.headers["Host"] == "example.com"
        assert req.headers["content-type"] == "text/html"
        assert req.headers["CONTENT-TYPE"] == "text/html"

    def test_header_with_colon_in_value(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost:8080\r\n\r\n"
        req = parser.parse(raw)
        assert req.headers["Host"] == "localhost:8080"

    def test_multiple_headers(self, parser):
        raw = (
            b"GET / HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Accept: text/html\r\n"
            b"Accept-Encoding: gzip, deflate\r\n"
            b"Connection: keep-alive\r\n"
            b"User-Agent: TestClient/1.0\r\n"
            b"\r\n"
        )
        req = parser.parse(raw)
        assert len(req.headers) == 5

    def test_malformed_header_raises(self, parser):
        raw = b"GET / HTTP/1.1\r\nBadHeader\r\n\r\n"
        with pytest.raises(BadRequest):
            parser.parse(raw)


class TestBodyParsing:
    """Test request body parsing."""

    def test_content_length_body(self, parser):
        body = b'{"key": "value"}'
        raw = (
            b"POST /api HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"\r\n" + body
        )
        req = parser.parse(raw)
        assert req.body == body

    def test_json_body(self, parser):
        body = b'{"name": "Haji", "age": 25}'
        raw = (
            b"POST /api HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"\r\n" + body
        )
        req = parser.parse(raw)
        data = req.json()
        assert data == {"name": "Haji", "age": 25}

    def test_no_body(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.body == b""

    def test_zero_content_length(self, parser):
        raw = b"POST /api HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n"
        req = parser.parse(raw)
        assert req.body == b""

    def test_body_too_large(self):
        small_parser = HTTPParser(max_body_size=10)
        body = b"x" * 100
        raw = (
            b"POST /api HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Length: 100\r\n"
            b"\r\n" + body
        )
        with pytest.raises(PayloadTooLarge):
            small_parser.parse(raw)

    def test_invalid_content_length(self, parser):
        raw = b"POST /api HTTP/1.1\r\nHost: localhost\r\nContent-Length: abc\r\n\r\n"
        with pytest.raises(BadRequest):
            parser.parse(raw)

    def test_chunked_body(self, parser):
        raw = (
            b"POST /api HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
            b"5\r\nHello\r\n"
            b"6\r\n World\r\n"
            b"0\r\n\r\n"
        )
        req = parser.parse(raw)
        assert req.body == b"Hello World"

    def test_form_data(self, parser):
        body = b"username=haji&password=secret"
        raw = (
            b"POST /login HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/x-www-form-urlencoded\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"\r\n" + body
        )
        req = parser.parse(raw)
        form = req.form()
        assert form["username"] == "haji"
        assert form["password"] == "secret"


class TestPathNormalization:
    """Test URL path decoding and normalization."""

    def test_url_encoded_path(self, parser):
        raw = b"GET /hello%20world HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.path == "/hello world"

    def test_double_slash(self, parser):
        raw = b"GET //users//42 HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.path == "/users/42"

    def test_trailing_slash_stripped(self, parser):
        raw = b"GET /users/ HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.path == "/users"

    def test_root_preserved(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.path == "/"


class TestRequestBoundary:
    """Test finding request boundaries in a byte stream."""

    def test_simple_get(self):
        data = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        assert find_request_boundary(data) == len(data)

    def test_with_body(self):
        data = b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\nHello"
        assert find_request_boundary(data) == len(data)

    def test_incomplete_headers(self):
        data = b"GET / HTTP/1.1\r\nHost: local"
        assert find_request_boundary(data) == -1

    def test_incomplete_body(self):
        data = b"POST / HTTP/1.1\r\nContent-Length: 100\r\n\r\nshort"
        assert find_request_boundary(data) == -1


class TestRequestProperties:
    """Test Request object convenience properties."""

    def test_is_json(self, parser):
        raw = (
            b"POST / HTTP/1.1\r\nHost: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 2\r\n\r\n{}"
        )
        req = parser.parse(raw)
        assert req.is_json is True

    def test_not_json(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.is_json is False

    def test_keep_alive_http11(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.is_keep_alive is True

    def test_close_connection(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        req = parser.parse(raw)
        assert req.is_keep_alive is False

    def test_keep_alive_http10(self, parser):
        raw = b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert req.is_keep_alive is False

    def test_user_agent(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: TestBot/1.0\r\n\r\n"
        req = parser.parse(raw)
        assert req.user_agent == "TestBot/1.0"

    def test_content_length_property(self, parser):
        raw = b"POST / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 42\r\n\r\n"
        req = parser.parse(raw)
        assert req.content_length == 42

    def test_host_property(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: example.com:8080\r\n\r\n"
        req = parser.parse(raw)
        assert req.host == "example.com:8080"

    def test_client_addr(self, parser):
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw, client_addr=("192.168.1.1", 5000))
        assert req.client_addr == ("192.168.1.1", 5000)

    def test_repr(self, parser):
        raw = b"GET /users HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = parser.parse(raw)
        assert repr(req) == "<Request GET /users>"
