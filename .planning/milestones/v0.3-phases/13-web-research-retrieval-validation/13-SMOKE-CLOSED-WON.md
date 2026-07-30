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
- **QRIC adjudicated 2026-07-21 (user):** a regulatory body is fairly out of ICP. The veto
  is correct; no taxonomy change needed.

---

# Closed-LOST Control Run — 2026-07-21

**Run:** `scripts/smoke_closed_won_research.py --dealstage closedlost --limit 10`, live,
read-only. Exit 0 (the exit-2 red flag is closedwon-only by design).

**Premise being tested:** if `lv_produces_content` discriminates, closed-lost should show a
materially lower `true` rate than closed-won's 9/10.

| Company | Domain | lv_produces_content | evidence URL |
|---|---|---|---|
| The Creek Agency | thecreek.com.au | true | https://www.thecreek.com.au/ |
| Scone Race Club | www.sconeraceclub.com.au | true | https://www.youtube.com/channel/UC1AqN0yBcRhDo_Mgr4CMPTg |
| Racing NSW | www.racingnsw.com.au | true | https://www.racingnsw.com.au/ |
| Supertech Electronics | www.supertech-electronics.com.au | true | https://myausweb.net.au/automotive/supertech-electronics/ |
| Cairns Jockey Club | www.cairnsjockeyclub.com.au | true | https://www.cairnsjockeyclub.com.au/news/ |
| Victoria Racing Club | flemington.com.au | true | https://www.vrc.com.au/ |
| Bunbury Trotting Club | www.bunburytrottingclub.com.au | true | https://visitbunburygeographe.com.au/business/bunbury-trotting-club/ |
| Sunshine Coast Turf Club | sctc.com.au | true | https://www.sctc.com.au/race-fields-footage/ |
| Harness Racing ACT | www.capitaltrots.com.au | true | https://capitaltrots.com.au/ |
| Thoroughbred Park | www.thoroughbredpark.com.au | true | https://thoroughbredpark.com.au/racing-information/ |

**Summary: true=10 null=0 false=0 unmatched=0** (of 10 closedlost companies)

## Reading — the hypothesis did NOT hold, and that is informative

The predicted inversion did not appear: closed-lost scored **10/10 true** vs closed-won's
9/10. Three separate conclusions, kept apart deliberately:

1. **Not a defect — the population is the same ICP.** 8 of these 10 are racing clubs or
   governing bodies: exactly the target profile. They were lost on price, timing, incumbency
   or budget, not on fit. `lv_produces_content` is a **qualifier, not a predictor** — by
   design it is +20 and a hard veto (does this org belong in the market at all), never a
   win-probability signal. A won/lost split was the wrong thing to expect from it. Tier
   separation is supposed to come from `lv_org_type`, geography and revenue band.
2. **A real limitation is now measured, not assumed.** This field cannot help prioritise
   *within* the racing vertical — nearly every racing body passes it. Its value is
   excluding non-content orgs (QRIC in the won set), and that is all it should be credited
   with. Anyone reading tier A/B/C separation as content-driven would be wrong.
3. **A genuine finding: evidence-quality inflation.** The model now always returns a URL
   (the Phase-13 fix worked), but several citations do not actually evidence broadcast or
   streaming output:
   - **Supertech Electronics** — an electronics firm, cited via a third-party business
     directory (`myausweb.net.au/automotive/...`). Probable **false positive**, and probable
     `lv_is_hardware_vendor` (itself a hard veto). The most suspicious row here.
   - **Bunbury Trotting Club** — cited via a tourism directory (`visitbunburygeographe.com.au`),
     not first-party.
   - **Racing NSW, VRC, Harness Racing ACT, The Creek Agency** — bare homepages, which prove
     the org exists, not that it produces content.
   Only **Scone (YouTube channel)**, **Sunshine Coast (race-fields-footage)**, **Cairns
   (news)** and **Thoroughbred Park (racing-information)** cite pages that actually
   substantiate the claim.

   Spec RT-2 already prefers first-party domains, but nothing today *enforces* that the
   cited page substantiates the specific claim. The evidence gate checks presence, not
   probative value. That is the gap the judge (Phase 14) exists to close — and this run is
   the concrete evidence set to point it at.

## Actions

- **No taxonomy or rubric change from this run.** The field behaves as specified.
- **Carry to Phase 14 (judge):** evidence *sufficiency* — reject homepage-only and
  third-party-directory citations for `lv_produces_content`; a citation must plausibly show
  the content. Supertech Electronics is the worked counter-example to plan against.
- **Carry to Phase 14 / anti-ICP:** verify `lv_is_hardware_vendor` fires on Supertech
  Electronics. If it does, the hard veto catches the false positive regardless of the
  content field — worth confirming rather than assuming.
- **Script gap:** the smoke prints only `lv_produces_content`; `lv_org_type` and the vendor
  flags would have made rows 4 and 7 self-explanatory. Add before the next run.
