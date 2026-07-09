"""
SEAT OLLAMA: The organism's first voice — local LLM thesis proposals.
Ollama as Seat One, proposing theses for events that pass triage.

Prerequisites: Ollama must be running locally
    ollama serve
    ollama pull llama3.2 (or another model)

Usage (integrated into runner.py):
    When triage wakes a swarm, Ollama gets a chance to propose a thesis.
    Proposal logged to reality_ledger under proposer='ollama-local'.
"""

import requests
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SEAT_OLLAMA")


class OllamaThesisProposer:
    """Local Ollama LLM as the first council seat."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=2
            )
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check if our model is available (might be "llama3.2:latest")
                model_available = any(self.model in m for m in models)
                
                if model_available:
                    logger.info(f"✓ Ollama available with model {self.model}")
                else:
                    logger.warning(f"Model {self.model} not found. Available: {models[:3]}")
                    # Fall back to first available model
                    if models:
                        self.model = models[0]
                        logger.info(f"Using fallback model: {self.model}")
                
                return True
        except requests.ConnectionError:
            logger.warning("Ollama not running. Local seat will be inactive.")
        except Exception as e:
            logger.warning(f"Error checking Ollama: {e}")
        
        return False
    
    def propose_thesis(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Ask Ollama to propose a thesis for this event.
        
        Args:
            event: Triaged event dict from triage.py
        
        Returns:
            Dict with thesis, mechanism, action, risk, invalidation, or None if error
        """
        if not self.available:
            logger.debug("Ollama not available, skipping proposal")
            return None
        
        try:
            ticker = event.get("ticker") or event.get("entity") or "N/A"
            source = event.get("source", "unknown")
            source_trust = event.get("source_trust", 0.5)
            category = event.get("category", "unknown")
            description = event.get("description") or event.get("summary", "Unknown event")
            
            # Construct prompt per Constitutional brief
            prompt = f"""You are a market research analyst in a council of equals. You have been shown the following market event:

{description}

Ticker: {ticker}
Source: {source} (trust level: {source_trust:.1f}/1.0)
Category: {category}

Your job is to propose a THESIS about what this event means for the stock price over the next 1-10 trading days. You must respond in EXACTLY this format, line by line:

THESIS: [one sentence — what you believe will happen and why]
MECHANISM: [the causal chain — what physical or economic constraint is being affected]
ACTION: [BUY / SELL / HOLD / PASS]
CONFIDENCE: [LOW / MEDIUM / HIGH]
RISK: [what could make this thesis wrong]
INVALIDATION: [specific measurable condition that kills this thesis]
EVIDENCE_TAG: [HYPOTHESIS]

Be concise. Do not hedge. State your thesis clearly. If you don't have enough information, say ACTION: PASS.
"""
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.5
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama error: {response.status_code}")
                return None
            
            result = response.json()
            response_text = result.get("response", "")
            
            # Parse structured response
            thesis_dict = self._parse_response(response_text, ticker)
            return thesis_dict
        
        except requests.Timeout:
            logger.warning("Ollama request timed out")
            return None
        except Exception as e:
            logger.error(f"Error proposing thesis: {e}")
            return None
    
    def _parse_response(self, response_text: str, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Parse Ollama's structured response into a thesis dict.
        """
        try:
            lines = response_text.strip().split("\n")
            thesis_dict = {}
            
            for line in lines:
                if line.startswith("THESIS:"):
                    thesis_dict["thesis"] = line.replace("THESIS:", "").strip()
                elif line.startswith("MECHANISM:"):
                    thesis_dict["mechanism"] = line.replace("MECHANISM:", "").strip()
                elif line.startswith("ACTION:"):
                    action = line.replace("ACTION:", "").strip()
                    thesis_dict["action"] = action if action in ["BUY", "SELL", "HOLD", "PASS"] else "PASS"
                elif line.startswith("CONFIDENCE:"):
                    thesis_dict["confidence"] = line.replace("CONFIDENCE:", "").strip()
                elif line.startswith("RISK:"):
                    thesis_dict["risk"] = line.replace("RISK:", "").strip()
                elif line.startswith("INVALIDATION:"):
                    thesis_dict["invalidation"] = line.replace("INVALIDATION:", "").strip()
                elif line.startswith("EVIDENCE_TAG:"):
                    thesis_dict["evidence_tag"] = line.replace("EVIDENCE_TAG:", "").strip()
            
            # Ensure required fields
            if all(k in thesis_dict for k in ["thesis", "mechanism", "action", "risk", "invalidation"]):
                thesis_dict["ticker"] = ticker
                thesis_dict["proposer"] = "ollama-local"
                thesis_dict["timestamp"] = datetime.utcnow().isoformat()
                return thesis_dict
            else:
                logger.warning(f"Incomplete parse. Got: {thesis_dict}")
                return None
        
        except Exception as e:
            logger.error(f"Error parsing thesis response: {e}")
            return None
    
    def log_thesis(self, thesis: Dict[str, Any], ledger) -> Optional[int]:
        """
        Log the proposed thesis to reality_ledger.
        """
        if not thesis:
            return None
        
        try:
            ledger_id = ledger.log_decision(
                ticker=thesis["ticker"],
                trigger_event=f"Event from {thesis.get('source', 'unknown')}",
                causal_mechanism=thesis.get("mechanism", ""),
                action_taken=thesis.get("action", "PASS"),
                evidence_tag="HYPOTHESIS",
                reasoning_trace=f"Ollama proposal: {thesis.get('thesis', '')}\nRisk: {thesis.get('risk', '')}\nInvalidation: {thesis.get('invalidation', '')}",
                proposer="ollama-local"
            )
            
            logger.info(f"Logged Ollama thesis (ID {ledger_id}): {thesis.get('ticker')} {thesis.get('action')}")
            return ledger_id
        
        except Exception as e:
            logger.error(f"Error logging thesis: {e}")
            return None


def propose_and_log_thesis(event: Dict[str, Any], ledger, db_path: str = "cosmo.sqlite") -> Optional[int]:
    """
    Convenience function: take a triaged event, propose via Ollama, log to ledger.
    
    Returns:
        Ledger ID if successful, None otherwise
    """
    proposer = OllamaThesisProposer()
    
    if not proposer.available:
        return None
    
    thesis = proposer.propose_thesis(event)
    if thesis:
        return proposer.log_thesis(thesis, ledger)
    
    return None
