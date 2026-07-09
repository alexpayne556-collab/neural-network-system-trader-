import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class Constitution:
    """The governance layer for Cosmo: proposals, votes, and graveyard checks."""

    def __init__(self, db_path: Optional[str] = None):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.db_path = db_path or str(self.repo_root / "cosmo.sqlite")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        schema_path = self.repo_root / "schema" / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        with schema_path.open("r", encoding="utf-8") as handle:
            sql = handle.read()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(sql)
            conn.commit()

    def create_proposal(self, proposal_type: str, target_entity: Optional[str], thesis: str, evidence_json: Optional[Dict[str, Any]] = None, agent_id: str = "system") -> str:
        proposal_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO proposals (id, proposal_type, target_entity, thesis, evidence_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                (proposal_id, proposal_type, target_entity, thesis, repr(evidence_json or {}), "PENDING"),
            )
            conn.execute(
                "INSERT INTO ledger (proposal_id, agent_id, bill_type, justification, evidence_class, status) VALUES (?, ?, ?, ?, ?, ?)",
                (proposal_id, agent_id, proposal_type, thesis, "[HYPOTHESIS]", "PENDING"),
            )
            conn.commit()
        return proposal_id

    def add_vote(self, proposal_id: str, agent_id: str, vote: str, rationale: Optional[str] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO proposal_votes (proposal_id, agent_id, vote, rationale) VALUES (?, ?, ?, ?)",
                (proposal_id, agent_id, vote, rationale),
            )
            conn.commit()

    def add_graveyard_entry(self, ticker: str, cause_of_death: str, strategy_type: str, audit_log_ref: Optional[str] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO graveyard (ticker, cause_of_death, kill_date, strategy_type, audit_log_ref) VALUES (?, ?, ?, ?, ?)",
                (ticker, cause_of_death, "CURRENT_TIMESTAMP", strategy_type, audit_log_ref),
            )
            conn.commit()

    def list_proposals(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, proposal_type, target_entity, thesis, evidence_json, status FROM proposals ORDER BY created_at"
            ).fetchall()
        return [
            {
                "id": row[0],
                "proposal_type": row[1],
                "target_entity": row[2],
                "thesis": row[3],
                "evidence_json": row[4],
                "status": row[5],
            }
            for row in rows
        ]
