"""URL router with path parameters, method matching, and route groups.

Supports:
- Exact paths:      /users
- Path parameters:  /users/{id}
- Wildcards:        /static/*
- Method routing:   GET /users vs POST /users
- Route groups:     group("/api/v1")
- Priority: exact > parameterized > wildcard
"""

from __future__ import annotations
from typing import Callable, Any
from servekit.errors import NotFound, MethodNotAllowed


HandlerFunc = Callable  # (Request, Response) -> None


class Route:
    """A single route definition."""

    __slots__ = ("method", "pattern", "handler", "segments", "param_names", "is_wildcard")

    def __init__(self, method: str, pattern: str, handler: HandlerFunc):
        self.method = method.upper()
        self.pattern = pattern
        self.handler = handler
        self.segments = self._split(pattern)
        self.param_names = [
            seg[1:-1] for seg in self.segments if seg.startswith("{") and seg.endswith("}")
        ]
        self.is_wildcard = pattern.endswith("/*") or pattern.endswith("/*path")

    @staticmethod
    def _split(path: str) -> list[str]:
        """Split a path into segments, filtering empty strings."""
        return [s for s in path.split("/") if s]

    def match(self, method: str, path: str) -> dict[str, str] | None:
        """Try to match a request method+path against this route.

        Returns a dict of path params if matched, None otherwise.
        """
        if self.method != method and self.method != "ANY":
            return None

        path_segments = self._split(path)
        route_segments = self.segments

        # Wildcard matching: /static/* matches /static/foo/bar/baz
        if self.is_wildcard:
            prefix = route_segments[:-1]  # Everything before *
            if len(path_segments) < len(prefix):
                return None
            for ps, rs in zip(path_segments, prefix):
                if rs.startswith("{") and rs.endswith("}"):
                    continue  # param matches anything
                if ps != rs:
                    return None
            # Build params
            params = {}
            for ps, rs in zip(path_segments, prefix):
                if rs.startswith("{") and rs.endswith("}"):
                    params[rs[1:-1]] = ps
            # Wildcard captures the rest
            wildcard_text = route_segments[-1]
            if wildcard_text.startswith("*"):
                wildcard_name = wildcard_text[1:] or "path"
                params[wildcard_name] = "/".join(path_segments[len(prefix):])
            return params

        # Exact/param matching: must have same segment count
        if len(path_segments) != len(route_segments):
            return None

        params = {}
        for ps, rs in zip(path_segments, route_segments):
            if rs.startswith("{") and rs.endswith("}"):
                params[rs[1:-1]] = ps
            elif ps != rs:
                return None

        return params

    def __repr__(self) -> str:
        return f"<Route {self.method} {self.pattern}>"


class RouteGroup:
    """A group of routes sharing a common prefix."""

    def __init__(self, prefix: str, router: "Router"):
        self._prefix = prefix.rstrip("/")
        self._router = router

    def route(self, method: str, path: str, handler: HandlerFunc) -> Route:
        full_path = self._prefix + path
        return self._router.add_route(method, full_path, handler)

    def get(self, path: str):
        def decorator(fn):
            self.route("GET", path, fn)
            return fn
        return decorator

    def post(self, path: str):
        def decorator(fn):
            self.route("POST", path, fn)
            return fn
        return decorator

    def put(self, path: str):
        def decorator(fn):
            self.route("PUT", path, fn)
            return fn
        return decorator

    def delete(self, path: str):
        def decorator(fn):
            self.route("DELETE", path, fn)
            return fn
        return decorator


class Router:
    """URL router matching requests to handlers.

    Routes are matched in priority order:
        1. Exact match
        2. Parameterized match
        3. Wildcard match
    """

    def __init__(self):
        self._routes: list[Route] = []
        self._error_handlers: dict[int, HandlerFunc] = {}

    def add_route(self, method: str, pattern: str, handler: HandlerFunc) -> Route:
        """Register a route."""
        # Normalize pattern
        if not pattern.startswith("/"):
            pattern = "/" + pattern
        if len(pattern) > 1 and pattern.endswith("/") and not pattern.endswith("/*"):
            pattern = pattern.rstrip("/")

        route = Route(method, pattern, handler)
        self._routes.append(route)
        return route

    def get(self, pattern: str):
        def decorator(fn):
            self.add_route("GET", pattern, fn)
            return fn
        return decorator

    def post(self, pattern: str):
        def decorator(fn):
            self.add_route("POST", pattern, fn)
            return fn
        return decorator

    def put(self, pattern: str):
        def decorator(fn):
            self.add_route("PUT", pattern, fn)
            return fn
        return decorator

    def delete(self, pattern: str):
        def decorator(fn):
            self.add_route("DELETE", pattern, fn)
            return fn
        return decorator

    def patch(self, pattern: str):
        def decorator(fn):
            self.add_route("PATCH", pattern, fn)
            return fn
        return decorator

    def options(self, pattern: str):
        def decorator(fn):
            self.add_route("OPTIONS", pattern, fn)
            return fn
        return decorator

    def any(self, pattern: str):
        """Match any HTTP method."""
        def decorator(fn):
            self.add_route("ANY", pattern, fn)
            return fn
        return decorator

    def group(self, prefix: str) -> RouteGroup:
        """Create a route group with a shared prefix."""
        return RouteGroup(prefix, self)

    def error_handler(self, status_code: int):
        """Register a custom error handler for a status code."""
        def decorator(fn):
            self._error_handlers[status_code] = fn
            return fn
        return decorator

    def resolve(self, method: str, path: str) -> tuple[HandlerFunc, dict[str, str]]:
        """Find the matching handler for a method+path.

        Returns (handler, params) tuple.
        Raises NotFound or MethodNotAllowed.
        """
        method = method.upper()

        # Normalize path
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        if not path:
            path = "/"

        # Collect matches by priority: exact > param > wildcard
        exact_matches = []
        param_matches = []
        wildcard_matches = []
        method_seen = set()

        for route in self._routes:
            # Try with matching method first
            params = route.match(method, path)
            if params is not None:
                if route.is_wildcard:
                    wildcard_matches.append((route, params))
                elif route.param_names:
                    param_matches.append((route, params))
                else:
                    exact_matches.append((route, params))

            # Also check if path matches with different method (for 405)
            for m in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
                if route.match(m, path) is not None:
                    method_seen.add(route.method if route.method != "ANY" else m)

        # Return first match by priority
        for matches in (exact_matches, param_matches, wildcard_matches):
            if matches:
                route, params = matches[0]
                return route.handler, params

        # No match — check if it's a 405 or 404
        if method_seen:
            raise MethodNotAllowed(
                f"Method {method} not allowed for {path}",
                allowed=sorted(method_seen),
            )
        raise NotFound(f"No route matches {method} {path}")

    def get_error_handler(self, status_code: int) -> HandlerFunc | None:
        """Get custom error handler for a status code, if registered."""
        return self._error_handlers.get(status_code)

    @property
    def routes(self) -> list[Route]:
        return list(self._routes)

    def __len__(self) -> int:
        return len(self._routes)
