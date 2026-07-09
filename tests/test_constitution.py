import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cosmo.constitution import Constitution


class ConstitutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="cosmo-constitution-", dir=".")
        self.db_path = os.path.join(self.tmp_dir, "cosmo.sqlite")
        self.constitution = Constitution(self.db_path)

    def test_create_proposal_and_vote(self):
        proposal_id = self.constitution.create_proposal(
            proposal_type="THESIS",
            target_entity="LUMN",
            thesis="Photonics is the next bottleneck",
            evidence_json={"source": "10-K"},
            agent_id="bottleneck-swarm",
        )
        self.constitution.add_vote(proposal_id, "governor", "APPROVE", rationale="Evidence is strong")
        proposals = self.constitution.list_proposals()
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["proposal_type"], "THESIS")

    def test_add_graveyard_entry(self):
        self.constitution.add_graveyard_entry("XYZ", "failed thesis", "bottleneck")
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
