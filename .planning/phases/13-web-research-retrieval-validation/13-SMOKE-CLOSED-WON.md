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
