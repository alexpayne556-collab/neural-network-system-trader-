"""
DIRECTIVE ACCEPTANCE TESTS
Testing the three scoped, sequential changes from Constitutional briefing.
"""

import unittest
import sqlite3
import json
from pathlib import Path
from cosmo.scribe import RealityScribe
from cosmo.ghost_listener import GhostListener
from cosmo.migrate import migrate


class DirectiveTests(unittest.TestCase):
    """Tests for Directives 1-3 implementation."""
    
    test_counter = 0
    
    def setUp(self):
        """Initialize test database."""
        DirectiveTests.test_counter += 1
        self.test_db = f"test_directives_{DirectiveTests.test_counter}.sqlite"
        if Path(self.test_db).exists():
            Path(self.test_db).unlink()
        migrate(self.test_db)
        self.scribe = RealityScribe(self.test_db)
        self.ghost = GhostListener(self.test_db)
    
    def tearDown(self):
        """Clean up test database."""
        try:
            self.scribe.close()
        except:
            pass
        try:
            self.ghost.conn.close()
        except:
            pass
        import time
        time.sleep(0.1)  # Wait for file to be released
        if Path(self.test_db).exists():
            try:
                Path(self.test_db).unlink()
            except:
                pass
    
    # ==================== DIRECTIVE 1: PROPOSER COLUMN ==================== #
    
    def test_directive_1_proposer_column_tracked(self):
        """Directive 1: Proposer column separates seats in meritocracy measurement."""
        # Log decisions from different proposers
        id1 = self.scribe.log_decision(
            ticker="NVDA",
            trigger_event="AI-Shortage",
            causal_mechanism="AI-HBM-Copper",
            action_taken="BUY",
            proposer="tyr"
        )
        id2 = self.scribe.log_decision(
            ticker="TSM",
            trigger_event="Taiwan-Risk",
            causal_mechanism="AI-HBM-Copper",
            action_taken="BUY",
            proposer="adversary"
        )
        
        # Update outcomes
        self.scribe.update_outcome(id1, outcome_1d=-0.03, truth_score=0.2)
        self.scribe.update_outcome(id2, outcome_1d=-0.02, truth_score=0.1)
        
        # Get scorecards
        tyr_card = self.scribe.get_proposer_scorecard("tyr")
        adversary_card = self.scribe.get_proposer_scorecard("adversary")
        
        # Verify proposer separation
        self.assertEqual(tyr_card["proposer"], "tyr")
        self.assertEqual(tyr_card["total"], 1)
        self.assertEqual(tyr_card["wins"], 0)
        self.assertEqual(tyr_card["win_rate"], 0.0)
        
        self.assertEqual(adversary_card["proposer"], "adversary")
        self.assertEqual(adversary_card["total"], 1)
        self.assertEqual(adversary_card["wins"], 0)
        self.assertEqual(adversary_card["win_rate"], 0.0)
        
        # Verify list_all_proposers works
        proposers = self.scribe.list_all_proposers()
        self.assertIn("tyr", proposers)
        self.assertIn("adversary", proposers)
        self.assertEqual(len(proposers), 2)
    
    def test_directive_1_scorecard_win_rate_calculation(self):
        """Directive 1: Scorecard correctly calculates win rate (truth_score >= 0.5)."""
        # Log 3 decisions from same proposer with different outcomes
        for i in range(3):
            id = self.scribe.log_decision(
                ticker=f"TICKER{i}",
                trigger_event=f"Event{i}",
                causal_mechanism="Test-Mechanism",
                action_taken="BUY",
                proposer="synthesizer"
            )
        
        # Update with 1 win (truth >= 0.5), 2 losses
        self.scribe.update_outcome(1, outcome_1d=0.05, truth_score=0.75)  # WIN
        self.scribe.update_outcome(2, outcome_1d=-0.02, truth_score=0.2)  # LOSS
        self.scribe.update_outcome(3, outcome_1d=-0.03, truth_score=0.3)  # LOSS
        
        card = self.scribe.get_proposer_scorecard("synthesizer")
        self.assertEqual(card["total"], 3)
        self.assertEqual(card["wins"], 1)
        self.assertAlmostEqual(card["win_rate"], 0.333, places=2)
        self.assertAlmostEqual(card["avg_truth_score"], 0.417, places=2)
    
    # ==================== DIRECTIVE 2: GHOST EXPECTANCY MATH ==================== #
    
    def test_directive_2_expectancy_positive_approves(self):
        """Directive 2: Positive expectancy → APPROVED (even at low win rate)."""
        # Log: -$500, -$500, +$5000 (33% win rate but +$3500 net = +$1167 expectancy)
        for i in range(2):
            id = self.scribe.log_decision(
                ticker="TEST",
                trigger_event="Catalyst",
                causal_mechanism="Expectancy-Test",
                action_taken="BUY"
            )
        
        self.scribe.update_outcome(1, outcome_1d=-0.05, truth_score=0.1)    # -5%
        self.scribe.update_outcome(2, outcome_1d=-0.05, truth_score=0.1)    # -5%
        
        # Add one big win
        id3 = self.scribe.log_decision(
            ticker="TEST",
            trigger_event="Catalyst",
            causal_mechanism="Expectancy-Test",
            action_taken="BUY"
        )
        self.scribe.update_outcome(3, outcome_1d=0.50, truth_score=0.9)     # +50%
        
        # Ghost evaluation: 33% win rate but +13.3% expectancy
        result = self.ghost.evaluate_proposal(
            "Expectancy-Test", "TEST", "BUY", "Test"
        )
        
        # Should NOT veto (positive expectancy)
        self.assertFalse(result.should_veto, "Should APPROVE with positive expectancy despite 33% win rate")
        self.assertGreater(result.expectancy, 0.0, "Expectancy should be positive")
        self.assertLess(result.success_rate, 0.5, "Win rate is sub-50%")
    
    def test_directive_2_expectancy_negative_vetoes(self):
        """Directive 2: Negative expectancy → VETO (regardless of win rate)."""
        # Log: -$1000, -$1000, +$500 (33% win rate, but -$1500 net = -500 expectancy)
        id1 = self.scribe.log_decision(
            ticker="BAD",
            trigger_event="Trigger",
            causal_mechanism="Bad-Expectancy",
            action_taken="BUY"
        )
        self.scribe.update_outcome(id1, outcome_1d=-0.10, truth_score=0.1)  # -10%
        
        id2 = self.scribe.log_decision(
            ticker="BAD",
            trigger_event="Trigger",
            causal_mechanism="Bad-Expectancy",
            action_taken="BUY"
        )
        self.scribe.update_outcome(id2, outcome_1d=-0.10, truth_score=0.1)  # -10%
        
        id3 = self.scribe.log_decision(
            ticker="BAD",
            trigger_event="Trigger",
            causal_mechanism="Bad-Expectancy",
            action_taken="BUY"
        )
        self.scribe.update_outcome(id3, outcome_1d=0.05, truth_score=0.5)   # +5%
        
        # Ghost: 33% win rate, -5% expectancy
        result = self.ghost.evaluate_proposal(
            "Bad-Expectancy", "BAD", "BUY", "Test"
        )
        
        # Should VETO (negative expectancy)
        self.assertTrue(result.should_veto, "Should VETO with negative expectancy")
        self.assertLess(result.expectancy, 0.0, "Expectancy should be negative")
    
    def test_directive_2_novel_mechanism_approved(self):
        """Directive 2: Novel mechanism (no history) → APPROVED with caution."""
        result = self.ghost.evaluate_proposal(
            "Never-Tried-Before", "XYZ", "BUY", "Test"
        )
        
        # Should NOT veto (novel)
        self.assertFalse(result.should_veto)
        self.assertEqual(result.sample_size, 0)
        self.assertIn("Novel", result.reason)
    
    # ==================== DIRECTIVE 3: SHADOW LEDGER ==================== #
    
    def test_directive_3_shadow_ledger_logs_discards(self):
        """Directive 3: Discarded events logged to shadow_ledger for later grading."""
        # Create a ledger and triage for testing
        from cosmo.ledger import CosmoLedger
        from cosmo.triage import TriageOrchestrator
        
        ledger = CosmoLedger(self.test_db)
        triage = TriageOrchestrator(ledger)
        
        # Create low-score event (should be discarded)
        event = {
            "entity": "NOISE_TICKER",
            "source": "twitter",
            "event_type": "noise",
            "summary": "Random noise",
            "severity": 0.1,
            "prediction_error": 0.1,
            "convergence": 0,
            "magnitude": 0.0,
            "tags": ["noise"]
        }
        
        # Evaluate (should discard)
        result = triage.evaluate_event(event)
        self.assertFalse(result["wake_swarm"], "Event should be discarded")
        
        # Check that it was logged to shadow_ledger
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shadow_ledger WHERE ticker = ?", ("NOISE_TICKER",))
        count = cursor.fetchone()[0]
        conn.close()
        self.assertGreater(count, 0, "Discarded event should be in shadow_ledger")
    
    def test_directive_3_shadow_outcome_update(self):
        """Directive 3: Shadow outcomes updateable with truth score."""
        # Manually insert a shadow entry
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shadow_ledger (ticker, event_source, event_type, triage_score, discard_reason)
            VALUES (?, ?, ?, ?, ?)
        """, ("TEST", "api", "signal", 0.5, "Below threshold"))
        conn.commit()
        shadow_id = cursor.lastrowid
        conn.close()
        
        # Update outcome
        success = self.scribe.update_shadow_outcome(
            shadow_id, 
            outcome_1d=0.05,
            outcome_5d=0.15,
            shadow_truth_score=0.8,
            notes="This was valuable after all"
        )
        
        self.assertTrue(success)
        
        # Verify update
        misses = self.scribe.list_shadow_misses()
        # Note: misses list only includes entries with shadow_truth_score < 0.5
        # so this won't appear there. Let's verify differently.
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT outcome_1d, outcome_5d, shadow_truth_score FROM shadow_ledger WHERE id = ?", (shadow_id,))
        row = cursor.fetchone()
        conn.close()
        
        self.assertEqual(row[0], 0.05)
        self.assertEqual(row[1], 0.15)
        self.assertEqual(row[2], 0.8)
    
    def test_directive_3_shadow_misses_report(self):
        """Directive 3: Shadow report shows discarded events that moved significantly."""
        # Manually insert expensive misses
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        
        # This was discarded but later moved +10%
        cursor.execute("""
            INSERT INTO shadow_ledger 
            (ticker, event_source, event_type, triage_score, discard_reason, outcome_5d, shadow_truth_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("MISS1", "api", "signal", 0.5, "Below threshold", 0.10, 0.1))
        
        # This was discarded and didn't move (no miss)
        cursor.execute("""
            INSERT INTO shadow_ledger 
            (ticker, event_source, event_type, triage_score, discard_reason, outcome_5d, shadow_truth_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("MISS2", "api", "signal", 0.5, "Below threshold", -0.02, 0.8))
        
        conn.commit()
        conn.close()
        
        # Get misses (only includes shadow_truth_score < 0.5)
        misses = self.scribe.list_shadow_misses()
        
        # Should find at least the first one (truth_score=0.1 < 0.5)
        miss_tickers = [m["ticker"] for m in misses]
        self.assertIn("MISS1", miss_tickers)
        
        # Should NOT find the second one (truth_score=0.8 >= 0.5, not a miss)
        self.assertNotIn("MISS2", miss_tickers)


if __name__ == "__main__":
    unittest.main()
