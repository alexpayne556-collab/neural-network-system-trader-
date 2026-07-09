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
    expectancy: float = 0.0  # Expected return (mean of outcomes)
    sample_size: int = 0  # Number of trials


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
        Uses EXPECTANCY (mean of outcomes) as primary metric, not just win-rate.
        
        Returns:
            {
                'total_attempts': int,
                'successful': int,  (truth_score >= 0.5)
                'failed': int,
                'success_rate': float,
                'expectancy': float,  (mean of outcome_1d or outcome_5d)
                'avg_truth_score': float,
                'recent_failures': list of dicts
            }
        """
        cursor = self.conn.cursor()
        
        # Get all decisions with this mechanism (prefer outcome_5d, fall back to outcome_1d)
        cursor.execute("""
            SELECT *, 
                   COALESCE(outcome_5d, outcome_1d) as outcome_used
            FROM reality_ledger 
            WHERE causal_mechanism = ? 
            ORDER BY created_at DESC
        """, (causal_mechanism,))
        
        all_decisions = [dict(row) for row in cursor.fetchall()]
        
        if not all_decisions:
            return {
                'total_attempts': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.5,
                'expectancy': 0.0,
                'avg_truth_score': 0.5,
                'recent_failures': []
            }
        
        # Calculate success metrics (truth_score based)
        successful = sum(1 for d in all_decisions if d['truth_score'] and d['truth_score'] >= 0.5)
        failed = len(all_decisions) - successful
        success_rate = successful / len(all_decisions) if all_decisions else 0.5
        
        # Calculate EXPECTANCY: mean of realized outcomes (in %, as decimal)
        outcomes = [d['outcome_used'] for d in all_decisions if d['outcome_used'] is not None]
        expectancy = sum(outcomes) / len(outcomes) if outcomes else 0.0
        
        truth_scores = [d['truth_score'] for d in all_decisions if d['truth_score']]
        avg_truth_score = sum(truth_scores) / len(truth_scores) if truth_scores else 0.5
        
        # Recent failures (last 5)
        recent_failures = [d for d in all_decisions if d['truth_score'] and d['truth_score'] < 0.5][:5]
        
        return {
            'total_attempts': len(all_decisions),
            'successful': successful,
            'failed': failed,
            'success_rate': success_rate,
            'expectancy': expectancy,
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
        PRIMARY DECIDER: EXPECTANCY (mean of past outcomes)
        SECONDARY: win-rate and recency
        
        Args:
            causal_mechanism: The mechanism being proposed (e.g., "AI-HBM-Copper-Melt")
            ticker: Target ticker
            proposed_action: BUY, SELL, HOLD, PASS
            trigger_event: What triggered this proposal
        
        Returns:
            VetoRationale with recommendation (includes expectancy calculation)
        """
        analysis = self.analyze_causal_mechanism(causal_mechanism)
        sample_size = analysis['total_attempts']
        expectancy = analysis['expectancy']
        
        # Rule 1: If no history, allow with caution (NOVEL)
        if sample_size == 0:
            return VetoRationale(
                should_veto=False,
                reason=f"Novel mechanism: {causal_mechanism} (no prior history; small-size recommended)",
                confidence=0.3,
                similar_failures=0,
                success_rate=0.5,
                expectancy=0.0,
                sample_size=0
            )
        
        # Rule 2: Insufficient sample, but show metrics if available
        if sample_size < 3:
            flag = "⚠ INSUFFICIENT DATA" if expectancy <= 0 else "✓ PROVISIONAL"
            reason = (
                f"{flag}: Mechanism '{causal_mechanism}' has limited track record "
                f"({sample_size} attempts, expectancy: {expectancy:+.2%}). "
                f"Suggest small position or wait for more data."
            )
            return VetoRationale(
                should_veto=False,
                reason=reason,
                confidence=0.5,
                similar_failures=analysis['failed'],
                success_rate=analysis['success_rate'],
                expectancy=expectancy,
                sample_size=sample_size
            )
        
        # Rule 3: EXPECTANCY-PRIMARY decision
        # If expectancy > 0: APPROVED (mechanism has positive expected value)
        if expectancy > 0:
            # Escalation: recent consecutive failures override positive expectancy
            if len(analysis['recent_failures']) >= 2:
                reason = (
                    f"CAUTION: Mechanism '{causal_mechanism}' shows positive expectancy "
                    f"({expectancy:+.2%}) but recent attempts failed ({len(analysis['recent_failures'])} of last 5). "
                    f"Market conditions may have shifted. Suggest review before trading."
                )
                return VetoRationale(
                    should_veto=False,  # Don't veto, but warn
                    reason=reason,
                    confidence=0.6,
                    similar_failures=len(analysis['recent_failures']),
                    success_rate=analysis['success_rate'],
                    expectancy=expectancy,
                    sample_size=sample_size
                )
            
            reason = (
                f"APPROVED: Mechanism '{causal_mechanism}' has positive expectancy "
                f"({expectancy:+.2%}) over {sample_size} attempts. "
                f"Win rate: {analysis['success_rate']:.1%}. Trade with full sizing."
            )
            return VetoRationale(
                should_veto=False,
                reason=reason,
                confidence=min(0.95, 0.5 + abs(expectancy)),
                similar_failures=analysis['failed'],
                success_rate=analysis['success_rate'],
                expectancy=expectancy,
                sample_size=sample_size
            )
        
        # Rule 4: EXPECTANCY <= 0: VETO (negative or zero expected value)
        reason = (
            f"🔒 VETO: Mechanism '{causal_mechanism}' has non-positive expectancy "
            f"({expectancy:+.2%}) over {sample_size} attempts. "
            f"Win rate: {analysis['success_rate']:.1%}. Expected value is negative."
        )
        return VetoRationale(
            should_veto=True,
            reason=reason,
            confidence=min(1.0, 0.8 + abs(expectancy)),
            similar_failures=analysis['failed'],
            success_rate=analysis['success_rate'],
            expectancy=expectancy,
            sample_size=sample_size
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
