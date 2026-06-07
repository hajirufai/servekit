"""Tests for static file serving."""

import os
import pytest
import tempfile
from pathlib import Path
from servekit.static import StaticFileHandler
from servekit.request import Request
from servekit.response import Response
from servekit.errors import NotFound, Forbidden
from servekit.utils import CaseInsensitiveDict


@pytest.fixture
def static_dir(tmp_path):
    """Create a temporary directory with test files."""
    # Create files
    (tmp_path / "index.html").write_text("<h1>Home</h1>")
    (tmp_path / "style.css").write_text("body { color: red; }")
    (tmp_path / "app.js").write_text("console.log('hi');")
    (tmp_path / "data.json").write_text('{"key": "value"}')

    # Create subdirectory
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "page.html").write_text("<h1>Sub</h1>")
    (sub / "index.html").write_text("<h1>Sub Index</h1>")

    return tmp_path


@pytest.fixture
def handler(static_dir):
    return StaticFileHandler(str(static_dir))


def make_request(path="/", headers=None):
    req = Request(path=path, headers=headers or CaseInsensitiveDict())
    req.params = {}
    return req


class TestStaticFileServing:
    """Test serving static files."""

    def test_serve_html(self, handler):
        req = make_request("/static/index.html")
        req.params["path"] = "index.html"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert res.status_code == 200
        assert "text/html" in res.headers["Content-Type"]
        assert res.body == b"<h1>Home</h1>"

    def test_serve_css(self, handler):
        req = make_request("/static/style.css")
        req.params["path"] = "style.css"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert "text/css" in res.headers["Content-Type"]

    def test_serve_js(self, handler):
        req = make_request("/static/app.js")
        req.params["path"] = "app.js"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert "javascript" in res.headers["Content-Type"]

    def test_serve_json(self, handler):
        req = make_request("/static/data.json")
        req.params["path"] = "data.json"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert "application/json" in res.headers["Content-Type"]

    def test_serve_subdirectory_file(self, handler):
        req = make_request("/static/sub/page.html")
        req.params["path"] = "sub/page.html"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert res.body == b"<h1>Sub</h1>"

    def test_not_found(self, handler):
        req = make_request("/static/missing.txt")
        req.params["path"] = "missing.txt"
        res = Response()
        with pytest.raises(NotFound):
            handler.handle(req, res, url_prefix="/static")


class TestDirectoryTraversal:
    """Test directory traversal prevention."""

    def test_traversal_blocked(self, handler):
        req = make_request("/static/../../etc/passwd")
        req.params["path"] = "../../etc/passwd"
        res = Response()
        with pytest.raises(Forbidden):
            handler.handle(req, res, url_prefix="/static")

    def test_traversal_with_encoded_dots(self, handler):
        req = make_request("/static/%2e%2e/etc/passwd")
        req.params["path"] = "../etc/passwd"
        res = Response()
        with pytest.raises(Forbidden):
            handler.handle(req, res, url_prefix="/static")


class TestCaching:
    """Test ETag-based caching."""

    def test_etag_header(self, handler):
        req = make_request("/static/index.html")
        req.params["path"] = "index.html"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert "ETag" in res.headers
        assert res.headers["ETag"].startswith('"')

    def test_cache_control(self, handler):
        req = make_request("/static/index.html")
        req.params["path"] = "index.html"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert "Cache-Control" in res.headers
        assert "max-age=" in res.headers["Cache-Control"]

    def test_304_not_modified(self, handler):
        # First request to get ETag
        req1 = make_request("/static/index.html")
        req1.params["path"] = "index.html"
        res1 = Response()
        handler.handle(req1, res1, url_prefix="/static")
        etag = res1.headers["ETag"].strip('"')

        # Second request with If-None-Match
        req2 = make_request(
            "/static/index.html",
            headers=CaseInsensitiveDict({"If-None-Match": f'"{etag}"'}),
        )
        req2.params["path"] = "index.html"
        res2 = Response()
        handler.handle(req2, res2, url_prefix="/static")
        assert res2.status_code == 304


class TestIndexFile:
    """Test index file serving for directories."""

    def test_directory_serves_index(self, handler):
        req = make_request("/static/sub")
        req.params["path"] = "sub"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert res.body == b"<h1>Sub Index</h1>"

    def test_root_serves_index(self, handler):
        req = make_request("/static")
        req.params["path"] = ""
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert res.body == b"<h1>Home</h1>"


class TestDirectoryListing:
    """Test directory listing."""

    def test_listing_enabled(self, static_dir):
        handler = StaticFileHandler(str(static_dir), show_directory=True)
        # Create a dir without index.html
        (static_dir / "empty_dir").mkdir()
        req = make_request("/static/empty_dir")
        req.params["path"] = "empty_dir"
        res = Response()
        handler.handle(req, res, url_prefix="/static")
        assert res.status_code == 200
        assert "text/html" in res.headers["Content-Type"]

    def test_listing_disabled_404(self, static_dir):
        handler = StaticFileHandler(str(static_dir), show_directory=False)
        (static_dir / "empty_dir").mkdir()
        req = make_request("/static/empty_dir")
        req.params["path"] = "empty_dir"
        res = Response()
        with pytest.raises(NotFound):
            handler.handle(req, res, url_prefix="/static")


class TestInvalidDirectory:
    """Test error handling for invalid directories."""

    def test_nonexistent_directory(self):
        with pytest.raises(ValueError, match="does not exist"):
            StaticFileHandler("/nonexistent/path")
