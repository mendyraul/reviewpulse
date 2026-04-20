# Owner Routing Visibility + Done-State UX (Slice C)

## Goal
Make assignment responsibility and closure state obvious so leads can answer in seconds:
1. Who owns this finding now?
2. Is it acknowledged/in progress or stalled?
3. Is it inside SLA or stale/overdue?
4. Is it fully done (archived) vs only resolved?

## Primary UI Surfaces

### 1) Active Findings row (compact)
Each row includes a compact routing cluster:
- **Owner pill**: avatar + handle (`@owner`) or explicit `Unassigned`
- **Status pill**: `Unassigned | Assigned | Acknowledged | In Progress | Resolved | Closed`
- **SLA chip**: `Due in 2h 14m` / `Overdue by 36m`
- **Escalation badge**: hidden unless active (`Escalated: Lead`, `Escalated: Security`)
- **Stale badge**: visible when no assignment activity crosses stale threshold (`Stale 18h`)

### 2) Routing details panel (expanded)
Structured ownership block:
- Current owner + team
- Assignment timestamp
- Acknowledgement timestamp (or pending)
- SLA due timestamp + policy source
- Escalation target + reason
- Last routing actor (`who changed what, when`)

### 3) Activity timeline drawer
Timeline entries for:
- Assignment/reassignment
- Acknowledge/unacknowledge
- Escalate/de-escalate
- Status transitions through completion (`Resolved -> Closed`)
- Archive/unarchive actions

Each entry includes actor, previous->next value, UTC timestamp, and optional reason note.

## Status Model

### Canonical statuses
1. **Unassigned**
2. **Assigned**
3. **Acknowledged**
4. **In Progress**
5. **Resolved** (work done, pending verification)
6. **Closed** (verified complete)

### Done-state + archive behavior
- `Resolved` remains visible in active board until verified/closed.
- `Closed` moves to done-state presentation (collapsed by default in active board).
- `Closed` findings are archived after retention window (default 14 days) but remain queryable in archive view.
- Unarchive action is allowed only for leads and reopens item as `In Progress`.

### Derived flags (non-canonical)
- `isOverdue`: now > SLA dueAt and status not terminal.
- `isStale`: no owner/status activity for stale threshold (default 8h for high+).
- `isEscalated`: active escalation target present.
- `isAwaitingAck`: status `Assigned` with no `acknowledgedAt`.

## Transition Rules

Allowed forward transitions:
- `Unassigned -> Assigned`
- `Assigned -> Acknowledged`
- `Acknowledged -> In Progress`
- `In Progress -> Resolved`
- `Resolved -> Closed`

Reopen/fallback transitions:
- `Resolved -> In Progress` (verification failed)
- `Closed -> In Progress` (regression/new evidence)
- `Assigned -> Unassigned` (owner removed)
- `Acknowledged -> Assigned` (ack revoked)

Blocked transitions (UI/API must reject):
- `Unassigned -> In Progress`
- `Assigned -> Closed`
- `Closed -> Assigned` (must reopen to `In Progress` first)

## Ownership + SLA Highlighting Rules

### Unassigned emphasis
- Unassigned findings always show danger-border row treatment for critical/high severity.
- `Unassigned` chip includes age suffix (`Unassigned 3h 21m`).
- Queue default sort surfaces unassigned first within same severity.

### Stale emphasis
- Stale threshold defaults:
  - Critical/high: 8h without activity
  - Medium: 24h
  - Low/info: 72h
- Stale rows show amber-to-red badge progression by breach duration.

### Escalation triggers
- Manual escalation by lead.
- Automatic escalation if overdue by policy threshold.
- Escalation creates timeline event and badges row/panel.

## Role Permissions

### Lead
Can modify assignment, all status transitions, escalation, SLA overrides, archive/unarchive.

### Contributor
Can acknowledge and update progress only on findings they own (`Assigned -> Acknowledged -> In Progress -> Resolved`).
Cannot reassign or archive.

## UI-Facing Contract (Routing Extension)

```json
{
  "findingId": "F-123",
  "owner": { "id": "u_17", "handle": "@alex" },
  "status": "Assigned",
  "assignedAt": "2026-04-12T01:20:00Z",
  "acknowledgedAt": null,
  "sla": {
    "dueAt": "2026-04-12T03:20:00Z",
    "isOverdue": false,
    "isStale": false,
    "staleThresholdHours": 8,
    "policy": "sev2_default_2h"
  },
  "escalation": {
    "active": false,
    "target": null,
    "reason": null,
    "startedAt": null
  },
  "doneState": {
    "isClosed": false,
    "archived": false,
    "archivedAt": null,
    "archiveAfterDays": 14
  },
  "auditSummary": {
    "lastChangedAt": "2026-04-12T01:20:00Z",
    "lastChangedBy": "@lead"
  }
}
```

## Acceptance Checklist
- [x] Owner assignment + escalation visibility specified for compact and expanded views.
- [x] Unassigned/stale indicators and SLA highlighting rules documented.
- [x] Done-state/archival behavior defined with reopen path.
- [x] Activity timeline requirements specified.
- [x] Role permissions and transition guardrails documented.
