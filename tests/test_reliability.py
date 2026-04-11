from __future__ import annotations

import unittest

from src.reliability import ReliabilityTracker


class ReliabilityTrackerTests(unittest.TestCase):
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
