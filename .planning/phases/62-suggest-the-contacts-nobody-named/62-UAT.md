---
status: complete
phase: 62-suggest-the-contacts-nobody-named
source: [62-VERIFICATION.md]
started: 2026-09-02T01:30:00Z
updated: 2026-09-03T13:31:21Z
---

## Current Test

[testing complete — all 3 pass; 4 new gaps recorded, 2 of them operator-directed]

## Tests

### 1. A real company's sitemap yields a usable people page on a live racing-club-shaped site
expected: The sitemap-ladder rung resolves a people/board/team page and names at least one person, mirroring UAT 2.4's precedent (9/9 directors on gctc.com.au)
why_human: `url_fallback.py` is pure string-building with no I/O by construction (62-VALIDATION.md manual-verification row 1) — the unit suite proves the ladder logic and the host-bound guard, never whether a given site's sitemap actually lists a people page. Requires a live plugin sitting with a real `web_fetch`.
result: pass
resolved_on: second run, 2026-09-03, after the G-62-1 fix shipped
evidence: |
  Live sitting 2026-09-03, run_id `d1898a9480a947d1baf6e952cfc5498e`, operator grant over
  4 racing clubs. The ladder resolved a real people page on live racing-club-shaped sites,
  which is exactly the precedent this test names (gctc.com.au, 9/9 directors):

      Lismore Turf Club      /about/board-members-and-staff/  -> 13 people, all with roles
      The Roma Turf Club     /our-committee/                  -> 16 people, all with roles
      Muswellbrook Race Club /club-info/                      -> 14 people, all with roles
      The Gladstone Turf Club  reached, but its `dt_staff` sitemap is venue-booking pages

  43 people named across 3 clubs. All four sites are sitemap INDEXES, so stage 1 is three
  hops deep (index -> nested sitemap -> people page); the 5-fetch per-company budget
  absorbed that with room to spare and is enforced in code.

  Every ladder carried the fix's own disclosure note, e.g. "'lismoreturfclub.com.au' had
  no scheme; every candidate below is bound to 'https://lismoreturfclub.com.au'."

first_run_result: issue
first_run_reported: |
  The ladder never reached a fetch, on any company. `suggest_contacts.discovery_plan`
  builds candidate URLs with an EMPTY HOST for 83.5% of this portal's companies, so every
  candidate is an unfetchable `https:///...`.

  Observed live on the two companies the review lane had just processed:

      9604738976  Bunbury Turf Club           website: bunburyturfclub.com.au
        host = ''
        https:///wp-json/wp/v2/pages?slug=bunburyturfclub.com     <- no host; .au lost
        https:///sitemap.xml

      9604787229  The Alice Springs Turf Club website: alicespringsturfclub.org.au
        host = ''
        https:///wp-json/wp/v2/pages?slug=alicespringsturfclub.org

  Reproduced deterministically with no network (`url_fallback.plan_ladder`):

      'bunburyturfclub.com.au'            -> host ''                          BROKEN
      'www.bunburyturfclub.com.au'        -> host ''                          BROKEN
      'https://bunburyturfclub.com.au'    -> host 'bunburyturfclub.com.au'    fine
      'https://www.bunburyturfclub.com.au/' -> host 'www.bunburyturfclub.com.au' fine

  Portal-wide (`scripts/uat62_website_survey.py`, read-only, 715 companies):

      companies with a website/domain : 699
      BARE (no scheme)                : 584   -> 83.5% build an unfetchable ladder
      usable (has scheme)             : 115
      eligible (0 associated contacts): 321
      eligible AND scheme-bearing     :  78   <- all a round could fetch today
first_run_severity: blocker

