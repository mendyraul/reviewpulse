# PR Risk Summary UX Spec

Parent issue: #4  
Slice: #18

## Goal
Enable rapid merge decisions by presenting a deterministic, at-a-glance risk summary with clear drill-down into findings.

## Panel layout

### Header row
- **Title:** `PR Risk Summary`
- **Last updated:** relative timestamp + absolute on hover
- **Actions:**
  - `Recompute` (manual refresh)
  - `View all findings` (deep link to findings list)

### Core summary grid
1. **Risk score card**
   - Numeric score (0–100)
   - Badge (`Low`, `Medium`, `High`)
   - One-line rationale (“High due to auth + schema changes”).
2. **Top risks card**
   - Up to 3 highest-severity findings
   - Each row: short label + severity chip + affected area
3. **Confidence card**
   - Confidence percent (0–100)
   - Confidence band (`Low confidence`, `Moderate confidence`, `High confidence`)
   - Tooltip with causes of low confidence (missing tests, partial diff, stale analysis)
4. **Change footprint card**
   - Files changed
   - Net lines changed (+/-)
   - Critical surface count (auth, payments, migrations, infra, security)

### Footer row
- **Decision hint copy:**
  - Low: “Safe to merge with standard review.”
  - Medium: “Needs focused reviewer attention on flagged areas.”
  - High: “Requires senior review and explicit sign-off before merge.”

---

## Severity visualization rules (deterministic)

### Score to badge mapping
- **Low risk:** `0–34`
- **Medium risk:** `35–69`
- **High risk:** `70–100`

### Badge styling
- **Low:** green (`success` tone)
- **Medium:** amber (`warning` tone)
- **High:** red (`danger` tone)
- Always pair color with text label for accessibility.

### Finding severity chips
- `Critical`, `High`, `Medium`, `Low`, `Info`
- Ordered display by severity then confidence desc.

### Deterministic tie-breakers
If two findings have same severity:
1. Higher confidence first
2. Larger affected footprint first
3. Stable sort by finding id

---

## Drill-down behavior

### From score badge
- Clicking risk score opens filtered findings drawer:
  - `Low` => low+info findings
  - `Medium` => medium+high+critical
  - `High` => high+critical

### From top-risks rows
- Clicking a row opens finding detail panel with:
  - Summary
  - Evidence snippets
  - Affected files/functions
  - Suggested mitigations
  - Link to code locations/diff anchors

### URL + navigation state contract
- Summary panel deep link: `?panel=pr-risk`
- Finding detail deep link: `?panel=pr-risk&finding=<findingId>`
- Severity filter state: `?panel=pr-risk&severity=high|medium|low`
- Browser back must return to prior scroll position in the summary panel.

### From change footprint
- Clicking critical surface count filters findings by surface area (e.g., auth/migrations).

---

## Component states

### 1) No findings
- Show neutral card state:
  - Headline: `No actionable risks found`
  - Subcopy: `Current analysis did not detect merge-blocking concerns.`
  - Keep footprint visible so reviewer still sees scope.

### 2) Stale data
- Trigger condition: analysis timestamp older than configured freshness window.
- UI behavior:
  - Banner: `Risk analysis may be outdated.`
  - Primary CTA: `Recompute now`
  - Score card muted until refresh completes.

### 3) Recompute in progress
- Show loading skeleton in all cards.
- Keep previous score visible with stale pill: `Updating…`
- Disable repeated recompute clicks until current run completes.

---

## Copy set (final)

### Badges
- `Low risk`
- `Medium risk`
- `High risk`

### Confidence labels
- `Low confidence`
- `Moderate confidence`
- `High confidence`

### Empty/stale/loading messages
- Empty: `No actionable risks found`
- Stale: `Risk analysis may be outdated`
- Loading: `Recomputing risk summary…`

---

## Threshold rubric

### Low risk (0–34)
Typical profile:
- Cosmetic/UI changes
- Minor refactors
- Strong test coverage
- No critical surfaces changed

### Medium risk (35–69)
Typical profile:
- Multi-file feature changes
- Partial test coverage or mixed confidence
- Touches one critical surface without severe finding

### High risk (70–100)
Typical profile:
- Schema/auth/security or infra-sensitive changes
- Multiple high/critical findings
- Low confidence + broad footprint

---

## Accessibility + responsiveness notes
- Never rely on color-only severity communication.
- Badge/chip labels must be screen-reader friendly.
- On mobile, cards stack in this order: score → top risks → confidence → footprint.
- Keep top-risk list capped at 3 on mobile with `View all findings` CTA.
