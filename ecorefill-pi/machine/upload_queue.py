"""Durable FIFO of scan records. Network calls never hold a SQLite lock."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3


class RecyclingUploadQueue:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS uploads (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS photos (
                item_id TEXT PRIMARY KEY, image TEXT NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def put(self, payload):
        encoded = json.dumps(payload, allow_nan=False)
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO uploads(item_id, payload) VALUES (?, ?)",
                       (payload["item_id"], encoded))

    def peek(self):
        with closing(self.connect()) as db:
            row = db.execute("SELECT payload FROM uploads ORDER BY sequence LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def remove(self, item_id):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM uploads WHERE item_id = ?", (item_id,))

    def contains(self, item_id):
        with closing(self.connect()) as db:
            return db.execute("SELECT 1 FROM uploads WHERE item_id = ?", (item_id,)).fetchone() is not None

    def acknowledge(self, payload):
        """Move its photo to low priority atomically with removing the record."""
        with closing(self.connect()) as db, db:
            if payload.get("image_data_url"):
                db.execute("INSERT OR IGNORE INTO photos VALUES (?, ?)",
                           (payload["item_id"], payload["image_data_url"]))
            db.execute("DELETE FROM uploads WHERE item_id = ?", (payload["item_id"],))

    def peek_photo(self):
        with closing(self.connect()) as db:
            return db.execute("SELECT item_id, image FROM photos ORDER BY rowid LIMIT 1").fetchone()

    def remove_photo(self, item_id):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM photos WHERE item_id = ?", (item_id,))
