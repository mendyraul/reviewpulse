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

    def test_idempotency_key_camel_case_supported(self):
        payload = _sample_payload()
        payload.pop("idempotency_key")
        payload["idempotencyKey"] = "EVT-CAMEL"
        self.assertEqual("evt-camel", normalize_idempotency_key(payload))

    def test_event_id_supported_when_key_missing(self):
        payload = _sample_payload()
        payload.pop("idempotency_key")
        payload["event_id"] = "EVT-EVENT-ID"
        self.assertEqual("evt-event-id", normalize_idempotency_key(payload))

    def test_hash_fallback_deterministic_and_distinct(self):
        payload_a = _sample_payload()
        payload_a.pop("idempotency_key")
        payload_b = dict(payload_a)
        payload_b["message"] = "Changed payload"

        key_a_1 = normalize_idempotency_key(payload_a)
        key_a_2 = normalize_idempotency_key(dict(payload_a))
        key_b = normalize_idempotency_key(payload_b)

        self.assertEqual(key_a_1, key_a_2)
        self.assertNotEqual(key_a_1, key_b)

    def test_first_write_accepted_and_duplicate_rejected(self):
        payload = _sample_payload()
        id_store = InMemoryIdempotencyStore()
        draft_store = InMemoryFindingDraftStore()

        accepted_first = ingest_finding_event(payload, idempotency_store=id_store, finding_store=draft_store)
        accepted_duplicate = ingest_finding_event(payload, idempotency_store=id_store, finding_store=draft_store)

        self.assertTrue(accepted_first)
        self.assertFalse(accepted_duplicate)
        self.assertEqual(1, len(draft_store.findings))

    def test_duplicate_rejected_when_event_id_is_key_source(self):
        payload = _sample_payload()
        payload.pop("idempotency_key")
        payload["event_id"] = "evt-from-event-id"

        id_store = InMemoryIdempotencyStore()
        draft_store = InMemoryFindingDraftStore()

        first = ingest_finding_event(payload, idempotency_store=id_store, finding_store=draft_store)
        second = ingest_finding_event(dict(payload), idempotency_store=id_store, finding_store=draft_store)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(1, len(draft_store.findings))


if __name__ == "__main__":
    unittest.main()
