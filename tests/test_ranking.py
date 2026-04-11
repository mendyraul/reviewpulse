import unittest

from src.ranking import rank_findings


class TestRanking(unittest.TestCase):
    def test_dedupes_same_line_and_cross_source_duplicates(self):
        findings = [
            {
                "source": "github_review",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 12,
                "path": "src/app.py",
                "lineStart": 10,
                "lineEnd": 10,
                "ruleId": "security.sql-injection",
                "severity": "high",
                "message": "Unsanitized query input",
                "fingerprint": "gh-1",
                "sourceFindingId": "gh-comment-100",
            },
            {
                "source": "coderabbit",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 12,
                "path": "src/app.py",
                "lineStart": 10,
                "lineEnd": 10,
                "ruleId": "security.sql-injection",
                "severity": "high",
                "message": "Unsanitized query input",
                "fingerprint": "cr-1",
                "sourceFindingId": "cr-200",
            },
            {
                "source": "github_review",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 12,
                "path": "src/app.py",
                "lineStart": 10,
                "lineEnd": 10,
                "ruleId": "security.sql-injection",
                "severity": "high",
                "message": "Unsanitized query input",
                "fingerprint": "gh-2",
                "sourceFindingId": "gh-comment-101",
            },
        ]

        ranked = rank_findings(findings)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["count"], 3)
        self.assertEqual(ranked[0]["sources"], ["coderabbit", "github_review"])
        self.assertEqual(
            ranked[0]["sourceFindingIds"],
            ["cr-200", "gh-comment-100", "gh-comment-101"],
        )

    def test_near_duplicates_stay_separate(self):
        findings = [
            {
                "source": "github_review",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 18,
                "path": "src/job.py",
                "lineStart": 42,
                "lineEnd": 42,
                "ruleId": "perf.n-plus-one",
                "severity": "medium",
                "message": "N+1 query in loop",
            },
            {
                "source": "coderabbit",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 18,
                "path": "src/job.py",
                "lineStart": 42,
                "lineEnd": 42,
                "ruleId": "perf.n-plus-one",
                "severity": "medium",
                "message": "N+1 query in nested loop",
            },
        ]

        ranked = rank_findings(findings)
        self.assertEqual(len(ranked), 2)

    def test_deterministic_ordering_with_tie_breakers(self):
        findings = [
            {
                "source": "github_review",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 1,
                "path": "src/z.py",
                "lineStart": 9,
                "lineEnd": 9,
                "ruleId": "style.trailing-space",
                "severity": "high",
                "message": "Trailing whitespace",
            },
            {
                "source": "github_review",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 1,
                "path": "src/a.py",
                "lineStart": 3,
                "lineEnd": 3,
                "ruleId": "security.shell",
                "severity": "critical",
                "message": "Unsanitized shell execution",
            },
            {
                "source": "github_review",
                "repo": "mendyraul/reviewpulse",
                "prNumber": 1,
                "path": "src/a.py",
                "lineStart": 4,
                "lineEnd": 4,
                "ruleId": "security.path",
                "severity": "critical",
                "message": "Path traversal risk",
            },
        ]

        first = rank_findings(findings)
        second = rank_findings(list(reversed(findings)))

        self.assertEqual(first, second)
        self.assertEqual(first[0]["severity"], "critical")
        self.assertEqual(first[0]["path"], "src/a.py")
        self.assertEqual(first[0]["lineStart"], 3)
        self.assertEqual(first[1]["lineStart"], 4)
        self.assertEqual(first[2]["severity"], "high")


if __name__ == "__main__":
    unittest.main()
