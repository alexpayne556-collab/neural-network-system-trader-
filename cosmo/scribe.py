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
from typing import Optional, Dict, Any, List


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
        proposer: str = "tyr",
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
                reasoning_trace, notes, proposer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            proposer,
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

    def get_proposer_scorecard(self, proposer: str) -> Dict[str, Any]:
        """
        Get performance metrics for a proposer (seat).
        Meritocracy becomes measurable: every seat gets graded.
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN truth_score >= 0.5 THEN 1 ELSE 0 END) as wins,
                   AVG(truth_score) as avg_truth_score
            FROM reality_ledger
            WHERE proposer = ? AND truth_score IS NOT NULL
        """, (proposer,))
        
        row = cursor.fetchone()
        if not row:
            return {
                'proposer': proposer,
                'total': 0,
                'wins': 0,
                'win_rate': 0.0,
                'avg_truth_score': None
            }
        
        total = row[0] or 0
        wins = row[1] or 0
        win_rate = (wins / total) if total > 0 else 0.0
        
        return {
            'proposer': proposer,
            'total': total,
            'wins': wins,
            'win_rate': win_rate,
            'avg_truth_score': row[2]
        }
    
    def list_all_proposers(self) -> List[str]:
        """Get list of all proposers in the ledger."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT proposer FROM reality_ledger ORDER BY proposer")
        return [row[0] for row in cursor.fetchall()]
    
    def update_shadow_outcome(
        self,
        shadow_id: int,
        outcome_1d: Optional[float] = None,
        outcome_3d: Optional[float] = None,
        outcome_5d: Optional[float] = None,
        outcome_10d: Optional[float] = None,
        shadow_truth_score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Update shadow ledger entry with actual outcomes."""
        cursor = self.conn.cursor()
        
        updates = []
        params = []
        
        if outcome_1d is not None:
            updates.append("outcome_1d = ?")
            params.append(outcome_1d)
        if outcome_3d is not None:
            updates.append("outcome_3d = ?")
            params.append(outcome_3d)
        if outcome_5d is not None:
            updates.append("outcome_5d = ?")
            params.append(outcome_5d)
        if outcome_10d is not None:
            updates.append("outcome_10d = ?")
            params.append(outcome_10d)
        if shadow_truth_score is not None:
            updates.append("shadow_truth_score = ?")
            params.append(shadow_truth_score)
        if notes is not None:
            updates.append("audit_notes = ?")
            params.append(notes)
        
        if not updates:
            return False
        
        params.append(shadow_id)
        query = f"UPDATE shadow_ledger SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        self.conn.commit()
        
        return cursor.rowcount > 0
    
    def list_shadow_misses(self, threshold: float = 0.05) -> List[Dict[str, Any]]:
        """
        List shadow-ledger entries that were expensive misses:
        discarded events that later moved significantly in price.
        shadow_truth_score < 0.5 means we wrongly discarded something valuable.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM shadow_ledger 
            WHERE shadow_truth_score IS NOT NULL AND shadow_truth_score < 0.5
            ORDER BY outcome_5d DESC LIMIT 20
        """)
        
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
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
    log_parser.add_argument("--proposer", default="tyr", help="Proposer/seat name")
    
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
    
    # SCORECARD command: meritocracy metrics for a proposer
    scorecard_parser = subparsers.add_parser("scorecard", help="Get performance metrics for a proposer/seat")
    scorecard_parser.add_argument("--proposer", help="Proposer name (optional; if omitted, shows all)")
    
    # SHADOW command: manage shadow ledger (discarded events)
    shadow_parser = subparsers.add_parser("shadow", help="Manage shadow ledger (discarded events)")
    shadow_subparsers = shadow_parser.add_subparsers(dest="shadow_command")
    
    shadow_update = shadow_subparsers.add_parser("update", help="Update shadow entry with outcome")
    shadow_update.add_argument("--id", type=int, required=True, help="Shadow ledger ID")
    shadow_update.add_argument("--outcome-1d", type=float, help="1-day return (as decimal)")
    shadow_update.add_argument("--outcome-5d", type=float, help="5-day return (as decimal)")
    shadow_update.add_argument("--truth-score", type=float, help="Shadow truth score (0.0-1.0)")
    shadow_update.add_argument("--notes", help="Audit notes")
    
    shadow_report = shadow_subparsers.add_parser("report", help="Show expensive misses (what we discarded that moved)")

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
            proposer=args.proposer,
        )
        print(f"✓ Decision logged (ID: {ledger_id})")
        print(f"  Ticker: {args.ticker}")
        print(f"  Trigger: {args.trigger}")
        print(f"  Mechanism: {args.mechanism}")
        print(f"  Action: {args.action}")
        print(f"  Proposer: {args.proposer}")
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
    
    elif args.command == "scorecard":
        if args.proposer:
            # Single proposer scorecard
            card = scribe.get_proposer_scorecard(args.proposer)
            print(f"\nSCORECARD: {card['proposer']}")
            print(f"  Total Decisions: {card['total']}")
            print(f"  Wins (truth_score >= 0.5): {card['wins']}")
            print(f"  Win Rate: {card['win_rate']:.1%}")
            print(f"  Avg Truth Score: {card['avg_truth_score']:.2f if card['avg_truth_score'] else 'N/A'}")
        else:
            # All proposers scorecard
            proposers = scribe.list_all_proposers()
            print("\nMERITOCRACY SCORECARD (All Proposers):")
            print(f"{'Proposer':<20} {'Total':<8} {'Wins':<8} {'Win Rate':<12} {'Avg Truth':<12}")
            print("-" * 60)
            for proposer in proposers:
                card = scribe.get_proposer_scorecard(proposer)
                avg_score = f"{card['avg_truth_score']:.2f}" if card['avg_truth_score'] else "N/A"
                print(f"{card['proposer']:<20} {card['total']:<8} {card['wins']:<8} {card['win_rate']:>10.1%}  {avg_score:>10}")
    
    elif args.command == "shadow":
        if args.shadow_command == "update":
            success = scribe.update_shadow_outcome(
                shadow_id=args.id,
                outcome_1d=args.outcome_1d,
                outcome_5d=args.outcome_5d,
                shadow_truth_score=args.truth_score,
                notes=args.notes,
            )
            if success:
                print(f"✓ Shadow entry {args.id} updated")
            else:
                print(f"✗ Could not find shadow entry {args.id}")
        
        elif args.shadow_command == "report":
            misses = scribe.list_shadow_misses()
            if not misses:
                print("✓ No expensive misses found. Triage gate calibrated well.")
            else:
                print(f"\n⚠ EXPENSIVE MISSES (Events we discarded that moved significantly):")
                print(f"\nTotal misses found: {len(misses)}")
                print(f"{'ID':<5} {'Ticker':<10} {'Triage Score':<15} {'5D Outcome':<15} {'Truth':<8}")
                print("-" * 60)
                for m in misses:
                    print(f"{m['id']:<5} {str(m['ticker']):<10} {m['triage_score']:<15.3f} {m['outcome_5d']:>+14.1%} {m['shadow_truth_score']:<8.2f}")
    
    scribe.close()


if __name__ == "__main__":
    main()
