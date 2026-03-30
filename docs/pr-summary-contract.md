# PR Summary Output Contract (Slice D)

`render_pr_summary(findings)` emits deterministic markdown for downstream posting.

## Fixed section order
1. `## ReviewPulse Summary`
2. `### Critical (N)`
3. `### High (N)`
4. `### Medium (N)`
5. `### Low (N)`
6. `### Next Actions`

## Determinism guarantees
- Findings are sorted by: severity rank, path, lineStart, ruleId, fingerprint.
- Section headings and bullet format are constant.
- Empty sections render as `- None`.

## Bullet line format
- ``- `path:start[-end]` [ruleId] message``

## Baseline metrics
`calculate_baseline_metrics(findings)` returns:
- `openFindings: int`
- `resolvedFindings: int`
- `timeToGreenHours: float | null`

`timeToGreenHours` remains `null` until all findings are resolved and enough timestamps exist (`firstSeenAt`, `resolvedAt`) to compute elapsed time.
