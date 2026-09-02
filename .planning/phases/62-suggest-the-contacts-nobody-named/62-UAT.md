---
status: partial
phase: 62-suggest-the-contacts-nobody-named
source: [62-VERIFICATION.md]
started: 2026-09-02T01:30:00Z
updated: 2026-09-02T02:10:00Z
---

## Current Test

[testing paused — 3 items outstanding]

## Tests

### 1. A real company's sitemap yields a usable people page on a live racing-club-shaped site
expected: The sitemap-ladder rung resolves a people/board/team page and names at least one person, mirroring UAT 2.4's precedent (9/9 directors on gctc.com.au)
why_human: `url_fallback.py` is pure string-building with no I/O by construction (62-VALIDATION.md manual-verification row 1) — the unit suite proves the ladder logic and the host-bound guard, never whether a given site's sitemap actually lists a people page. Requires a live plugin sitting with a real `web_fetch`.
result: blocked
blocked_by: other
reason: "defer live UATs - I can't run a live test at this point"

### 2. Stage 1 → stage 2 handoff on a real discovered person (name+company → Lusha search-and-enrich → proposal)
expected: A person named by the ladder with no email resolves through identity group 2, the waterfall fills email/phone, and the row lands as a proposal (or HELD if still emailless) — never a silent write
why_human: Requires a real page fetch (plugin-side `web_fetch`) followed by a real Lusha credit spend; neither runs in the stub-transport test suite (62-VALIDATION.md manual-verification row 2).
result: blocked
blocked_by: third-party
reason: "defer live UATs - I can't run a live test at this point (needs a real Lusha credit spend)"

### 3. The priced ceiling is not exceeded in a real sitting
expected: Actual page fetches and provider credits spent land at or under the quoted worst-case ceiling shown at grant-open; a bad or omitted per-company cap does not silently blow the ceiling
why_human: The ceiling arithmetic and the cap-refusal guard (`agreed_cap` / `synthesise_rows`) are both now unit- and live-probe-tested outside the test suite, but "the operator saw a number and the round stayed under it in a real sitting" is an end-to-end property only a live sitting can demonstrate (62-VALIDATION.md manual-verification row 3). This item is also the acceptance test for the 62-06 cap fix.
result: blocked
blocked_by: third-party
reason: "defer live UATs - I can't run a live test at this point (needs a real Lusha credit spend)"

## Summary

total: 3
passed: 0
issues: 0
pending: 0
skipped: 0
blocked: 3

## Gaps

[none — all three items are blocked on a live attended sitting, not failing. Blocked tests are prerequisite gates, not code issues, so they produce no gap entries and no fix plans.]
