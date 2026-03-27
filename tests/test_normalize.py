import json
import unittest
from pathlib import Path

from src.normalize import compute_fingerprint, normalize_finding, validate_finding

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class TestNormalizeFinding(unittest.TestCase):
    def test_valid_fixtures_normalize_and_fingerprint_stable(self):
        for path in sorted(FIXTURE_DIR.glob("*.json")):
            if path.name.startswith("malformed_"):
                continue

            raw = json.loads(path.read_text(encoding="utf-8"))
            finding = normalize_finding(raw)

            # deterministic fingerprint re-compute
            self.assertEqual(finding["fingerprint"], compute_fingerprint(finding))

            # schema-level baseline validation
            self.assertEqual([], list(validate_finding(finding)), path.name)

    def test_malformed_fixture_missing_rule_raises(self):
        raw = json.loads((FIXTURE_DIR / "malformed_missing_rule.json").read_text(encoding="utf-8"))
        with self.assertRaises(KeyError):
            normalize_finding(raw)

    def test_malformed_fixture_bad_line_fails_validation(self):
        raw = json.loads((FIXTURE_DIR / "malformed_bad_line.json").read_text(encoding="utf-8"))
        finding = normalize_finding(raw)
        self.assertIn("lineStart<1", list(validate_finding(finding)))

    def test_whitespace_normalization_is_deterministic(self):
        a = {
            "source": "github_review",
            "repo": "mendyraul/reviewpulse",
            "prNumber": 12,
            "path": "src/app.py",
            "lineStart": 10,
            "lineEnd": 10,
            "ruleId": "STYLE.WS",
            "severity": "LOW",
            "message": "  Use   explicit   return   type   hints ",
        }
        b = dict(a)
        b["message"] = "Use explicit return type hints"

        na = normalize_finding(a)
        nb = normalize_finding(b)

        self.assertEqual(na["message"], nb["message"])
        self.assertEqual(na["fingerprint"], nb["fingerprint"])


if __name__ == "__main__":
    unittest.main()
