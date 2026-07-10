"""
REAL END-TO-END TEST — no mocks, no toy data.

Exercises the actual organism loop against live reality:
  1. LIVE EDGAR: pull real filings from the SEC getcurrent feed, resolve
     CIK -> ticker, and ingest them through Forager -> Triage -> Ledger.
  2. LIVE ALPACA: take a real filer's ticker, fetch real historical prices,
     and grade a real decision written to the RealityLedger.
  3. GHOST: judge the graded mechanism with real expectancy math.

This test PASSES ONLY IF the real pipeline works. If EDGAR or Alpaca is
unreachable, or the wiring is broken, it FAILS — that is the point. The
organism learns on the real stethoscope: real filings, real prices,
real graded outcomes. The only thing paper is the dollars.

Requires network + live Alpaca keys (loaded from .env by config.py).
"""

import os
import re
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cosmo.migrate import migrate
from cosmo.edgar_poller import EDGARPoller
from cosmo.price_grader import PriceGrader
from cosmo.ghost_listener import GhostListener
from cosmo.scribe import RealityScribe
from cosmo.config import load_provider_config

ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


class RealEndToEndTest(unittest.TestCase):
    """The real stethoscope: live filings -> live prices -> graded outcome -> Ghost."""

    @classmethod
    def setUpClass(cls):
        cls.db = "test_e2e_real.sqlite"
        if Path(cls.db).exists():
            Path(cls.db).unlink()
        migrate(cls.db)
        cls.cfg = load_provider_config()

    def test_1_alpaca_keys_present(self):
        """Live keys are required — this is not a mock."""
        self.assertTrue(
            self.cfg.alpaca_api_key_id and self.cfg.alpaca_api_secret_key,
            "Live Alpaca keys required (config/.env) — this is a REAL test",
        )

    def test_2_full_pipeline_live(self):
        # ---------- LEG 1: LIVE EDGAR -> ingest ----------
        poller = EDGARPoller(self.db)
        filings = poller.fetch_recent_filings(forms=["8-K"], count=60)
        self.assertGreater(len(filings), 0, "EDGAR returned no real filings")
        self.assertTrue(
            all(ACCESSION_RE.match(f["accession_number"]) for f in filings),
            "Filings must carry real SEC accession numbers",
        )

        poller.ingest_filings(filings)

        # raw_events populated => log_raw_event(entity=...) wiring works on real data
        conn = sqlite3.connect(self.db)
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
        conn.close()
        self.assertGreater(raw_count, 0, "Ingest wrote no raw_events (wiring broken)")

        # at least one filing marked seen => forager.ingest_event result['triage'] path succeeded
        survived = [f for f in filings if poller._has_seen(f["accession_number"])]
        self.assertGreater(len(survived), 0, "No filing survived ingest (result['triage'] wiring broken)")
        poller.close()

        # ---------- LEG 2: LIVE ALPACA -> grade a real decision ----------
        grader = PriceGrader(self.db)
        self.assertIsNotNone(grader.api, "Alpaca API failed to initialize with live keys")

        # settled historical window so forward returns actually exist
        entry_date = (datetime.utcnow() - timedelta(days=45)).strftime("%Y-%m-%d")

        chosen, returns = None, None
        for f in filings:
            if not f.get("ticker"):
                continue
            r = grader.calculate_returns(entry_date, f["ticker"])
            if r and r.get("outcome_5d") is not None:
                chosen, returns = f, r
                break
        self.assertIsNotNone(chosen, "Could not grade ANY real filer ticker on live Alpaca data")

        # Schema for Truth: every decision row carries its causal mechanism + physical dependency
        mechanism = f"{chosen['form_type']}-disclosure-catalyst"
        scribe = RealityScribe(self.db)
        ledger_id = scribe.log_decision(
            ticker=chosen["ticker"],
            trigger_event=f"EDGAR-{chosen['form_type']}-{chosen['accession_number']}",
            causal_mechanism=mechanism,
            action_taken="BUY",
            evidence_tag="MEASURED",
            physical_dependency="SEC-mandated-disclosure",
            reasoning_trace=(
                f"Real {chosen['form_type']} by {chosen['company']} ({chosen['ticker']}); "
                f"grading realized forward return from {entry_date}."
            ),
            proposer="edgar-live",
        )

        ok = grader.grade_entry(ledger_id, chosen["ticker"], entry_date)
        self.assertTrue(ok, "Grading the real ledger entry failed")
        grader.close()

        row = sqlite3.connect(self.db).execute(
            "SELECT outcome_1d, outcome_5d FROM reality_ledger WHERE id=?", (ledger_id,)
        ).fetchone()
        self.assertIsNotNone(row[1], "outcome_5d was not written from real prices")
        self.assertIsInstance(row[1], float)
        self.assertAlmostEqual(row[1], returns["outcome_5d"], places=6)

        # real truth score from the real sign: did reality confirm the BUY thesis?
        scribe.update_outcome(ledger_id, truth_score=1.0 if row[1] > 0 else 0.0)
        scribe.close()

        # ---------- LEG 3: GHOST judges the real, graded mechanism ----------
        ghost = GhostListener(self.db)
        verdict = ghost.evaluate_proposal(
            causal_mechanism=mechanism,
            ticker=chosen["ticker"],
            proposed_action="BUY",
            trigger_event="live-e2e",
        )
        self.assertGreaterEqual(verdict.sample_size, 1, "Ghost saw no graded history")
        self.assertAlmostEqual(
            verdict.expectancy, returns["outcome_5d"], places=4,
            msg="Ghost expectancy must equal the real graded outcome",
        )
        ghost.close()

        print(
            f"\n[REAL E2E] {chosen['ticker']} ({chosen['company']}) {chosen['form_type']} "
            f"acc={chosen['accession_number']} | entry {entry_date} "
            f"| outcome_1d={returns['outcome_1d']} outcome_5d={returns['outcome_5d']:.4f} "
            f"| Ghost expectancy={verdict.expectancy:+.2%} veto={verdict.should_veto}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
