# Active Findings Board UX Spec

Parent: Epic #4  
Slice: #17

## Goal
Give developers/leads a deterministic, keyboard-friendly board to triage active findings quickly.

## Information Architecture

### Global header
- **Title:** `Active Findings`
- **Context chip:** repo or org scope (`reviewpulse`, `all repos`)
- **Last refresh timestamp:** ISO string in UTC
- **Actions:** `Refresh`, `Export CSV`

### Left rail: Filters
- **Severity:** `critical`, `high`, `medium`, `low`
- **Status:** `new`, `acknowledged`, `in_progress`, `blocked`
- **Owner:** `unassigned` + known owners
- **Source:** `coderabbit`, `custom-lint`, `manual`
- **Repo selector** (single-select for MVP)
- **Reset filters** button

### Top row controls
- **Search input:** by PR number, file path, rule id, owner
- **Sort:**
  - `risk_desc` (default)
  - `updated_desc`
  - `sla_asc`
- **Group by:** `none` (default), `owner`, `severity`, `repo`

### Main content area
- Findings list rendered as cards with deterministic order from sort/group rules.
- Pagination: 25 items per page (cursor-based).

## Card Contract (UI)
Each finding card must render:
- `findingId`
- `title`
- `severity`
- `riskScore` (0-100)
- `repo`
- `prNumber`
- `filePath`
- `owner` (or `Unassigned`)
- `status`
- `updatedAt` (UTC)
- `slaDeadline` + countdown badge
- `topEvidence` (single-line snippet)
- `actions`: `Open PR`, `Acknowledge`, `Assign`

## Deterministic Mock Payload Schema

```json
{
  "meta": {
    "generatedAt": "2026-04-12T00:00:00Z",
    "cursor": "opaque-next-cursor",
    "pageSize": 25,
    "total": 128
  },
  "filters": {
    "severity": ["high", "critical"],
    "status": ["new", "acknowledged"],
    "owner": ["unassigned"],
    "repo": "mendyraul/reviewpulse",
    "source": ["coderabbit"],
    "query": "auth middleware"
  },
  "sort": "risk_desc",
  "groupBy": "owner",
  "findings": [
    {
      "findingId": "FND-2026-0001",
      "title": "Missing auth check in route handler",
      "severity": "high",
      "riskScore": 88,
      "repo": "mendyraul/reviewpulse",
      "prNumber": 11,
      "filePath": "src/server.py",
      "owner": null,
      "status": "new",
      "updatedAt": "2026-04-12T00:00:00Z",
      "slaDeadline": "2026-04-12T12:00:00Z",
      "topEvidence": "handler returns 200 before auth guard",
      "source": "coderabbit"
    }
  ]
}
```

### Backend/Frontend Alignment Rules
- `riskScore` is integer 0..100.
- `severity` is enum: `critical|high|medium|low`.
- `status` is enum: `new|acknowledged|in_progress|blocked|resolved`.
- `owner: null` must render as `Unassigned`.
- All timestamps are UTC ISO-8601.

## Interaction Flows

### 1) Triage new finding
1. User lands on default sort `risk_desc`.
2. User opens top card details drawer.
3. User clicks `Acknowledge`.
4. Status updates to `acknowledged` and activity toast appears.

### 2) Assign owner
1. User filters `owner=unassigned`.
2. User clicks `Assign` on a card.
3. Owner picker appears; selection persists.
4. Card moves if grouped by owner.

### 3) Deep-link to code context
1. User clicks `Open PR` from card.
2. New tab opens exact PR anchor (file + line when available).

## UI States

### Loading
- Skeleton cards (5 placeholders)
- Disabled filter controls
- Header shows `Refreshing…`

### Empty
- Message: `No active findings match current filters.`
- CTA: `Reset filters`

### Populated
- Cards + pagination + active filter chips

### Error
- Inline alert: `Could not load findings.`
- CTA: `Retry`
- Preserve prior filter selections

## Accessibility + Keyboard Checklist
- [ ] Tab order: header -> filters -> search/sort/group -> cards -> pagination
- [ ] All buttons/inputs have visible focus state
- [ ] Severity badges include text (not color-only encoding)
- [ ] Card actions are reachable with keyboard only
- [ ] `Enter` opens details drawer; `Esc` closes drawer
- [ ] Screen reader labels for SLA countdown and risk score
- [ ] Error/empty/loading states announced with aria-live region

## Acceptance Checklist
- [ ] `docs/ux/active-findings-board.md` committed
- [ ] Mock payload schema documented and deterministic
- [ ] Empty/loading/populated/error states defined
- [ ] Accessibility + keyboard navigation checklist included
