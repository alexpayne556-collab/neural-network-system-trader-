"""
EDGAR POLLER: The organism's ground-truth eyes.
Fetches SEC filings from the free EDGAR feed and routes them through triage.

Uses the SEC "getcurrent" Atom feed — the canonical real-time latest-filings
stream — and resolves each filer's CIK to a tradeable ticker via the official
SEC company_tickers.json map. No mock, no toy data: real filings only.

Usage:
    python edgar_poller.py --once --dry-run
    python edgar_poller.py --poll --interval 120
"""

import re
import time
import argparse
import sqlite3
from typing import Dict, Any, List, Optional
import logging
import xml.etree.ElementTree as ET

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EDGAR")

# SEC requires a declared User-Agent on every request or it returns 403.
SEC_USER_AGENT = "Cosmos Research alexpayne556@gmail.com"
GETCURRENT_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

# Form types we care about, with a materiality (severity) prior for triage.
FORM_SEVERITY = {"8-K": 0.9, "4": 0.85, "6-K": 0.8, "10-Q": 0.7, "10-K": 0.7}


class EDGARPoller:
    """Fetch SEC filings from the EDGAR real-time getcurrent feed."""

    def __init__(self, db_path: str = "cosmo.sqlite"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
        self._cik_ticker: Optional[Dict[int, str]] = None
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
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM edgar_dedup WHERE accession_number = ?", (accession_number,))
        return cursor.fetchone() is not None

    def _mark_seen(self, accession_number: str):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO edgar_dedup (accession_number) VALUES (?)", (accession_number,))
        self.conn.commit()

    def _load_cik_ticker_map(self) -> Dict[int, str]:
        """Load (and cache) the official SEC CIK -> ticker map."""
        if self._cik_ticker is not None:
            return self._cik_ticker
        mapping: Dict[int, str] = {}
        try:
            resp = requests.get(COMPANY_TICKERS_URL, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for _, row in data.items():
                mapping[int(row["cik_str"])] = row["ticker"]
        except Exception as e:
            logger.warning(f"Could not load CIK->ticker map: {e}")
        self._cik_ticker = mapping
        return mapping

    def _resolve_ticker(self, cik: Optional[str]) -> Optional[str]:
        if not cik:
            return None
        try:
            return self._load_cik_ticker_map().get(int(cik))
        except (ValueError, TypeError):
            return None

    def fetch_recent_filings(self, forms: Optional[List[str]] = None, count: int = 40) -> List[Dict[str, Any]]:
        """
        Fetch the most recent real filings from the SEC getcurrent Atom feed.
        Returns triage-ready event dicts (already shaped for ForagerEngine.ingest_event).
        """
        forms = forms or ["8-K", "4", "10-Q"]
        filings: List[Dict[str, Any]] = []

        for form_type in forms:
            try:
                resp = requests.get(
                    GETCURRENT_URL,
                    params={
                        "action": "getcurrent",
                        "type": form_type,
                        "count": str(count),
                        "output": "atom",
                    },
                    headers=self.headers,
                    timeout=15,
                )
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
            except Exception as e:
                logger.error(f"Error fetching EDGAR {form_type} feed: {e}")
                continue

            for entry in root.findall("a:entry", ATOM_NS):
                title_el = entry.find("a:title", ATOM_NS)
                id_el = entry.find("a:id", ATOM_NS)
                link_el = entry.find("a:link", ATOM_NS)
                updated_el = entry.find("a:updated", ATOM_NS)
                cat_el = entry.find("a:category", ATOM_NS)

                title = title_el.text if title_el is not None else ""
                accession = (id_el.text or "").split("accession-number=")[-1].strip() if id_el is not None else ""
                if not accession or self._has_seen(accession):
                    continue

                # Title looks like: "8-K - Ainos, Inc. (0001014763) (Filer)"
                cik_matches = re.findall(r"\((\d{6,10})\)", title)
                cik = cik_matches[0] if cik_matches else None
                form = (cat_el.get("term") if cat_el is not None else None) or (
                    title.split(" - ", 1)[0].strip() if " - " in title else form_type
                )
                company = title.split(" - ", 1)[1].split(" (")[0].strip() if " - " in title else title
                ticker = self._resolve_ticker(cik)
                url = link_el.get("href") if link_el is not None else None
                filed_at = updated_el.text if updated_el is not None else None

                filings.append({
                    "source": "edgar",
                    "source_trust": 1.0,
                    "entity": ticker or cik,          # ledger entity: prefer ticker, fall back to CIK
                    "ticker": ticker,
                    "cik": cik,
                    "company": company,
                    "form_type": form,
                    "event_type": form,               # forager/triage reads event_type
                    "description": f"{form} filing by {company}" + (f" ({ticker})" if ticker else ""),
                    "summary": f"{form} filing by {company}" + (f" ({ticker})" if ticker else ""),
                    "accession_number": accession,
                    "filed_at": filed_at,
                    "url": url,
                    "severity": FORM_SEVERITY.get(form, 0.6),
                    "prediction_error": 0.5,
                    "convergence": 0,
                    "magnitude": 0.5,
                    "tags": [],
                    "category": "filing",
                })

        return filings

    def ingest_filings(self, filings: List[Dict[str, Any]], dry_run: bool = False):
        """Ingest fetched filings into the ledger and triage pipeline."""
        from cosmo.ledger import CosmoLedger
        from cosmo.forager import ForagerEngine

        if not filings:
            logger.info("No new filings to ingest.")
            return

        ledger = CosmoLedger(self.db_path)
        forager = ForagerEngine(ledger)

        for filing in filings:
            accession = filing["accession_number"]

            if self._has_seen(accession):
                continue

            if dry_run:
                logger.info(f"[DRY RUN] Would ingest: {filing['form_type']} - {filing['description']}")
                continue

            try:
                ledger.log_raw_event(
                    source="edgar",
                    event_type=filing["form_type"],
                    entity=filing.get("entity") or "UNKNOWN",
                    summary=filing["description"],
                    payload=filing,
                )

                # Ingest through forager/triage (returns {"event":..., "triage":...})
                result = forager.ingest_event(filing)
                triage = result["triage"]
                logger.info(
                    f"Ingested {filing['form_type']} {filing.get('entity')}: "
                    f"score={triage['score']}, route={triage['route']}"
                )

                self._mark_seen(accession)

            except Exception as e:
                logger.error(f"Error ingesting {accession}: {e}")

    def poll(self, interval: int = 120, max_iterations: Optional[int] = None):
        """Continuously poll EDGAR for new filings."""
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
