---
status: partial
phase: quick-tasks-2026-09-04 (260904-39r, 260904-447, 260904-5a8, 260904-5sd, 260904-pav)
source:
  - .planning/quick/260904-39r-role-vocabulary-derivation/260904-39r-SUMMARY.md
  - .planning/quick/260904-447-double-unescape-fix-in-role-vocabulary-n/260904-447-SUMMARY.md
  - .planning/quick/260904-5a8-laneof-domain-lane-vs-companies-appropri/260904-5a8-SUMMARY.md
  - .planning/quick/260904-5sd-sitemap-crawl-fallback-to-client-side-cl/260904-5sd-SUMMARY.md
  - .planning/quick/260904-pav-provenance-aware-manual-protected/260904-pav-SUMMARY.md
started: 2026-09-04T19:40:00Z
updated: 2026-09-04T19:40:00Z
---

<!-- On the two statuses for 260904-5sd. Its STATE.md row reads `Verified` and this file
     reads `partial`; both are correct and they measure different things. `Verified` is the
     gsd-verifier's verdict on the plan's must_haves (11/11, offline, against the codebase).
     `partial` is this UAT's verdict, which additionally wants test 8 — the fallback exercised
     on a real company — and nothing but an operator run can supply that. Do not reconcile
     these to one value. -->

## Current Test

number: 7
name: 260904-39r — role-vocabulary derivation, live `--dry-run` acceptance
expected: |
  `scripts/role_vocabulary.py --dry-run` completes against the real portal without
  raising, prints a drop-list and a `cp` adoption command, and writes only
  `role_vocabulary.derived.yaml` — never the shipped 17-family `role_vocabulary.yaml`.
awaiting: operator response

## Tests

<!-- Tests 1-6 were executed in-process by the orchestrator against the SHIPPED modules,
     not inferred from any SUMMARY. Commands and observed output are recorded inline so a
     later reader can re-run them. -->

### 1. 260904-447 — a double-encoded job title still classifies
expected: `classify_title` resolves `'Finance &amp;amp; Admin Officer'`, `'Finance &amp; Admin Officer'` and `'Finance & Admin Officer'` all to the same family, so a portal-stored double-encoded title is no longer silently missed
result: pass
observed: all three returned `Treasurer` (shipped `operator-claude-plugin/scripts/role_classify.py`, real `role_vocabulary.yaml`)

### 2. 260904-5a8 — a companies row reports a companies-shaped match reason
expected: the committed `Decide Company Action` node reaches `summarizeMatch`'s `lane === "company"` arm, whose reason names domain/name resolution, not the contacts "no searchable identity" sentence
result: pass
observed: call site in `n8n/wf_enrichment_cloud.json` is the literal `summarizeMatch({ lane: "company" })`; the arm returns `tier: "unknown"`, `auto: false`, reason `"company identity resolves upstream by domain, then exact company name — see this row's own hs_object_id/action for the outcome"`. The contacts sentence is still present in the file only because the whole `summarizeMatch` module is inlined; it is unreachable on this lane.

### 3. 260904-5sd — the ladder-disposition gate is fail-closed in every direction
expected: `empty` and `cap_exhausted` open the search path; any `refused` blocks it order-free; unknown/absent disposition, empty list and `None` are all ineligible without raising
result: pass
observed: 8/8 cases correct — `[empty]` True, `[cap_exhausted]` True, `[empty,refused]` False, `[refused,empty]` False, `[{'disposition':'wat'}]` False, entry with no `disposition` key False, `[]` False, `None` False. Zero exceptions. The refusal reason names the refused URL.

### 4. 260904-5sd — source ranking and the suffix trap, both directions
expected: rank 1 = the company's own host including real subdomains; rank 2 = LinkedIn; a host on no rank is REJECTED, not ranked last; `linkedin.com.attacker.tld` and `example.com.attacker.tld` both reject
result: pass
observed: `board.example.com` → rank 1, `au.linkedin.com` → rank 2; `linkedin.com.attacker.tld`, `example.com.attacker.tld` and `totally-unlisted-host.tld` all rejected with a reason naming the host

### 5. 260904-pav — provenance-aware `manual_protected` corrects only a system-written value
expected: a `create_seed`-provenance domain whose recorded value still equals the current value, on an unconflicted row, IS corrected; every other shape refuses
result: pass
observed: against the shipped `n8n/code/mergeCompanies.js` — system+match+no-conflict → `CORRECTED -> lions.com.au`; human source → REFUSED; stale entry (recorded not equal to current) → REFUSED; row conflicted → REFUSED

### 6. 260904-pav — the gate fails closed on missing inputs
expected: an omitted `rowConflicted` flag, and a record with no provenance blob at all, both refuse rather than defaulting to correctable
result: pass
observed: both REFUSED

### 7. 260904-39r — role-vocabulary derivation, live `--dry-run` acceptance
expected: `scripts/role_vocabulary.py --dry-run` completes against the real portal without raising, prints a drop-list and a `cp` adoption command, and writes only `role_vocabulary.derived.yaml`
result: [pending]
note: carried forward from 260904-39r's own STATE row, which recorded live operator acceptance as outstanding. Cannot be run by the orchestrator — needs the operator's portal session.

### 8. 260904-5sd — the search fallback on a real company with no findable staff page
expected: on a company whose sitemap ladder ends clean-but-empty, `suggest-contacts` offers search-sourced people; a rank-3 (industry-site) person is shown but HELD with its source URL quoted in the reason, and only own-host or LinkedIn people are offered as sendable
result: [pending]
note: the search and every fetch are model-invoked tools the module cannot call, so this is only exercisable by an actual `/operator-claude-plugin:suggest-contacts` run. Reaching a send also spends a Lusha credit at the promote gate.

## Summary

total: 8
passed: 6
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

<!-- none -->
