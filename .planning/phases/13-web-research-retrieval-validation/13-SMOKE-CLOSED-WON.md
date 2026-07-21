# Closed-Won Ground-Truth Smoke — 2026-07-21

**Run:** `scripts/smoke_closed_won_research.py --limit 10`, live (HubSpot read-only +
Anthropic web_search), operator-initiated post-verification. Exit 0.

**Premise:** closed-won customers must produce content (they bought the product), so any
researched `false` is a detected false-negative on the hard-veto field.

## Results

| Company | Domain | lv_produces_content | evidence URL |
|---|---|---|---|
| Australian Turf Club | australianturfclub.com.au | true | — |
| Redcliffe Harness RC | redcliffehrc.com.au | true | — |
| Rockhampton Jockey Club | callaghanpark.com.au | true | — |
| Wyong | www.wyongraceclub.com.au | true | — |
| Melbourne Racing Club | mrc.racing.com | true | — |
| Panasonic Studio Productions | www.pspvideo.com.au | true | — |
| Brisbane Racing Club (BRC) | brc.com.au | true | — |
| Racing and Wagering Western Australia | rwwa.com.au | true | — |
| Queensland Racing Integrity Commission | www.qric.qld.gov.au | true | — |
| GRAVITY MEDIA | www.gravitymedia.com | true | — |

**Summary: true=10 null=0 false=0 unmatched=0** (of 10 closed-won companies)

## Reading

- **Ground truth: 10/10.** Zero false negatives on the veto field, zero evidenced-false
  red flags (exit-2 path never fired), zero unmatched. The false-disqualification risk this
  smoke was built to detect did not materialize on any account.
- **Finding: `evidence_by_field.lv_produces_content` empty on all 10.** The model answers
  `true` but does not return a per-field evidence URL. Tri-state is unaffected (TS-2 only
  gates `false`), but downstream the evidence-gated promotion path
  (field policy `require_evidence_url: true` for `lv_produces_content`) will WITHHOLD these
  `true` values from canonical promotion. Net effect in a real run today: correct verdicts
  that stall in staging.
- **Action:** tighten the research prompt so `evidence_by_field` is populated per answered
  field (the contract already asks for it; the model is dropping it). Candidate home:
  Phase 14 (judge wiring touches the same prompt surface) or a small pre-14 fix. Re-run this
  smoke after — expect same `true` split WITH URLs.

## Cost note

10 companies, `WEB_RESEARCH_MAX_SEARCHES=5` cap each. No caching until Phase 15 — a re-run
re-spends.

## Re-run after fix — 2026-07-21

**Root cause of the empty-evidence finding above:** this smoke script was never actually
making live research calls. `scripts/smoke_closed_won_research.py` used
`os.environ.setdefault("USE_MOCK_WEB_RESEARCH", "false")` to force live mode, but the
documented run command sources `.env` first (`set -a && source .env && set +a`), which
exports `USE_MOCK_WEB_RESEARCH=true` into the process environment before Python starts.
`setdefault` never overrides an already-present key, so every "live" research call silently
returned the static `tests/fixtures/claude_web_research_company.json` fixture — identical
`lv_produces_content=true` for every company (the fixture never varies by input), and an
empty `evidence_by_field` for every company (the fixture predates the Phase 13
`evidence_by_field` field entirely). Fixed by assigning the env var directly
(`os.environ["USE_MOCK_WEB_RESEARCH"] = "false"`). A second, independently-confirmed bug was
also fixed while investigating: `max_tokens=2000` (both the Python dev oracle and the
parity n8n prompt) is too small for `claude-sonnet-5`'s extended thinking (~1000-1300
tokens) plus the full JSON payload, causing `stop_reason=max_tokens` truncation that drops
`evidence_by_field` — raised to 4096 in both places. Full analysis in
`.planning/debug/resolved/empty-evidence-by-field.md`.

**Run:** `scripts/smoke_closed_won_research.py --limit 10`, live, same 10 closed-won
companies. Exit 2 (one evidenced-FALSE red flag — by design, see below).

| Company | Domain | lv_produces_content | evidence URL |
|---|---|---|---|
| Australian Turf Club | australianturfclub.com.au | true | https://www.youtube.com/user/AtcracesTV?cbrd=1 |
| Redcliffe Harness RC | redcliffehrc.com.au | true | https://redcliffehrc.com.au/ |
| Rockhampton Jockey Club | callaghanpark.com.au | true | https://www.youtube.com/@rockhamptonjockeyclub6459 |
| Wyong | www.wyongraceclub.com.au | true | https://www.bets.com.au/horse-racing/race-courses/wyong-races-live-stream-20210406-0030/ |
| Melbourne Racing Club | mrc.racing.com | true | https://www.troa.com.au/content/racingdotcom |
| Panasonic Studio Productions | www.pspvideo.com.au | true | https://pspvideo.com.au/ |
| Brisbane Racing Club (BRC) | brc.com.au | true | https://www.youtube.com/@brisbaneracingclub427 |
| Racing and Wagering Western Australia | rwwa.com.au | true | https://racingwa.com.au/tv |
| Queensland Racing Integrity Commission | www.qric.qld.gov.au | false | https://qric.qld.gov.au/about-us/functions-powers/ |
| GRAVITY MEDIA | www.gravitymedia.com | true | https://www.gravitymedia.com/us/what-we-do/production-content/ |

**Summary: true=9 null=0 false=1 unmatched=0** (of 10 closed-won companies)

### Reading

- **Evidence bug fixed:** every answered field now carries a distinct, genuine, per-company
  citable URL (0/10 -> 10/10 coverage). This was the actual bug this smoke run was tracking.
- **Split changed 10/0/0/0 -> 9/0/1/0, and this is expected, not a regression:** the prior
  run never performed real research (see root cause above) — it replayed one static fixture
  10 times. This run is the first time genuine per-company web research has run against
  these accounts.
- **The one `false` (QRIC) is the smoke script working as designed.** Queensland Racing
  Integrity Commission is the state's racing *regulator/integrity body*, not a content
  producer — a plausible true negative rather than a false negative, but it is exactly the
  kind of evidenced disagreement this smoke test exists to surface for a human look before
  the hard veto fires on a real customer. Recorded here for that review; not auto-resolved.
- **Exit code 2** is the script's intentional RED FLAG path (an evidenced `false` on a
  closed-won company), not a script failure.
