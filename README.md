# reviewpulse
Open-source PR review-to-fix loop automation for GitHub + CodeRabbit

## Quickstart (one-command MVP flow)
Run deterministic intake -> normalize -> dedupe/rank -> PR summary artifact generation:

```bash
python3 -m src.pipeline
```

Artifacts are written to `artifacts/pipeline-run/`:
- `ranked-findings.json`
- `pr-summary.md`
- `metrics.json`
- `invalid-findings.json`

You can also pass explicit payload files and custom output path:

```bash
python3 -m src.pipeline fixtures/adapter_github_review_payload.json fixtures/adapter_coderabbit_payload.json --output-dir /tmp/reviewpulse-run
```

## Current foundation docs
- `docs/finding-schema.md` — canonical deterministic finding schema and fingerprint formula
- `docs/slice-b-ingest-handoff.md` — handoff contract for next ingest adapter slices
- `docs/pr-summary-contract.md` — deterministic PR summary + baseline metrics contract
