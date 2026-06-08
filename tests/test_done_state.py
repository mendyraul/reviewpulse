import unittest

from src.done_state import DoneDecision, apply_done_decision, done_timeline


class TestDoneState(unittest.TestCase):
    def test_apply_done_decision_requires_confirmation(self):
        finding = {"id": "f-1", "status": "in_progress"}
        decision = DoneDecision(
            state="resolved",
            rationale="Fixed by PR #12",
            actor="rico",
            confirmation=False,
        )

        with self.assertRaises(ValueError) as exc_info:
            apply_done_decision(finding, decision, now_iso="2026-05-12T19:10:00+00:00")

        self.assertEqual(str(exc_info.exception), "confirmation_required")

    def test_apply_done_decision_records_traceable_rationale_and_history(self):
        finding = {"id": "f-1", "status": "in_progress", "history": []}
        decision = DoneDecision(
            state="dismissed",
            rationale="False positive: test fixture-only path",
            actor="rico",
            confirmation=True,
        )

        updated = apply_done_decision(finding, decision, now_iso="2026-05-12T19:10:00+00:00")

        self.assertEqual(updated["status"], "dismissed")
        self.assertEqual(updated["closeRationale"], "False positive: test fixture-only path")
        self.assertEqual(updated["closedAt"], "2026-05-12T19:10:00+00:00")
        self.assertEqual(updated["history"][-1]["event"], "done_state_set")
        self.assertEqual(updated["history"][-1]["state"], "dismissed")

    def test_apply_done_decision_rejects_done_to_done_transition(self):
        finding = {"id": "f-1", "status": "resolved", "history": []}
        decision = DoneDecision(
            state="dismissed",
            rationale="Reclassifying closure type",
            actor="rico",
            confirmation=True,
        )

        with self.assertRaises(ValueError) as err:
            apply_done_decision(finding, decision, now_iso="2026-05-12T19:10:00+00:00")
        self.assertEqual(str(err.exception), "invalid_transition:done_to_done")

    def test_done_timeline_sorts_history(self):
        finding = {
            "history": [
                {"at": "2026-05-12T19:12:00+00:00", "event": "done_state_set"},
                {"at": "2026-05-12T19:11:00+00:00", "event": "status_changed"},
            ]
        }
        timeline = done_timeline(finding)
        self.assertEqual(timeline[0]["event"], "status_changed")


if __name__ == "__main__":
    unittest.main()
