"""Simple in-memory rate limiter using a sliding window.

Limits requests per client IP within a time window.
"""

import time
from collections import defaultdict


class RateLimitMiddleware:
    """Rate limiting middleware using sliding window counters.

    Usage:
        app.use(RateLimitMiddleware(max_requests=100, window_seconds=60))
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def __call__(self, req, res, next_handler):
        client_ip = req.client_addr[0]
        now = time.monotonic()

        # Clean old entries outside the window
        timestamps = self._requests[client_ip]
        cutoff = now - self.window
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]
        timestamps = self._requests[client_ip]

        # Check limit
        if len(timestamps) >= self.max_requests:
            remaining = 0
            retry_after = int(self.window - (now - timestamps[0]))
            res.status(429)
            res.header("Retry-After", str(max(1, retry_after)))
            res.header("X-RateLimit-Limit", str(self.max_requests))
            res.header("X-RateLimit-Remaining", "0")
            res.json({"error": "Too many requests", "retry_after": max(1, retry_after)})
            return  # Short-circuit

        # Record this request
        timestamps.append(now)
        remaining = self.max_requests - len(timestamps)

        # Add rate limit headers
        res.header("X-RateLimit-Limit", str(self.max_requests))
        res.header("X-RateLimit-Remaining", str(remaining))

        next_handler(req, res)
