---
status: diagnosed
phase: 62-suggest-the-contacts-nobody-named
source: [62-VERIFICATION.md]
started: 2026-09-02T01:30:00Z
updated: 2026-09-03T16:48:08Z
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

  **Round 2 (2026-09-04) re-ran this through the FIXED documented sequence and it passed
  again — but found two defects this test does not itself assert. Read G-62-6 and G-62-7
  before treating this `pass` as "the lane is sound":** 2 of 6 rows came back with no verdict
  at all while credit was spent (G-62-6), and of the 2 rows that did get an email, one was a
  different person at an unrelated company — and that false match is precisely the row
  promoted to sendable (G-62-7). Both are recorded as gaps rather than as a failure of this
  test, because this test's own stated truth — resolves through identity group 2, lands as a
  proposal or HELD, never a silent write — did hold for every row.

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

      ROUND 1
      stage 1 page fetches   ceiling 20   actual 11   (4 indexes + 4 nested + 3 people pages)
      stage 2 contacts       ceiling  8   actual  1
      Lusha credits          ceiling  8   actual  0   (see the billing note below)

      ROUND 2 (2026-09-04, same ceiling, the cap actually binding this time)
      stage 1 page fetches   ceiling 20   actual  4
      stage 2 contacts       ceiling  8   actual  6
      Lusha credits          ceiling  8   actual  7   (3886 -> 3879)

      Round 2 stayed under the ceiling on every axis with the cap binding at 2/company on
      three companies. Note the credit efficiency, which the ceiling does NOT measure: 7
      credits bought 4 verdicts, because 2 of the 6 dispatched rows returned nothing at all
      (G-62-6). Under the ceiling, and still wasteful.

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

**Removed (62-10-PLAN.md Decision 4, 2026-09-04).** All three scripts named above, plus
`scripts/uat62_cluster_probe.py` (the live-Anthropic-call diagnostic behind the "Second
run account" root-cause note below — it turned out to have been an untracked working-tree
file, never committed), are gone from the repo. Nothing in the committed corpus imports or
invokes any of them, confirmed by a repo-wide search before deletion. Their findings live
entirely in this document: the 83.5%/78-scheme-bearing figures and the eligibility/
discovery-plan renderings are quoted above; the cluster-probe root cause is recorded under
G-62-5. A future reader looking for one of these scripts by name should read this line and
this file, not assume the finding was lost.

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

