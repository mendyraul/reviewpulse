from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.reliability import (
    DeadLetterEntry,
    DeadLetterQueue,
    ReliabilityTracker,
    ReplayLedger,
    RetryPolicy,
    is_retryable_error,
    replay_dead_letters,
)


class ReliabilityTrackerTests(unittest.TestCase):
    def test_retry_policy_backoff_is_bounded_and_deterministic(self) -> None:
        policy = RetryPolicy(max_attempts=4, base_delay_seconds=0.5, max_delay_seconds=1.0)
        self.assertEqual(policy.delay_for_attempt(1), 0.5)
        self.assertEqual(policy.delay_for_attempt(2), 1.0)
        self.assertEqual(policy.delay_for_attempt(3), 1.0)

    def test_retry_classifier_only_flags_transient_errors(self) -> None:
        self.assertTrue(is_retryable_error(TimeoutError("timeout")))
        self.assertTrue(is_retryable_error(ConnectionError("conn drop")))
        self.assertFalse(is_retryable_error(ValueError("bad payload")))

    def test_metrics_and_events_are_deterministic_shape(self) -> None:
        tracker = ReliabilityTracker()
        tracker.record_processed("fixtures/a.json")
        tracker.record_retry("fixtures/a.json", reason="network timeout", attempts=2)
        tracker.record_dead_letter("fixtures/b.json", reason="invalid schema")
        tracker.record_replay("fixtures/b.json")

        metrics = tracker.metrics()
        self.assertEqual(
            metrics,
            {
                "processed": 1,
                "retried": 1,
                "deadLettered": 1,
                "replayed": 1,
            },
        )

        self.assertEqual(len(tracker.events), 4)
        for event in tracker.events:
            self.assertIn("timestamp", event)
            self.assertIn("event", event)
            self.assertIn("payloadFile", event)
            self.assertIn("attempts", event)

    def test_dead_letter_artifact_schema_and_replay_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dlq_path = Path(tmp, "dead-letter.jsonl")
            ledger_path = Path(tmp, "replay-ledger.json")
            queue = DeadLetterQueue(dlq_path)
            ledger = ReplayLedger(ledger_path)

            written = queue.write(
                DeadLetterEntry(
                    payload_file="fixtures/bad.json",
                    reason="invalid schema",
                    payload={"source": "github_review", "ruleId": "style/nit"},
                    attempts=2,
                )
            )

            self.assertEqual(written["version"], 1)
            self.assertIn("id", written)
            self.assertIn("payloadHash", written)
            self.assertEqual(written["attempts"], 2)

            entries = queue.read_entries()
            dry_run_report = replay_dead_letters(entries, ledger=ledger, dry_run=True)
            self.assertEqual(dry_run_report["replayed"], 1)
            self.assertFalse(ledger_path.exists(), "dry-run should not mutate replay ledger")

            real_report = replay_dead_letters(entries, ledger=ledger, dry_run=False)
            self.assertEqual(real_report["replayed"], 1)
            self.assertTrue(ledger.has_replayed(written["id"]))

            second_pass = replay_dead_letters(entries, ledger=ledger, dry_run=False)
            self.assertEqual(second_pass["replayed"], 0)
            self.assertEqual(second_pass["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
