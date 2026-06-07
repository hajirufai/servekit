"""Tests for utility functions."""

import pytest
from datetime import datetime, timezone
from servekit.utils import (
    url_decode,
    url_encode,
    parse_query_string,
    parse_form_data,
    http_date,
    parse_http_date,
    normalize_path,
    CaseInsensitiveDict,
)


class TestURLEncoding:
    """Test URL encoding/decoding."""

    def test_decode_space(self):
        assert url_decode("hello%20world") == "hello world"

    def test_decode_plus(self):
        assert url_decode("hello+world") == "hello+world"  # + is literal in path

    def test_decode_special(self):
        assert url_decode("%2F") == "/"
        assert url_decode("%3F") == "?"

    def test_encode(self):
        encoded = url_encode("hello world")
        assert "hello" in encoded
        assert "%20" in encoded or "+" in encoded


class TestQueryStringParsing:
    """Test query string parsing."""

    def test_simple(self):
        assert parse_query_string("key=value") == {"key": "value"}

    def test_multiple(self):
        result = parse_query_string("a=1&b=2&c=3")
        assert result == {"a": "1", "b": "2", "c": "3"}

    def test_empty_value(self):
        assert parse_query_string("key=") == {"key": ""}

    def test_bare_key(self):
        assert parse_query_string("debug") == {"debug": ""}

    def test_empty_string(self):
        assert parse_query_string("") == {}

    def test_encoded_values(self):
        result = parse_query_string("q=hello%20world")
        assert result == {"q": "hello world"}

    def test_ampersand_only(self):
        assert parse_query_string("&&") == {}

    def test_form_data_same_format(self):
        result = parse_form_data("user=haji&pass=secret")
        assert result == {"user": "haji", "pass": "secret"}


class TestHTTPDate:
    """Test HTTP date formatting and parsing."""

    def test_format(self):
        dt = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
        result = http_date(dt)
        assert "29 May 2026" in result
        assert "12:00:00 GMT" in result

    def test_format_default(self):
        result = http_date()
        assert "GMT" in result

    def test_parse_rfc7231(self):
        dt = parse_http_date("Thu, 29 May 2026 12:00:00 GMT")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 29

    def test_parse_invalid(self):
        assert parse_http_date("not-a-date") is None


class TestPathNormalization:
    """Test URL path normalization."""

    def test_root(self):
        assert normalize_path("/") == "/"

    def test_simple(self):
        assert normalize_path("/users") == "/users"

    def test_trailing_slash(self):
        assert normalize_path("/users/") == "/users"

    def test_double_slash(self):
        assert normalize_path("//users//42") == "/users/42"

    def test_no_leading_slash(self):
        assert normalize_path("users") == "/users"

    def test_encoded(self):
        assert normalize_path("/hello%20world") == "/hello world"


class TestCaseInsensitiveDict:
    """Test the case-insensitive dict used for headers."""

    def test_get_set(self):
        d = CaseInsensitiveDict()
        d["Content-Type"] = "text/html"
        assert d["Content-Type"] == "text/html"
        assert d["content-type"] == "text/html"
        assert d["CONTENT-TYPE"] == "text/html"

    def test_contains(self):
        d = CaseInsensitiveDict()
        d["Host"] = "localhost"
        assert "Host" in d
        assert "host" in d
        assert "HOST" in d
        assert "Missing" not in d

    def test_get_default(self):
        d = CaseInsensitiveDict()
        assert d.get("Missing") is None
        assert d.get("Missing", "default") == "default"

    def test_delete(self):
        d = CaseInsensitiveDict()
        d["Key"] = "value"
        del d["key"]
        assert "Key" not in d

    def test_len(self):
        d = CaseInsensitiveDict()
        assert len(d) == 0
        d["A"] = "1"
        d["B"] = "2"
        assert len(d) == 2

    def test_items(self):
        d = CaseInsensitiveDict({"Content-Type": "text/html", "Host": "localhost"})
        items = dict(d.items())
        assert "Content-Type" in items or "content-type" in items

    def test_overwrite_preserves_last_case(self):
        d = CaseInsensitiveDict()
        d["Content-Type"] = "text/html"
        d["content-type"] = "application/json"
        assert d["Content-Type"] == "application/json"
        assert len(d) == 1

    def test_copy(self):
        d = CaseInsensitiveDict({"A": "1"})
        c = d.copy()
        c["B"] = "2"
        assert "B" not in d
        assert "A" in c

    def test_iter(self):
        d = CaseInsensitiveDict({"X": "1", "Y": "2"})
        keys = list(d)
        assert len(keys) == 2

    def test_repr(self):
        d = CaseInsensitiveDict({"Host": "localhost"})
        r = repr(d)
        assert "CaseInsensitiveDict" in r
        assert "Host" in r
