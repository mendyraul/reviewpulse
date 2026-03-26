# ReviewPulse — CTO Roadmap (Start → Scale)

## Product vision
ReviewPulse turns messy PR review threads (human + bot) into a deterministic fix pipeline that shortens merge time without sacrificing code quality.

## End users
1. **IC developer** — wants clear "what to fix next".
2. **Tech lead** — wants PR risk visibility and merge predictability.
3. **Engineering manager/founder** — wants trend metrics (time-to-green, recurring finding classes).

## Core value proposition
- Deterministic review intake
- De-duplicated actionable fix list
- Measurable review-to-merge loop

## Phase plan

### Phase 0 (Week 1): MVP foundation
- Ingest GitHub review comments + CodeRabbit findings
- Normalize to deterministic schema
- Deduplicate + severity ranking
- PR summary comment generator
- Basic metrics: open/resolved findings + time-to-green

### Phase 1 (Weeks 2–3): Reliability + operator workflow
- Replay-safe webhooks + idempotency
- Retry queue + dead-letter handling
- "Explain this finding" and "mark duplicate" controls
- Multi-PR dashboard for active repos

### Phase 2 (Weeks 4–6): Team features
- Team routing rules (owner by file/path)
- SLA alerts for stale findings
- Cross-repo weekly digest

### Phase 3 (Weeks 7–10): Monetizable platform
- Hosted onboarding flow
- Per-repo policies + org-level analytics
- Billing-ready plan gating (free/team)

## Success metrics
- P50 PR time-to-green reduced by 25%
- Duplicate finding noise reduced by 40%
- >70% of findings converted into tracked actions

## Tech architecture
- Ingest: GitHub webhooks + CodeRabbit events
- Core: normalization + reconciliation engine
- Storage: findings, clusters, lifecycle states
- Output: PR comments, API, dashboard
- Jobs: retries, reconciliation sweeps, metrics rollups

## Operating cadence (CTO mode)
- Daily: triage backlog, ship one visible improvement
- Weekly: release notes + user feedback synthesis
- Biweekly: architecture review + debt burn-down

## Side-project portfolio policy
- ReviewPulse is primary focus.
- Other repos continue through planned issue slices only; no random context switching.
- Allocate capacity: 70% ReviewPulse, 30% existing backlog (mission-control/openclaw-v2).

