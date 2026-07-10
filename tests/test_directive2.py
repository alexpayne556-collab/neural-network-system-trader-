"""
DIRECTIVE 2 TESTS (post-mock-purge).

The market-reality seams (EDGAR HTTP, Alpaca bars, Finnhub HTTP) are no longer
mocked here — that coverage moved to tests/test_e2e_real.py, which hits LIVE
EDGAR and LIVE Alpaca. What remains here are structural checks and pure-logic
unit tests that do not fake reality: dedup tables, triage scoring math, and the
local Ollama seat's response parser.
"""

import unittest
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch
from cosmo.migrate import migrate


class Directive2Tests(unittest.TestCase):
    """Structural + pure-logic tests for Directive 2 (data feeds + Ollama seat)."""

    test_counter = 0

    def setUp(self):
        Directive2Tests.test_counter += 1
        self.test_db = f"test_directive2_{Directive2Tests.test_counter}.sqlite"
        if Path(self.test_db).exists():
            Path(self.test_db).unlink()
        migrate(self.test_db)

    def tearDown(self):
        try:
            if Path(self.test_db).exists():
                Path(self.test_db).unlink()
        except Exception:
            pass

    # ==================== ITEM 1: EDGAR POLLER (structural) ==================== #

    def test_item1_edgar_poller_initializes(self):
        """EDGAR poller initializes with dedup table."""
        from cosmo.edgar_poller import EDGARPoller

        poller = EDGARPoller(self.test_db)
        conn = sqlite3.connect(self.test_db)
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='edgar_dedup'"
        ).fetchone() is not None
        conn.close()
        self.assertTrue(exists, "edgar_dedup table should exist")
        poller.close()

    def test_item1_edgar_deduplication_works(self):
        """EDGAR poller deduplicates by accession number."""
        from cosmo.edgar_poller import EDGARPoller

        poller = EDGARPoller(self.test_db)
        poller._mark_seen("0001493152-26-032729")
        self.assertTrue(poller._has_seen("0001493152-26-032729"))
        self.assertFalse(poller._has_seen("0000000000-00-000000"))
        poller.close()

    # ==================== ITEM 2: PRICE GRADER (structural) ==================== #

    def test_item2_price_grader_initializes(self):
        """Price grader initializes and wires Alpaca config (or degrades gracefully)."""
        from cosmo.price_grader import PriceGrader

        grader = PriceGrader(self.test_db)
        self.assertIsNotNone(grader)
        grader.close()

    # ==================== ITEM 3: NEWS POLLER (structural + triage logic) ======= #

    def test_item3_news_poller_initializes(self):
        """News poller initializes with dedup table."""
        from cosmo.news_poller import NewsPoller

        poller = NewsPoller(self.test_db, api_key="test_key")
        conn = sqlite3.connect(self.test_db)
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='news_dedup'"
        ).fetchone() is not None
        conn.close()
        self.assertTrue(exists, "news_dedup table should exist")
        poller.close()

    def test_item3_news_headlines_scored_low_in_triage(self):
        """News (source_trust 0.4 + 'news' dampener) scores below the wake threshold."""
        from cosmo.triage import TriageOrchestrator
        from cosmo.ledger import CosmoLedger

        ledger = CosmoLedger(self.test_db)
        triage = TriageOrchestrator(ledger)
        event = {
            "source": "finnhub_news",
            "source_trust": 0.4,
            "severity": 0.5,
            "prediction_error": 0.3,
            "convergence": 0,
            "magnitude": 0.4,
            "tags": ["news"],
            "ticker": "AAPL",
            "description": "Market news",
        }
        result = triage.evaluate_event(event)
        self.assertLess(result["score"], 0.70, "News headlines should score below wake threshold")
        self.assertFalse(result["wake_swarm"], "Should not wake swarm for low-trust news")

    # ==================== ITEM 4: OLLAMA SEAT (parser logic) ==================== #

    def test_item4_ollama_seat_checks_availability(self):
        """Ollama seat gracefully handles unavailability (no crash if not running)."""
        from cosmo.seat_ollama import OllamaThesisProposer

        proposer = OllamaThesisProposer()
        self.assertIsNotNone(proposer)

    @patch("requests.post")
    def test_item4_ollama_parses_structured_thesis(self, mock_post):
        """The Ollama seat parses a structured LLM response into a thesis dict.

        This mocks the LOCAL model transport only (not market reality) to test our
        deterministic parser.
        """
        from cosmo.seat_ollama import OllamaThesisProposer

        ollama_response = """THESIS: AAPL will rise on strong earnings
MECHANISM: Earnings surprise triggers algorithm buying
ACTION: BUY
CONFIDENCE: HIGH
RISK: Guidance might be weak despite beat
INVALIDATION: If price drops below $140 within 5 days
EVIDENCE_TAG: HYPOTHESIS"""

        mock_response = Mock()
        mock_response.json.return_value = {"response": ollama_response}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        proposer = OllamaThesisProposer()
        proposer.available = True  # force the seat active for the parser test

        thesis = proposer.propose_thesis({
            "ticker": "AAPL",
            "source": "edgar",
            "source_trust": 1.0,
            "category": "earnings",
            "description": "AAPL beats Q3 earnings",
        })

        self.assertIsNotNone(thesis, "Parser should produce a thesis from a well-formed response")
        self.assertEqual(thesis["ticker"], "AAPL")
        self.assertEqual(thesis["action"], "BUY")
        self.assertIn("earnings", thesis["mechanism"].lower())
        self.assertEqual(thesis["evidence_tag"], "HYPOTHESIS")

    def test_item4_ollama_logs_thesis_to_ledger(self):
        """A parsed thesis logs to reality_ledger under proposer='ollama-local'.

        The seat writes decisions through the RealityScribe API (log_decision),
        which is the reality-ledger interface.
        """
        from cosmo.seat_ollama import OllamaThesisProposer
        from cosmo.scribe import RealityScribe

        proposer = OllamaThesisProposer()
        scribe = RealityScribe(self.test_db)
        thesis = {
            "ticker": "TEST",
            "mechanism": "Test causal mechanism",
            "action": "BUY",
            "risk": "Test risk",
            "invalidation": "Test invalidation",
            "thesis": "Test thesis",
            "source": "test",
        }
        ledger_id = proposer.log_thesis(thesis, scribe)
        self.assertIsNotNone(ledger_id, "Thesis should log to the reality ledger")

        conn = sqlite3.connect(self.test_db)
        row = conn.execute(
            "SELECT proposer FROM reality_ledger WHERE id = ?", (ledger_id,)
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "ollama-local")
        scribe.close()


if __name__ == "__main__":
    unittest.main()
