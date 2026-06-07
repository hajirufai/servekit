"""Tests for the URL router."""

import pytest
from servekit.router import Router, Route, RouteGroup
from servekit.errors import NotFound, MethodNotAllowed


@pytest.fixture
def router():
    r = Router()
    return r


def dummy_handler(req, res):
    """Placeholder handler for tests."""
    pass


def another_handler(req, res):
    pass


class TestExactRoutes:
    """Test exact path matching."""

    def test_root_route(self, router):
        router.add_route("GET", "/", dummy_handler)
        handler, params = router.resolve("GET", "/")
        assert handler is dummy_handler
        assert params == {}

    def test_simple_path(self, router):
        router.add_route("GET", "/users", dummy_handler)
        handler, params = router.resolve("GET", "/users")
        assert handler is dummy_handler

    def test_nested_path(self, router):
        router.add_route("GET", "/api/v1/users", dummy_handler)
        handler, params = router.resolve("GET", "/api/v1/users")
        assert handler is dummy_handler

    def test_not_found(self, router):
        router.add_route("GET", "/users", dummy_handler)
        with pytest.raises(NotFound):
            router.resolve("GET", "/posts")

    def test_trailing_slash_normalized(self, router):
        router.add_route("GET", "/users", dummy_handler)
        handler, params = router.resolve("GET", "/users/")
        assert handler is dummy_handler


class TestMethodRouting:
    """Test HTTP method-based routing."""

    def test_different_methods_same_path(self, router):
        router.add_route("GET", "/users", dummy_handler)
        router.add_route("POST", "/users", another_handler)

        h1, _ = router.resolve("GET", "/users")
        h2, _ = router.resolve("POST", "/users")
        assert h1 is dummy_handler
        assert h2 is another_handler

    def test_method_not_allowed(self, router):
        router.add_route("GET", "/users", dummy_handler)
        with pytest.raises(MethodNotAllowed) as exc_info:
            router.resolve("DELETE", "/users")
        assert "GET" in exc_info.value.allowed_methods

    def test_any_method(self, router):
        router.add_route("ANY", "/health", dummy_handler)
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            handler, _ = router.resolve(method, "/health")
            assert handler is dummy_handler


class TestPathParameters:
    """Test path parameter extraction."""

    def test_single_param(self, router):
        router.add_route("GET", "/users/{id}", dummy_handler)
        handler, params = router.resolve("GET", "/users/42")
        assert handler is dummy_handler
        assert params == {"id": "42"}

    def test_multiple_params(self, router):
        router.add_route("GET", "/users/{user_id}/posts/{post_id}", dummy_handler)
        handler, params = router.resolve("GET", "/users/7/posts/99")
        assert params == {"user_id": "7", "post_id": "99"}

    def test_param_with_dash(self, router):
        router.add_route("GET", "/users/{id}", dummy_handler)
        handler, params = router.resolve("GET", "/users/my-user-123")
        assert params == {"id": "my-user-123"}

    def test_param_not_matched_with_extra_segments(self, router):
        router.add_route("GET", "/users/{id}", dummy_handler)
        with pytest.raises(NotFound):
            router.resolve("GET", "/users/42/extra")


class TestWildcardRoutes:
    """Test wildcard path matching."""

    def test_wildcard_matches_subpath(self, router):
        router.add_route("GET", "/static/*path", dummy_handler)
        handler, params = router.resolve("GET", "/static/css/style.css")
        assert handler is dummy_handler
        assert params["path"] == "css/style.css"

    def test_wildcard_matches_single_segment(self, router):
        router.add_route("GET", "/files/*path", dummy_handler)
        handler, params = router.resolve("GET", "/files/readme.txt")
        assert params["path"] == "readme.txt"

    def test_wildcard_matches_deep_path(self, router):
        router.add_route("GET", "/static/*path", dummy_handler)
        handler, params = router.resolve("GET", "/static/a/b/c/d.js")
        assert params["path"] == "a/b/c/d.js"

    def test_bare_wildcard(self, router):
        router.add_route("GET", "/files/*", dummy_handler)
        handler, params = router.resolve("GET", "/files/something")
        assert handler is dummy_handler


