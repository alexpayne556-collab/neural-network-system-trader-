import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cosmo.ledger import CosmoLedger
from cosmo.reconcile import ReconciliationEngine
from cosmo.triage import TriageOrchestrator


class CosmoCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="cosmo-test-", dir=".")
        self.db_path = os.path.join(self.tmp_dir, "cosmo.sqlite")
        self.ledger = CosmoLedger(self.db_path)
        self.orchestrator = TriageOrchestrator(self.ledger)
        self.reconciler = ReconciliationEngine(self.ledger)

    def test_thesis_and_evidence_round_trip(self):
        thesis_id = self.ledger.create_thesis(
            title="HBM bottleneck thesis",
            hypothesis="Memory bandwidth is the bottleneck",
            owner="alex",
            tags=["bottleneck", "memory"],
        )
        self.ledger.add_evidence(thesis_id, "sec", "Micron mentions HBM demand", {"source": "10-K"})
        self.ledger.add_kill_condition(thesis_id, "supply_response", "The supply response is delivered on time")

        stored = self.ledger.get_thesis(thesis_id)
        self.assertEqual(stored["title"], "HBM bottleneck thesis")
        self.assertEqual(len(self.ledger.list_evidence(thesis_id)), 1)
        self.assertEqual(len(self.ledger.list_kill_conditions(thesis_id)), 1)

    def test_triage_wakes_swarm_for_converging_signal(self):
        self.ledger.create_thesis(
            title="Photonic interconnect thesis",
            hypothesis="Optical interconnects are the next bottleneck",
            owner="alex",
            tags=["photonics", "ai"],
        )

        result = self.orchestrator.evaluate_event(
            {
                "source": "edgar",
                "event_type": "filing",
                "entity": "LUMN",
                "summary": "Coherent expands photonics capacity",
                "severity": 0.92,
                "magnitude": 0.85,
                "prediction_error": 0.88,
                "convergence": 2,
                "tags": ["photonics", "ai"],
            }
        )

        self.assertTrue(result["wake_swarm"])
        self.assertGreater(result["score"], 0.7)

    def test_triage_suppresses_noise(self):
        result = self.orchestrator.evaluate_event(
            {
                "source": "social",
                "event_type": "headline",
                "entity": "XYZ",
                "summary": "Cramer says the market looks great",
                "severity": 0.15,
                "magnitude": 0.21,
                "prediction_error": 0.1,
                "convergence": 0,
                "tags": ["noise"],
            }
        )

        self.assertFalse(result["wake_swarm"])

    def test_reconciliation_blocks_repeat_failure(self):
        trade_id = self.reconciler.log_trade(
            ticker="NVDA",
            thesis="AI demand will remain strong",
            trigger="earnings surprise",
            expected_window="3d",
            actual_outcome="loss",
            correctness_split={"signal": 0.2, "timing": 0.1, "execution": 0.3, "allocation": 0.4},
            trade_type="ai_bottleneck",
        )

        self.reconciler.reconcile_trade(
            trade_id=trade_id,
            realized_pnl=-0.08,
            expected_return=0.05,
            notes="The thesis was too optimistic and timed poorly",
        )
        self.reconciler.reconcile_trade(
            trade_id=self.reconciler.log_trade(
                ticker="AMD",
                thesis="AI demand will remain strong",
                trigger="earnings surprise",
                expected_window="3d",
                actual_outcome="loss",
                correctness_split={"signal": 0.2, "timing": 0.1, "execution": 0.3, "allocation": 0.4},
                trade_type="ai_bottleneck",
            ),
            realized_pnl=-0.11,
            expected_return=0.04,
            notes="The signal persisted but the timing failed",
        )

        block = self.reconciler.should_block_trade("ai_bottleneck", limit=5, failure_threshold=0.6)
        self.assertTrue(block["blocked"])
        self.assertGreaterEqual(block["failure_rate"], 0.6)


if __name__ == "__main__":
    unittest.main()
