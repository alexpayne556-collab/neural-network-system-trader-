import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


class CosmoLedger:
    """A lightweight stateful ledger for thesis, evidence, and kill conditions."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(os.getcwd(), "cosmo.sqlite")
        self._initialize()

    def close(self) -> None:
        """No-op for API consistency with other components."""
        pass

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS theses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    tags TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thesis_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(thesis_id) REFERENCES theses(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kill_conditions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thesis_id INTEGER NOT NULL,
                    condition_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(thesis_id) REFERENCES theses(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def create_thesis(self, title: str, hypothesis: str, owner: str, tags: Optional[List[str]] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO theses (title, hypothesis, owner, tags) VALUES (?, ?, ?, ?)",
                (title, hypothesis, owner, json.dumps(tags or [])),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def add_evidence(self, thesis_id: int, source_type: str, summary: str, payload: Optional[Dict[str, Any]] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO evidence (thesis_id, source_type, summary, payload) VALUES (?, ?, ?, ?)",
                (thesis_id, source_type, summary, json.dumps(payload or {})),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def add_kill_condition(self, thesis_id: int, condition_name: str, description: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO kill_conditions (thesis_id, condition_name, description) VALUES (?, ?, ?)",
                (thesis_id, condition_name, description),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_thesis(self, thesis_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, title, hypothesis, owner, tags FROM theses WHERE id = ?",
                (thesis_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "hypothesis": row[2],
            "owner": row[3],
            "tags": json.loads(row[4] or "[]"),
        }

    def list_evidence(self, thesis_id: int) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, thesis_id, source_type, summary, payload FROM evidence WHERE thesis_id = ? ORDER BY id",
                (thesis_id,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "thesis_id": row[1],
                "source_type": row[2],
                "summary": row[3],
                "payload": json.loads(row[4] or "{}"),
            }
            for row in rows
        ]

    def list_kill_conditions(self, thesis_id: int) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, thesis_id, condition_name, description FROM kill_conditions WHERE thesis_id = ? ORDER BY id",
                (thesis_id,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "thesis_id": row[1],
                "condition_name": row[2],
                "description": row[3],
            }
            for row in rows
        ]

    def log_raw_event(self, source: str, event_type: str, entity: str, summary: str, payload: Optional[Dict[str, Any]] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO raw_events (source, event_type, entity, summary, payload) VALUES (?, ?, ?, ?, ?)",
                (source, event_type, entity, summary, json.dumps(payload or {})),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_raw_events(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, source, event_type, entity, summary, payload FROM raw_events ORDER BY id"
            ).fetchall()
        return [
            {
                "id": row[0],
                "source": row[1],
                "event_type": row[2],
                "entity": row[3],
                "summary": row[4],
                "payload": json.loads(row[5] or "{}"),
            }
            for row in rows
        ]
