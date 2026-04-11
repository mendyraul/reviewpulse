from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.adapters import adapt_coderabbit_finding, adapt_github_review_comment
from src.normalize import normalize_finding, validate_finding
from src.ranking import rank_findings
from src.reporting import calculate_baseline_metrics, render_pr_summary


def _load_payload(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _adapt_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = str(payload.get("source", "")).lower()

    # Already in FindingDraft/normalized-ish shape.
    if source in {"github_review", "coderabbit"} and "path" in payload and "prNumber" in payload:
        return payload

    # GitHub review webhook payload shape.
    if "pull_request" in payload and "repository" in payload and "body" in payload:
        return adapt_github_review_comment(payload)

    # CodeRabbit payload shape.
    if ("checkId" in payload or "lineStart" in payload or "line" in payload) and (
        "repo" in payload or "repository" in payload
    ):
        return adapt_coderabbit_finding(payload)

    raise ValueError("Unsupported payload shape")


def run_pipeline(input_files: Iterable[Path], output_dir: Path) -> Dict[str, Any]:
    files = list(input_files)
    output_dir.mkdir(parents=True, exist_ok=True)

    findings: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []

    for file in files:
        payload = _load_payload(file)
        try:
            adapted = _adapt_payload(payload)
            normalized = normalize_finding(adapted)
            errors = list(validate_finding(normalized))
            if errors:
                invalid.append({"file": str(file), "errors": errors})
                continue
            findings.append(normalized)
        except Exception as exc:  # noqa: BLE001 - keep deterministic report in one pass
            invalid.append({"file": str(file), "errors": [str(exc)]})

    ranked = rank_findings(findings)
    summary = render_pr_summary(ranked)
    metrics = calculate_baseline_metrics(ranked)

    (output_dir / "ranked-findings.json").write_text(json.dumps(ranked, indent=2) + "\n", encoding="utf-8")
    (output_dir / "pr-summary.md").write_text(summary, encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (output_dir / "invalid-findings.json").write_text(json.dumps(invalid, indent=2) + "\n", encoding="utf-8")

    return {
        "totalInput": len(files),
        "normalized": len(findings),
        "invalid": len(invalid),
        "clusters": len(ranked),
        "outputDir": str(output_dir),
    }


def _collect_inputs(args: argparse.Namespace) -> List[Path]:
    if args.inputs:
        return [Path(item) for item in args.inputs]

    fixture_dir = Path(args.fixtures_dir)
    return sorted(fixture_dir.glob("*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ReviewPulse deterministic intake->reconcile->summary pipeline")
    parser.add_argument("inputs", nargs="*", help="JSON payload files. If omitted, all fixtures/*.json are used.")
    parser.add_argument("--fixtures-dir", default="fixtures", help="Fixture directory when inputs are omitted")
    parser.add_argument("--output-dir", default="artifacts/pipeline-run", help="Where pipeline artifacts are written")

    args = parser.parse_args()
    inputs = _collect_inputs(args)

    report = run_pipeline(inputs, Path(args.output_dir))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
