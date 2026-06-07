"""WebSocket echo server — demonstrates WebSocket upgrade and frame handling."""

import sys
sys.path.insert(0, "..")

from servekit import ServeKit
from servekit.websocket import parse_frame, encode_text, encode_pong, OPCODE_TEXT, OPCODE_PING, OPCODE_CLOSE

app = ServeKit()


@app.get("/")
def home(req, res):
    res.html("""
    <!DOCTYPE html>
    <html>
    <head><title>ServeKit WebSocket Demo</title></head>
    <body>
        <h1>WebSocket Echo</h1>
        <input id="msg" placeholder="Type a message..." />
        <button onclick="send()">Send</button>
        <pre id="log"></pre>
        <script>
            const ws = new WebSocket("ws://localhost:8080/ws");
            const log = document.getElementById("log");
            ws.onmessage = (e) => { log.textContent += "← " + e.data + "\\n"; };
            ws.onopen = () => { log.textContent += "Connected!\\n"; };
            ws.onclose = () => { log.textContent += "Disconnected.\\n"; };
            function send() {
                const msg = document.getElementById("msg").value;
                ws.send(msg);
                log.textContent += "→ " + msg + "\\n";
                document.getElementById("msg").value = "";
            }
        </script>
    </body>
    </html>
    """)


@app.websocket("/ws")
def ws_echo(sock, request):
    """Echo every text message back to the client."""
    buffer = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk

            while buffer:
                frame, consumed = parse_frame(buffer)
                if frame is None:
                    break
                buffer = buffer[consumed:]

                if frame.is_text:
                    response = encode_text(f"Echo: {frame.text}")
                    sock.sendall(response)
                elif frame.is_ping:
                    sock.sendall(encode_pong(frame.payload))
                elif frame.is_close:
                    return
        except Exception:
            break


if __name__ == "__main__":
    app.listen(8080)
