"""Basic HTTP authentication middleware.

Checks the Authorization header for valid Basic auth credentials.
"""

import base64


class BasicAuthMiddleware:
    """Basic HTTP authentication.

    Usage:
        users = {"admin": "secret", "reader": "pass123"}
        app.use(BasicAuthMiddleware(users, realm="My API"))
    """

    def __init__(self, users: dict[str, str], realm: str = "ServeKit"):
        self.users = users  # username -> password
        self.realm = realm

    def __call__(self, req, res, next_handler):
        auth_header = req.headers.get("Authorization", "")

        if not auth_header.startswith("Basic "):
            self._send_challenge(res)
            return

        try:
            encoded = auth_header[6:]  # Strip "Basic "
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            self._send_challenge(res)
            return

        if username not in self.users or self.users[username] != password:
            self._send_challenge(res)
            return

        # Auth passed — store username on request for downstream handlers
        req.params["_auth_user"] = username
        next_handler(req, res)

    def _send_challenge(self, res):
        """Send a 401 Unauthorized response with WWW-Authenticate header."""
        res.status(401)
        res.header("WWW-Authenticate", f'Basic realm="{self.realm}"')
        res.json({"error": "Unauthorized", "message": "Valid credentials required"})
