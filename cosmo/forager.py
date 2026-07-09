from typing import Any, Dict, List

from cosmo.ledger import CosmoLedger
from cosmo.triage import TriageOrchestrator


class ForagerEngine:
    """A lightweight ingestion engine that logs raw events and passes them through triage."""

    def __init__(self, ledger: CosmoLedger):
        self.ledger = ledger
        self.orchestrator = TriageOrchestrator(ledger)

    def ingest_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        self.ledger.log_raw_event(
            source=event.get("source", "unknown"),
            event_type=event.get("event_type", "unknown"),
            entity=event.get("entity", "unknown"),
            summary=event.get("summary", ""),
            payload=event,
        )
        triage_result = self.orchestrator.evaluate_event(event)
        return {
            "event": event,
            "triage": triage_result,
        }
