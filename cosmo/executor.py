"""
EXECUTOR: the organism's hands — Alpaca PAPER execution + position monitoring.

This is the "Alpaca (Execute)" node of the architecture. It places real orders
on real tickers with paper dollars (the residency), logs every execution as a
real decision in the RealityLedger, and lets you watch live P&L.

Order policy: buys use a MARKETABLE LIMIT (last price * (1 + limit_pct)) so we
never eat an uncapped market print on a thin name. Sizing is bounded by the
limit price, so the worst-case notional never exceeds --notional.

Usage:
    python -m cosmo.executor buy AIMDW --notional 90 --limit-pct 0.16 --proposer e2e-live \
        --mechanism "8-K-disclosure-catalyst" --physical-dep "SEC-mandated-disclosure" \
        --trigger "EDGAR-8-K-0001493152-26-032729"
    python -m cosmo.executor pnl AIMDW
    python -m cosmo.executor orders
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from cosmo.config import load_provider_config

ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets"
DASHBOARD_URL = "https://app.alpaca.markets/paper/dashboard/overview"


class AlpacaExecutor:
    """Places paper orders and reports positions/P&L from the live Alpaca account."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(repo_root / "cosmo.sqlite")
        cfg = load_provider_config()
        if not (cfg.alpaca_api_key_id and cfg.alpaca_api_secret_key):
            raise RuntimeError("Alpaca keys not configured (.env). Executor needs live paper keys.")
        import alpaca_trade_api as tradeapi
        self.api = tradeapi.REST(
            key_id=cfg.alpaca_api_key_id,
            secret_key=cfg.alpaca_api_secret_key,
            base_url=ALPACA_PAPER_BASE,
        )

    # ---------- market data helpers ----------
    def last_price(self, ticker: str) -> float:
        try:
            return float(self.api.get_latest_trade(ticker).price)
        except Exception:
            bars = self.api.get_bars(ticker, "1Day").df
            return float(bars.iloc[-1]["close"])

    def asset_ok(self, ticker: str) -> Dict[str, Any]:
        a = self.api.get_asset(ticker)
        return {"tradable": a.tradable, "fractionable": a.fractionable,
                "exchange": a.exchange, "status": a.status}

    # ---------- execution ----------
    def buy(self, ticker: str, notional: float, limit_pct: float = 0.16,
            proposer: str = "e2e-live", mechanism: str = "unspecified-mechanism",
            physical_dep: Optional[str] = None, trigger: Optional[str] = None,
            reasoning: Optional[str] = None) -> Dict[str, Any]:
        info = self.asset_ok(ticker)
        if not info["tradable"] or info["status"] != "active":
            raise RuntimeError(f"{ticker} is not tradable on Alpaca ({info}). Refusing to fake a fill.")

        last = self.last_price(ticker)
        limit_price = max(0.01, round(last * (1 + limit_pct), 2))
        qty = max(1, int(notional // limit_price))          # bound worst-case notional by --notional
        clock = self.api.get_clock()

        order = self.api.submit_order(
            symbol=ticker, qty=qty, side="buy", type="limit",
            time_in_force="day", limit_price=limit_price,
        )
        submitted = {
            "order_id": order.id,
            "symbol": ticker,
            "side": "buy",
            "qty": qty,
            "limit_price": limit_price,
            "last_price": last,
            "worst_case_notional": round(qty * limit_price, 2),
            "est_notional": round(qty * last, 2),
            "status": order.status,
            "market_open": clock.is_open,
            "fills": "immediately" if clock.is_open else f"queued for next open {clock.next_open}",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        ledger_id = self._log_decision(ticker, proposer, mechanism, physical_dep, trigger,
                                       reasoning, submitted)
        submitted["ledger_id"] = ledger_id
        return submitted

    def _log_decision(self, ticker, proposer, mechanism, physical_dep, trigger, reasoning, order_info) -> int:
        from cosmo.scribe import RealityScribe
        scribe = RealityScribe(self.db_path)
        try:
            ledger_id = scribe.log_decision(
                ticker=ticker,
                trigger_event=trigger or f"manual-{ticker}",
                causal_mechanism=mechanism,
                action_taken="BUY",
                evidence_tag="HYPOTHESIS",
                physical_dependency=physical_dep,
                evidence_json={"paper_order": order_info},
                reasoning_trace=reasoning or f"Paper BUY {order_info['qty']} {ticker} @ limit {order_info['limit_price']}.",
                notes=f"alpaca_order_id={order_info['order_id']}; {order_info['fills']}",
                proposer=proposer,
            )
            return ledger_id
        finally:
            scribe.close()

    # ---------- monitoring ----------
    def pnl(self, ticker: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {"ticker": ticker, "position": None, "open_orders": []}
        try:
            p = self.api.get_position(ticker)
            out["position"] = {
                "qty": p.qty,
                "avg_entry": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "cost_basis": float(p.cost_basis),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
        except Exception:
            out["position"] = None  # no fill yet
        for o in self.api.list_orders(status="open"):
            if o.symbol == ticker:
                out["open_orders"].append({
                    "id": o.id, "side": o.side, "qty": o.qty,
                    "type": o.type, "limit_price": o.limit_price, "status": o.status,
                })
        return out


def _print_pnl(executor: "AlpacaExecutor", ticker: str):
    data = executor.pnl(ticker)
    print(f"\n=== P&L  {ticker} ===")
    pos = data["position"]
    if pos:
        arrow = "▲" if pos["unrealized_pl"] >= 0 else "▼"
        print(f"  {pos['qty']} sh @ avg {pos['avg_entry']:.4f}  ->  now {pos['current_price']:.4f}")
        print(f"  market value ${pos['market_value']:.2f} | cost ${pos['cost_basis']:.2f}")
        print(f"  {arrow} unrealized P&L: ${pos['unrealized_pl']:+.2f} ({pos['unrealized_plpc']*100:+.2f}%)")
    else:
        print("  no filled position yet")
    for o in data["open_orders"]:
        print(f"  OPEN ORDER {o['side']} {o['qty']} @ {o['limit_price']} [{o['status']}] id={o['id'][:8]}")
    print(f"  dashboard: {DASHBOARD_URL}")


def main():
    parser = argparse.ArgumentParser(description="Cosmos paper executor + monitor")
    sub = parser.add_subparsers(dest="cmd")

    b = sub.add_parser("buy", help="Place a paper BUY (marketable limit) and log the decision")
    b.add_argument("ticker")
    b.add_argument("--notional", type=float, default=90.0, help="Max dollars to deploy (worst-case bound)")
    b.add_argument("--limit-pct", type=float, default=0.16, help="Limit price = last * (1 + this)")
    b.add_argument("--proposer", default="e2e-live")
    b.add_argument("--mechanism", default="unspecified-mechanism")
    b.add_argument("--physical-dep", default=None)
    b.add_argument("--trigger", default=None)
    b.add_argument("--reasoning", default=None)

    p = sub.add_parser("pnl", help="Show position + open orders + unrealized P&L")
    p.add_argument("ticker")

    sub.add_parser("orders", help="List all open orders")

    args = parser.parse_args()
    ex = AlpacaExecutor()

    if args.cmd == "buy":
        result = ex.buy(args.ticker, notional=args.notional, limit_pct=args.limit_pct,
                        proposer=args.proposer, mechanism=args.mechanism,
                        physical_dep=args.physical_dep, trigger=args.trigger, reasoning=args.reasoning)
        print(json.dumps(result, indent=2))
        _print_pnl(ex, args.ticker)
    elif args.cmd == "pnl":
        _print_pnl(ex, args.ticker)
    elif args.cmd == "orders":
        for o in ex.api.list_orders(status="open"):
            print(f"  {o.symbol} {o.side} {o.qty} {o.type} @ {o.limit_price} [{o.status}] id={o.id}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
