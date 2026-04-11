import unittest

from src.idempotency import InMemoryIdempotencyStore, normalize_idempotency_key
from src.intake import InMemoryFindingDraftStore, ingest_finding_event


def _sample_payload() -> dict:
    return {
        "source": "github_review",
        "repo": "mendyraul/reviewpulse",
        "prNumber": 42,
        "path": "src/intake.py",
        "lineStart": 10,
        "lineEnd": 10,
        "ruleId": "py.idempotency.001",
        "severity": "medium",
        "message": "Use deterministic idempotency handling",
        "idempotency_key": "EVT-123",
    }


class TestIdempotencyContract(unittest.TestCase):
    def test_idempotency_key_normalization(self):
        payload = _sample_payload()
        self.assertEqual("evt-123", normalize_idempotency_key(payload))

    def test_first_write_accepted_and_duplicate_rejected(self):
        payload = _sample_payload()
        id_store = InMemoryIdempotencyStore()
        draft_store = InMemoryFindingDraftStore()

        accepted_first = ingest_finding_event(payload, idempotency_store=id_store, finding_store=draft_store)
        accepted_duplicate = ingest_finding_event(payload, idempotency_store=id_store, finding_store=draft_store)

        self.assertTrue(accepted_first)
        self.assertFalse(accepted_duplicate)
        self.assertEqual(1, len(draft_store.findings))


if __name__ == "__main__":
    unittest.main()
