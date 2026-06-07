"""Request logging middleware.

Logs method, path, status code, and timing for every request.
"""

import time
import sys


class LoggerMiddleware:
    """Logs requests with method, path, status, and duration.

    Usage:
        app.use(LoggerMiddleware())
        # or with a custom stream:
        app.use(LoggerMiddleware(stream=my_file))
    """

    def __init__(self, stream=None, prefix: str = ""):
        self.stream = stream or sys.stdout
        self.prefix = prefix

    def __call__(self, req, res, next_handler):
        start = time.monotonic()
        client = f"{req.client_addr[0]}:{req.client_addr[1]}"

        next_handler(req, res)

        elapsed_ms = (time.monotonic() - start) * 1000
        status = res.status_code
        method = req.method
        path = req.path

        # Color-code status (works in terminals with ANSI support)
        if 200 <= status < 300:
            status_str = f"\033[32m{status}\033[0m"  # Green
        elif 300 <= status < 400:
            status_str = f"\033[36m{status}\033[0m"  # Cyan
        elif 400 <= status < 500:
            status_str = f"\033[33m{status}\033[0m"  # Yellow
        else:
            status_str = f"\033[31m{status}\033[0m"  # Red

        line = f"{self.prefix}{client} — {method} {path} → {status_str} ({elapsed_ms:.1f}ms)\n"
        self.stream.write(line)
        self.stream.flush()
