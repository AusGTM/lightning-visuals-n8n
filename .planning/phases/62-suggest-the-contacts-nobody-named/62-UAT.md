---
status: diagnosed
phase: 62-suggest-the-contacts-nobody-named
source: [62-VERIFICATION.md]
started: 2026-09-02T01:30:00Z
updated: 2026-09-03T12:05:00Z
---

## Current Test

[testing paused — test 1 failed with a blocker; tests 2 and 3 are unreachable until it is fixed]

## Tests

### 1. A real company's sitemap yields a usable people page on a live racing-club-shaped site
expected: The sitemap-ladder rung resolves a people/board/team page and names at least one person, mirroring UAT 2.4's precedent (9/9 directors on gctc.com.au)
why_human: `url_fallback.py` is pure string-building with no I/O by construction (62-VALIDATION.md manual-verification row 1) — the unit suite proves the ladder logic and the host-bound guard, never whether a given site's sitemap actually lists a people page. Requires a live plugin sitting with a real `web_fetch`.
result: issue
reported: |
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
severity: blocker

### 2. Stage 1 → stage 2 handoff on a real discovered person (name+company → Lusha search-and-enrich → proposal)
expected: A person named by the ladder with no email resolves through identity group 2, the waterfall fills email/phone, and the row lands as a proposal (or HELD if still emailless) — never a silent write
why_human: Requires a real page fetch (plugin-side `web_fetch`) followed by a real Lusha credit spend; neither runs in the stub-transport test suite (62-VALIDATION.md manual-verification row 2).
result: blocked
blocked_by: prior-phase
reason: "Unreachable until test 1's defect is fixed: stage 2 enriches the people stage 1 named, and stage 1 currently names nobody. Could be forced today against one of the 78 scheme-bearing eligible companies, but that would spend Lusha credit on a sitting that must be repeated after the fix anyway — the fix changes discovery_plan, so test 1 needs a re-run regardless and tests 2 and 3 come along free in that same sitting."

### 3. The priced ceiling is not exceeded in a real sitting
expected: Actual page fetches and provider credits spent land at or under the quoted worst-case ceiling shown at grant-open; a bad or omitted per-company cap does not silently blow the ceiling
why_human: The ceiling arithmetic and the cap-refusal guard (`agreed_cap` / `synthesise_rows`) are both now unit- and live-probe-tested outside the test suite, but "the operator saw a number and the round stayed under it in a real sitting" is an end-to-end property only a live sitting can demonstrate (62-VALIDATION.md manual-verification row 3). This item is also the acceptance test for the 62-06 cap fix.
result: blocked
blocked_by: prior-phase
reason: "Measures the actual spend of tests 1 and 2 against the ceiling quoted at grant-open. With stage 1 naming nobody, a round spends nothing, and 'nothing is under the ceiling' would be a vacuous pass — the worst possible outcome for this particular test, which exists to catch a ceiling that does not bind."

## Summary

total: 3
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 2

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
  status: failed
  reason: |
    User-visible effect: a suggestion round finds nobody at 83.5% of companies that have a
    website, because every ladder candidate is built with an empty host and 404s. The round
    reports the give-up message as though the site had no people page, so the failure reads
    as "nothing found" rather than "the URL was malformed".
  severity: blocker
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
