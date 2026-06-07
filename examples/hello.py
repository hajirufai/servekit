"""Minimal hello world — the simplest possible ServeKit app."""

import sys
sys.path.insert(0, "..")

from servekit import ServeKit

app = ServeKit()


@app.get("/")
def home(req, res):
    res.json({"message": "Hello, World!", "path": req.path})


@app.get("/greet/{name}")
def greet(req, res):
    name = req.params["name"]
    res.json({"greeting": f"Hello, {name}!"})


if __name__ == "__main__":
    app.listen(8080)
