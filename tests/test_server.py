"""Integration tests — spin up a real TCP server and make requests."""

import socket
import threading
import time
import json
import pytest
from servekit.app import ServeKit


def get_free_port():
    """Find a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def send_request(port, raw_request):
    """Send a raw HTTP request and return the raw response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(("127.0.0.1", port))
        sock.sendall(raw_request)
        # Read response
        chunks = []
        while True:
            try:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
                # Check if we got a complete response
                full = b"".join(chunks)
                if b"\r\n\r\n" in full:
                    # Check if there's a Content-Length
                    head, _, body = full.partition(b"\r\n\r\n")
                    for line in head.decode("latin-1").split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            expected = int(line.split(":")[1].strip())
                            if len(body) >= expected:
                                return full
                    # No content-length, or connection: close
                    if b"connection: close" in head.lower():
                        continue
                    return full
            except socket.timeout:
                break
        return b"".join(chunks)
    finally:
        sock.close()


@pytest.fixture
def app_server():
    """Create an app, start it in a background thread, yield (app, port), then stop."""
    app = ServeKit()
    port = get_free_port()

    @app.get("/")
    def home(req, res):
        res.json({"message": "Hello"})

    @app.get("/users/{id}")
    def get_user(req, res):
        res.json({"id": req.params["id"]})

    @app.post("/echo")
    def echo(req, res):
        data = req.json()
        res.status(201).json({"echoed": data})

    @app.get("/error")
    def error_route(req, res):
        raise ValueError("test error")

    thread = threading.Thread(
        target=app.listen,
        kwargs={"port": port, "host": "127.0.0.1", "workers": 2},
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)  # Wait for server to start

    yield app, port

    app.stop()


class TestServerIntegration:
    """Full integration tests with actual TCP connections."""

    def test_get_root(self, app_server):
        _, port = app_server
        raw = b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        response = send_request(port, raw)
        assert b"200 OK" in response
        assert b'"message"' in response

    def test_get_with_params(self, app_server):
        _, port = app_server
        raw = b"GET /users/42 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        response = send_request(port, raw)
        assert b"200 OK" in response
        assert b'"id"' in response
        assert b'"42"' in response

    def test_post_json(self, app_server):
        _, port = app_server
        body = b'{"name": "Haji"}'
        raw = (
            b"POST /echo HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Connection: close\r\n"
            b"\r\n" + body
        )
        response = send_request(port, raw)
        assert b"201 Created" in response
        assert b'"Haji"' in response

    def test_404_not_found(self, app_server):
        _, port = app_server
        raw = b"GET /nonexistent HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        response = send_request(port, raw)
        assert b"404" in response

    def test_server_error(self, app_server):
        _, port = app_server
        raw = b"GET /error HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        response = send_request(port, raw)
        assert b"500" in response
