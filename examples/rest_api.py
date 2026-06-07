"""REST API demo — CRUD operations with JSON, showing how to build
a real API with ServeKit (in-memory storage for simplicity)."""

import sys
sys.path.insert(0, "..")

from servekit import ServeKit
from servekit.builtin_middleware import LoggerMiddleware, CORSMiddleware

app = ServeKit()

# Middleware
app.use(LoggerMiddleware())
app.use(CORSMiddleware(allow_origins=["*"]))

# In-memory "database"
books = {}
next_id = 1


@app.get("/api/books")
def list_books(req, res):
    """List all books."""
    res.json({"books": list(books.values()), "count": len(books)})


@app.get("/api/books/{id}")
def get_book(req, res):
    """Get a single book by ID."""
    book_id = req.params["id"]
    if book_id not in books:
        res.status(404).json({"error": "Book not found"})
        return
    res.json(books[book_id])


@app.post("/api/books")
def create_book(req, res):
    """Create a new book."""
    global next_id
    data = req.json()
    book = {
        "id": str(next_id),
        "title": data.get("title", "Untitled"),
        "author": data.get("author", "Unknown"),
        "year": data.get("year"),
    }
    books[book["id"]] = book
    next_id += 1
    res.status(201).json(book)


@app.put("/api/books/{id}")
def update_book(req, res):
    """Update an existing book."""
    book_id = req.params["id"]
    if book_id not in books:
        res.status(404).json({"error": "Book not found"})
        return
    data = req.json()
    books[book_id].update({k: v for k, v in data.items() if k != "id"})
    res.json(books[book_id])


@app.delete("/api/books/{id}")
def delete_book(req, res):
    """Delete a book."""
    book_id = req.params["id"]
    if book_id not in books:
        res.status(404).json({"error": "Book not found"})
        return
    deleted = books.pop(book_id)
    res.json({"deleted": deleted})


if __name__ == "__main__":
    app.listen(8080)
