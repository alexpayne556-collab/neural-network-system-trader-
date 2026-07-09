"""
EDGAR POLLER: The organism's ground-truth eyes.
Fetches SEC filings from the free EDGAR feed and routes them through triage.

Usage:
    python edgar_poller.py --once --dry-run
    python edgar_poller.py --poll --interval 120
"""

import requests
import sqlite3
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EDGAR")


class EDGARPoller:
    """Fetch SEC filings from EDGAR free feed."""
    
    def __init__(self, db_path: str = "cosmo.sqlite"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_dedup_table()
    
    def _ensure_dedup_table(self):
        """Create deduplication table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edgar_dedup (
                accession_number TEXT PRIMARY KEY,
                seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def _has_seen(self, accession_number: str) -> bool:
        """Check if we've already processed this filing."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM edgar_dedup WHERE accession_number = ?", (accession_number,))
        return cursor.fetchone() is not None
    
    def _mark_seen(self, accession_number: str):
        """Mark a filing as seen."""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO edgar_dedup (accession_number) VALUES (?)", (accession_number,))
        self.conn.commit()
    
    def fetch_recent_filings(self) -> List[Dict[str, Any]]:
        """
        Fetch recent 8-K, Form 4, and 10-K/10-Q filings from EDGAR.
        Uses the free SEC EDGAR JSON search API.
        """
        filings = []
        
        # SEC EDGAR free endpoint: search for recent filings
        try:
            # Simple approach: fetch 10 most recent 8-K filings
            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            
            for form_type in ["8-K", "4", "10-K", "10-Q"]:
                params = {
                    "action": "getcompany",
                    "type": form_type,
                    "dateb": datetime.now().strftime("%Y%m%d"),
                    "owner": "exclude",
                    "count": 5,
                    "output": "json"
                }
                
                response = requests.get(url, params=params, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                if "filings" in data and "files" in data["filings"]:
                    for filing in data["filings"]["files"][:5]:  # Last 5 filings per type
                        accession = filing.get("accession_number", "").replace("-", "")
                        
                        if not accession or self._has_seen(accession):
                            continue
                        
                        filings.append({
                            "source": "edgar",
                            "source_trust": 1.0,
                            "ticker": filing.get("cik_str"),
                            "form_type": form_type,
                            "description": f"{form_type} filing",
                            "accession_number": accession,
                            "filed_at": filing.get("filing_date"),
                            "url": f"https://www.sec.gov/Archives/{filing.get('href', '')}",
                            "severity": 0.9 if form_type in ["8-K", "4"] else 0.7,
                            "prediction_error": 0.5,
                            "convergence": 0.0,
                            "magnitude": 0.5,
                            "tags": [],
                            "category": "filing"
                        })
        
        except Exception as e:
            logger.error(f"Error fetching EDGAR filings: {e}")
            return []
        
        return filings
    
    def ingest_filings(self, filings: List[Dict[str, Any]], dry_run: bool = False):
        """
        Ingest fetched filings into the ledger and triage pipeline.
        """
        from cosmo.ledger import CosmoLedger
        from cosmo.forager import Forager
        
        if not filings:
            logger.info("No new filings to ingest.")
            return
        
        ledger = CosmoLedger(self.db_path)
        forager = Forager(ledger)
        
        for filing in filings:
            accession = filing["accession_number"]
            
            if self._has_seen(accession):
                continue
            
            if dry_run:
                logger.info(f"[DRY RUN] Would ingest: {filing['form_type']} - {filing['description']}")
            else:
                try:
                    # Log raw event
                    event_id = ledger.log_raw_event(
                        source="edgar",
                        event_type=filing["form_type"],
                        summary=filing["description"],
                        tags=[filing["form_type"], "filing"]
                    )
                    
                    # Ingest through forager/triage
                    result = forager.ingest_event(filing)
                    logger.info(f"Ingested {filing['form_type']}: score={result[0]['score']}, route={result[0]['route']}")
                    
                    self._mark_seen(accession)
                
                except Exception as e:
                    logger.error(f"Error ingesting {accession}: {e}")
    
    def poll(self, interval: int = 120, max_iterations: Optional[int] = None):
        """
        Continuously poll EDGAR for new filings.
        """
        iteration = 0
        try:
            while True:
                if max_iterations and iteration >= max_iterations:
                    break
                
                logger.info(f"Polling EDGAR (iteration {iteration + 1})...")
                filings = self.fetch_recent_filings()
                self.ingest_filings(filings)
                
                iteration += 1
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("EDGAR poller stopped.")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="EDGAR Poller: Fetch SEC filings")
    parser.add_argument("--once", action="store_true", help="Fetch once and exit")
    parser.add_argument("--poll", action="store_true", help="Continuously poll")
    parser.add_argument("--interval", type=int, default=120, help="Polling interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Print filings without storing")
    parser.add_argument("--db", default="cosmo.sqlite", help="Database path")
    
    args = parser.parse_args()
    
    poller = EDGARPoller(args.db)
    
    try:
        if args.once:
            filings = poller.fetch_recent_filings()
            logger.info(f"Fetched {len(filings)} new filings")
            for f in filings:
                logger.info(f"  {f['form_type']}: {f['description']}")
            poller.ingest_filings(filings, dry_run=args.dry_run)
        elif args.poll:
            logger.info(f"Starting EDGAR poller (interval={args.interval}s)")
            poller.poll(interval=args.interval)
        else:
            parser.print_help()
    finally:
        poller.close()


if __name__ == "__main__":
    main()