- gap_id: G-62-2
  truth: "A company's own sitemap is reachable when the site serves it from the apex while HubSpot records www (or vice versa)"
  status: resolved
  resolved_by: 62-10-PLAN.md
  resolved_at: 2026-09-04
  live_confirmed: "round-2 sitting 2026-09-04 — see '## Round 2 live sitting'"
  origin: OPERATOR RULING, 2026-09-03 — "Accept apex and www as one and the same (redirects accepted)"
  reason: |
    Live, on 1 of 4 companies in the first real batch (25%). Gladstone Turf Club is recorded
    as `www.gladstoneturfclub.com.au`; its own sitemap index points at the apex
    `gladstoneturfclub.com.au`. `same_host` refuses every one of those URLs:
      "gladstoneturfclub.com.au is not the pasted URL's host (www.gladstoneturfclub.com.au)
       — refusing to follow it off-host."
    The guard is behaving correctly — this is not a defect in it. The cost is that the
    company is lost to the round, including a sitemap literally named `dt_staff-sitemap.xml`.
  severity: major
  test: 1
  root_cause: |
    `url_fallback.same_host` compares `urlsplit().netloc` exactly. 62-07 Decision 2
    deliberately scoped apex<->www canonicalisation OUT ("deliberately does not fix: apex/www
    canonical mismatch"), which was a defensible call at plan time; this sitting measured its
    incidence at 25% of a real batch, which is the new information.
  missing:
    - "Treat apex and www as the same host for the same registrable domain — the operator's ruling. Scope it to that ONE equivalence; do not weaken same_host into a suffix or subdomain match, which would let `evil.gladstoneturfclub.com.au.attacker.tld` through"
    - "Accept redirects (operator ruling). Note `WebFetch` returns a cross-host redirect to the caller rather than following it, so 'accept redirects' needs an explicit decision about which redirect targets are in scope — same registrable domain only, most likely"
    - "A regression fixture for BOTH directions: recorded apex + site serves www, and recorded www + site serves apex"
    - "Keep the refusal message's shape for genuinely off-host URLs — naming both hosts is what made this diagnosable in one read"
  debug_session: ""

- gap_id: G-62-3
  truth: "The default role vocabulary matches the job titles that actually appear on this portal's companies' people pages"
  status: resolved
  resolved_by: 62-09-PLAN.md
  resolved_at: 2026-09-04
  live_confirmed: "round-2 sitting 2026-09-04 — see '## Round 2 live sitting'"
  origin: OPERATOR RULING, 2026-09-03 — "expand default fallback positions in role_vocabulary.py list to match and partial match what was observed"
  reason: |
    43 people were named across three racing-club board/committee pages. TWO survived the
    role filter. Roma Turf Club: 16 named, 0 selected.
    Observed titles the generic list does not contain: Chairman, Deputy Chairman, President,
    Vice President, Vice Chairman, Director, Board Of Directors, Treasurer, Secretary,
    Secretary Manager, Committee member, Track Manager, Catering Manager, Racecourse Track
    Curator, Executive Assistant, Finance & Admin Officer, Trackwork Supervisor.
    The two that matched did so exactly: "Operations Manager" and "General Manager".
  severity: major
  test: 1
  root_cause: |
    `role_classify.load_families()` is serving `source: generic_fallback`, `evidenced: false`,
    `distinct_titles_sampled: 0` — eight generic corporate roles (CEO, CMO, Head of Broadcast,
    …). Matching is exact-label only. Racing clubs use governance vocabulary, not corporate
    vocabulary, so the intersection is nearly empty.
    D-62-07's disclosure predicted this in prose and was shown verbatim to the operator; what
    is new is the measured yield — 2/43.
  missing:
    - "Expand the generic fallback list to include the governance titles observed above (operator ruling)"
    - "Add PARTIAL matching (operator ruling) — 'Secretary Manager' should match a Secretary family, 'Board Of Directors' a Director family. Decide and record the matching rule (substring? token overlap? normalised contains?) rather than leaving it implicit, and make sure it cannot over-match, e.g. 'Track Manager' must not be swept into 'General Manager'"
    - "Case/entity normalisation on both sides of the comparison — the portal already stores 'AV &amp; Broadcast Senior Executive' with the entity unescaped"
  debug_session: ""

- gap_id: G-62-4
  truth: "A suggestion round can dispatch its stage-2 enrichment by following the documented skill sequence"
  status: resolved
  resolved_by: 62-08-PLAN.md
  resolved_at: 2026-09-04
  live_confirmed: "round-2 sitting 2026-09-04 — see '## Round 2 live sitting'"
  reason: |
    It cannot. Following `suggest-contacts/SKILL.md` exactly, stage 2 dies on the first chunk:
      ChunkResult(index=0, rows=1, ok=False,
        reason='A row without a `row_id` can never be matched back to its response —
                `row_id` is the join key every downstream verdict is keyed on.')
    Nothing is spent and nothing is sent — the refusal is clean and fail-closed — but the
    round cannot proceed. Test 2 passed in this sitting ONLY because the missing call was
    supplied by hand.
  severity: blocker
  test: 2
  root_cause: |
    `preingest.build_rows_spec(rows)` is the single place `row_id` is minted ("once, at the
    whole-batch level — before anything is chunked", preingest.py:129), and it returns exactly
    the `{"rows": [...], "object_type": "contacts"}` spec `chunking.plan_chunks` takes.
    `suggest-contacts/SKILL.md` never calls it. Grepping the skill for `build_rows_spec`,
    `row_id` or `mint` returns nothing.
    Nothing else in the documented chain supplies one either, verified by running it:
    `synthesise_rows` emits only canonical props and ASSERTS that no non-canonical key
    (including `row_id`) is present; `round_artifact` only wraps; and
    `extraction.validate()` returns the row still carrying just the four canonical keys.
    The skill's step 8 additionally places `extraction.validate()` AFTER stage 2, so even if
    validate did mint an id it would arrive too late for the dispatch in step 7.
    Same class as G-62-1: a seam between two components whose contracts do not meet, invisible
    to a unit suite that never drives the documented end-to-end order.
  artifacts:
    - path: "operator-claude-plugin/skills/suggest-contacts/SKILL.md"
      issue: "steps 7-8 dispatch stage 2 without ever calling preingest.build_rows_spec; the worked example in step 8 has the same omission"
  missing:
    - "Call `preingest.build_rows_spec()` on the round's synthesised rows before stage-2 dispatch, and use its returned spec as the chunking spec"
    - "Decide where it belongs given the round is per-company but ids must be minted once for the WHOLE batch — build_rows_spec refuses a row that already has an id, so it cannot be called per company and then again for the batch"
    - "Fix the worked example in step 8, which an implementer will copy verbatim"
    - "An end-to-end test that drives the documented sequence with a stub transport and asserts a chunk is ACCEPTED — the existing suite tests the parts, and every part passes"
  debug_session: ""

- gap_id: G-62-5
  truth: "`role_vocabulary.py` can derive an evidenced role vocabulary from this portal"
  status: failed
  fix_landed: |
    Quick task 260904-39r, 2026-09-04, commits 38020fd / fb18884 / 2e7b364.
    Rank-then-cluster (fixed head of 200 by recurrence, `--head N` to raise), truncation
    raises `RoleVocabularyDerivationError` BY NAME before the text is parsed, tolerant parse
    reuses `src/web_research._extract_json` with one repair retry per CLAUDE.md §26.3, and
    `_normalize_title` (html.unescape + whitespace collapse) is applied at COUNT time and
    again to returned members before `rank_top_families`' `in counts` check — which kills the
    silent-drop class, not just the one `&amp;` instance seen. Junk rule `<2 alpha chars`
    drops `+61407 911 185`, deliberately keeps bare `AV`.
    16 new tests, RED observed first; root suite 1743 passed; plugin suite 2362 unchanged.

    Verified independently by the orchestrator: the curated 17-family vocabulary is INTACT
    (all 9 governance families present) — derived output goes to a separate, gitignored
    `role_vocabulary.derived.yaml` and the shipped file is never overwritten; zero diff under
    `operator-claude-plugin/`, so the plugin stays at 0.38.3.

  status_note: |
    **STILL OPEN, deliberately.** This gap's truth is that the script CAN DERIVE a vocabulary
    from this portal, and that has not happened. The fix is unit-proven against a fixture, but
    the fixture is a shape-faithful RECONSTRUCTION rather than captured bytes — the probe
    script that produced the original response was deleted by 62-10's housekeeping before the
    fix was written. No live run has occurred.
    Closing this needs one operator command, which spends one Anthropic call and reads the
    portal, and is deliberately not an executor task:
        set -a; source .env; set +a; .venv/bin/python scripts/role_vocabulary.py --dry-run
    Expected: no crash; a printed head-coverage line (head/2045 distinct, contacts covered of
    3772) showing whether 200 sufficed; and the would-be YAML. Marking this resolved on unit
    evidence alone would repeat the pattern this phase has now hit four times.
  reason: |
    `python scripts/role_vocabulary.py --dry-run` crashes:
      JSONDecodeError: Expecting value: line 1 column 1 (char 0)   (role_vocabulary.py:129)
    The portal is NOT sparse — 2,045 distinct job titles across 3,772 contacts, far above
    SPARSE_THRESHOLD (20) — so the generic fallback currently in use is not the portal's fault.
  severity: major
  test: 1
  root_cause: |
    Probed live (`scripts/uat62_cluster_probe.py`). TWO independent causes, and the second is
    the one that matters:
      1. The response is fenced — text begins '```json\n{' — so the bare `json.loads(text)`
         at line 129 fails at char 0. The repo already has a tolerant parser for exactly this
         (`src/web_research.py::_extract_json`, strips fences, falls back to a regex object
         scan) and this script does not use it. CLAUDE.md §26.3 also specifies
         "Haiku invalid JSON -> Retry once with repair prompt"; there is no retry.
      2. It is ALSO truncated: `stop_reason: max_tokens`, `out=2000` exactly at the cap, text
         ending mid-object. So fence-stripping alone does NOT fix it — `_extract_json` was
         tried against the same text and failed at char 8464 with "Expecting ',' delimiter".
    The underlying error is one of scale: the system prompt requires every family member to be
    a verbatim input title, so output grows with input, and 2,045 titles (16,079 input tokens)
    cannot be echoed inside max_tokens=2000.
    Sharpest observation: `TOP_N_FAMILIES = 8`. The script clusters all 2,045 titles and then
    keeps 8 families — it pays to cluster the entire tail in order to discard nearly all of it.
  missing:
    - "Rank by recurrence FIRST and cluster only the head, rather than clustering 2,045 titles to keep 8 families — this is the design fix; a max_tokens bump alone just moves the ceiling"
    - "Use the repo's existing `_extract_json` (or the same technique) instead of a bare json.loads, and honour CLAUDE.md §26.3's retry-once-with-repair contract"
    - "Fail loudly on `stop_reason == 'max_tokens'` rather than letting a truncated body reach the parser as an opaque JSONDecodeError"
    - "Decode HTML entities and drop non-title junk before counting — the portal stores 'AV &amp; Broadcast Senior Executive' and '+61407 911 185' as distinct job titles, and `rank_top_families` silently drops any member that does not match `counts` exactly"
  note: |
    The operator's chosen remedy for the immediate problem is G-62-3 (expand and partial-match
    the FALLBACK list), which does not require this to be fixed. Recorded because it is a live
    crash in a shipped script, and because until it works this portal cannot have an evidenced
    vocabulary at all. Sequencing is the operator's call.
  debug_session: ""

## G-62-2 — independent adversarial check of the shipped guard (2026-09-04)

Run by the orchestrator against the shipped `url_fallback.same_host` after 62-10 landed, not
by the plan's own tests. Pure string-building, no network. 13 asserted cases, 0 unexpected:

    ok   recorded www -> apex (the measured Gladstone case)      True
    ok   reverse: recorded apex -> www                           True
    ok   evil.gladstoneturfclub.com.au.attacker.tld  SUFFIX TRAP False
    ok   board.gladstoneturfclub.com.au (real subdomain)         False
    ok   www.x.example:8080 vs x.example (differing port)        False
    ok   www.x.example:8080 vs x.example:8080 (same port)        True
    ok   www.com vs com (dotless remainder)                      False
    ok   www.www.x.example vs www.x.example (one label only)     False
    ok   trailing dot: www.example.com. vs example.com           False
    ok   uppercase WWW.Example.COM vs example.com                True
    ok   IPv6 literal [2001:db8::1] vs 2001:db8::1               False
    ok   example.com vs example.com.evil.tld (apex is a prefix)  False
    ok   www-example.com vs example.com (hyphen is not a label)  False

The five shapes 62-10 recorded as UNPINNED were included deliberately; four behave safely and
are now measured rather than assumed.

**Two behaviours recorded, not asserted:**

- `user@www.example.com` vs `example.com` -> **refused**. Conservative and safe; userinfo makes
  the authorities unequal and the `www.` prefix test never fires.
- `192.168.0.1` vs `www.192.168.0.1` -> **treated as the SAME host**. This is a genuine, minor
  over-match: stripping `www.` leaves `192.168.0.1`, which contains dots, so the dot rule does
  not catch it — but `www.192.168.0.1` is a hostname, not that IP address. Not reopened,
  because reaching it needs a company recorded in HubSpot with a bare IP as its website AND a
  sitemap on it pointing at a www-prefixed variant of itself. Recorded so a future widening of
  `_canonical_authority` starts from a known list rather than rediscovering it.

Regression after the full round: 2339 plugin, 1727 root pytest (149 skipped), 867 node — all
passing. `git status --porcelain n8n/ scripts/build_cloud_workflows.py` silent. The three
`scripts/uat62_*.py` diagnostics are gone.

## Round 2 live sitting (2026-09-04) — the three fixes re-tested, two NEW defects found

run_id `15ea995a2ae44f7097ac938356cf95bb`. Same 4 companies as round 1, deliberately, so each
is a live regression test for a different fix. Grant over 4 companies, cap 2, 11 role families.
Gate `disarmed PASS` before and after; all five cloud workflows zero-drift.

**G-62-2 CONFIRMED FIXED, live.** Gladstone Turf Club (recorded `www.`, serves apex):
`next_candidates` now ACCEPTS `https://gladstoneturfclub.com.au/dt_staff-sitemap.xml` and still
REFUSES `https://evil.gladstoneturfclub.com.au.attacker.tld/x`. The sitemap was fetched; its
contents are marquee/table/beer-garden booking pages, so the company yields no people. Reach
succeeded, content is a dead end — reported as such, not as a failure.

**G-62-3 CONFIRMED FIXED, live.** Same three people pages, same 43 people:

    round 1 (exact-match, 8 families) : 43 named ->  2 selected
    round 2 (token matcher, 17 families): 43 named -> 41 selected -> 6 rows after the cap

    Lismore      13 named -> 13 selected -> 2 rows
    Muswellbrook 14 named -> 12 selected -> 2 rows
    Roma         16 named -> 16 selected -> 2 rows   (was 0)
    Gladstone     0                        0 rows

Over-match guard holds live: `Track Manager` classifies as `Track & Facilities`, NOT
`General Manager`.

**G-62-4 CONFIRMED FIXED, live.** `mint_row_ids` minted `row-1`..`row-6` once for the batch;
`plan_chunks` produced 3 chunks; **all 3 dispatched ok=True**. Round 1 could not dispatch at
all. `rejoin_enriched` returned 6 records carrying their merged rows and did not raise.

**The cap now actually binds** — 13/12/16 selected truncated to 2 each — which is what test 3
needed in order to mean anything. In round 1 it never bound.

## Gaps found by round 2

- gap_id: G-62-6
  truth: "Every row dispatched to the enrichment lane comes back with a verdict"
  status: resolved
  resolved_by: 62-11-PLAN.md
  resolved_at: 2026-09-04
  reason: |
    2 of 6 rows (33%) produced NO verdict.

    **CORRECTED 2026-09-04 by the 62-11 diagnosis — twice, in ways that matter:**
    (a) The rows were never lost IN n8n. `Build Response` emitted BOTH; the CLIENT's reader
        took `runs[0]` and discarded the rest. Verdict `reader_reads_run_0`. So this is a
        client-side defect needing no workflow change and no deploy.
    (b) "while provider credit was spent on the batch" was an inference from a balance delta
        and is WRONG for the lost rows specifically: `Lusha Enrich`'s own per-item billing
        block shows `NOT_FOUND` / `creditsCharged: 0` for both `row-2` and `row-5`. They cost
        nothing. This is the SECOND time in this phase a before/after balance read produced a
        false cost claim — the first was the phantom credit in test 3's round-1 note. Take
        provider cost from the provider's own per-item billing block, never from a delta.

    Proven fixed at zero cost by re-running recovery against the SAME run_id
    (`15ea995a2ae44f7097ac938356cf95bb`) after the fix: 4 responses -> **6**, with `row-2`
    (Tim Curry) and `row-5` (Brett Ashney) both recovered from the original execution data.
    No re-dispatch, no credit, same input, different reader.
    `merge_enriched` reports them honestly rather than as "nothing found":
      row-2 Tim Curry (Lismore, Deputy Chairman)  — "no verdict was received for this row"
      row-5 Brett Ashney (Roma, President)        — same
    Both were correctly HELD, so nothing wrong was written. The cost is real credit spent for
    no answer, and a person the operator will never see proposed.
  severity: major
  test: 2
  root_cause: |
    The row is lost INSIDE the workflow, not in recovery and not in the client. Read directly
    off the three executions:
      12096  Parse HubSpot Event: 2 rows [row-1,row-2] -> Build Response: 1 [row-1]
      12097  Parse HubSpot Event: 2 rows [row-3,row-4] -> Build Response: 2 [row-3,row-4]
      12098  Parse HubSpot Event: 2 rows [row-5,row-6] -> Build Response: 1 [row-6]
    Two of three chunks dropped one row between `Parse HubSpot Event` and `Build Response`.
    Not positional (12096 lost the 2nd, 12098 lost the 1st) and not "no provider match"
    (row-3 and row-4 both returned with `email: None` and survived).
    This is the CONTACTS propose lane. It is the same CLASS as the long-standing suspected
    companies research-lane row-loss note in project memory, but that one is about
    `existingRecord`/`scored` being stripped across HTTP hops in the companies branch and has
    never been proven live. This one is proven live, on contacts, with execution ids.
  missing:
    - "Diagnose where between `Parse HubSpot Event` and `Build Response` the item is dropped — walk the node list of 12096 and 12098 and find the first node whose output count is 1 where its input was 2"
    - "Determine whether the lost row still consumed provider credit (the batch spent 7 credits for 6 rows, so almost certainly yes) — a row that costs money and returns nothing is the worst shape available"
    - "Once found, decide whether the fix belongs in the node or in a fan-in guard; regenerate via scripts/build_cloud_workflows.py, never by hand-editing n8n/wf_*.json"
    - "A regression test that dispatches a 2-row chunk through the stub transport and asserts TWO verdicts come back"
  debug_session: ""

- gap_id: G-62-7
  truth: "A suggested contact's enriched email belongs to the person named on that company's own page"
  status: resolved
  resolved_by: 62-12-PLAN.md
  resolved_at: 2026-09-04
  reason: |
    Live, on 1 of the 2 rows that got an email. Roma Turf Club's committee page names
    **Craig Smith, Vice President**. The waterfall returned
    **`craig.smith@thehartford.com`** — The Hartford is a US insurance company, not a
    Queensland racing club. A different Craig Smith entirely.
    The system flagged it: `needs_review: true`, `match.tier: none`, `agreedBy: []`. Nothing
    was written. That part worked.
    **But the false match is the row that gets PROMOTED.** `partition_for_dispatch` splits on
    having an email, so of 6 rows the 2 sendable ones are exactly the 2 with emails — and one
    of those two is a stranger. The wrong row is the one that advances.
  severity: major
  test: 2
  root_cause: |
    A stage-1 row carries firstname + lastname + company + jobtitle and NO email, so it
    resolves through identity group 2 (`[firstname, lastname, company]`). For a common name
    this is weak: the provider matches the person, not the person-at-this-company. Nothing
    downstream re-checks that the returned email's domain bears any relation to the company
    whose page named them — `craig.smith@thehartford.com` against Roma Turf Club is not
    questioned by anything except the generic `needs_review` flag every unmatched row gets.
  operator_ruling: |
    OPERATOR RULING, 2026-09-04: "the email domain should be related to the company."
    A suggested row whose enriched email domain is unrelated to the company that named the
    person is HELD, not made sendable.

    **Measured consequence, surfaced to the operator before this was recorded:** applied to
    this sitting's own results the rule holds BOTH emails and yields zero sendable rows
    instead of two —
        Craig Smith  romaturfclub.com.au    vs thehartford.com  -> hold (a stranger; correct)
        Mark Oaten   lismoreturfclub.com.au vs oatens.com       -> hold (plausibly his own
                                                                   business, not the club)
    That is a deliberate precision-for-recall trade, accepted with the numbers in view.
  missing:
    - "Implement the operator's ruling: hold a row whose enriched email domain is not the company's domain or a close variant of it"
    - "Decide the freemail case explicitly and label it DISTINCTLY. Racing-club officials commonly use gmail/bigpond; those match no company domain and are held under any strict reading. **CORRECTION 2026-09-04: this was WRONG.** `company_domain.py` holds no host collection at all — it imports `enrichment._clean_domain`, which knows profile hosts and nothing about freemail. The repo's only freemail set is `FREEMAIL_DOMAINS` in `n8n/code/companyLink.js` (backend JS). The error came from reading CLAUDE.md §13.0.1, which describes the INGEST LANE's freemail behaviour as implemented in that JS, not in Python. Plan 62-12 therefore mirrors JS→Python with a parity test — the arrangement `enrichment.NOT_A_COMPANY_DOMAIN` already uses — rather than reusing a classifier that does not exist. The operator should be able to see at a glance whether the held pile is strangers or just people with Gmail"
    - "Say the reason in the operator report, not just a flag: 'email domain thehartford.com does not match romaturfclub.com.au' is actionable; a bare needs_review is not"
    - "If yes, the check belongs where sendability is decided, not in the provider adapters"
    - "Consider surfacing the mismatch in the operator report explicitly — 'this email's domain does not match the company' is far more actionable than a bare needs_review"
    - "Note the interaction with G-62-3: widening the role filter multiplies the number of common-name rows going through identity group 2, so this gets WORSE as the vocabulary improves"
  debug_session: ""

## Round 3 (2026-09-04) — G-62-6 and G-62-7 closed, verified independently

Plans `62-11` (diagnosis + fix) and `62-12` (operator ruling + freemail parity + release
0.38.3). Regression after: **2362 plugin, 1727 root pytest (149 skipped), 867 node**, all
passing. `git status --porcelain n8n/ scripts/build_cloud_workflows.py` silent — zero backend
change in the whole round, and no deploy is needed for either fix.

**G-62-6 — proven fixed against the ORIGINAL data, at zero cost.** Re-ran
`watch.recover_async_dispatch` on the same run_id from the round-2 sitting
(`15ea995a2ae44f7097ac938356cf95bb`) after the fix:

    before: 4 responses  [row-1, row-3, row-4, row-6]
    after : 6 responses  [row-1, row-2, row-3, row-4, row-5, row-6]
    still missing: NONE

`row-2` (Tim Curry) and `row-5` (Brett Ashney) were recovered from the ORIGINAL execution
data — no re-dispatch, no provider credit, same input, different reader. That is the
strongest form this proof could take: the executions were never the problem.

**G-62-7 — the shipped rule, checked by the orchestrator against every measured case:**

    craig.smith@thehartford.com        vs romaturfclub.com.au    -> mismatch  HELD
    markoaten@oatens.com               vs lismoreturfclub.com.au -> mismatch  HELD
    kdaniel@lismoreturfclub.com        vs lismoreturfclub.com.au -> mismatch  HELD  (accepted cost)
    x@romaturfclub.com.au.attacker.tld vs romaturfclub.com.au    -> mismatch  HELD  (suffix trap)
    sec@mail.romaturfclub.com.au       vs romaturfclub.com.au    -> related   SENDABLE
    someone@gmail.com                  -> freemail HELD   (labelled distinctly, NOT a mismatch)
    someone@bigpond.com                -> freemail HELD   (the parse hazard did not bite)
    office@romaturfclub.com.au         -> related  SENDABLE

Three properties confirmed by direct call, not by reading the plan:
- `partition_for_dispatch(rows, company_domains)` — the parameter is genuinely REQUIRED;
  calling with one argument raises. No one-keyword bypass of the operator's ruling.
- `enrichment.FREEMAIL_DOMAINS` mirrors the JS at 33 entries and CONTAINS `bigpond.com` — the
  parity-test parse hazard (a `// AU consumer ISPs` comment line silently swallowing
  `bigpond.com` onward) did not materialise.
- `extraction.hold_emailless` still returns the stranger as sendable when called alone, which
  is what proves `contact-upload` and `enrich-before-ingest` are unaffected by this change.

### Status of every gap this phase raised

    G-62-1  resolved  62-07  schemeless website -> empty host ladder
    G-62-2  resolved  62-10  apex/www treated as different hosts
    G-62-3  resolved  62-09  role vocabulary missed governance titles
    G-62-4  resolved  62-08  stage 2 could not dispatch (no row_id)
    G-62-5  OPEN      —      role_vocabulary.py clustering crash (operator-deferred)
    G-62-6  resolved  62-11  reader discarded rows split across n8n runs
    G-62-7  resolved  62-12  false-match email was the row promoted to sendable

Six of seven closed. G-62-5 remains deferred by operator sequencing, not by oversight: it is
an offline derivation script no round path calls, its chosen remedy (G-62-3) shipped and was
confirmed live at 41/43, and its real fix can only be proven against a live Anthropic call.

### What has NOT been live-proven in round 3

Both round-3 fixes are verified against real recorded data, but neither has run in a live
sitting: G-62-6's proof replays stored executions rather than dispatching new ones, and
G-62-7's rule has never decided a real round's sendable set. On this phase's own record —
four defects found by live walks, three of them at seams where every component passed its own
tests — that distinction is worth keeping until a sitting closes it.