class TestRoutePriority:
    """Test route matching priority: exact > param > wildcard."""

    def test_exact_over_param(self, router):
        router.add_route("GET", "/users/me", dummy_handler)
        router.add_route("GET", "/users/{id}", another_handler)

        h1, _ = router.resolve("GET", "/users/me")
        h2, _ = router.resolve("GET", "/users/42")
        assert h1 is dummy_handler  # exact match
        assert h2 is another_handler  # param match

    def test_param_over_wildcard(self, router):
        router.add_route("GET", "/files/{name}", dummy_handler)
        router.add_route("GET", "/files/*path", another_handler)

        h1, _ = router.resolve("GET", "/files/readme.txt")
        assert h1 is dummy_handler  # param wins

        h2, _ = router.resolve("GET", "/files/sub/deep.txt")
        assert h2 is another_handler  # wildcard handles multi-segment


class TestRouteGroups:
    """Test route groups with prefixes."""

    def test_group_prefix(self, router):
        api = router.group("/api/v1")
        api.route("GET", "/users", dummy_handler)

        handler, _ = router.resolve("GET", "/api/v1/users")
        assert handler is dummy_handler

    def test_group_decorator(self, router):
        api = router.group("/api")

        @api.get("/items")
        def get_items(req, res):
            pass

        handler, _ = router.resolve("GET", "/api/items")
        assert handler is get_items

    def test_group_with_params(self, router):
        api = router.group("/api")
        api.route("GET", "/users/{id}", dummy_handler)

        handler, params = router.resolve("GET", "/api/users/42")
        assert params == {"id": "42"}

    def test_multiple_groups(self, router):
        v1 = router.group("/api/v1")
        v2 = router.group("/api/v2")
        v1.route("GET", "/users", dummy_handler)
        v2.route("GET", "/users", another_handler)

        h1, _ = router.resolve("GET", "/api/v1/users")
        h2, _ = router.resolve("GET", "/api/v2/users")
        assert h1 is dummy_handler
        assert h2 is another_handler


class TestDecorators:
    """Test decorator-style route registration."""

    def test_get_decorator(self, router):
        @router.get("/test")
        def handler(req, res):
            pass

        h, _ = router.resolve("GET", "/test")
        assert h is handler

    def test_post_decorator(self, router):
        @router.post("/test")
        def handler(req, res):
            pass

        h, _ = router.resolve("POST", "/test")
        assert h is handler

    def test_put_decorator(self, router):
        @router.put("/test")
        def handler(req, res):
            pass

        h, _ = router.resolve("PUT", "/test")
        assert h is handler

    def test_delete_decorator(self, router):
        @router.delete("/test")
        def handler(req, res):
            pass

        h, _ = router.resolve("DELETE", "/test")
        assert h is handler

    def test_patch_decorator(self, router):
        @router.patch("/test")
        def handler(req, res):
            pass

        h, _ = router.resolve("PATCH", "/test")
        assert h is handler


class TestRouteObject:
    """Test Route internals."""

    def test_route_repr(self):
        r = Route("GET", "/users/{id}", dummy_handler)
        assert repr(r) == "<Route GET /users/{id}>"

    def test_route_param_names(self):
        r = Route("GET", "/users/{uid}/posts/{pid}", dummy_handler)
        assert r.param_names == ["uid", "pid"]

    def test_route_no_params(self):
        r = Route("GET", "/users", dummy_handler)
        assert r.param_names == []

    def test_route_is_wildcard(self):
        r1 = Route("GET", "/static/*", dummy_handler)
        r2 = Route("GET", "/users/{id}", dummy_handler)
        assert r1.is_wildcard is True
        assert r2.is_wildcard is False


class TestErrorHandlers:
    """Test custom error handler registration."""

    def test_register_error_handler(self, router):
        @router.error_handler(404)
        def custom_404(req, res, error):
            pass

        handler = router.get_error_handler(404)
        assert handler is custom_404

    def test_no_error_handler(self, router):
        assert router.get_error_handler(500) is None

    def test_router_len(self, router):
        assert len(router) == 0
        router.add_route("GET", "/a", dummy_handler)
        router.add_route("GET", "/b", dummy_handler)
        assert len(router) == 2
