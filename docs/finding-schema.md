# Deterministic Finding Schema (Slice A)

Canonical normalized finding fields:

- `source`: `github_review` | `coderabbit`
- `repo`: owner/repo string
- `prNumber`: integer PR number
- `path`: file path in the PR diff
- `lineStart` / `lineEnd`: normalized inclusive range
- `ruleId`: stable rule key from source signal
- `severity`: critical/high/medium/low/info
- `message`: normalized finding text
- `fingerprint`: deterministic SHA-256 key (hex)
- `firstSeenAt` / `lastSeenAt`: RFC3339 timestamps
- `metadata`: optional source extras

## Fingerprint formula

Fingerprint is SHA-256 over this exact pipe-delimited normalized payload:

`source|repo|prNumber|path|lineStart|lineEnd|ruleId|severity|message_normalized`

Normalization rules:

1. Trim leading/trailing whitespace on message
2. Collapse internal whitespace runs to a single space
3. Lowercase `source`, `severity`, and `ruleId`
4. Keep `repo`, `path`, and `message` casing as-is after whitespace normalization

## Stability guarantee

Given the same semantic finding input after normalization, output fingerprint remains identical across runs.