### 2. Stage 1 → stage 2 handoff on a real discovered person (name+company → Lusha search-and-enrich → proposal)
expected: A person named by the ladder with no email resolves through identity group 2, the waterfall fills email/phone, and the row lands as a proposal (or HELD if still emailless) — never a silent write
why_human: Requires a real page fetch (plugin-side `web_fetch`) followed by a real Lusha credit spend; neither runs in the stub-transport test suite (62-VALIDATION.md manual-verification row 2).
result: pass
evidence: |
  Daniel Kedraika (Operations Manager, Lismore Turf Club) — named by the ladder, no email,
  resolved through identity group 2 exactly as the test describes:

      ChunkResult(index=0, rows=1, ok=True)
      response  : {"accepted": true, "row_id": "row-1"}
      recovery  : recover_async_dispatch recovered=true, matched the execution by run_id
      proposal  : action="proposed", mode="propose", needs_review=true
                  match: {tier: "none", auto: false, reason: "searched, no hit"}
      ZoomInfo  : kdaniel@lismoreturfclub.com | +61 435 938 322 | North Lismore, NSW

  The row landed as a PROPOSAL flagged for review — never a silent write, which is the
  property this test exists to protect. `match.auto` is false and `needs_review` is true,
  so nothing could have been written unattended.

  **This passes only because the missing `preingest.build_rows_spec()` call was supplied
  by hand — see gap G-62-4.** Following `suggest-contacts/SKILL.md` as written, this test
  cannot be run at all: `chunking.dispatch_plan` hard-refuses every row. The capability
  works; the documented sequence does not reach it.

  One provenance observation worth carrying forward, not a defect: stage 1 read
  "Operations Manager" off the club's own board page, and ZoomInfo returned "Functions"
  for the same person. The winner map took ZoomInfo's. That is precisely the case
  `source_by_field` (D-62-17) exists to disambiguate — worth an explicit check that stage
  1's own jobtitle wins over a provider's for a person stage 1 named.

### 3. The priced ceiling is not exceeded in a real sitting
expected: Actual page fetches and provider credits spent land at or under the quoted worst-case ceiling shown at grant-open; a bad or omitted per-company cap does not silently blow the ceiling
why_human: The ceiling arithmetic and the cap-refusal guard (`agreed_cap` / `synthesise_rows`) are both now unit- and live-probe-tested outside the test suite, but "the operator saw a number and the round stayed under it in a real sitting" is an end-to-end property only a live sitting can demonstrate (62-VALIDATION.md manual-verification row 3). This item is also the acceptance test for the 62-06 cap fix.
result: pass
evidence: |
  Ceiling quoted at grant-open, BEFORE anything was spent:
  "Suggestion round ceiling -- stage 1 discovery: up to 20 page fetches (4 x 5/company)
   -- dollar cost not measured; stage 2 enrichment: up to 8 contacts, up to 8 Lusha credits."

      stage 1 page fetches   ceiling 20   actual 11   (4 indexes + 4 nested + 3 people pages)
      stage 2 contacts       ceiling  8   actual  1
      Lusha credits          ceiling  8   actual  0   (see the billing note below)

  Actuals landed under the ceiling on every axis.

  **Cost-accounting note — a single balance read would have recorded this wrong.** The
  Lusha balance was read three times around the run: 3886 before, **3885** immediately
  after, 3886 again a few minutes later. The provider node's own report is authoritative
  and agrees with the third read: `Lusha Enrich` returned
  `{"error":{"code":"NOT_FOUND"},"billing":{"creditsCharged":0,"resultsReturned":0}}` —
  Lusha had no record of this person and charged nothing. The 3885 was an
  eventually-consistent blip, not a spend. Net provider credit for this round: **0**.
  Worth carrying into any cost ledger built on balance deltas: one before/after pair can
  manufacture a phantom credit.

  The second half of this test — "a bad or omitted per-company cap does not silently blow
  the ceiling", the acceptance test for the 62-06 fix — was exercised live against the real
  grant envelope at ZERO cost, before any spend:

      agreed_cap(1) -> 1
      agreed_cap(2) -> 2
      agreed_cap(3) -> CapRefused: the grant priced this round at a cap of 2; a cap of 3
                       was not what was agreed to.
      agreed_cap(5) -> CapRefused: (same shape)
      agreed_cap(0 / -1 / None / 'two') -> CapRefused: must be a positive int --
                       refusing rather than guessing what the operator meant.

  Note it refuses 3, not merely 5: the envelope prices against the cap the operator
  actually chose (2), which is STRICTER than D-62-12's band ceiling of 3. "The round may
  spend LESS than the priced cap; it may never spend more." 

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Preconditions discharged this session (2026-09-03, all read-only)

1. **Deployed vs committed — zero drift, and this one mattered.** CLAUDE.md §13.0.2 warns
   that Phase 62 regenerated six workflows and committed them WITHOUT deploying, which
   would have meant testing an instance that lacked this phase's own
   `num_associated_contacts` search property and `sourceByField` wiring. Hashed every node
   body of all five cloud workflows live against the committed JSON:

       wf_backend_status_cloud        17/17 nodes    0 differing
       wf_contact_ingest_cloud        29/29 nodes    0 differing
       wf_enrichment_cloud          123/123 nodes    0 differing
       wf_review_decision_cloud       26/26 nodes    0 differing
       wf_scheduled_maintenance_cloud 39/39 nodes    0 differing

   `num_associated_contacts` is live in 5 nodes of `LV Enrichment (Cloud template)`.
   **§13.0.2's caveat is STALE and should be corrected** — the instance is current.
   (The three `*_local*.json` replicas are not deployed, by design.)

