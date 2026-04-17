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
