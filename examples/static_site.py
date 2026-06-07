"""Static file server — serves files from a directory with caching and MIME types."""

import sys
import os
sys.path.insert(0, "..")

from servekit import ServeKit
from servekit.builtin_middleware import LoggerMiddleware

app = ServeKit()
app.use(LoggerMiddleware())

# Serve static files from the templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
app.static("/", templates_dir, show_directory=True)

if __name__ == "__main__":
    app.listen(8080)