2. **Provider credits** — Lusha 3,886, ZoomInfo 9,380, Apollo `None`/200 (expected: the
   key is not a master key, so the endpoint returns no balance rather than failing). The
   2026-09-02 deferral cited "needs a real Lusha credit spend" as a blocker; that axis is
   now clear.

3. **Role vocabulary** — `role_classify.load_families()` renders un-evidenced, and its
   disclosure was shown to the operator verbatim as D-62-07 requires: "These roles were NOT
   derived from this portal's own contacts -- they are a generic list."

4. **Eligibility of the batch just processed** — the two racing clubs the review lane
   approved earlier today both came back `has_contacts` (1 and 3 associated contacts) and
   were correctly skipped. That batch could not have served as this round's scope
   regardless of the defect.

## Gaps

- gap_id: G-62-1
  truth: "A company's own people page is reachable through the sitemap ladder for companies as they are actually recorded in this portal"
  status: resolved
  resolved_by: 62-07-PLAN.md
  resolved_at: 2026-09-03
  reason: |
    User-visible effect: a suggestion round finds nobody at 83.5% of companies that have a
    website, because every ladder candidate is built with an empty host and 404s. The round
    reports the give-up message as though the site had no people page, so the failure reads
    as "nothing found" rather than "the URL was malformed".
  severity: blocker
  status_note: "FIX LANDED 2026-09-03 (plan 62-07, commits 8c45946 / f5fd69a / 2d99cfa, plugin 0.38.1). Not yet live-proven — test 1 stays `issue` until the supervised sitting re-runs it."
  test: 1
  root_cause: |
    `url_fallback.plan_ladder(pasted_url)` is named and written for a URL the operator
    PASTED, and it requires a scheme: it does `urlsplit(pasted_url)` and takes
    `parts.netloc` as the host. Given a bare domain, `urlsplit` puts the whole string in
    `path`, so `netloc` is `''` and every candidate renders as `https:///...`. The slug
    rungs additionally derive a bogus slug by dropping the final dot-segment
    (`bunburyturfclub.com` from `bunburyturfclub.com.au`).

    `suggest_contacts.discovery_plan` (Phase 62, plan 62-01) passes
    `company_row["website"] or company_row["domain"]` — HubSpot properties that hold a bare
    domain for 584 of this portal's 699 companies-with-a-website — straight into it with no
    normalisation.

    The defect is NEW AT THE PHASE 62 SEAM, not pre-existing in the ladder. `plan_ladder`'s
    only other caller is `contact-upload`'s URL adapter, where the operator pastes a link
    and a scheme is present by construction. D-62-01's instruction to call the ladder as a
    library rather than rebuild it was the right call; what was missed is that the two
    callers have different input contracts, and nothing normalises at the join.

    This is invisible to the unit suite by construction: `url_fallback.py` is pure
    string-building with no I/O, so its tests assert on well-formed fixture URLs and pass.
    Only real portal data exposes it — which is exactly what this manual-only item existed
    to catch.
  artifacts:
    - path: "operator-claude-plugin/scripts/suggest_contacts.py"
      issue: "discovery_plan passes a possibly-schemeless website/domain into url_fallback.plan_ladder, which requires a scheme; no normalisation at the seam (line ~93-108)"
    - path: "operator-claude-plugin/scripts/url_fallback.py"
      issue: "plan_ladder silently yields host='' and https:/// candidates for a schemeless input instead of refusing it; its docstring documents no scheme requirement"
  missing:
    - "Normalise the company's website/domain to a scheme-bearing URL before it reaches plan_ladder — the seam in discovery_plan is the natural place, since that is where a bare CRM property enters a function written for a pasted URL"
    - "Make plan_ladder fail loudly rather than silently on a schemeless input, so a future third caller cannot reintroduce this quietly. discovery_plan's own docstring already promises 'no candidates and a reason, never a constructed guess at a path' for an unusable website — a schemeless input should take that documented path, not emit four guesses"
    - "Decide http vs https and www-prefixing deliberately rather than by accident, and record the choice: the ladder's later rungs are host-bound, so the host chosen here determines every subsequent fetch"
    - "A regression test using a BARE domain fixture (e.g. 'bunburyturfclub.com.au'), which today's suite lacks — every existing fixture is a well-formed URL, which is why this passed CI"
  debug_session: ""

## Tooling written for this UAT (read-only, committed)

- `scripts/uat62_eligibility_read.py` — reads `num_associated_contacts` + website/domain
  for a named batch and renders the plugin's OWN `suggest_contacts.eligibility` verdict and
  `discovery_plan` ladder, rather than re-deriving either.
