"""Tests for the middleware chain and built-in middleware."""

import pytest
import io
from servekit.request import Request
from servekit.response import Response
from servekit.middleware import MiddlewareChain
from servekit.utils import CaseInsensitiveDict


def make_request(method="GET", path="/", headers=None):
    """Helper to create a test Request."""
    return Request(method=method, path=path, headers=headers)


class TestMiddlewareChain:
    """Test the middleware chain execution."""

    def test_empty_chain(self):
        chain = MiddlewareChain()
        req = make_request()
        res = Response()
        called = []

        def handler(req, res):
            called.append("handler")

        chain.execute(req, res, handler)
        assert called == ["handler"]

    def test_single_middleware(self):
        chain = MiddlewareChain()
        order = []

        def mw(req, res, next_handler):
            order.append("before")
            next_handler(req, res)
            order.append("after")

        def handler(req, res):
            order.append("handler")

        chain.add(mw)
        chain.execute(make_request(), Response(), handler)
        assert order == ["before", "handler", "after"]

    def test_multiple_middleware_order(self):
        chain = MiddlewareChain()
        order = []

        def mw1(req, res, next_handler):
            order.append("mw1-before")
            next_handler(req, res)
            order.append("mw1-after")

        def mw2(req, res, next_handler):
            order.append("mw2-before")
            next_handler(req, res)
            order.append("mw2-after")

        def handler(req, res):
            order.append("handler")

        chain.add(mw1)
        chain.add(mw2)
        chain.execute(make_request(), Response(), handler)
        assert order == ["mw1-before", "mw2-before", "handler", "mw2-after", "mw1-after"]

    def test_middleware_short_circuit(self):
        chain = MiddlewareChain()
        order = []

        def auth_mw(req, res, next_handler):
            order.append("auth")
            # Short-circuit: don't call next
            res.status(401).json({"error": "Unauthorized"})

        def handler(req, res):
            order.append("handler")  # Should NOT be called

        chain.add(auth_mw)
        res = Response()
        chain.execute(make_request(), res, handler)
        assert order == ["auth"]
        assert res.status_code == 401

    def test_middleware_modifies_request(self):
        chain = MiddlewareChain()

        def add_header_mw(req, res, next_handler):
            req.params["custom"] = "injected"
            next_handler(req, res)

        captured = {}

        def handler(req, res):
            captured["custom"] = req.params.get("custom")

        chain.add(add_header_mw)
        chain.execute(make_request(), Response(), handler)
        assert captured["custom"] == "injected"

    def test_middleware_modifies_response(self):
        chain = MiddlewareChain()

        def add_header_mw(req, res, next_handler):
            next_handler(req, res)
            res.header("X-Processed", "true")

        def handler(req, res):
            res.text("ok")

        chain.add(add_header_mw)
        res = Response()
        chain.execute(make_request(), res, handler)
        assert res.headers["X-Processed"] == "true"

    def test_chain_length(self):
        chain = MiddlewareChain()
        assert len(chain) == 0
        chain.add(lambda r, s, n: n(r, s))
        assert len(chain) == 1


class TestCORSMiddleware:
    """Test the CORS middleware."""

    def test_wildcard_origin(self):
        from servekit.builtin_middleware.cors import CORSMiddleware

        cors = CORSMiddleware(allow_origins=["*"])
        req = make_request(headers=CaseInsensitiveDict({"Origin": "https://example.com"}))
        res = Response()

        cors(req, res, lambda r, s: s.text("ok"))
        assert res.headers["Access-Control-Allow-Origin"] == "*"

    def test_specific_origin(self):
        from servekit.builtin_middleware.cors import CORSMiddleware

        cors = CORSMiddleware(allow_origins=["https://mysite.com"])
        req = make_request(headers=CaseInsensitiveDict({"Origin": "https://mysite.com"}))
        res = Response()

        cors(req, res, lambda r, s: s.text("ok"))
        assert res.headers["Access-Control-Allow-Origin"] == "https://mysite.com"

    def test_unmatched_origin(self):
        from servekit.builtin_middleware.cors import CORSMiddleware

        cors = CORSMiddleware(allow_origins=["https://mysite.com"])
        req = make_request(headers=CaseInsensitiveDict({"Origin": "https://evil.com"}))
        res = Response()

        cors(req, res, lambda r, s: s.text("ok"))
        assert "Access-Control-Allow-Origin" not in res.headers

    def test_preflight_options(self):
        from servekit.builtin_middleware.cors import CORSMiddleware

        cors = CORSMiddleware(allow_origins=["*"])
        req = make_request(
            method="OPTIONS",
            headers=CaseInsensitiveDict({"Origin": "https://example.com"}),
        )
        res = Response()
        handler_called = []

        cors(req, res, lambda r, s: handler_called.append(True))
        assert res.status_code == 204
        assert len(handler_called) == 0  # Handler not called for preflight
        assert "Access-Control-Allow-Methods" in res.headers

    def test_credentials(self):
        from servekit.builtin_middleware.cors import CORSMiddleware

        cors = CORSMiddleware(allow_origins=["*"], allow_credentials=True)
        req = make_request(headers=CaseInsensitiveDict({"Origin": "https://example.com"}))
        res = Response()

        cors(req, res, lambda r, s: s.text("ok"))
        assert res.headers["Access-Control-Allow-Credentials"] == "true"


