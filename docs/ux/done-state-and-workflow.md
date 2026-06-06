# Done-State UX + Workflow Completion Model

Issue: #20 (Parent: #4)

## 1) Goal
Define a deterministic “clear done” experience so users know when work is complete, what was completed, and what (if anything) still needs attention.

This state should remove ambiguity at handoff time and keep confidence high when transitioning from active review to archive.

---

## 2) Workflow Stages (Canonical)

Use one shared workflow model across dashboard surfaces:

1. **Active Findings**
   - Findings currently open and requiring owner action.
   - Action-heavy view.
2. **Resolved**
   - Findings marked fixed/accepted and waiting for final verification window (if configured).
   - Validation-focused view.
3. **Archived**
   - Findings that passed completion criteria and are no longer part of active throughput metrics.
   - Historical/audit view.

### Stage transition rules
- `Active -> Resolved`
  - Requires explicit owner action (`mark_resolved`) with timestamp + actor.
- `Resolved -> Archived`
  - Requires completion criteria pass (see section 3).
- `Resolved -> Active`
  - Allowed if regression/reopen signal arrives.
- `Archived -> Active`
  - Allowed for rare reopen cases with reason code (`regression`, `false_done`, `new_evidence`).

---

## 3) Done-State Criteria

A workflow item is “done” when all criteria are true:

- **No open blocking findings** in current scope.
- **Completion confidence score >= threshold** (default 0.90).
- **No pending owner assignment gaps** for current sprint window.
- **No stale unresolved findings** older than SLA for critical/high severity.

### Completion confidence (deterministic inputs)
`completion_confidence` should be computed from:
- closure ratio by severity (weighted),
- unresolved stale count penalty,
- recent reopen count penalty,
- owner acknowledgement coverage.

Output is a normalized float `0.00..1.00` with fixed rounding to 2 decimals in UI.

---

## 4) Done-State Messaging UX

When criteria pass, show a prominent success panel:

- **Title:** `Workflow complete`
- **Primary message:** `All required findings are resolved and archived for this scope.`
- **Subtext:** `Confidence: {completion_confidence} • Last verified {timestamp}`
- **Actions:**
  - `View archived findings`
  - `Export completion summary`
  - `Start new review cycle`

When criteria do not pass, show exact blockers with deterministic reason codes.

---

## 5) KPI Widget Set (Completion + Throughput)

Done-state view should include these top widgets:

1. **Completion Confidence**
   - Numeric badge + trend sparkline.
2. **Cycle Throughput**
   - Findings closed in selected time window.
3. **Reopen Rate**
   - `% reopened after resolve` (lower is better).
4. **SLA Compliance**
   - `% findings resolved within SLA by severity`.
5. **Owner Coverage**
   - `% findings with assigned and acknowledged owner`.

All KPI widgets must share the same date-range filter and timezone basis.

---

## 6) Empty/No-Data Behavior

### Empty state: no findings yet
- Message: `No findings yet. Start a review run to populate this dashboard.`
- CTA: `Run intake`

### Empty resolved/archived state
- Message: `No resolved findings in this range.`
- CTA: `Expand date range`

### API unavailable/error state
- Message: `We couldn't load completion state right now.`
- Include retry action and trace id.

---

## 7) Success/Failure Visual States

### Success visual state
- Green completion badge + check icon.
- Timeline marker shows latest transition `Resolved -> Archived`.
- KPI cards rendered with normal emphasis.

### Failure/blocked visual state
- Amber/red status pill based on blocker severity.
- Blocker list rendered with reason code chips:
  - `OPEN_BLOCKING_FINDINGS`
  - `LOW_CONFIDENCE`
  - `STALE_CRITICAL_FINDINGS`
  - `OWNER_GAP`
- Primary CTA routes user to exact filtered active list.

---

## 8) API/Contract Expectations (No Regression)

No new API endpoints required for this UX slice.

Expected payload fields (existing + additive-compatible):
- `workflow_stage`
- `completion_confidence`
- `open_blocking_count`
- `stale_critical_count`
- `owner_coverage_ratio`
- `reopen_rate`
- `last_verified_at`
- `blockers[]` (with reason codes)

If a field is unavailable, UI must degrade gracefully with `N/A` and maintain layout stability.

---

## 9) QA Checklist

- [ ] Stage transitions render correctly for Active/Resolved/Archived.
- [ ] Done-state panel appears only when all criteria pass.
- [ ] Blocked state lists deterministic reason codes.
- [ ] KPI cards remain stable across empty and error states.
- [ ] Date filter/timezone are applied consistently across all metrics.
- [ ] Reopen transitions correctly move archived/resolved items back to active.
- [ ] No regression in existing API calls (same endpoints continue to work).
- [ ] Keyboard navigation reaches completion panel actions + blocker links.

---

## 10) Suggested Acceptance Test Scenarios

1. **Happy path**: all findings resolved -> archived, confidence >= 0.90, done-state panel visible.
2. **Low confidence**: all findings resolved but high reopen penalty -> blocked with `LOW_CONFIDENCE`.
3. **Critical stale**: one unresolved critical over SLA -> blocked with `STALE_CRITICAL_FINDINGS`.
4. **Owner gap**: unresolved owner coverage < threshold -> blocked with `OWNER_GAP`.
5. **No data**: fresh workspace shows onboarding empty state and no crashes.
6. **API error**: simulated backend failure shows retry+trace without breaking routing/navigation.
