"""
SCRIBE: Manual decision logging for Cosmos reality ledger.
Captures human intuition with full causal reasoning chain.
This is HITL (Human-In-The-Loop) ground truth generation.

Usage:
    python scribe.py log --ticker NVDA --trigger "Macro_War_Oil" --mechanism "AI-HBM-Copper" --action BUY
    python scribe.py list --ticker NVDA
    python scribe.py update --id 1 --outcome-1d 2.5 --truth-score 0.8
"""

import sqlite3
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class RealityScribe:
    def __init__(self, db_path: str = "cosmo.sqlite"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure reality_ledger table exists."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='reality_ledger'
        """)
        if not cursor.fetchone():
            raise RuntimeError("reality_ledger table not found. Run schema migration first.")

    def log_decision(
        self,
        ticker: str,
        trigger_event: str,
        causal_mechanism: str,
        action_taken: str,
        evidence_tag: str = "HYPOTHESIS",
        physical_dependency: Optional[str] = None,
        evidence_json: Optional[Dict[str, Any]] = None,
        reasoning_trace: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """
        Log a human decision to the reality ledger.
        
        Args:
            ticker: Stock ticker (e.g., "NVDA")
            trigger_event: The event that triggered this thesis (e.g., "Macro_War_Oil_Cascade")
            causal_mechanism: The physical mechanism (e.g., "AI-HBM-Copper-Melt")
            action_taken: BUY, SELL, HOLD, PASS
            evidence_tag: [MEASURED], [LITERATURE], [HYPOTHESIS], [DELETED]
            physical_dependency: Physical bottleneck (e.g., "Gallium_Magnesium_Squeeze")
            evidence_json: Supporting evidence as dict
            reasoning_trace: Full chain-of-thought explanation
            notes: Additional human notes
        
        Returns:
            id of the inserted record
        """
        cursor = self.conn.cursor()
        
        evidence_str = json.dumps(evidence_json) if evidence_json else None
        
        cursor.execute("""
            INSERT INTO reality_ledger (
                ticker, trigger_event, causal_mechanism, action_taken,
                evidence_tag, physical_dependency, evidence_json,
                reasoning_trace, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            trigger_event,
            causal_mechanism,
            action_taken,
            evidence_tag,
            physical_dependency,
            evidence_str,
            reasoning_trace,
            notes,
        ))
        
        self.conn.commit()
        return cursor.lastrowid

    def update_outcome(
        self,
        ledger_id: int,
        outcome_1d: Optional[float] = None,
        outcome_5d: Optional[float] = None,
        outcome_end_period: Optional[float] = None,
        truth_score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Update a decision with its actual outcome and truth score.
        truth_score: 0.0 = completely wrong, 1.0 = perfectly predicted
        """
        cursor = self.conn.cursor()
        
        updates = []
        params = []
        
        if outcome_1d is not None:
            updates.append("outcome_1d = ?")
            params.append(outcome_1d)
        if outcome_5d is not None:
            updates.append("outcome_5d = ?")
            params.append(outcome_5d)
        if outcome_end_period is not None:
            updates.append("outcome_end_period = ?")
            params.append(outcome_end_period)
        if truth_score is not None:
            updates.append("truth_score = ?")
            params.append(truth_score)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        
        if not updates:
            return False
        
        params.append(ledger_id)
        query = f"UPDATE reality_ledger SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        self.conn.commit()
        
        return cursor.rowcount > 0

    def list_decisions(self, ticker: Optional[str] = None, limit: int = 20) -> list:
        """List recent decisions, optionally filtered by ticker."""
        cursor = self.conn.cursor()
        
        if ticker:
            cursor.execute("""
                SELECT * FROM reality_ledger 
                WHERE ticker = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (ticker, limit))
        else:
            cursor.execute("""
                SELECT * FROM reality_ledger 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]

    def get_causal_failures(self, causal_mechanism: str, limit: int = 10) -> list:
        """
        Retrieve all past decisions with the same causal_mechanism that FAILED.
        Used by Ghost listener to block repeat failures.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM reality_ledger 
            WHERE causal_mechanism = ? 
            AND (truth_score < 0.5 OR outcome_1d < 0)
            ORDER BY created_at DESC 
            LIMIT ?
        """, (causal_mechanism, limit))
        
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="Scribe: Reality ledger CLI for Cosmos")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # LOG command: record a new decision
    log_parser = subparsers.add_parser("log", help="Log a new decision")
    log_parser.add_argument("--ticker", required=True, help="Stock ticker")
    log_parser.add_argument("--trigger", required=True, help="Trigger event")
    log_parser.add_argument("--mechanism", required=True, help="Causal mechanism")
    log_parser.add_argument("--action", required=True, help="BUY, SELL, HOLD, PASS")
    log_parser.add_argument("--evidence-tag", default="HYPOTHESIS", help="[MEASURED], [LITERATURE], [HYPOTHESIS], [DELETED]")
    log_parser.add_argument("--physical-dep", help="Physical dependency (bottleneck)")
    log_parser.add_argument("--reasoning", help="Chain-of-thought explanation")
    log_parser.add_argument("--notes", help="Additional notes")
    
    # LIST command: view decisions
    list_parser = subparsers.add_parser("list", help="List recent decisions")
    list_parser.add_argument("--ticker", help="Filter by ticker")
    list_parser.add_argument("--limit", type=int, default=20, help="Number of records")
    
    # UPDATE command: record outcome
    update_parser = subparsers.add_parser("update", help="Update decision outcome")
    update_parser.add_argument("--id", type=int, required=True, help="Ledger ID")
    update_parser.add_argument("--outcome-1d", type=float, help="1-day return (as decimal)")
    update_parser.add_argument("--outcome-5d", type=float, help="5-day return (as decimal)")
    update_parser.add_argument("--truth-score", type=float, help="Truth score (0.0-1.0)")
    update_parser.add_argument("--notes", help="Outcome notes")
    
    # FAILURES command: query past failures for Ghost
    failures_parser = subparsers.add_parser("failures", help="Find past failures by causal mechanism")
    failures_parser.add_argument("--mechanism", required=True, help="Causal mechanism to check")
    
    args = parser.parse_args()
    
    scribe = RealityScribe()
    
    if args.command == "log":
        ledger_id = scribe.log_decision(
            ticker=args.ticker,
            trigger_event=args.trigger,
            causal_mechanism=args.mechanism,
            action_taken=args.action,
            evidence_tag=args.evidence_tag,
            physical_dependency=args.physical_dep,
            reasoning_trace=args.reasoning,
            notes=args.notes,
        )
        print(f"✓ Decision logged (ID: {ledger_id})")
        print(f"  Ticker: {args.ticker}")
        print(f"  Trigger: {args.trigger}")
        print(f"  Mechanism: {args.mechanism}")
        print(f"  Action: {args.action}")
        print(f"  Timestamp: {datetime.utcnow().isoformat()}")
    
    elif args.command == "list":
        decisions = scribe.list_decisions(ticker=args.ticker, limit=args.limit)
        if not decisions:
            print("No decisions found.")
        else:
            print(f"\n{'ID':<5} {'Ticker':<8} {'Trigger':<20} {'Mechanism':<25} {'Action':<6} {'1D':<8} {'Truth':<7}")
            print("-" * 90)
            for d in decisions:
                print(f"{d['id']:<5} {d['ticker']:<8} {d['trigger_event']:<20} {d['causal_mechanism']:<25} {d['action_taken']:<6} {str(d['outcome_1d']):<8} {str(d['truth_score']):<7}")
    
    elif args.command == "update":
        success = scribe.update_outcome(
            ledger_id=args.id,
            outcome_1d=args.outcome_1d,
            outcome_5d=args.outcome_5d,
            truth_score=args.truth_score,
            notes=args.notes,
        )
        if success:
            print(f"✓ Decision {args.id} updated")
        else:
            print(f"✗ Could not find decision {args.id}")
    
    elif args.command == "failures":
        failures = scribe.get_causal_failures(args.mechanism)
        if not failures:
            print(f"✓ No past failures found for mechanism: {args.mechanism}")
        else:
            print(f"\n⚠ Found {len(failures)} past failures for mechanism: {args.mechanism}")
            print("-" * 90)
            for f in failures:
                print(f"  ID {f['id']}: {f['ticker']} - {f['trigger_event']}")
                print(f"    Action: {f['action_taken']}, Truth Score: {f['truth_score']}, 1D Return: {f['outcome_1d']}")
    
    scribe.close()


if __name__ == "__main__":
    main()
