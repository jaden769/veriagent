"""Append-only structured traces with portable JSON export and readable rendering."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class TraceStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                "run_id TEXT NOT NULL, timestamp TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT)"
            )

    def append(self, run_id: str, kind: str, payload: BaseModel | dict[str, Any]) -> None:
        data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO events (run_id, timestamp, kind, payload) VALUES (?, ?, ?, ?)",
                (run_id, datetime.now(UTC).isoformat(), kind, json.dumps(data)),
            )

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(
                "SELECT seq, timestamp, kind, payload FROM events WHERE run_id = ? ORDER BY seq",
                (run_id,),
            ).fetchall()
        return [dict(seq=r[0], timestamp=r[1], kind=r[2], payload=json.loads(r[3])) for r in rows]

    def export(self, run_id: str, path: Path) -> None:
        path.write_text(json.dumps(self.events(run_id), indent=2) + "\n", encoding="utf-8")

    def render(self, run_id: str) -> str:
        return "\n".join(
            f"{e['seq']:04d} {e['kind']}: {json.dumps(e['payload'], sort_keys=True)}"
            for e in self.events(run_id)
        )
