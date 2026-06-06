# Owner Routing Visibility UX + Status Model

Parent epic: #4  
Slice: #19

## Purpose
Give leads clear, actionable visibility into finding ownership so nothing stalls silently.

## Owner Routing Panel (Finding Detail)
The owner-routing section should appear near finding metadata and include:

- **Owner**
  - Current owner avatar + name
  - Team/role badge (optional)
- **Routing status**
  - Current status pill (see taxonomy below)
  - Last updated timestamp
- **SLA timer**
  - Relative countdown/count-up based on policy target
  - Color states: neutral (on track), warning (near SLA), critical (breach)
- **Escalation indicator**
  - Not escalated / escalated level + trigger reason
  - Link to escalation event in audit trail
- **Acknowledgement state**
  - Explicit "Acknowledged" indicator with actor + timestamp

## Status Taxonomy
Required statuses for routing lifecycle:

1. **unassigned**
   - No owner exists yet.
2. **assigned_pending_ack**
   - Owner assigned, waiting for acknowledgement.
3. **acknowledged**
   - Owner acknowledged responsibility.
4. **in_progress**
   - Owner started active work.
5. **resolved_pending_verification**
   - Owner marked fix complete; waiting verification/review.
6. **closed**
   - Finding is completed and accepted.
7. **escalated**
   - SLA/risk escalation is active (overlay state that can coexist with primary workflow state).

## Transition Rules
### Allowed primary transitions
- `unassigned -> assigned_pending_ack`
- `assigned_pending_ack -> acknowledged`
- `assigned_pending_ack -> in_progress` (implicit acknowledgement)
- `acknowledged -> in_progress`
- `in_progress -> resolved_pending_verification`
- `resolved_pending_verification -> closed`
- `resolved_pending_verification -> in_progress` (reopen on failed verification)
- `in_progress -> assigned_pending_ack` (reassignment resets acknowledgement)
- `acknowledged -> assigned_pending_ack` (reassignment)

### Escalation overlay transitions
- Any non-closed primary state can move to `escalated` when SLA/risk triggers hit.
- Escalation clears only when:
  - lead explicitly de-escalates, or
  - finding enters `closed`.

### Guardrails
- `closed` is terminal unless lead reopens finding (reopen returns to `in_progress`).
- Every reassignment must reset acknowledgement and SLA anchor.
- System-generated transitions (SLA escalation) must be clearly tagged as automated.

## Interaction Model
### Reassign owner
- Lead opens owner selector from routing panel.
- Confirm dialog includes:
  - previous owner
  - new owner
  - optional reason
  - warning that acknowledgement + SLA anchor reset
- On confirm:
  - status -> `assigned_pending_ack`
  - audit event recorded
  - new owner notified

### Acknowledge finding
- Owner clicks **Acknowledge** from panel/list row.
- Immediate transition: `assigned_pending_ack -> acknowledged`
- Timestamp and actor captured.

### Start work
- Owner clicks **Start work** (or first update implicitly starts).
- Transition to `in_progress`.

### Mark resolved
- Owner marks finding as resolved.
- Transition to `resolved_pending_verification`.
- Verification owner/reviewer receives notification.

## Audit Trail Visibility Requirements
Show routing history in an always-available timeline section:

Each event includes:
- event type (assigned, acknowledged, reassigned, escalated, de-escalated, resolved, reopened)
- actor (user/system)
- from/to status
- from/to owner (when relevant)
- reason/note (optional but encouraged)
- timestamp

Filtering:
- Toggle: all events / routing-only / escalation-only.

Integrity requirements:
- Audit entries are append-only.
- System events are visually distinct from human actions.

## Role-Based Visibility
### Lead
Can:
- view all routing fields and full audit trail
- reassign owner
- de-escalate/escalate manually
- reopen closed findings

### Contributor (non-lead)
Can:
- view owner, current status, SLA state, escalation state
- acknowledge/start/resolve only if they are current owner
- view audit trail (read-only, no manual escalation controls)

## List View Requirements
In findings table/list, include compact routing columns:
- Owner
- Status
- SLA state (countdown + color)
- Escalation badge

Rows in `assigned_pending_ack` or `escalated` should be visually emphasized for lead triage.

## Acceptance Checklist
- [x] Owner routing panel defined (owner/status/SLA/escalation/ack).
- [x] Status taxonomy documented.
- [x] Transition rules + guardrails documented.
- [x] Reassign + acknowledge interactions specified.
- [x] Audit trail visibility requirements defined.
- [x] Lead vs contributor visibility defined.
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
