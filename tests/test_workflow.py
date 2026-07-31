import unittest

from src.workflow import (
    build_done_state_confirmation,
    reopen_finding,
    render_history_timeline,
    transition_finding_state,
)


class TestWorkflow(unittest.TestCase):
    def test_done_state_transition_writes_resolution_and_history(self) -> None:
        finding = {"id": "F-1", "status": "open"}

        updated = transition_finding_state(
            finding,
            actor="rico",
            to_state="resolved",
            rationale="Fix merged in PR #35",
            now_iso="2026-05-12T06:30:00Z",
        )

        self.assertEqual(updated["status"], "resolved")
        self.assertEqual(updated["resolvedAt"], "2026-05-12T06:30:00Z")
        self.assertEqual(updated["resolution"]["rationale"], "Fix merged in PR #35")
        self.assertEqual(updated["history"][0]["from"], "open")
        self.assertEqual(updated["history"][0]["to"], "resolved")

    def test_done_state_requires_rationale(self) -> None:
        with self.assertRaisesRegex(ValueError, "Rationale is required"):
            transition_finding_state({"status": "open"}, actor="rico", to_state="dismissed", rationale="  ")

    def test_reopen_clears_resolution_timestamp_and_appends_history(self) -> None:
        finding = {
            "id": "F-2",
            "status": "resolved",
            "resolvedAt": "2026-05-12T06:00:00Z",
            "history": [],
        }

        updated = reopen_finding(
            finding,
            actor="rico",
            rationale="Regression detected in follow-up review",
            now_iso="2026-05-12T07:30:00Z",
        )

        self.assertEqual(updated["status"], "reopened")
        self.assertNotIn("resolvedAt", updated)
        self.assertEqual(updated["reopenedAt"], "2026-05-12T07:30:00Z")
        self.assertEqual(updated["history"][-1]["from"], "resolved")
        self.assertEqual(updated["history"][-1]["to"], "reopened")

    def test_reopen_requires_done_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "already open"):
            reopen_finding({"status": "open"}, actor="rico", rationale="Still under investigation")

    def test_done_state_confirmation_payload_is_explicit(self) -> None:
        finding = {"id": "F-3", "status": "open"}

        confirmation = build_done_state_confirmation(
            finding,
            actor="rico",
            to_state="accepted_risk",
            rationale="Legacy dependency accepted for this release window",
        )

        self.assertEqual(confirmation["findingId"], "F-3")
        self.assertEqual(confirmation["from"], "open")
        self.assertEqual(confirmation["to"], "accepted_risk")
        self.assertIs(confirmation["requiresConfirmation"], True)
        self.assertIn("audit timeline", confirmation["message"])

    def test_history_timeline_renders_readable_entries(self) -> None:
        finding = {
            "history": [
                {
                    "at": "2026-05-12T06:30:00Z",
                    "actor": "rico",
                    "from": "open",
                    "to": "dismissed",
                    "rationale": "False positive confirmed in tests",
                }
            ]
        }

        lines = render_history_timeline(finding)

        self.assertEqual(len(lines), 1)
        self.assertIn("rico", lines[0])
        self.assertIn("open -> dismissed", lines[0])
        self.assertIn("False positive confirmed in tests", lines[0])


if __name__ == "__main__":
    unittest.main()
