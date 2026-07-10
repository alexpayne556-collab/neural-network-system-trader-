import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ProviderConfig:
    claude_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    hermes_api_key: Optional[str] = None
    hermes_base_url: Optional[str] = None
    alpaca_api_key_id: Optional[str] = None
    alpaca_api_secret_key: Optional[str] = None
    alpaca_base_url: Optional[str] = None
    alpaca_recovery_code: Optional[str] = None
    finnhub_api_key: Optional[str] = None
    newsapi_key: Optional[str] = None
    polygon_api_key: Optional[str] = None
    fmp_api_key: Optional[str] = None
    alphavantage_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    eodhd_api_key: Optional[str] = None


def _load_dotenv(path: Optional[str] = None) -> Dict[str, str]:
    """Load .env file into a dictionary."""
    values: Dict[str, str] = {}
    env_path = path or os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    
    if not os.path.exists(env_path):
        return values
    
    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                values[key.strip()] = val.strip()
    
    return values


def _extract_from_doc(path: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path or not os.path.exists(path):
        return values

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    patterns = {
        "APCA_API_KEY_ID": r"APCA_API_KEY_ID\s*=\s*([^\s]+)",
        "APCA_API_SECRET_KEY": r"APCA_API_SECRET_KEY\s*=\s*([^\s]+)",
        "ALPACA_BASE_URL": r"ALPACA_BASE_URL\s*=\s*([^\s]+)",
        "FINNHUB_API_KEY": r"FINNHUB_API_KEY\s*=\s*([^\s]+)",
        "NEWSAPI_KEY": r"NEWSAPI_KEY\s*=\s*([^\s]+)",
        "POLYGON_API_KEY": r"POLYGON_API_KEY\s*=\s*([^\s]+)",
        "FMP_API_KEY": r"FMP_API_KEY\s*=\s*([^\s]+)",
        "ALPHAVANTAGE_API_KEY": r"ALPHAVANTAGE_API_KEY\s*=\s*([^\s]+)",
        "OPENAI_API_KEY": r"OPENAI_API_KEY\s*=\s*([^\s]+)",
        "CLAUDE_API_KEY": r"CLAUDE_API_KEY\s*=\s*([^\s]+)",
        "GEMINI_API_KEY": r"GEMINI_API_KEY\s*=\s*([^\s]+)",
        "OLLAMA_BASE_URL": r"OLLAMA_BASE_URL\s*=\s*([^\s]+)",
        "HERMES_API_KEY": r"HERMES_API_KEY\s*=\s*([^\s]+)",
        "HERMES_BASE_URL": r"HERMES_BASE_URL\s*=\s*([^\s]+)",
        "EODHD_API_KEY": r"EODHD_API_KEY\s*=\s*([^\s]+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            values[key] = match.group(1)

    return values


def load_provider_config(
    env: Optional[Dict[str, str]] = None,
    api_keys_doc_path: Optional[str] = None,
    env_file_path: Optional[str] = None,
) -> ProviderConfig:
    env = env or os.environ
    doc_values = _extract_from_doc(api_keys_doc_path) if api_keys_doc_path else {}
    dotenv_values = _load_dotenv(env_file_path)
    
    # Precedence (low -> high): .env fills gaps, explicit env wins over .env,
    # legacy api-keys doc applied last for backward compatibility.
    merged = dict(dotenv_values)
    merged.update({k: v for k, v in env.items() if v})
    merged.update({k: v for k, v in doc_values.items() if v})

    return ProviderConfig(
        claude_api_key=merged.get("CLAUDE_API_KEY"),
        gemini_api_key=merged.get("GEMINI_API_KEY"),
        ollama_base_url=merged.get("OLLAMA_BASE_URL"),
        hermes_api_key=merged.get("HERMES_API_KEY"),
        hermes_base_url=merged.get("HERMES_BASE_URL"),
        alpaca_api_key_id=merged.get("APCA_API_KEY_ID"),
        alpaca_api_secret_key=merged.get("APCA_API_SECRET_KEY"),
        alpaca_base_url=merged.get("ALPACA_BASE_URL"),
        alpaca_recovery_code=merged.get("ALPACA_RECOVERY_CODE"),
        finnhub_api_key=merged.get("FINNHUB_API_KEY"),
        newsapi_key=merged.get("NEWSAPI_KEY"),
        polygon_api_key=merged.get("POLYGON_API_KEY"),
        fmp_api_key=merged.get("FMP_API_KEY"),
        alphavantage_api_key=merged.get("ALPHAVANTAGE_API_KEY"),
        openai_api_key=merged.get("OPENAI_API_KEY"),
        eodhd_api_key=merged.get("EODHD_API_KEY"),
    )
