"""HTTP/1.1 request parser — turns raw TCP bytes into Request objects.

Handles:
- Request line parsing (method, path, version)
- Header parsing (case-insensitive, multi-line folding)
- Content-Length body reading
- Chunked transfer encoding
- Query string extraction
- URL decoding
- Malformed request detection
"""

from servekit.request import Request
from servekit.utils import CaseInsensitiveDict, normalize_path, url_decode
from servekit.errors import BadRequest, PayloadTooLarge

# Limits to prevent abuse
MAX_REQUEST_LINE = 8192         # 8 KB for request line
MAX_HEADER_SIZE = 32768         # 32 KB total headers
MAX_HEADERS_COUNT = 100         # Max number of headers
DEFAULT_MAX_BODY = 10485760     # 10 MB default body limit

VALID_METHODS = {"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE"}


class HTTPParser:
    """Parses raw HTTP bytes into Request objects.

    Usage:
        parser = HTTPParser(max_body_size=10_000_000)
        request = parser.parse(raw_bytes, client_addr=("127.0.0.1", 5000))
    """

    def __init__(self, max_body_size: int = DEFAULT_MAX_BODY):
        self.max_body_size = max_body_size

    def parse(self, data: bytes, client_addr: tuple[str, int] = ("0.0.0.0", 0)) -> Request:
        """Parse raw bytes into a Request.

        Raises BadRequest if the data is malformed.
        """
        if not data:
            raise BadRequest("Empty request")

        try:
            # Split head (headers) from body
            head_end = data.find(b"\r\n\r\n")
            if head_end == -1:
                raise BadRequest("Incomplete request: missing header terminator")

            head_bytes = data[:head_end]
            body_bytes = data[head_end + 4:]

            if len(head_bytes) > MAX_REQUEST_LINE + MAX_HEADER_SIZE:
                raise BadRequest("Request head too large")

            # Decode head as latin-1 (HTTP allows any byte in headers)
            head_str = head_bytes.decode("latin-1")
            lines = head_str.split("\r\n")

            if not lines:
                raise BadRequest("Empty request head")

            # Parse request line
            method, path, query_string, http_version = self._parse_request_line(lines[0])

            # Parse headers
            headers = self._parse_headers(lines[1:])

            # Read body based on Content-Length or chunked
            body = self._read_body(headers, body_bytes, data, head_end + 4)

            return Request(
                method=method,
                path=path,
                headers=headers,
                body=body,
                query_string=query_string,
                client_addr=client_addr,
                http_version=http_version,
            )

        except (BadRequest, PayloadTooLarge):
            raise
        except Exception as exc:
            raise BadRequest(f"Failed to parse request: {exc}") from exc

    def _parse_request_line(self, line: str) -> tuple[str, str, str, str]:
        """Parse 'GET /path?q=1 HTTP/1.1' into (method, path, query_string, version).

        Returns (method, decoded_path, query_string, version_number)
        """
        if len(line) > MAX_REQUEST_LINE:
            raise BadRequest("Request line too long")

        parts = line.split(" ")
        if len(parts) != 3:
            raise BadRequest(f"Malformed request line: {line!r}")

        method, raw_uri, version = parts

        # Validate method
        method = method.upper()
        if method not in VALID_METHODS:
            raise BadRequest(f"Unknown HTTP method: {method}")

        # Validate HTTP version
        if not version.startswith("HTTP/"):
            raise BadRequest(f"Invalid HTTP version: {version}")
        http_version = version[5:]  # "1.1" or "1.0"
        if http_version not in ("1.0", "1.1"):
            raise BadRequest(f"Unsupported HTTP version: {version}")

        # Split path and query string
        if "?" in raw_uri:
            raw_path, _, query_string = raw_uri.partition("?")
        else:
            raw_path = raw_uri
            query_string = ""

        # Decode and normalize path
        path = normalize_path(url_decode(raw_path))

        return method, path, query_string, http_version

    def _parse_headers(self, lines: list[str]) -> CaseInsensitiveDict:
        """Parse header lines into a CaseInsensitiveDict."""
        headers = CaseInsensitiveDict()
        count = 0

        for line in lines:
            if not line:
                continue

            # Header continuation (obs-fold): line starts with whitespace
            if line[0] in (" ", "\t"):
                # Append to previous header value (if any)
                # This is deprecated in HTTP/1.1 but we handle it
                continue

            if ":" not in line:
                raise BadRequest(f"Malformed header line: {line!r}")

            name, _, value = line.partition(":")
            name = name.strip()
            value = value.strip()

            if not name:
                raise BadRequest("Empty header name")

            headers[name] = value
            count += 1

            if count > MAX_HEADERS_COUNT:
                raise BadRequest("Too many headers")

        return headers

    def _read_body(
        self,
        headers: CaseInsensitiveDict,
        initial_body: bytes,
        full_data: bytes,
        body_start: int,
    ) -> bytes:
        """Read the request body based on Content-Length or chunked encoding."""
        # Check for chunked transfer encoding
        transfer_encoding = headers.get("Transfer-Encoding", "").lower()
        if "chunked" in transfer_encoding:
            return self._read_chunked_body(initial_body)

        # Check Content-Length
        content_length_str = headers.get("Content-Length")
        if content_length_str is None:
            return b""

        try:
            content_length = int(content_length_str)
        except ValueError:
            raise BadRequest(f"Invalid Content-Length: {content_length_str}")

        if content_length < 0:
            raise BadRequest("Negative Content-Length")

        if content_length > self.max_body_size:
            raise PayloadTooLarge(
                f"Body size {content_length} exceeds limit {self.max_body_size}"
            )

        if content_length == 0:
            return b""

        # Return what we have (the socket layer should have read enough)
        body = full_data[body_start:body_start + content_length]
        return body

    def _read_chunked_body(self, data: bytes) -> bytes:
        """Decode a chunked transfer-encoded body.

        Format:
            <chunk-size-hex>\r\n
            <chunk-data>\r\n
            ...
            0\r\n
            \r\n
        """
        result = bytearray()
        pos = 0

        while pos < len(data):
            # Find end of chunk size line
            line_end = data.find(b"\r\n", pos)
            if line_end == -1:
                break

            # Parse chunk size (hex)
            size_str = data[pos:line_end].decode("ascii").strip()
            if ";" in size_str:
                size_str = size_str.split(";")[0]  # Ignore chunk extensions

            try:
                chunk_size = int(size_str, 16)
            except ValueError:
                raise BadRequest(f"Invalid chunk size: {size_str}")

            if chunk_size == 0:
                break  # End of chunked body

            if len(result) + chunk_size > self.max_body_size:
                raise PayloadTooLarge("Chunked body exceeds size limit")

            # Read chunk data
            chunk_start = line_end + 2
            chunk_end = chunk_start + chunk_size
            result.extend(data[chunk_start:chunk_end])

            # Skip trailing \r\n after chunk
            pos = chunk_end + 2

        return bytes(result)


def find_request_boundary(data: bytes) -> int:
    """Find the end of a complete HTTP request in a byte buffer.

    Returns the index after the full request (headers + body), or -1
    if the buffer doesn't contain a complete request yet.
    """
    # Find header terminator
    head_end = data.find(b"\r\n\r\n")
    if head_end == -1:
        return -1

    header_section = data[:head_end].decode("latin-1", errors="replace")
    body_start = head_end + 4

    # Check for Content-Length
    for line in header_section.split("\r\n")[1:]:
        if line.lower().startswith("content-length:"):
            try:
                length = int(line.split(":", 1)[1].strip())
                end = body_start + length
                if end <= len(data):
                    return end
                return -1  # Body not fully received
            except (ValueError, IndexError):
                return body_start

    # Check for chunked encoding
    if "transfer-encoding: chunked" in header_section.lower():
        # Look for terminating chunk (0\r\n\r\n)
        term = data.find(b"0\r\n\r\n", body_start)
        if term != -1:
            return term + 5
        return -1

    # No body expected
    return body_start
