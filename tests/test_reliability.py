from __future__ import annotations

import unittest

from src.reliability import ReliabilityTracker, RetryPolicy, is_retryable_error


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


if __name__ == "__main__":
    unittest.main()
