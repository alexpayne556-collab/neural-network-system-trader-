"""
NEWS POLLER: Market event nerve via Finnhub headlines.
Fetches news headlines from Finnhub's free tier and routes through triage.

Usage:
    python news_poller.py --once --dry-run
    python news_poller.py --poll --interval 300
"""

import requests
import sqlite3
import json
import time
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NEWS")


class NewsPoller:
    """Fetch market news headlines from Finnhub."""
    
    def __init__(self, db_path: str = "cosmo.sqlite", api_key: Optional[str] = None):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Load API key: from parameter, environment, or .env config
        self.api_key = api_key
        if not self.api_key:
            import os
            self.api_key = os.environ.get("FINNHUB_API_KEY")
        if not self.api_key:
            try:
                from cosmo.config import load_provider_config
                config = load_provider_config()
                self.api_key = config.finnhub_api_key
            except:
                logger.warning("Could not load Finnhub API key from config")
        
        self._ensure_dedup_table()
    
    def _ensure_dedup_table(self):
        """Create deduplication table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_dedup (
                article_id TEXT PRIMARY KEY,
                seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def _has_seen(self, article_id: str) -> bool:
        """Check if we've already processed this headline."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM news_dedup WHERE article_id = ?", (article_id,))
        return cursor.fetchone() is not None
    
    def _mark_seen(self, article_id: str):
        """Mark a headline as seen."""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO news_dedup (article_id) VALUES (?)", (article_id,))
        self.conn.commit()
    
    def fetch_headlines(self, category: str = "general") -> List[Dict[str, Any]]:
        """
        Fetch recent headlines from Finnhub.
        
        Args:
            category: news category (general, forex, crypto, merger, earnings)
        
        Returns:
            List of headline event dicts
        """
        headlines = []
        
        if not self.api_key:
            logger.error("Finnhub API key not configured")
            return []
        
        try:
            url = "https://finnhub.io/api/v1/news"
            params = {
                "category": category,
                "token": self.api_key
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if "data" not in data:
                logger.warning(f"Unexpected Finnhub response: {data}")
                return []
            
            for article in data.get("data", []):
                article_id = f"{article.get('id')}_{article.get('datetime', '')}"
                
                if self._has_seen(article_id):
                    continue
                
                headlines.append({
                    "source": "finnhub_news",
                    "source_trust": 0.4,  # News is noisy, not ground truth
                    "ticker": article.get("related", [None])[0] if article.get("related") else None,
                    "description": article.get("headline", ""),
                    "url": article.get("url", ""),
                    "published_at": datetime.fromtimestamp(article.get("datetime", 0)).isoformat(),
                    "severity": 0.5,
                    "prediction_error": 0.3,
                    "convergence": 0.0,
                    "magnitude": 0.4,
                    "tags": ["news"],  # Triggers 0.75x dampener in triage
                    "category": category,
                    "article_id": article_id
                })
        
        except Exception as e:
            logger.error(f"Error fetching Finnhub headlines: {e}")
            return []
        
        return headlines
    
    def ingest_headlines(self, headlines: List[Dict[str, Any]], dry_run: bool = False):
        """
        Ingest fetched headlines into the ledger and triage pipeline.
        """
        from cosmo.ledger import CosmoLedger
        from cosmo.forager import Forager
        
        if not headlines:
            logger.info("No new headlines to ingest.")
            return
        
        ledger = CosmoLedger(self.db_path)
        forager = Forager(ledger)
        
        for headline in headlines:
            article_id = headline["article_id"]
            
            if self._has_seen(article_id):
                continue
            
            if dry_run:
                logger.info(f"[DRY RUN] Would ingest: {headline['description'][:60]}...")
            else:
                try:
                    # Log raw event
                    event_id = ledger.log_raw_event(
                        source="finnhub_news",
                        event_type="news",
                        summary=headline["description"],
                        tags=["news"]
                    )
                    
                    # Ingest through forager/triage
                    result = forager.ingest_event(headline)
                    status = "WAKE" if result[0]["wake_swarm"] else "DISCARD"
                    logger.info(f"[{status}] {headline['description'][:50]}... (score={result[0]['score']:.2f})")
                    
                    self._mark_seen(article_id)
                
                except Exception as e:
                    logger.error(f"Error ingesting headline: {e}")
    
    def poll(self, interval: int = 300, max_iterations: Optional[int] = None):
        """
        Continuously poll Finnhub for new headlines.
        """
        iteration = 0
        try:
            while True:
                if max_iterations and iteration >= max_iterations:
                    break
                
                logger.info(f"Polling Finnhub news (iteration {iteration + 1})...")
                headlines = self.fetch_headlines()
                self.ingest_headlines(headlines)
                
                iteration += 1
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("News poller stopped.")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="News Poller: Fetch market headlines")
    parser.add_argument("--once", action="store_true", help="Fetch once and exit")
    parser.add_argument("--poll", action="store_true", help="Continuously poll")
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds")
    parser.add_argument("--category", default="general", help="News category")
    parser.add_argument("--dry-run", action="store_true", help="Print headlines without storing")
    parser.add_argument("--db", default="cosmo.sqlite", help="Database path")
    
    args = parser.parse_args()
    
    poller = NewsPoller(args.db)
    
    try:
        if args.once:
            headlines = poller.fetch_headlines(args.category)
            logger.info(f"Fetched {len(headlines)} new headlines")
            for h in headlines:
                logger.info(f"  {h['description'][:70]}")
            poller.ingest_headlines(headlines, dry_run=args.dry_run)
        elif args.poll:
            logger.info(f"Starting news poller (interval={args.interval}s)")
            poller.poll(interval=args.interval)
        else:
            parser.print_help()
    finally:
        poller.close()


if __name__ == "__main__":
    main()
