import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cosmo.config import ProviderConfig, load_provider_config
from cosmo.forager import ForagerEngine
from cosmo.ledger import CosmoLedger


class ForagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="cosmo-forager-", dir=".")
        self.db_path = os.path.join(self.tmp_dir, "cosmo.sqlite")
        self.ledger = CosmoLedger(self.db_path)
        self.engine = ForagerEngine(self.ledger)

    def test_provider_config_reads_env(self):
        env = {
            "CLAUDE_API_KEY": "claude-key",
            "GEMINI_API_KEY": "gemini-key",
            "OLLAMA_BASE_URL": "http://localhost:11434",
        }
        config = load_provider_config(env)
        self.assertEqual(config.claude_api_key, "claude-key")
        self.assertEqual(config.gemini_api_key, "gemini-key")
        self.assertEqual(config.ollama_base_url, "http://localhost:11434")

    def test_provider_config_reads_legacy_wolf_pack_keys(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        keys_doc = os.path.join(repo_root, "clones", "the-wolf-pack-v1.1", "YOUR_API_KEYS.md")
        config = load_provider_config({}, api_keys_doc_path=keys_doc)

        self.assertTrue(config.alpaca_api_key_id)
        self.assertTrue(config.alpaca_api_secret_key)
        self.assertTrue(config.alpaca_base_url)
        self.assertTrue(config.finnhub_api_key)
        self.assertTrue(config.newsapi_key)

    def test_forager_logs_and_triages_event(self):
        result = self.engine.ingest_event(
            {
                "source": "edgar",
                "event_type": "filing",
                "entity": "LUMN",
                "summary": "Coherent expands photonics capacity",
                "severity": 0.92,
                "magnitude": 0.85,
                "prediction_error": 0.88,
                "convergence": 2,
                "tags": ["photonics", "ai"],
            }
        )

        self.assertTrue(result["triage"]["wake_swarm"])
        self.assertEqual(len(self.ledger.list_raw_events()), 1)
        self.assertEqual(self.ledger.list_raw_events()[0]["entity"], "LUMN")


if __name__ == "__main__":
    unittest.main()
