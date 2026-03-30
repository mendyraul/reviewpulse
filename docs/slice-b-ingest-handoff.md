# Slice B/C Handoff: Ingest Adapter Implementation Notes

This handoff is the bridge from **Slice A (schema + fixtures)** to adapter work.

## What is now stable (do not change casually)

- Canonical schema: `schema/finding.schema.json`
- Deterministic normalization + fingerprinting: `src/normalize.py`
- Golden fixtures for GitHub + CodeRabbit + malformed edge cases: `fixtures/*.json`
- Baseline determinism/validation tests: `tests/test_normalize.py`

## Adapter contract (required output)

Each ingest adapter must emit a dict that can be passed directly to:

```python
normalize_finding(raw)
```

Minimum fields expected before normalization:

- `source`
- `repo`
- `prNumber`
- `path`
- `lineStart`
- `lineEnd` (optional; defaults to `lineStart` in normalization path)
- `ruleId`
- `severity`
- `message`

## Slice B: GitHub review comment adapter

Input targets:

- Pull request review comments
- Inline and threaded comments
- Suggested-change comments

Rules:

1. Map GitHub identifiers to canonical `repo` + `prNumber`.
2. Resolve `path` and line range robustly for both single-line and range comments.
3. Derive `ruleId` from machine-readable markers first; otherwise fallback to stable synthetic rule keys.
4. Preserve user-visible message text (only normalization should trim/collapse whitespace).

## Slice C: CodeRabbit adapter

Input targets:

- CodeRabbit review findings/comments from webhook payloads or API exports.

Rules:

1. Use CodeRabbit rule/check identifiers when available for `ruleId`.
2. Normalize severity into: `critical/high/medium/low/info`.
3. Preserve original path/line anchors if valid; otherwise produce explicit malformed-case fixtures.

## Test strategy for adapter slices

- Add adapter-specific fixtures under `fixtures/github_*` and `fixtures/coderabbit_*`.
- Extend tests to assert:
  - adapter output passes `validate_finding`
  - repeated runs produce identical fingerprints
  - malformed source payloads fail loudly with predictable errors

## Guardrails

- Do not change fingerprint formula without adding migration/versioning notes.
- Keep adapter logic separate from canonical normalization logic.
- Any schema changes must update:
  - `schema/finding.schema.json`
  - `docs/finding-schema.md`
  - fixture set + tests
