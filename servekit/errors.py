"""HTTP error classes for clean error handling."""


class HTTPError(Exception):
    """Base HTTP error with status code and message."""

    def __init__(self, status_code: int = 500, message: str = ""):
        self.status_code = status_code
        self.message = message or self._default_message()
        super().__init__(self.message)

    def _default_message(self) -> str:
        defaults = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            408: "Request Timeout",
            413: "Payload Too Large",
            429: "Too Many Requests",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
        }
        return defaults.get(self.status_code, "Unknown Error")

    def to_dict(self) -> dict:
        return {
            "error": {
                "status": self.status_code,
                "message": self.message,
            }
        }


class BadRequest(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(400, message)


class Unauthorized(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(401, message)


class Forbidden(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(403, message)


class NotFound(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(404, message)


class MethodNotAllowed(HTTPError):
    def __init__(self, message: str = "", allowed: list[str] | None = None):
        self.allowed_methods = allowed or []
        super().__init__(405, message)


class RequestTimeout(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(408, message)


class PayloadTooLarge(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(413, message)


class TooManyRequests(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(429, message)


class InternalServerError(HTTPError):
    def __init__(self, message: str = ""):
        super().__init__(500, message)


# Status code to reason phrase mapping
STATUS_PHRASES = {
    100: "Continue",
    101: "Switching Protocols",
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    413: "Payload Too Large",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}
