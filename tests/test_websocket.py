"""Tests for WebSocket frame parsing and encoding."""

import struct
import pytest
from servekit.websocket import (
    parse_frame,
    encode_frame,
    encode_text,
    encode_binary,
    encode_close,
    encode_ping,
    encode_pong,
    compute_accept_key,
    is_websocket_upgrade,
    build_upgrade_response,
    WebSocketFrame,
    OPCODE_TEXT,
    OPCODE_BINARY,
    OPCODE_CLOSE,
    OPCODE_PING,
    OPCODE_PONG,
)
from servekit.request import Request
from servekit.utils import CaseInsensitiveDict


class TestFrameEncoding:
    """Test encoding WebSocket frames."""

    def test_encode_text(self):
        frame = encode_text("Hello")
        # First byte: FIN(1) + TEXT(0x1) = 0x81
        assert frame[0] == 0x81
        # Second byte: no mask + length 5
        assert frame[1] == 5
        assert frame[2:] == b"Hello"

    def test_encode_binary(self):
        data = b"\x00\x01\x02"
        frame = encode_binary(data)
        assert frame[0] == 0x82  # FIN + BINARY
        assert frame[1] == 3
        assert frame[2:] == data

    def test_encode_medium_payload(self):
        # Payload 126-65535 uses 2-byte extended length
        data = b"x" * 200
        frame = encode_frame(OPCODE_TEXT, data)
        assert frame[0] == 0x81
        assert frame[1] == 126  # Extended length marker
        length = struct.unpack("!H", frame[2:4])[0]
        assert length == 200
        assert frame[4:] == data

    def test_encode_large_payload(self):
        # Payload > 65535 uses 8-byte extended length
        data = b"x" * 70000
        frame = encode_frame(OPCODE_TEXT, data)
        assert frame[1] == 127  # 8-byte extended length marker
        length = struct.unpack("!Q", frame[2:10])[0]
        assert length == 70000

    def test_encode_masked(self):
        frame = encode_text("Hi", mask=True)
        assert frame[1] & 0x80 == 0x80  # Mask bit set
        # 4-byte mask key after length
        # Total: 1 (byte0) + 1 (byte1) + 4 (mask) + 2 (payload) = 8
        assert len(frame) == 8

    def test_encode_close(self):
        frame = encode_close(1000, "goodbye")
        assert frame[0] == 0x88  # FIN + CLOSE
        payload = frame[2:]
        code = struct.unpack("!H", payload[:2])[0]
        assert code == 1000
        assert payload[2:] == b"goodbye"

    def test_encode_ping(self):
        frame = encode_ping(b"ping")
        assert frame[0] == 0x89  # FIN + PING
        assert frame[2:] == b"ping"

    def test_encode_pong(self):
        frame = encode_pong(b"pong")
        assert frame[0] == 0x8A  # FIN + PONG
        assert frame[2:] == b"pong"

    def test_encode_empty(self):
        frame = encode_text("")
        assert frame[0] == 0x81
        assert frame[1] == 0
        assert len(frame) == 2


class TestFrameParsing:
    """Test parsing WebSocket frames."""

    def test_parse_text(self):
        raw = encode_text("Hello")
        frame, consumed = parse_frame(raw)
        assert frame is not None
        assert frame.opcode == OPCODE_TEXT
        assert frame.text == "Hello"
        assert frame.fin is True
        assert consumed == len(raw)

    def test_parse_binary(self):
        data = b"\xDE\xAD\xBE\xEF"
        raw = encode_binary(data)
        frame, consumed = parse_frame(raw)
        assert frame.opcode == OPCODE_BINARY
        assert frame.payload == data

    def test_parse_masked_frame(self):
        raw = encode_text("Hi", mask=True)
        frame, consumed = parse_frame(raw)
        assert frame is not None
        assert frame.text == "Hi"
        assert frame.masked is True

    def test_parse_close(self):
        raw = encode_close(1000, "bye")
        frame, consumed = parse_frame(raw)
        assert frame.is_close

    def test_parse_ping(self):
        raw = encode_ping(b"test")
        frame, consumed = parse_frame(raw)
        assert frame.is_ping
        assert frame.payload == b"test"

    def test_parse_pong(self):
        raw = encode_pong(b"test")
        frame, consumed = parse_frame(raw)
        assert frame.is_pong

    def test_parse_incomplete(self):
        # Only one byte — not enough
        frame, consumed = parse_frame(b"\x81")
        assert frame is None
        assert consumed == 0

    def test_parse_incomplete_payload(self):
        # Header says 100 bytes but only 5 provided
        raw = b"\x81\x64" + b"short"  # 0x64 = 100
        frame, consumed = parse_frame(raw)
        assert frame is None

    def test_parse_medium_payload(self):
        data = b"y" * 300
        raw = encode_frame(OPCODE_TEXT, data)
        frame, consumed = parse_frame(raw)
        assert frame is not None
        assert len(frame.payload) == 300

    def test_roundtrip(self):
        """Encode → parse should recover original data."""
        for text in ["", "a", "Hello, World!", "🎉" * 50, "x" * 10000]:
            raw = encode_text(text)
            frame, _ = parse_frame(raw)
            assert frame.text == text


class TestFrameProperties:
    """Test WebSocketFrame properties."""

    def test_is_text(self):
        f = WebSocketFrame(True, OPCODE_TEXT, b"hi")
        assert f.is_text is True
        assert f.is_binary is False

    def test_is_binary(self):
        f = WebSocketFrame(True, OPCODE_BINARY, b"\x00")
        assert f.is_binary is True
        assert f.is_text is False

    def test_is_control(self):
        f_close = WebSocketFrame(True, OPCODE_CLOSE, b"")
        f_ping = WebSocketFrame(True, OPCODE_PING, b"")
        f_text = WebSocketFrame(True, OPCODE_TEXT, b"")
        assert f_close.is_control is True
        assert f_ping.is_control is True
        assert f_text.is_control is False

    def test_repr(self):
        f = WebSocketFrame(True, OPCODE_TEXT, b"hello")
        assert "TEXT" in repr(f)
        assert "len=5" in repr(f)


class TestHandshake:
    """Test WebSocket upgrade handshake."""

    def test_compute_accept_key(self):
        # Known test vector from RFC 6455
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        expected = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        assert compute_accept_key(key) == expected

    def test_is_websocket_upgrade(self):
        req = Request(
            method="GET",
            path="/ws",
            headers=CaseInsensitiveDict({
                "Upgrade": "websocket",
                "Connection": "Upgrade",
                "Sec-WebSocket-Key": "test-key",
            }),
        )
        assert is_websocket_upgrade(req) is True

    def test_not_websocket_upgrade(self):
        req = Request(method="GET", path="/", headers=CaseInsensitiveDict())
        assert is_websocket_upgrade(req) is False

    def test_build_upgrade_response(self):
        req = Request(
            method="GET",
            path="/ws",
            headers=CaseInsensitiveDict({
                "Upgrade": "websocket",
                "Connection": "Upgrade",
                "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            }),
        )
        response = build_upgrade_response(req)
        response_str = response.decode("utf-8")
        assert "101 Switching Protocols" in response_str
        assert "Upgrade: websocket" in response_str
        assert "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" in response_str