class TestCompressMiddleware:
    """Test the gzip compression middleware."""

    def test_compress_large_json(self):
        from servekit.builtin_middleware.compress import CompressMiddleware

        compress = CompressMiddleware(min_size=100)
        req = make_request(
            headers=CaseInsensitiveDict({"Accept-Encoding": "gzip, deflate"}),
        )
        res = Response()

        def handler(r, s):
            s.json({"data": "x" * 500})

        compress(req, res, handler)
        assert res.headers.get("Content-Encoding") == "gzip"
        assert len(res._body) < 500  # Should be smaller

    def test_skip_small_body(self):
        from servekit.builtin_middleware.compress import CompressMiddleware

        compress = CompressMiddleware(min_size=1024)
        req = make_request(
            headers=CaseInsensitiveDict({"Accept-Encoding": "gzip"}),
        )
        res = Response()

        def handler(r, s):
            s.text("small")

        compress(req, res, handler)
        assert "Content-Encoding" not in res.headers

    def test_skip_no_accept_encoding(self):
        from servekit.builtin_middleware.compress import CompressMiddleware

        compress = CompressMiddleware(min_size=10)
        req = make_request()
        res = Response()

        def handler(r, s):
            s.json({"data": "x" * 500})

        compress(req, res, handler)
        assert "Content-Encoding" not in res.headers


class TestRateLimitMiddleware:
    """Test the rate limiter."""

    def test_allows_under_limit(self):
        from servekit.builtin_middleware.rate_limit import RateLimitMiddleware

        limiter = RateLimitMiddleware(max_requests=5, window_seconds=60)
        for _ in range(5):
            req = make_request()
            res = Response()
            limiter(req, res, lambda r, s: s.text("ok"))
            assert res.status_code == 200

    def test_blocks_over_limit(self):
        from servekit.builtin_middleware.rate_limit import RateLimitMiddleware

        limiter = RateLimitMiddleware(max_requests=3, window_seconds=60)
        for i in range(4):
            req = make_request()
            res = Response()
            limiter(req, res, lambda r, s: s.text("ok"))

        # 4th request should be blocked
        assert res.status_code == 429
        assert "Retry-After" in res.headers

    def test_rate_limit_headers(self):
        from servekit.builtin_middleware.rate_limit import RateLimitMiddleware

        limiter = RateLimitMiddleware(max_requests=10, window_seconds=60)
        req = make_request()
        res = Response()
        limiter(req, res, lambda r, s: s.text("ok"))
        assert res.headers["X-RateLimit-Limit"] == "10"
        assert res.headers["X-RateLimit-Remaining"] == "9"


class TestBasicAuthMiddleware:
    """Test the basic auth middleware."""

    def test_valid_credentials(self):
        from servekit.builtin_middleware.auth import BasicAuthMiddleware
        import base64

        auth = BasicAuthMiddleware({"admin": "secret"})
        creds = base64.b64encode(b"admin:secret").decode()
        req = make_request(
            headers=CaseInsensitiveDict({"Authorization": f"Basic {creds}"}),
        )
        res = Response()
        handler_called = []

        auth(req, res, lambda r, s: handler_called.append(True))
        assert len(handler_called) == 1
        assert req.params["_auth_user"] == "admin"

    def test_invalid_credentials(self):
        from servekit.builtin_middleware.auth import BasicAuthMiddleware
        import base64

        auth = BasicAuthMiddleware({"admin": "secret"})
        creds = base64.b64encode(b"admin:wrong").decode()
        req = make_request(
            headers=CaseInsensitiveDict({"Authorization": f"Basic {creds}"}),
        )
        res = Response()
        handler_called = []

        auth(req, res, lambda r, s: handler_called.append(True))
        assert len(handler_called) == 0
        assert res.status_code == 401
        assert "WWW-Authenticate" in res.headers

    def test_no_auth_header(self):
        from servekit.builtin_middleware.auth import BasicAuthMiddleware

        auth = BasicAuthMiddleware({"admin": "secret"})
        req = make_request()
        res = Response()
        handler_called = []

        auth(req, res, lambda r, s: handler_called.append(True))
        assert len(handler_called) == 0
        assert res.status_code == 401


class TestLoggerMiddleware:
    """Test the logger middleware."""

    def test_logs_request(self):
        from servekit.builtin_middleware.logger import LoggerMiddleware

        output = io.StringIO()
        logger = LoggerMiddleware(stream=output)
        req = make_request(path="/api/test")
        res = Response()

        logger(req, res, lambda r, s: s.text("ok"))

        log_line = output.getvalue()
        assert "GET" in log_line
        assert "/api/test" in log_line
        assert "200" in log_line
