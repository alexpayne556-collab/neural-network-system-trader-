import json
import sqlite3
from typing import Any, Dict, List, Optional


class ReconciliationEngine:
    """Tracks trade outcomes and blocks repeated thesis failures."""

    def __init__(self, ledger: Any):
        self.ledger = ledger
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.ledger.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    expected_window TEXT NOT NULL,
                    actual_outcome TEXT NOT NULL,
                    correctness_split TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    realized_pnl REAL,
                    expected_return REAL,
                    notes TEXT,
                    cost_of_error REAL,
                    death_certificate TEXT,
                    proposer TEXT NOT NULL DEFAULT 'tyr',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def log_trade(
        self,
        ticker: str,
        thesis: str,
        trigger: str,
        expected_window: str,
        actual_outcome: str,
        correctness_split: Dict[str, float],
        trade_type: str,
        proposer: str = "tyr",
    ) -> int:
        with sqlite3.connect(self.ledger.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO trades (
                    ticker, thesis, trigger, expected_window, actual_outcome,
                    correctness_split, trade_type, proposer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    thesis,
                    trigger,
                    expected_window,
                    actual_outcome,
                    json.dumps(correctness_split),
                    trade_type,
                    proposer,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def reconcile_trade(
        self,
        trade_id: int,
        realized_pnl: float,
        expected_return: float,
        notes: str,
    ) -> Dict[str, Any]:
        cost_of_error = abs(realized_pnl - expected_return)
        death_certificate = None
        if cost_of_error >= 0.08:
            death_certificate = "thesis_failed"

        with sqlite3.connect(self.ledger.db_path) as conn:
            conn.execute(
                """
                UPDATE trades
                SET realized_pnl = ?, expected_return = ?, notes = ?, cost_of_error = ?, death_certificate = ?
                WHERE id = ?
                """,
                (realized_pnl, expected_return, notes, cost_of_error, death_certificate, trade_id),
            )
            conn.commit()

        return {
            "trade_id": trade_id,
            "cost_of_error": cost_of_error,
            "death_certificate": death_certificate,
        }

    def should_block_trade(self, trade_type: str, limit: int = 5, failure_threshold: float = 0.6) -> Dict[str, Any]:
        with sqlite3.connect(self.ledger.db_path) as conn:
            rows = conn.execute(
                """
                SELECT death_certificate, cost_of_error
                FROM trades
                WHERE trade_type = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (trade_type, limit),
            ).fetchall()

        recent = [row[0] for row in rows if row[0] is not None]
        failure_rate = len(recent) / len(rows) if rows else 0.0
        blocked = failure_rate >= failure_threshold and len(recent) >= 2
        return {
            "trade_type": trade_type,
            "failure_rate": failure_rate,
            "blocked": blocked,
            "recent_failures": recent,
        }
