"""Middleware chain — before/after hooks wrapping request handlers.

Middleware functions receive (request, response, next_handler) and can:
- Modify the request before it reaches the handler
- Short-circuit by setting a response without calling next_handler
- Modify the response after the handler runs
"""

from __future__ import annotations
from typing import Callable
from servekit.request import Request
from servekit.response import Response


MiddlewareFunc = Callable  # (Request, Response, next) -> None
HandlerFunc = Callable     # (Request, Response) -> None


class MiddlewareChain:
    """Manages an ordered chain of middleware functions.

    Middleware is executed in FIFO order. Each middleware must call
    next_handler(req, res) to continue the chain, or skip it to
    short-circuit (e.g., return 401 for auth failure).

    Example:
        chain = MiddlewareChain()

        def log_middleware(req, res, next_handler):
            print(f"→ {req.method} {req.path}")
            next_handler(req, res)
            print(f"← {res.status_code}")

        chain.add(log_middleware)
    """

    def __init__(self):
        self._middlewares: list[MiddlewareFunc] = []

    def add(self, middleware: MiddlewareFunc) -> None:
        """Add a middleware function to the chain."""
        self._middlewares.append(middleware)

    def execute(self, request: Request, response: Response, handler: HandlerFunc) -> None:
        """Execute the full middleware chain, then the final handler.

        Builds a nested chain: mw1 → mw2 → mw3 → handler
        Each middleware calls next_handler to proceed, or skips it
        to short-circuit the chain.
        """
        # Build the chain from inside out
        # Start with the actual route handler
        def final(req: Request, res: Response):
            handler(req, res)

        # Wrap each middleware around the chain (reverse order)
        chain = final
        for mw in reversed(self._middlewares):
            chain = self._wrap(mw, chain)

        # Execute the chain
        chain(request, response)

    @staticmethod
    def _wrap(middleware: MiddlewareFunc, next_handler: HandlerFunc) -> HandlerFunc:
        """Wrap a middleware around a next_handler, producing a new handler."""
        def wrapped(req: Request, res: Response):
            middleware(req, res, next_handler)
        return wrapped

    def __len__(self) -> int:
        return len(self._middlewares)

    @property
    def middlewares(self) -> list[MiddlewareFunc]:
        return list(self._middlewares)
