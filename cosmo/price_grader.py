"""
PRICE GRADER: Outcome measurement via real market data.
Fetches actual prices from Alpaca (free IEX data) and grades ledger entries.

Usage:
    python price_grader.py --all
    python price_grader.py --ticker AAPL --date 2026-07-09
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import logging
from cosmo.config import load_provider_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PRICE_GRADER")


class PriceGrader:
    """Grade outcomes using real price data from Alpaca."""
    
    def __init__(self, db_path: str = "cosmo.sqlite"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Load Alpaca config
        self.config = load_provider_config()
        self.alpaca_api_key_id = self.config.alpaca_api_key_id
        self.alpaca_api_secret_key = self.config.alpaca_api_secret_key
        
        # Import alpaca_trade_api
        try:
            import alpaca_trade_api as tradeapi
            self.api = tradeapi.REST(
                key_id=self.alpaca_api_key_id,
                secret_key=self.alpaca_api_secret_key,
                base_url="https://paper-api.alpaca.markets"
            )
        except Exception as e:
            logger.warning(f"Could not initialize Alpaca API: {e}")
            self.api = None
    
    def fetch_bars(self, ticker: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """
        Fetch price bars from Alpaca (IEX data).
        
        Args:
            ticker: Stock symbol (e.g., "AAPL")
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format
        
        Returns:
            Dict with bars data or None if error
        """
        if not self.api:
            logger.error("Alpaca API not initialized")
            return None
        
        try:
            bars = self.api.get_bars(
                ticker,
                "1Day",
                start=start_date,
                end=end_date,
                adjustment="all"
            ).df
            
            return {
                "ticker": ticker,
                "bars": bars.to_dict(orient="records") if hasattr(bars, "to_dict") else []
            }
        except Exception as e:
            logger.error(f"Error fetching bars for {ticker}: {e}")
            return None
    
    def calculate_returns(self, entry_date: str, ticker: str) -> Optional[Dict[str, float]]:
        """
        Calculate returns at 1d, 3d, 5d, and 10d horizons.
        
        Args:
            entry_date: YYYY-MM-DD format (date of decision/event)
            ticker: Stock symbol
        
        Returns:
            Dict with outcome_1d, outcome_3d, outcome_5d, outcome_10d or None
        """
        try:
            entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
            
            # Fetch 10 trading days of data (add buffer for weekends/holidays)
            end_date = (entry_dt + timedelta(days=15)).strftime("%Y-%m-%d")
            
            bars_data = self.fetch_bars(ticker, entry_date, end_date)
            if not bars_data or not bars_data["bars"]:
                logger.warning(f"No bars found for {ticker} from {entry_date}")
                return None
            
            bars = bars_data["bars"]
            if not bars:
                return None
            
            entry_price = bars[0]["close"]  # Close of entry day
            
            returns = {
                "outcome_1d": None,
                "outcome_3d": None,
                "outcome_5d": None,
                "outcome_10d": None
            }
            
            # Calculate returns at each horizon
            if len(bars) > 1:
                returns["outcome_1d"] = (bars[1]["close"] - entry_price) / entry_price
            if len(bars) > 3:
                returns["outcome_3d"] = (bars[3]["close"] - entry_price) / entry_price
            if len(bars) > 5:
                returns["outcome_5d"] = (bars[5]["close"] - entry_price) / entry_price
            if len(bars) > 10:
                returns["outcome_10d"] = (bars[10]["close"] - entry_price) / entry_price
            
            return returns
        
        except Exception as e:
            logger.error(f"Error calculating returns for {ticker} from {entry_date}: {e}")
            return None
    
    def grade_entry(self, ledger_id: int, ticker: str, entry_date: str) -> bool:
        """
        Grade a single ledger entry with real price data.
        
        Args:
            ledger_id: ID in reality_ledger
            ticker: Stock symbol
            entry_date: YYYY-MM-DD format
        
        Returns:
            True if successfully graded, False otherwise
        """
        returns = self.calculate_returns(entry_date, ticker)
        if not returns:
            logger.warning(f"Could not calculate returns for {ticker}")
            return False
        
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE reality_ledger 
                SET outcome_1d = ?, outcome_3d = ?, outcome_5d = ?, outcome_10d = ?
                WHERE id = ?
            """, (
                returns.get("outcome_1d"),
                returns.get("outcome_3d"),
                returns.get("outcome_5d"),
                returns.get("outcome_10d"),
                ledger_id
            ))
            
            self.conn.commit()
            logger.info(f"Graded {ticker} (ID {ledger_id}): 5d={returns.get('outcome_5d', 'N/A')}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating ledger: {e}")
            return False
    
    def grade_all_pending(self) -> int:
        """
        Find all ungraded entries and grade them.
        
        Returns:
            Number of entries graded
        """
        cursor = self.conn.cursor()
        
        # Find all entries where outcome_1d is NULL and created_at is > 1 day ago
        one_day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        cursor.execute("""
            SELECT id, ticker, created_at 
            FROM reality_ledger 
            WHERE outcome_1d IS NULL 
            AND created_at < ?
            ORDER BY created_at DESC
        """, (one_day_ago,))
        
        entries = cursor.fetchall()
        graded = 0
        
        for entry in entries:
            entry_id = entry["id"]
            ticker = entry["ticker"]
            entry_date = entry["created_at"][:10]  # YYYY-MM-DD
            
            if self.grade_entry(entry_id, ticker, entry_date):
                graded += 1
        
        logger.info(f"Graded {graded} entries")
        return graded
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="Price Grader: Grade outcomes with real data")
    parser.add_argument("--all", action="store_true", help="Grade all pending entries")
    parser.add_argument("--id", type=int, help="Grade specific ledger ID")
    parser.add_argument("--ticker", help="Ticker symbol (used with --id)")
    parser.add_argument("--date", help="Entry date YYYY-MM-DD (used with --ticker)")
    parser.add_argument("--db", default="cosmo.sqlite", help="Database path")
    
    args = parser.parse_args()
    
    grader = PriceGrader(args.db)
    
    try:
        if args.all:
            graded = grader.grade_all_pending()
            print(f"✓ Graded {graded} entries")
        elif args.id and args.ticker and args.date:
            success = grader.grade_entry(args.id, args.ticker, args.date)
            if success:
                print(f"✓ Graded entry {args.id}")
            else:
                print(f"✗ Failed to grade entry {args.id}")
        else:
            parser.print_help()
    finally:
        grader.close()


if __name__ == "__main__":
    main()
