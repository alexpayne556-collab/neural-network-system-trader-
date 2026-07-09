from typing import Any, Dict


class TriageOrchestrator:
    """Routes incoming market events into the swarm based on a simple graded anomaly score."""

    def __init__(self, ledger):
        self.ledger = ledger

    def evaluate_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        source_trust = 1.0 if event.get("source") in {"edgar", "filing", "sec"} else 0.45
        materiality = float(event.get("severity", 0.0))
        prediction_error = float(event.get("prediction_error", 0.0))
        convergence = float(event.get("convergence", 0))
        magnitude = float(event.get("magnitude", 0.0))
        tags = event.get("tags", [])

        weighted_score = (
            0.35 * source_trust
            + 0.25 * materiality
            + 0.20 * prediction_error
            + 0.10 * min(convergence / 3.0, 1.0)
            + 0.10 * magnitude
        )

        if tags and any(tag in {"noise", "social", "headline"} for tag in tags):
            weighted_score *= 0.75

        wake_swarm = weighted_score >= 0.7
        return {
            "score": round(weighted_score, 3),
            "wake_swarm": wake_swarm,
            "route": self._route(event, wake_swarm),
            "reason": self._reason(event, weighted_score),
        }

    def _route(self, event: Dict[str, Any], wake_swarm: bool) -> str:
        if not wake_swarm:
            return "discard"
        if "biotech" in event.get("tags", []) or event.get("event_type") == "calendar":
            return "biotech-binary-swarm"
        if "geopolitics" in event.get("tags", []) or event.get("event_type") == "news":
            return "cascade-swarm"
        if "photonics" in event.get("tags", []) or "ai" in event.get("tags", []):
            return "bottleneck-swarm"
        return "general-swarm"

    def _reason(self, event: Dict[str, Any], weighted_score: float) -> str:
        if weighted_score >= 0.7:
            return "High-confidence anomaly with multi-source convergence"
        return "Insufficient signal quality or low convergence"
