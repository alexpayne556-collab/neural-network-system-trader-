import argparse
import os
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from cosmo.config import load_provider_config
from cosmo.forager import ForagerEngine
from cosmo.ledger import CosmoLedger
from cosmo.reconcile import ReconciliationEngine
from cosmo.ghost_listener import GhostListener


def build_sample_event(iteration: int) -> dict:
    return {
        "source": "edgar",
        "event_type": "filing",
        "entity": "COSMO",
        "summary": f"Local heartbeat cycle {iteration}",
        "severity": 0.8,
        "magnitude": 0.7,
        "prediction_error": 0.75,
        "convergence": 2,
        "tags": ["ai", "bottleneck"],
    }


def main(loop: bool = False, iterations: int = 1, sleep_seconds: float = 2.0) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    db_path = str(repo_root / "cosmo.sqlite")
    ledger = CosmoLedger(db_path)
    forager = ForagerEngine(ledger)
    reconciler = ReconciliationEngine(ledger)
    ghost = GhostListener(db_path)  # Initialize Ghost listener
    config = load_provider_config(os.environ)

    print("Cosmos runtime starting...")
    print("Mode: local-only, no API keys required (but found:)")
    print(f"Ledger: {db_path}")
    print()
    print("Reasoning Providers:")
    print(f"  Claude configured: {'yes' if config.claude_api_key else 'no'}")
    print(f"  Gemini configured: {'yes' if config.gemini_api_key else 'no'}")
    print(f"  Ollama configured: {'yes' if config.ollama_base_url else 'no'}")
    print(f"  Hermes configured: {'yes' if config.hermes_api_key else 'no'}")
    print("\nTrading & Market Data:")
    print(f"  Alpaca configured: {'yes' if config.alpaca_api_key_id else 'no'}")
    print(f"  Finnhub configured: {'yes' if config.finnhub_api_key else 'no'}")
    print(f"  Polygon configured: {'yes' if config.polygon_api_key else 'no'}")
    print(f"  FMP configured: {'yes' if config.fmp_api_key else 'no'}")
    print(f"  EODHD configured: {'yes' if config.eodhd_api_key else 'no'}")
    print(f"  NewsAPI configured: {'yes' if config.newsapi_key else 'no'}")
    print()

    iteration = 0
    try:
        while True:
            iteration += 1
            sample_event = build_sample_event(iteration)
            result = forager.ingest_event(sample_event)
            trade_id = reconciler.log_trade(
                ticker="COSMO",
                thesis="The local event reflects a real bottleneck",
                trigger=sample_event["summary"],
                expected_window="3d",
                actual_outcome="pending",
                correctness_split={"signal": 0.5, "timing": 0.3, "execution": 0.1, "allocation": 0.1},
                trade_type="ai_bottleneck",
            )
            reconciler.reconcile_trade(
                trade_id=trade_id,
                realized_pnl=-0.09,
                expected_return=0.03,
                notes="The event was real but the timing was poor",
            )
            block_status = reconciler.should_block_trade("ai_bottleneck")

            # Ghost listener check: would this causal mechanism be vetoed?
            ghost_eval = ghost.evaluate_proposal(
                causal_mechanism="AI-HBM-Copper-Melt",
                ticker="COSMO",
                proposed_action="BUY",
                trigger_event=sample_event["summary"]
            )

            print(f"Cycle {iteration} processed")
            print("Event processed:", result["triage"])
            print("Raw events stored:", len(ledger.list_raw_events()))
            print("Reconciliation block status:", block_status)
            print(f"Ghost evaluation: {('🔒 VETO' if ghost_eval.should_veto else '✓ APPROVED')} - {ghost_eval.reason}")

            if not loop and iteration >= iterations:
                break
            if loop:
                time.sleep(sleep_seconds)
            else:
                break
    except KeyboardInterrupt:
        print("Cosmos runtime stopped.")
    finally:
        ghost.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Cosmos local runtime")
    parser.add_argument("--loop", action="store_true", help="Run continuously until interrupted")
    parser.add_argument("--iterations", type=int, default=1, help="Number of cycles to run when not looping")
    parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to wait between loop cycles")
    args = parser.parse_args()
    main(loop=args.loop, iterations=args.iterations, sleep_seconds=args.sleep)
