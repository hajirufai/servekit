"""TCP server — the engine that listens, accepts connections, and dispatches requests.

Built on raw socket + selectors for non-blocking I/O, with a thread pool
for request handling so one slow handler doesn't block everything.
"""

import socket
import selectors
import threading
import signal
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from servekit.http_parser import HTTPParser, find_request_boundary
from servekit.request import Request
from servekit.response import Response
from servekit.websocket import is_websocket_upgrade, build_upgrade_response
from servekit.errors import HTTPError, STATUS_PHRASES


# Connection read buffer
RECV_BUFFER = 65536       # 64 KB per recv()
CONNECTION_TIMEOUT = 30   # Seconds before idle connection is closed


class TCPServer:
    """Low-level TCP server with non-blocking I/O and thread pool.

    Accepts connections, reads HTTP requests, and dispatches them to a
    handler callback. Supports keep-alive and WebSocket upgrades.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        workers: int = 4,
        max_body_size: int = 10_485_760,
        connection_timeout: int = CONNECTION_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.workers = workers
        self.parser = HTTPParser(max_body_size=max_body_size)
        self.connection_timeout = connection_timeout

        self._selector = selectors.DefaultSelector()
        self._server_socket: socket.socket | None = None
        self._running = False
        self._executor: ThreadPoolExecutor | None = None

        # Callback set by the app layer
        self.on_request = None       # (Request) -> Response
        self.on_websocket = None     # (socket, Request) -> None

        # Stats
        self.connections_total = 0
        self.requests_total = 0
        self.errors_total = 0

    def start(self) -> None:
        """Start the TCP server (blocking call)."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(128)
        self._server_socket.setblocking(False)

        self._selector.register(self._server_socket, selectors.EVENT_READ, data=None)
        self._executor = ThreadPoolExecutor(max_workers=self.workers)
        self._running = True

        # Handle graceful shutdown (only works in main thread)
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            pass  # Not in main thread (e.g. during tests)

        self._log(f"Listening on {self.host}:{self.port} (workers={self.workers})")

        try:
            self._event_loop()
        except Exception:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Shut down the server cleanly."""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False)
        if self._server_socket:
            try:
                self._selector.unregister(self._server_socket)
            except Exception:
                pass
            self._server_socket.close()
        self._selector.close()
        self._log("Server stopped")

    def _signal_handler(self, sig, frame):
        self._log(f"Received signal {sig}, shutting down...")
        self._running = False

    def _event_loop(self) -> None:
        """Main event loop using selectors for non-blocking I/O."""
        while self._running:
            events = self._selector.select(timeout=1.0)
            for key, mask in events:
                if key.data is None:
                    # New connection on server socket
                    self._accept_connection()
                else:
                    # Data on a client connection
                    self._executor.submit(self._handle_client, key)

    def _accept_connection(self) -> None:
        """Accept a new TCP connection."""
        try:
            conn, addr = self._server_socket.accept()
            conn.setblocking(True)  # Worker threads use blocking I/O
            conn.settimeout(self.connection_timeout)
            self._selector.register(
                conn, selectors.EVENT_READ,
                data={"addr": addr, "buffer": b""},
            )
            self.connections_total += 1
        except OSError:
            pass

    def _handle_client(self, key: selectors.SelectorKey) -> None:
        """Handle data from a client connection in a worker thread."""
        sock = key.fileobj
        data = key.data
        addr = data["addr"]

        try:
            # Unregister from selector while handling (prevents double-dispatch)
            try:
                self._selector.unregister(sock)
            except (KeyError, ValueError):
                return

            # Read loop: handle keep-alive (multiple requests per connection)
            buffer = data.get("buffer", b"")
            keep_alive = True

            while keep_alive and self._running:
                # Read data from socket
                try:
                    chunk = sock.recv(RECV_BUFFER)
                    if not chunk:
                        break  # Client closed connection
                    buffer += chunk
                except socket.timeout:
                    break
                except OSError:
                    break

                # Find complete request in buffer
                boundary = find_request_boundary(buffer)
                if boundary == -1:
                    continue  # Need more data

                # Parse the request
                request_data = buffer[:boundary]
                buffer = buffer[boundary:]

                try:
                    request = self.parser.parse(request_data, client_addr=addr)
                    self.requests_total += 1

                    # WebSocket upgrade?
                    if is_websocket_upgrade(request) and self.on_websocket:
                        upgrade_bytes = build_upgrade_response(request)
                        sock.sendall(upgrade_bytes)
                        self.on_websocket(sock, request)
                        return  # WebSocket takes over the socket

                    # Normal HTTP request
                    if self.on_request:
                        response = self.on_request(request)
                    else:
                        response = Response()
                        response.status(503).text("No request handler configured")

                    # Send response
                    sock.sendall(response.serialize())

                    # Check keep-alive
                    keep_alive = request.is_keep_alive and response.headers.get("Connection", "").lower() != "close"

                except HTTPError as exc:
                    self._send_error(sock, exc.status_code, exc.message)
                    self.errors_total += 1
                    break
                except Exception as exc:
                    self._send_error(sock, 500, "Internal Server Error")
                    self.errors_total += 1
                    self._log(f"Error handling request from {addr}: {exc}")
                    traceback.print_exc()
                    break

        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _send_error(self, sock: socket.socket, status_code: int, message: str) -> None:
        """Send an error response."""
        phrase = STATUS_PHRASES.get(status_code, "Error")
        body = f'{{"error": {{"status": {status_code}, "message": "{message}"}}}}'
        response = (
            f"HTTP/1.1 {status_code} {phrase}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        )
        try:
            sock.sendall(response.encode("utf-8"))
        except Exception:
            pass

    @staticmethod
    def _log(msg: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
