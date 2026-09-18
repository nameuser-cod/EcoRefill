"""Durable pending rewards and refill outcomes; never stores executable commands."""

from contextlib import closing
import json
from .upload_queue import RecyclingUploadQueue


class MachineJournal(RecyclingUploadQueue):
    def __init__(self, path):
        super().__init__(path)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS journal (
                kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(kind, id))""")

    def save(self, kind, key, data):
        encoded = json.dumps(data, allow_nan=False)
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO journal VALUES (?, ?, ?)", (kind, key, encoded))

    def entries(self, kind):
        with closing(self.connect()) as db:
            rows = db.execute("SELECT id, payload FROM journal WHERE kind = ? ORDER BY rowid", (kind,)).fetchall()
        return [(key, json.loads(payload)) for key, payload in rows]

    def delete(self, kind, key):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM journal WHERE kind = ? AND id = ?", (kind, key))

    def recover_refills(self):
        # A reservation never starts hardware until 'executing' is durable.
        # After that boundary, a restart cannot prove how much water came out.
        for key, record in self.entries("refill"):
            if record["outcome"] in {"preparing", "reserved"}:
                record.update(outcome="reservation_unknown", error="Restarted before dispensing.")
                self.save("refill", key, record)
            elif record["outcome"] == "executing":
                record.update(outcome="uncertain", error="Restarted during dispensing; owner review required.")
                self.save("refill", key, record)
