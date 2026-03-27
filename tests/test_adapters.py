import json
import unittest
from pathlib import Path

from src.adapters import adapt_coderabbit_finding, adapt_github_review_comment
from src.normalize import compute_fingerprint, normalize_finding, validate_finding

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class TestAdapterMapping(unittest.TestCase):
    def test_github_adapter_maps_to_valid_draft(self):
        payload = json.loads((FIXTURE_DIR / "adapter_github_review_payload.json").read_text(encoding="utf-8"))
        draft = adapt_github_review_comment(payload)
        finding = normalize_finding(draft)

        self.assertEqual("github_review", finding["source"])
        self.assertEqual("mendyraul/reviewpulse", finding["repo"])
        self.assertEqual(12, finding["prNumber"])
        self.assertEqual(48, finding["lineStart"])
        self.assertEqual(49, finding["lineEnd"])
        self.assertEqual("py.return-type", finding["ruleId"])
        self.assertEqual("medium", finding["severity"])  # warning -> medium
        self.assertEqual([], list(validate_finding(finding)))

    def test_coderabbit_adapter_maps_to_valid_draft(self):
        payload = json.loads((FIXTURE_DIR / "adapter_coderabbit_payload.json").read_text(encoding="utf-8"))
        draft = adapt_coderabbit_finding(payload)
        finding = normalize_finding(draft)

        self.assertEqual("coderabbit", finding["source"])
        self.assertEqual("mendyraul/reviewpulse", finding["repo"])
        self.assertEqual("cr.determinism.001", finding["ruleId"])
        self.assertEqual("high", finding["severity"])
        self.assertEqual([], list(validate_finding(finding)))

    def test_adapter_output_is_deterministic(self):
        payload = json.loads((FIXTURE_DIR / "adapter_github_review_payload.json").read_text(encoding="utf-8"))
        draft_a = adapt_github_review_comment(payload)
        draft_b = adapt_github_review_comment(payload)

        finding_a = normalize_finding(draft_a)
        finding_b = normalize_finding(draft_b)

        self.assertEqual(compute_fingerprint(finding_a), compute_fingerprint(finding_b))
        self.assertEqual(finding_a["fingerprint"], finding_b["fingerprint"])


if __name__ == "__main__":
    unittest.main()