- `scripts/uat62_website_survey.py` — portal-wide counts behind the 83.5% figure, and which
  eligible companies are scheme-bearing. Explicitly a diagnostic to inform the operator's
  batch choice, NOT a round scope: D-62-04 scopes a round to a batch that was just
  processed, never to "every company in the portal with no contacts".

Neither writes, spends a provider credit, or runs an n8n execution.

## Gap closure (2026-09-03) — landed, locally verified, NOT yet live-proven

`62-07-PLAN.md` — commits `8c45946` (seam), `f5fd69a` (refusal), `2d99cfa` (0.38.1),
`e4a33bc` (summary). Regression after: 2300 plugin tests, 1727 root pytest, 867 node — all
passing. `git status --porcelain n8n/` silent: zero n8n change, proven rather than asserted.

**The plan found a SECOND instance of the defect this UAT did not diagnose.** `next_candidates`
was broken the same way: with a bare domain, `same_host` compared against an empty netloc and
refused every sitemap URL as off-host — and the sitemap rung is exactly what test 1 exercises.
Fixing only `discovery_plan`, which is what this UAT's `missing` list prescribed, would have
produced well-formed candidates that were then discarded anyway, and test 1 would have failed
a second time inside the same seam for a different reason. Both call sites now route through
one private helper (`_ladder_source`), not two copies.

Independently re-verified after the fix, on the exact data that failed (pure string-building,
no network):

    Bunbury Turf Club      host 'bunburyturfclub.com.au'      -> https://bunburyturfclub.com.au/sitemap.xml
    Alice Springs Turf Club host 'alicespringsturfclub.org.au' -> https://alicespringsturfclub.org.au/sitemap.xml

    no-op for values that already worked (seam output == direct plan_ladder output):
      'https://bunburyturfclub.com.au'    -> host preserved            True
      'https://www.gctc.com.au/'          -> www preserved             True
      'http://example.org/board?x=1'      -> http + path + query kept  True
      'https://WWW.MixedCase.COM/Board'   -> case preserved, not lowered True

    refusal at the entry point:
      plan_ladder('')           -> ValueError
      plan_ladder(None)         -> ValueError   (was TypeError from urlsplit — also fixed)
      plan_ladder('notadomain') -> ValueError

    the second instance, and its safety property intact:
      next_candidates(bare-domain row, ['…/board/', '…/our-team/', 'https://evil.example/x'])
        accepted: both same-host URLs   (previously ALL were refused as off-host)
        refused : evil.example, "is not the pasted URL's host (bunburyturfclub.com.au)"

That last check is the one that mattered most: the fix makes `same_host` work rather than
making it permissive — an off-host URL is still refused, with both hosts named.

### Still required: one supervised live sitting

Test 1 stays `issue` and tests 2 and 3 stay `blocked` deliberately. Nothing above involved a
`web_fetch`, a Lusha credit, or a real people page — the ladder now builds fetchable URLs, but
"a real racing-club site's sitemap yields a usable people page" is an end-to-end property only
a live sitting can show. 78 eligible scheme-bearing companies were available at survey time,
and the fix should raise that materially since bare domains now normalise; re-run the survey
at the start of the sitting rather than trusting that number.

## The waterfall actually ran — evidence, since the merged result hides it

Execution `12089`. All three providers were requested and enabled
(`providers_requested: ["lusha","apollo","zoominfo"]`, `provider_enabled` true for each on
every gate node). ZoomInfo won every field not because the waterfall stopped early, but
because it was the only source that had the person:

    Lusha Enrich    NOT_FOUND, creditsCharged 0 -- no record of Daniel Kedraika
    ZoomInfo Enrich full hit -- email, mobile, jobTitle "Functions", North Lismore NSW
    Apollo          key is not a master key; balance null, degrades rather than failing
                    (the standing known limitation, not new)

`provider_agreement` is `[]` for every field and every winner carries `agreedBy: []` —
single-source, no corroboration — which is consistent with the row coming back
`needs_review: true` rather than auto-writable.

## Second run account

run_id `d1898a9480a947d1baf6e952cfc5498e`. Two armed windows opened and closed across the
sitting (one refused-then-retried enrichment send); `disarmed PASS` verified by an
independent process after each, and again at the end of the sitting.

An earlier attempt was killed by a 10-minute command timeout mid-run. The gate was checked
immediately and read `disarmed PASS` — the context manager had already closed before the
kill. Recorded because it is the exact scenario the single-process discipline exists for,
and it held.
