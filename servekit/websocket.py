"""WebSocket support — HTTP upgrade, frame parsing, and messaging.

Implements WebSocket protocol per RFC 6455:
- Upgrade handshake from HTTP/1.1
- Frame encoding/decoding (text, binary, ping, pong, close)
- Client masking
- Fragmented message support
"""

import struct
import hashlib
import base64
import os
from servekit.request import Request
from servekit.response import Response
from servekit.errors import BadRequest

# WebSocket magic GUID (RFC 6455 Section 4.2.2)
WS_MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Opcodes
OPCODE_CONTINUATION = 0x0
OPCODE_TEXT = 0x1
OPCODE_BINARY = 0x2
OPCODE_CLOSE = 0x8
OPCODE_PING = 0x9
OPCODE_PONG = 0xA


class WebSocketFrame:
    """A single WebSocket frame."""

    __slots__ = ("fin", "opcode", "masked", "payload")

    def __init__(self, fin: bool, opcode: int, payload: bytes, masked: bool = False):
        self.fin = fin
        self.opcode = opcode
        self.payload = payload
        self.masked = masked

    @property
    def is_text(self) -> bool:
        return self.opcode == OPCODE_TEXT

    @property
    def is_binary(self) -> bool:
        return self.opcode == OPCODE_BINARY

    @property
    def is_close(self) -> bool:
        return self.opcode == OPCODE_CLOSE

    @property
    def is_ping(self) -> bool:
        return self.opcode == OPCODE_PING

    @property
    def is_pong(self) -> bool:
        return self.opcode == OPCODE_PONG

    @property
    def is_control(self) -> bool:
        return self.opcode >= 0x8

    @property
    def text(self) -> str:
        """Decode payload as UTF-8 text."""
        return self.payload.decode("utf-8")

    def __repr__(self) -> str:
        opcode_names = {
            0x0: "CONT", 0x1: "TEXT", 0x2: "BIN",
            0x8: "CLOSE", 0x9: "PING", 0xA: "PONG",
        }
        name = opcode_names.get(self.opcode, f"0x{self.opcode:02x}")
        return f"<Frame {name} fin={self.fin} len={len(self.payload)}>"


def compute_accept_key(ws_key: str) -> str:
    """Compute the Sec-WebSocket-Accept key for the handshake.

    Per RFC 6455: SHA-1(key + magic_guid) → base64
    """
    combined = ws_key.strip() + WS_MAGIC_GUID
    sha1 = hashlib.sha1(combined.encode("utf-8")).digest()
    return base64.b64encode(sha1).decode("utf-8")


def is_websocket_upgrade(request: Request) -> bool:
    """Check if a request is a WebSocket upgrade request."""
    upgrade = request.headers.get("Upgrade", "").lower()
    connection = request.headers.get("Connection", "").lower()
    return upgrade == "websocket" and "upgrade" in connection


def build_upgrade_response(request: Request) -> bytes:
    """Build the HTTP 101 Switching Protocols response for a WebSocket upgrade.

    Returns raw bytes to send on the TCP socket.
    """
    ws_key = request.headers.get("Sec-WebSocket-Key")
    if not ws_key:
        raise BadRequest("Missing Sec-WebSocket-Key header")

    accept_key = compute_accept_key(ws_key)

    response_lines = [
        "HTTP/1.1 101 Switching Protocols",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Accept: {accept_key}",
        "",
        "",
    ]
    return "\r\n".join(response_lines).encode("utf-8")


def parse_frame(data: bytes) -> tuple[WebSocketFrame | None, int]:
    """Parse a WebSocket frame from raw bytes.

    Returns (frame, bytes_consumed) or (None, 0) if not enough data.
    """
    if len(data) < 2:
        return None, 0

    byte0 = data[0]
    byte1 = data[1]

    fin = bool(byte0 & 0x80)
    opcode = byte0 & 0x0F
    masked = bool(byte1 & 0x80)
    payload_length = byte1 & 0x7F

    offset = 2

    # Extended payload length
    if payload_length == 126:
        if len(data) < 4:
            return None, 0
        payload_length = struct.unpack("!H", data[2:4])[0]
        offset = 4
    elif payload_length == 127:
        if len(data) < 10:
            return None, 0
        payload_length = struct.unpack("!Q", data[2:10])[0]
        offset = 10

    # Masking key (4 bytes, if masked)
    mask_key = None
    if masked:
        if len(data) < offset + 4:
            return None, 0
        mask_key = data[offset:offset + 4]
        offset += 4

    # Payload
    if len(data) < offset + payload_length:
        return None, 0

    payload = bytearray(data[offset:offset + payload_length])

    # Unmask if needed
    if masked and mask_key:
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]

    total_consumed = offset + payload_length
    frame = WebSocketFrame(fin, opcode, bytes(payload), masked)
    return frame, total_consumed


def encode_frame(
    opcode: int,
    payload: bytes,
    fin: bool = True,
    mask: bool = False,
) -> bytes:
    """Encode data into a WebSocket frame.

    Server frames are typically unmasked. Client frames must be masked.
    """
    frame = bytearray()

    # Byte 0: FIN + opcode
    byte0 = (0x80 if fin else 0x00) | opcode
    frame.append(byte0)

    # Byte 1: MASK + payload length
    payload_len = len(payload)
    mask_bit = 0x80 if mask else 0x00

    if payload_len <= 125:
        frame.append(mask_bit | payload_len)
    elif payload_len <= 65535:
        frame.append(mask_bit | 126)
        frame.extend(struct.pack("!H", payload_len))
    else:
        frame.append(mask_bit | 127)
        frame.extend(struct.pack("!Q", payload_len))

    # Masking key + masked payload
    if mask:
        mask_key = os.urandom(4)
        frame.extend(mask_key)
        masked_payload = bytearray(payload)
        for i in range(len(masked_payload)):
            masked_payload[i] ^= mask_key[i % 4]
        frame.extend(masked_payload)
    else:
        frame.extend(payload)

    return bytes(frame)


def encode_text(text: str, mask: bool = False) -> bytes:
    """Encode a text message as a WebSocket frame."""
    return encode_frame(OPCODE_TEXT, text.encode("utf-8"), mask=mask)


def encode_binary(data: bytes, mask: bool = False) -> bytes:
    """Encode a binary message as a WebSocket frame."""
    return encode_frame(OPCODE_BINARY, data, mask=mask)


def encode_close(code: int = 1000, reason: str = "", mask: bool = False) -> bytes:
    """Encode a close frame with optional status code and reason."""
    payload = struct.pack("!H", code) + reason.encode("utf-8")
    return encode_frame(OPCODE_CLOSE, payload, mask=mask)


def encode_ping(data: bytes = b"", mask: bool = False) -> bytes:
    """Encode a ping frame."""
    return encode_frame(OPCODE_PING, data, mask=mask)


def encode_pong(data: bytes = b"", mask: bool = False) -> bytes:
    """Encode a pong frame (reply to ping)."""
    return encode_frame(OPCODE_PONG, data, mask=mask)
