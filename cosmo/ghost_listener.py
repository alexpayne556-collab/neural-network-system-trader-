"""
GHOST LISTENER: Adversary seat in the council.
Prevents the system from repeating causal failures.

When a new thesis is proposed with a causal_mechanism, Ghost checks:
1. Have we tried this mechanism before?
2. What was the success rate?
3. Should we block this proposal?

This is the "adversary" that forces accountability.
"""

import sqlite3
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json


@dataclass
class VetoRationale:
    """Reasoning for why Ghost vetoes a proposal."""
    should_veto: bool
    reason: str
    confidence: float  # 0.0-1.0
    similar_failures: int
    success_rate: float


class GhostListener:
    def __init__(self, db_path: str = "cosmo.sqlite", failure_threshold: float = 0.4):
        """
        Initialize Ghost listener.
        
        Args:
            db_path: Path to Cosmos SQLite database
            failure_threshold: If success_rate < this, veto the proposal
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.failure_threshold = failure_threshold

    def analyze_causal_mechanism(self, causal_mechanism: str) -> Dict[str, Any]:
        """
        Analyze past performance of a causal mechanism.
        
        Returns:
            {
                'total_attempts': int,
                'successful': int,
                'failed': int,
                'success_rate': float,
                'avg_truth_score': float,
                'recent_failures': list of dicts
            }
        """
        cursor = self.conn.cursor()
        
        # Get all decisions with this mechanism
        cursor.execute("""
            SELECT * FROM reality_ledger 
            WHERE causal_mechanism = ? 
            ORDER BY created_at DESC
        """, (causal_mechanism,))
        
        all_decisions = [dict(row) for row in cursor.fetchall()]
        
        if not all_decisions:
            return {
                'total_attempts': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.5,  # Default neutral
                'avg_truth_score': 0.5,
                'recent_failures': []
            }
        
        # Calculate success metrics
        successful = sum(1 for d in all_decisions if d['truth_score'] and d['truth_score'] >= 0.5)
        failed = len(all_decisions) - successful
        success_rate = successful / len(all_decisions) if all_decisions else 0.5
        
        truth_scores = [d['truth_score'] for d in all_decisions if d['truth_score']]
        avg_truth_score = sum(truth_scores) / len(truth_scores) if truth_scores else 0.5
        
        # Recent failures (last 5)
        recent_failures = [d for d in all_decisions if d['truth_score'] and d['truth_score'] < 0.5][:5]
        
        return {
            'total_attempts': len(all_decisions),
            'successful': successful,
            'failed': failed,
            'success_rate': success_rate,
            'avg_truth_score': avg_truth_score,
            'recent_failures': recent_failures
        }

    def evaluate_proposal(
        self,
        causal_mechanism: str,
        ticker: str,
        proposed_action: str,
        trigger_event: str
    ) -> VetoRationale:
        """
        Evaluate whether Ghost should veto this proposal.
        
        Args:
            causal_mechanism: The mechanism being proposed (e.g., "AI-HBM-Copper-Melt")
            ticker: Target ticker
            proposed_action: BUY, SELL, HOLD, PASS
            trigger_event: What triggered this proposal
        
        Returns:
            VetoRationale with recommendation
        """
        analysis = self.analyze_causal_mechanism(causal_mechanism)
        
        # Rule 1: If no history, allow with caution
        if analysis['total_attempts'] == 0:
            return VetoRationale(
                should_veto=False,
                reason=f"Novel mechanism: {causal_mechanism} (no prior history)",
                confidence=0.3,
                similar_failures=0,
                success_rate=0.5
            )
        
        # Rule 2: If repeated failures, veto
        if analysis['success_rate'] < self.failure_threshold:
            failure_ratio = f"{analysis['failed']}/{analysis['total_attempts']}"
            reason = (
                f"VETO: Mechanism '{causal_mechanism}' has poor track record: "
                f"{failure_ratio} failures (success rate: {analysis['success_rate']:.1%}). "
                f"Recent attempts failed."
            )
            return VetoRationale(
                should_veto=True,
                reason=reason,
                confidence=min(1.0, 0.6 + (1.0 - analysis['success_rate'])),
                similar_failures=analysis['failed'],
                success_rate=analysis['success_rate']
            )
        
        # Rule 3: If marginal success and recent failures, caution
        if analysis['success_rate'] < 0.6 and analysis['recent_failures']:
            reason = (
                f"CAUTION: Mechanism '{causal_mechanism}' has marginal performance "
                f"({analysis['success_rate']:.1%} success rate) with recent failures. "
                f"Consider alternative approaches."
            )
            return VetoRationale(
                should_veto=False,
                reason=reason,
                confidence=0.7,
                similar_failures=len(analysis['recent_failures']),
                success_rate=analysis['success_rate']
            )
        
        # Rule 4: If mechanism has proven track record, allow
        reason = (
            f"APPROVED: Mechanism '{causal_mechanism}' has established track record "
            f"({analysis['success_rate']:.1%} success rate over {analysis['total_attempts']} attempts)"
        )
        return VetoRationale(
            should_veto=False,
            reason=reason,
            confidence=min(analysis['success_rate'], 0.95),
            similar_failures=analysis['failed'],
            success_rate=analysis['success_rate']
        )

    def check_ticker_causal_cascade(self, ticker: str) -> Dict[str, Any]:
        """
        For a given ticker, show all causal mechanisms that have been tried,
        their success rates, and which are currently "hot" vs "dead".
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT causal_mechanism FROM reality_ledger 
            WHERE ticker = ?
            ORDER BY causal_mechanism
        """, (ticker,))
        
        mechanisms = [row[0] for row in cursor.fetchall()]
        
        mechanism_stats = {}
        for mech in mechanisms:
            analysis = self.analyze_causal_mechanism(mech)
            mechanism_stats[mech] = analysis
        
        # Find which mechanisms are "dead" (high failure rate)
        dead_mechanisms = [
            m for m, s in mechanism_stats.items() 
            if s['success_rate'] < self.failure_threshold and s['total_attempts'] >= 2
        ]
        
        # Find which are "hot" (high success rate)
        hot_mechanisms = [
            m for m, s in mechanism_stats.items() 
            if s['success_rate'] >= 0.7
        ]
        
        return {
            'ticker': ticker,
            'total_mechanisms_tried': len(mechanisms),
            'mechanism_stats': mechanism_stats,
            'dead_mechanisms': dead_mechanisms,
            'hot_mechanisms': hot_mechanisms
        }

    def close(self):
        self.conn.close()


def main():
    """Quick CLI test for Ghost listener."""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python ghost_listener.py check <causal_mechanism>")
        print("       python ghost_listener.py ticker <ticker>")
        sys.exit(1)
    
    ghost = GhostListener()
    
    if sys.argv[1] == "check":
        mechanism = sys.argv[2]
        veto = ghost.evaluate_proposal(
            causal_mechanism=mechanism,
            ticker="TEST",
            proposed_action="BUY",
            trigger_event="TEST_EVENT"
        )
        
        print(f"\n{'🔒 VETO' if veto.should_veto else '✓ APPROVED'}: {veto.reason}")
        print(f"Confidence: {veto.confidence:.1%}")
        print(f"Similar Failures: {veto.similar_failures}")
        print(f"Success Rate: {veto.success_rate:.1%}")
    
    elif sys.argv[1] == "ticker":
        ticker = sys.argv[2]
        cascades = ghost.check_ticker_causal_cascade(ticker)
        
        print(f"\nCausal Cascades for {ticker}:")
        print(f"Total Mechanisms Tried: {cascades['total_mechanisms_tried']}")
        
        if cascades['hot_mechanisms']:
            print(f"\n🔥 HOT (Success Rate >= 70%):")
            for m in cascades['hot_mechanisms']:
                stats = cascades['mechanism_stats'][m]
                print(f"  {m}: {stats['success_rate']:.1%} ({stats['successful']}/{stats['total_attempts']})")
        
        if cascades['dead_mechanisms']:
            print(f"\n💀 DEAD (Success Rate < {ghost.failure_threshold:.0%}):")
            for m in cascades['dead_mechanisms']:
                stats = cascades['mechanism_stats'][m]
                print(f"  {m}: {stats['success_rate']:.1%} ({stats['successful']}/{stats['total_attempts']})")
    
    ghost.close()


if __name__ == "__main__":
    main()
