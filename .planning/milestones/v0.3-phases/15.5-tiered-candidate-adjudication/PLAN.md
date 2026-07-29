---
phase: 15.5-tiered-candidate-adjudication
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - n8n/code/judge.js
  - n8n/code/scoreEnrichment.js
  - n8n/code/webResearch.js
  - n8n/code/mergeCompanies.js
  - scripts/build_cloud_workflows.py
  - n8n/wf_enrichment_local_live.json
  - tests/n8n/mergeCompanies.test.mjs
  - tests/n8n/judge.test.mjs
  - tests/n8n/researchScoring.test.mjs
  - tests/n8n/webResearchFailure.test.mjs
  - tests/fixtures/research_scoring_cases.json
  - tests/test_judge_spec.py
  - docs/WEB-RESEARCH-SPEC.md
  - .planning/STATE.md
  - .planning/ROADMAP.md
autonomous: true
requirements: [TA-1, TA-2, TA-3, TA-4, TA-5, TA-6, TA-7, TA-8, TS-1, RO-2, JG-2]

must_haves:
  truths:
    - "Every research candidate for a judge-eligible field carries A/R/G/T components and a full ranked candidate set on the row, whether or not an escalation trigger fired (scoring ranks, it never decides)."
    - "A prior on file written by our own pipeline (provenance source claude_web / waterfall / any non-allowlisted source) contributes ZERO to the agreement (G) component; only a prior of independent origin (human/manual, or a provenance-absent legacy value) may raise G."
    - "Research candidates carry a recencyDate sourced from Anthropic's web_search_tool_result.page_age; an unmatched or absent page_age yields null and inherits scoreCandidates' existing neutral 0.5 — never a penalty."
    - "No recency or scoring value reaches mergeCompanies' promotion gate: a stale-page_age row and a fresh-page_age row produce byte-identical canonicalPatch (TS-1 / locked decision 4)."
    - "Judge invocation count per run is enforced by a pure, exported, unit-tested function; rows over the cap fall through the existing applyUnadjudicated fail-safe and never carry an unadjudicated hard-veto true."
    - "Size/firmographic fields never reach the judge — proven structurally (Judge Gate jsCode contains neither the downstream size array nor the watch-list constant, and Judge Gate is a graph ancestor of Merge Company, never the reverse), with the new scoring folded into that same node so the existing RO-2 test covers it unchanged."
    - "mergeCompanies.js has direct unit tests for the first time, and its new opts.confidenceByField is additive — absent, behavior is byte-identical to today for the waterfall call path."
    - "A second build_cloud_workflows.py run is a byte no-op; only wf_enrichment_local_live.json changes; test_top_level_is_exactly_the_deployable_set stays green; the full offline suite is green with zero live network calls."
  artifacts:
    - tests/n8n/mergeCompanies.test.mjs
    - tests/n8n/researchScoring.test.mjs
    - tests/fixtures/research_scoring_cases.json
    - "docs/WEB-RESEARCH-SPEC.md §8.5 (TA-1..TA-8 + Requirements→Test map)"
  key_links:
    - "scoreResearchCandidates calls the SAME scoreCandidates engine the provider waterfall uses — one formula, one weight set, one place a scoring bug can live."
    - "provenance[field].source (written by Phase 15's blob stamper) is the ONLY signal distinguishing an independent prior from our own pipeline's echo; lv_enrichment_provenance must therefore be in the company search property list or the guard silently fails open."
    - "page_age lives on the web_search_tool_result block keyed by url; the model's cited evidence_by_field url is an independently-generated string — the two are joined by a normalized-url match, and the match rate must be observable (recency_source), not silently invisible."
    - "Judge Gate is the single node hosting evidence sufficiency + scoring + escalation + cost cap, so RO-2's existing structural proof covers all four without duplication."
    - "The A/R/G/T composite is 0-1 and mergeCompanies' min_confidence thresholds are 0-100 calibrated against model self-reported confidence — these scales must never be mixed (see <scope_notes> Decision D2)."
---

<objective>
Phase 15.5 makes the adjudication point see everything it should and nothing it shouldn't.

Today the companies research branch bypasses `scoreCandidates` entirely: `rc.data` merges with
one flat `rc.confidence` for every field, no A/R/G/T, no recency, and the judge — which decides
`lv_org_type` / `lv_produces_content` / vendor flags, where a wrong answer moves a tier or fires
a veto — receives only the research candidate and a list of reason strings. Meanwhile size and
firmographic conflicts already resolve deterministically upstream of the judge and must keep
doing so (JG-2: LLMs are poorly calibrated on numeric plausibility; RO-2's intent).

This phase scores the research candidate with the SAME engine the provider waterfall uses,
sources a real `recencyDate` from Anthropic's `page_age`, hands the judge the full ranked set,
caps and asserts model-call cost, and closes two Wave-0 test gaps that would otherwise make all
of the above untrustworthy.

ROADMAP criteria C1..C6 map to spec IDs authored in Task 6: C1→TA-1, C2→TA-2, C3→TA-5/TA-6,
C4→TA-3, C5→TA-4, C6→TA-7.

Purpose: lock judge logic before Phase 16 deployment, and make "confidence" mean something that
is not manufactured.
Output: 3 new pure functions + 1 additive merge option + 1 additive scorer return key + 3 new/
extended test files + 1 new fixture + spec §8.5 + a rebuilt, byte-deterministic workflow.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/15.5-tiered-candidate-adjudication/RESEARCH.md
@docs/WEB-RESEARCH-SPEC.md
@n8n/code/judge.js
@n8n/code/scoreEnrichment.js
@n8n/code/webResearch.js
@n8n/code/mergeCompanies.js
@tests/test_judge_spec.py
@tests/n8n/judge.test.mjs
@.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md
</context>

<scope_notes>
RESEARCH.md was verified against source this session and CORRECTED TWO ROADMAP PREMISES. Trust
RESEARCH over the roadmap entry where they differ:

- **ROADMAP premise: "`best[field]` is retained but never read downstream."** FALSE for companies.
  `ENRICH_MERGE_CO` already reads `best[f].normalizedValue`, not `winners` — the companies
  waterfall survived the raw-winner bug that contacts intentionally keep. The premise is true only
  for contacts, which are out of scope by design.
- **ROADMAP premise: "the judge is blind to the provider evidence."** Directionally right, but the
  mechanism is not a collapse. There IS no provider candidate to be blind to: `normalizeProviders.js`
  never emits a candidate for ANY of the five judge-eligible fields. The real defect is that the
  research branch never enters `scoreCandidates` at all, so those fields carry no A/R/G/T and no
  recency — which is why the second candidate below is the PRIOR ON FILE, not a fourth provider.

The tier boundary the roadmap asks us to build ALREADY EXISTS as two disjoint constants
(`_JUDGE_DATA_FIELDS` in judge.js, `CONFLICT_WATCH` in the Merge Company wrapper). This phase
formalizes and asserts it; it does not invent it.

## Planner decisions (locked; do not re-litigate during execution)

**D1 — prior_on_file accuracy = 0.6 default, WITH a self-confirmation guard.** Adopt 0.6 for an
un-provenanced prior (matches `normalizeProviders.js`'s ungraded-field convention). ADDITIONALLY:
a prior whose Phase-15 provenance entry names one of OUR OWN pipeline sources must NOT contribute
to the agreement (G) component. Otherwise the pipeline agrees with its own previous guess and
manufactures confidence out of nothing — invisible in production, and inflated exactly where we
are least able to detect it. Only an independent-origin prior (provenance `source` in the
`human`/`manual` allowlist, OR no provenance entry at all = legacy/pre-pipeline value) may raise G.
A non-independent prior still contributes its own recency and is still shown to the judge, labeled
`independent: false`. Ambiguity fails CLOSED: an unrecognized source string is treated as
non-independent.

**D2 — the A/R/G/T composite NEVER feeds mergeCompanies' promotion gate.** RESEARCH's TA-8 as
drafted ("mergeCompanies MUST use that composite") is REJECTED for two independent reasons:
  1. It violates locked decision 1 ("scoring ranks, it does not decide") and locked decision 4
     ("recency is ordering bias only, never a veto, never a staleness gate") — the composite
     contains R, so routing it into a min_confidence threshold makes recency a gate by the back door.
  2. Scales do not match and the mismatch is not cosmetic. The composite is 0-1; the thresholds are
     0-100, calibrated against the model's self-reported confidence. With G=0 (the common
     single-candidate case), A=0.88, R=1.0, T=0.78, the composite is 0.674 → 67, BELOW
     `lv_org_type`'s 80 and `lv_produces_content`'s 85. Shipping RESEARCH's TA-8 literally would
     silently stop every research promotion in the pipeline.
  TA-8 is therefore re-scoped (Task 5): `opts.confidenceByField` exists and is additive, and it
  carries the JUDGE VERDICT's per-field confidence — which is per-field by construction, is
  currently discarded entirely, and is on the correct 0-100 scale. The composite rides on the row
  and in the judge payload, for ranking and grounding only.

**D3 — fold `scoreResearchCandidates` into the existing Judge Gate node** (locked user decision 2).
Smallest diff: zero new n8n nodes, zero new connections, zero new HTTP calls, and the Phase-14
graph-ancestry test `test_ro2_judge_gate_cannot_see_size_conflicts` keeps covering the new logic
unchanged rather than being duplicated against a second node.

**D4 — `scoreCandidates` gains ONE additive return key, `ranked`.** RESEARCH recommended leaving
`scoreEnrichment.js` untouched, but `best` is an argmax: with a prior on file it can be the PRIOR,
not the research candidate, and criterion 1 ("candidates stay parallel with their components
through to the adjudication point") and criterion 3 ("the judge receives the full ranked candidate
set") both require the non-winners to survive. `ranked` is 3 lines, purely additive, and existing
callers destructuring `{best}` / `{winners}` are unaffected.

**D5 — no Python twins in this phase, therefore no new NM-6 parity obligation.** `scoreResearchCandidates`,
`extractPageAgeByField` and `applyCostCap` are HTTP-response glue and node-orchestration
infrastructure, not shared business logic. This follows the precedent `src/judge.py` already
records for judge HTTP plumbing ("a parity test against a second hand-written copy of glue code
proves nothing"). `scoreEnrichment.js` has no Python twin today and does not gain one.

## OUT OF SCOPE (state explicitly in the SUMMARY)

- n8n Cloud deployment and the `$env` → credentials conversion (Phase 16).
- SJ-1/SJ-2/SJ-3 schedule wiring and the §22.2 review-surface wiring (Phase 16).
- RT-5 live caching activation — the cache-key properties exist since Phase 15; TTL-based cache-hit
  skip logic is Phase 16 (spec §4 RT-5's own note).
- The HubSpot-side `lv_icp_fit_score` / `lv_icp_tier` formula — downstream of this pipeline
  entirely (Approach C: this pipeline writes ICP INPUTS only).
- The contacts branch. `mergeContacts`' consumption of raw `winners` is intentional and documented
  (jobtitle casing); nothing in this phase touches it.
- Removing the dead `evidence.last_seen` from `src/web_research.py` / `src/schemas.py`. RESEARCH
  recommends it as cleanup and explicitly permits deferral; it is load-bearing for none of the six
  criteria and it touches a prompt block that `test_prompt_parity_vendor_flags` reads. Carried.
- Persisting the A/R/G/T composite into `lv_enrichment_provenance`. No criterion requires HubSpot
  persistence of the score; the row echo carries it for audit. Carried.
- Re-running the 20-row smoke live to capture real `page_age` values. Tests are offline-only; the
  new fixture layers SYNTHETIC page_age and prior-on-file values onto the REAL recorded rows.

## TRAP — read before writing any comment in judge.js or scoreEnrichment.js

`tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts` greps the BUILT Judge
Gate node's `jsCode` for the downstream size-array reference and the watch-list constant name.
Every file inlined into that node (`escalation.generated.js`, `scoreEnrichment.js`, `judge.js`)
has its comments concatenated into that string. Do NOT write either token into any of those
files — not in code, not in a comment, not in a "what this must never touch" note. Refer to them
by description ("the downstream size watch-list") instead. This is how a correct implementation
turns a green structural test red.
<!-- planner-discipline-allow: CONFLICT_WATCH -->
<!-- planner-discipline-allow: row.conflicts -->
</scope_notes>

<tasks>

<task type="auto">
  <name>Task 1: Wave-0 gap A — mergeCompanies.js gets its first direct unit tests (characterization only, zero production change)</name>
  <files>tests/n8n/mergeCompanies.test.mjs</files>
  <action>
`n8n/code/mergeCompanies.js` has survived four phases with ZERO direct unit tests (confirmed: no
such test file exists; the only `tests/` reference is a docstring mention in
tests/test_web_research_spec.py). Task 5 changes this module. Characterize its CURRENT behavior
FIRST, in its own commit, so Task 5's diff is provably additive rather than assumed to be.

Create `tests/n8n/mergeCompanies.test.mjs` following the existing tests/n8n/judge.test.mjs idiom
exactly: `node:test` + `node:assert/strict`, `createRequire` to load the CommonJS module from an
absolute ROOT-joined path. Make NO change to any production file in this task.

Cover the behavior Task 5 must not disturb:
- Promotion: a `system_owned` field (lv_content_type, no evidence requirement) at confidence above
  its threshold lands in canonicalPatch, with a provenance entry carrying source, confidence,
  verified_at, validation_status and value.
- Threshold: the same field below its min_confidence yields the needs_review decision, is ABSENT
  from canonicalPatch, and still gets a provenance entry (staging survives, promotion does not).
- The domain hard guard: a `domain` candidate that would otherwise promote is forced to stage_only
  and never appears in canonicalPatch, regardless of confidence.
- The evidence gate: lv_produces_content at confidence 95 with NO evidence url is withheld; the
  same value WITH an evidence url promotes and the provenance entry carries evidence_url.
- The evidence-gated org-type set: lv_org_type promoting to an evidence-gated value without a url
  is withheld, while an ungated value at the same confidence promotes. Read the gated set from the
  module's exported DEFAULT_COMPANY_POLICY rather than hand-typing org-type names (TX-4 discipline:
  that list derives from config/taxonomy.yaml and must not be copied a second time).
- Blank handling: null / "" / [] candidate values are skipped entirely — no canonicalPatch entry,
  no provenance entry, no decision.
- Cache keys: a promoted lv_org_type sets the lv_org_type_verified_at cache key; a field with no
  cache-key mapping sets none.
- The flat `opts.confidence` default (80) applies when opts omits it.

Assert the RETURN SHAPE explicitly — the four keys canonicalPatch / provenance / cacheKeys /
decisions and nothing else — so that if Task 5 (or a later phase) adds or renames a key, this test
is the thing that notices.
  </action>
  <verify>
    <automated>node --test tests/n8n/mergeCompanies.test.mjs</automated>
    <automated>git diff --quiet -- n8n/ src/ scripts/ && echo "no production change in Task 1 OK"</automated>
  </verify>
  <done>tests/n8n/mergeCompanies.test.mjs exists and is green; it pins promotion, threshold, domain guard, evidence gate, blank skip, cache keys and the exact return shape; zero production files changed in this commit.</done>
</task>

<task type="auto">
  <name>Task 2: Wave-0 gap B — extract applyCostCap into judge.js, rewire Judge Gate, assert the cap numerically (TA-7)</name>
  <files>n8n/code/judge.js, scripts/build_cloud_workflows.py, n8n/wf_enrichment_local_live.json, tests/n8n/judge.test.mjs, tests/test_judge_spec.py</files>
  <action>
`MAX_SONNET_VALIDATIONS_PER_RUN` is enforced today by a `remaining` counter that lives ONLY inside
a Python multi-line string in the builder, so it has zero tests (confirmed: grepping tests/ for the
env var name returns nothing). Criterion 6 requires the cap be ASSERTED, not documented. Extract it.

In `n8n/code/judge.js`, add and export a pure function `applyCostCap(rows, maxPerRun)`:
- Walks rows in input order, decrementing a budget only for rows whose `needs_judge` is true.
- A row that wants the judge but has no budget left is returned as a NEW object with `needs_judge`
  false and a `judge_capped` true marker. Rows that never wanted the judge pass through untouched.
- `maxPerRun` of 0 or a non-finite value caps everything (this is what lets the kill switch and the
  budget share one code path in the wrapper).
- Never mutates its input; returns a new array.

In `scripts/build_cloud_workflows.py`, rewrite the `ENRICH_JUDGE_GATE` wrapper body (anchor: the
`let remaining = MAX_PER_RUN;` line and the `if (!allowOn || remaining <= 0)` branch below it) into
three explicit passes over the items, which is what makes the extracted function meaningful:
  1. Per row: run the evidence-sufficiency step, then the escalation step, producing a row carrying
     the (possibly demoted) research candidate, `needs_judge` and `judge_reasons`.
  2. Apply the extracted cap function once to that array, passing the budget when the escalation
     kill switch is on and 0 when it is off — one path, no duplicated branch.
  3. Per row: any row that had reasons but ends with `needs_judge` false runs the existing
     unadjudicated fail-safe (this is the D5 behavior the current inline branch already has; it must
     survive the refactor unchanged, including for rows demoted by the cap rather than the switch).
Keep the `$vars`/`$env` reads and the default of 10 exactly as they are.

Extend `tests/n8n/judge.test.mjs` (TA-7): feed 15 synthetic rows whose `needs_judge` is true through
the cap function with a budget of 10 and assert EXACTLY 10 survive with `needs_judge` true, exactly
5 carry the capped marker, and input order determines which. Add: budget 0 caps all 15; rows with
`needs_judge` false are returned unchanged and never consume budget; the input array is not mutated.
Then assert the fail-safe composition directly — a capped row carrying a vendor-flag true, put
through the existing unadjudicated function with its reasons, comes back with that flag null and
its evidence key dropped, never false.

Extend `tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts` with ONE additional
assertion in place (do not create a second test): the Judge Gate node's jsCode must contain the
extracted cap function's name, proving the cost cap is enforced in the node the RO-2 graph-ancestry
assertions already pin as upstream of Merge Company — i.e. the cap is structurally upstream of the
HTTP call, not merely upstream by convention.

Rebuild with the builder and confirm the second run is a byte no-op. Only wf_enrichment_local_live.json
should change.
  </action>
  <verify>
    <automated>node --test tests/n8n/judge.test.mjs tests/n8n/judgeFailure.test.mjs</automated>
    <automated>.venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; .venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; git diff --quiet -- n8n/ &amp;&amp; echo "rebuild byte-no-op OK"</automated>
    <automated>.venv/bin/pytest tests/test_judge_spec.py tests/test_architecture_guard.py -x</automated>
  </verify>
  <done>applyCostCap is a pure exported function; the Judge Gate wrapper uses it via one kill-switch-and-budget path; 15-rows-into-a-10-budget is asserted numerically; capped rows still route through the unadjudicated fail-safe; the RO-2 test now also pins the cap's location; rebuild is a byte no-op.</done>
</task>

<task type="auto">
  <name>Task 3: recencyDate from Anthropic page_age (TA-3) — extract, match, never throw</name>
  <files>n8n/code/webResearch.js, tests/n8n/webResearchFailure.test.mjs, tests/fixtures/research_scoring_cases.json</files>
  <action>
Research candidates carry no recency signal at all today, which is how Wyong's 2021 stream listing
passed the sufficiency gate as current proof. Anthropic already supplies the answer and we already
have it in hand: the HTTP node's raw response `content` array contains `web_search_tool_result`
blocks whose per-result entries carry url, title and `page_age` ("when the site was last updated",
free text, e.g. an English month-day-year string). `researchCandidateFromHttpItem` reads that exact
array today and filters it down to text blocks only, discarding every page_age. Recover them.

In `n8n/code/webResearch.js` add two functions, and export both:
- A url-normalizer for tolerant matching: lowercase, strip protocol, strip a leading `www.`, drop
  query and fragment, drop a single trailing slash. The model's cited url in `evidence_by_field` and
  the search result's own url are two independently-generated strings that usually — not always —
  match exactly. Reuse the same `www.`-stripping shape the citation-sufficiency check already uses
  so the two normalizations cannot drift in opposite directions.
- `extractPageAgeByField(content, evidenceByField)`: build a normalized-url → page_age map from
  every `web_search_tool_result` block's result entries, then for each field in evidenceByField
  return that field's page_age or null. Defensive array/type guards at every level, wrapped so that
  a malformed or adversarial response shape returns an empty object rather than throwing — an
  exception here fails the whole n8n item and breaks the graceful-degradation contract every node in
  this chain relies on (ASVS V5; same never-throws rule researchCandidateFromHttpItem already holds).
  Do NOT parse the date here: pass the raw page_age string through. The scorer's age computation
  already uses Date.parse with a not-a-number guard, so an unparseable value degrades to neutral by
  the existing path and no date library is needed.

Wire it into `researchCandidateFromHttpItem`: after building the provider result, attach
`recency_by_field` (field → page_age string or null) and `recency_source_by_field` (field →
"page_age" when a matching url produced a non-empty value, "unmatched" otherwise). The failure
paths that return an unmatched candidate attach empty objects. Match-rate must be observable in a
future smoke run — a silently-always-null recency looks identical to "the world has no page ages".

Create `tests/fixtures/research_scoring_cases.json` with exactly two top-level keys: `_note` (a
string containing the word "synthetic", see below) and `cases` (the array of rows). Build it from
the REAL rows in
tests/fixtures/evidence_sufficiency_cases.json (same 20 companies, same domains, same citation
urls — Wyong's bets.com.au 2021 listing, QRIC's claim-false row, Supertech Electronics' directory
listing, Australian Turf Club's YouTube channel) and layer on the two fields this phase needs but
that were never recorded live: a synthetic `page_age` and a synthetic `prior_on_file` block
(value + provenance source + verified_at). State in a top-level `_note` key of the fixture AND in
every consuming test's docstring that the page_age and prior values are SYNTHETIC — the 20 runs
predate page_age extraction and did not log what was already on the record, so those values cannot
be reconstructed and must not be read as historical.

Extend `tests/n8n/webResearchFailure.test.mjs`: page_age is extracted for an exactly-matching url;
extracted for a url differing only by protocol / `www.` / a trailing slash / a query string;
null with source "unmatched" for a genuinely different url; empty object (never a throw) for each
of the malformed shapes that file already exercises — an execution-error item, an Anthropic
HTTP-level error body with no content array, a content array containing a search-result block whose
inner content is a string instead of an array, and a result entry with no url. Add a DELIBERATE-BREAK
in the test file: feed a content array shaped to hit the un-guarded path (a search-result block whose
content is null) and assert the function returns an empty object rather than throwing, so removing a
guard turns this red instead of surfacing as a dead n8n item in production.
  </action>
  <verify>
    <automated>node --test tests/n8n/webResearchFailure.test.mjs tests/n8n/parity.test.mjs</automated>
    <automated>node -e "const f=require('./tests/fixtures/research_scoring_cases.json'); if(!f._note||!/synthetic/i.test(f._note)) {throw new Error('fixture must document its synthetic fields')}; console.log('fixture OK', f.cases.length)"</automated>
  </verify>
  <done>page_age is extracted per field via tolerant url matching, exposed as recency_by_field plus an observable recency_source_by_field, and never throws on any malformed response shape; the new fixture carries the 20 real rows with clearly-labeled synthetic recency and prior values.</done>
</task>

<task type="auto">
  <name>Task 4: scoreResearchCandidates + the self-confirmation guard + the asserted tier boundary (TA-1, TA-2, TA-6)</name>
  <files>n8n/code/scoreEnrichment.js, n8n/code/judge.js, scripts/build_cloud_workflows.py, n8n/wf_enrichment_local_live.json, tests/n8n/researchScoring.test.mjs, tests/test_judge_spec.py</files>
  <action>
This is the core of the phase. Re-read <scope_notes> decisions D1, D3 and D4 and the TRAP note
before starting.

**(a) `n8n/code/scoreEnrichment.js` — one additive return key (D4).** Inside the per-field loop,
collect every scored candidate (not just the argmax) into an array; after the loop, sort that array
with the same deterministic tie-break the argmax already uses and expose it as `ranked[field]`.
Return `{ best, winners, ranked }`. Change nothing else — same weights, same components, same
argmax, same tie-break. Existing callers destructure best/winners and must remain byte-identical in
behavior; tests/n8n/enrichment.test.mjs and tests/n8n/parity.test.mjs are the regression proof.

**(b) `n8n/code/judge.js` — export the judge-eligible field list.** It is currently a private
constant. Export it so tests and the boundary check import it instead of hand-typing a third copy
of those five names (the drift TX-4 exists to prevent for the taxonomy — do not reintroduce the
pattern here). Import the scorer at the top of judge.js the same way the other modules do; the
builder strips require lines at inline time, so the Judge Gate node must gain the scorer module in
its inline list (see (d)).

**(c) `n8n/code/judge.js` — add and export `scoreResearchCandidates(researchCandidate, existingRecord, provenance, opts)`.**
For each judge-eligible field carrying a non-blank value in the candidate's data, build:
- The research candidate entry: source `claude_web`, value and normalizedValue both the researched
  value, accuracy = the candidate's confidence divided by 100 when numeric else 0.6, recencyDate =
  that field's entry in the candidate's recency_by_field (Task 3) or null.
- The prior-on-file entry, ONLY when the existing record has a non-blank value for that field:
  source `prior_on_file`, accuracy = that field's provenance confidence divided by 100 when numeric
  else 0.6 (D1), recencyDate = that field's provenance verified_at, falling back to the field's
  top-level `_verified_at` cache-key property, else null.

**THE SELF-CONFIRMATION GUARD (D1) — implement this as the primary structural decision of the
function, not as a filter tacked on afterwards.** Add and export a predicate that decides whether a
prior is of INDEPENDENT origin: a prior with NO provenance entry is independent (a legacy /
pre-pipeline / manually-typed value); a prior whose provenance source is in an explicit allowlist of
independent origins (`human`, `manual`) is independent; EVERYTHING ELSE — including every source our
own pipeline writes — is NOT independent. Unrecognized source strings fail closed to
non-independent: we cannot prove independence, and the failure mode of guessing wrong is invisible
confidence inflation. Then:
- Independent prior → it joins the research candidate in the SAME scoreCandidates call, so the
  agreement component is real in both directions.
- Non-independent prior → it is scored in a SEPARATE scoreCandidates call, alone. A lone candidate
  has no other sources in its group, so the existing engine gives it (and, critically, the research
  candidate in the other call) an agreement component of zero, with no change to the engine at all.
  It still gets its own accuracy/recency/trust components and is still returned for the judge.
Pass trust explicitly: claude_web 0.78 (the claude_web trust rank recorded in
config/source_registry.yaml) and prior_on_file 0.9 (the crm trust rank in the same file); without
this the engine's unknown-source fallback would silently score both at 0.6. Pass `opts.now` through
so the function stays deterministic and injectable — never read the clock inside it.

Return, per field: the ranked candidate array, the research candidate's OWN scored entry (never the
group argmax — the argmax may be the prior, and the value we are grounding is the researched one),
the field's recency source, and a `prior_on_file` object carrying the prior's value, its scored
components and an explicit `independent` boolean. Attach nothing when a field has no research value.

**(d) `scripts/build_cloud_workflows.py` — fold into the Judge Gate node (D3).** Add the scorer
module to the Judge Gate node's inline list, ordered before judge.js. In the wrapper's first pass
(Task 2's step 1), after the evidence-sufficiency step and before the escalation step, call the new
function with the row's existing record, the parsed provenance blob and an injected now, and attach
the result to the row as `research_scoring` for EVERY researched row — including rows that do not
escalate. Criterion 1 is "no information is discarded before the judge", not "no information is
discarded when the judge runs". Parse the provenance blob defensively: it is a JSON string property
that may be absent, empty or malformed; a parse failure yields an empty object and must not throw.

Add a comment at the call site recording the boundary that must hold: this scoring is strictly
additive to the judge's INPUT. It must never become an alternate escalation gate — a high composite
score may never suppress an already-fired escalation reason. The escalation reasons list remains the
sole gate on whether the judge is invoked.

**(e) `scripts/build_cloud_workflows.py` — fetch what the guard depends on.** The company search
property list (anchor: the `properties:` array in the company search body expression, the one ending
with the two verified-at cache keys) currently omits `lv_enrichment_provenance` and three of the five
judge-eligible fields. Without the provenance blob the independence guard has nothing to read and
fails OPEN — every prior would look legacy-and-independent, which is exactly the inflation this task
exists to prevent. Add `lv_enrichment_provenance`, `lv_content_type`, `lv_is_hardware_vendor` and
`lv_is_gambling_operator`. All were created in the Phase 15 migration. Note for the executor: this
widens `existingRecord`, but every one of these fields is system_owned in the merge policy and
system_owned ignores the current value, so no promotion behavior changes — assert that rather than
assume it.

**(f) `tests/n8n/researchScoring.test.mjs` (new)** — drive it from tests/fixtures/research_scoring_cases.json
and import the judge-eligible field list from judge.js rather than retyping it:
- TA-1: a researched field with no prior on file scores on accuracy/recency/trust alone, its
  agreement component is 0, and the components are present on the row whether or not an escalation
  reason fired. Use the Supertech Electronics row (hardware-vendor false positive, no prior) for the
  no-prior case.
- Recency is ordering only: two otherwise-identical rows differing only in synthetic page_age
  (fresh vs the Wyong-style 2021 value) produce different composite scores and the SAME set of
  fields carrying values — nothing is dropped, nothing turns false.
- Unknown recency is neutral: a field whose page_age did not match produces the neutral recency
  component, identical to a field with no evidence url at all — a missing page age is not a penalty.
- **THE GUARD, positive case:** a prior EQUAL to the research value whose provenance source is one
  of our own pipeline sources yields agreement 0 and `prior_on_file.independent` false.
- **THE GUARD, negative control:** the SAME values with NO provenance entry (legacy prior) yields
  agreement 1 and `prior_on_file.independent` true. This pair is the whole proof — without the
  control, an always-zero agreement bug would pass the positive case.
- **THE GUARD, fail-closed case:** a prior whose provenance source is an unrecognized string is
  treated as non-independent.
- **DELIBERATE-BREAK (required):** add the pipeline source to the independence allowlist in a copy
  of the predicate, run the positive case through it, and assert agreement becomes 1 — proving the
  guard is load-bearing and that the positive assertion is not passing for some unrelated reason.
  Do this inside the test with a locally-shadowed predicate; do not edit and restore the source file.
- Disagreement: a prior that DIFFERS from the research value yields agreement 0 whether or not it is
  independent, and the ranked array carries both candidates with both sets of components.
- The ranked array is ordered by the same deterministic tie-break as the argmax, and contains every
  candidate, not just the winner.

**(g) `tests/test_judge_spec.py` — the tier boundary as an asserted invariant (TA-2).** Add a static
test that reads the judge-eligible field list out of the actual n8n/code/judge.js source text by
regex (the same style test_prompt_parity_vendor_flags already uses to read a block out of a source
file) and reads the size watch-list out of the BUILT wf_enrichment_local_live.json Merge Company
node's jsCode by regex. Assert: the two sets are disjoint; the judge-eligible set is exactly the
five expected names; and the judge-eligible set is disjoint from the full deterministic-only set
(the two size bands plus domain, industry, numberofemployees, annualrevenue and the normalized
country region). Do NOT hand-copy either list into a Python literal as the source of truth — read
both from their real homes so a future edit to either cannot drift past this test.
  </action>
  <verify>
    <automated>node --test tests/n8n/researchScoring.test.mjs tests/n8n/judge.test.mjs tests/n8n/enrichment.test.mjs tests/n8n/parity.test.mjs</automated>
    <automated>.venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; .venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; git diff --quiet -- n8n/ &amp;&amp; echo "rebuild byte-no-op OK"</automated>
    <automated>.venv/bin/pytest tests/test_judge_spec.py tests/test_architecture_guard.py -x</automated>
    <automated>node -e "const d=require('./n8n/wf_enrichment_local_live.json'); const n=d.nodes.find(x=>x.name==='Judge Gate'); const js=n.parameters.jsCode; if(!/scoreResearchCandidates/.test(js)) throw new Error('scoring not folded into Judge Gate'); if(/lv_revenue_band|lv_employee_band/.test(js)) throw new Error('size field leaked into Judge Gate'); console.log('Judge Gate fold OK')"</automated>
  </verify>
  <done>Research candidates are scored by the unmodified A/R/G/T engine against a prior on file; a prior written by our own pipeline cannot raise agreement, proven by a positive case, a legacy negative control, a fail-closed case and a deliberate-break; the full ranked set rides on every researched row regardless of escalation; the tier boundary is asserted from the real sources; Judge Gate hosts the fold and carries no size field; rebuild is a byte no-op.</done>
</task>

<task type="auto">
  <name>Task 5: Judge payload grounding + per-field judge confidence + the TS-1 recency-never-gates proof (TA-4, TA-5, TA-6, TA-8)</name>
  <files>n8n/code/judge.js, n8n/code/mergeCompanies.js, scripts/build_cloud_workflows.py, n8n/wf_enrichment_local_live.json, tests/n8n/judge.test.mjs, tests/n8n/mergeCompanies.test.mjs</files>
  <action>
**(a) `buildJudgeRequestBody` — hand the judge the grounding (TA-5).** Add ONE key to the company
object it serializes: the row's `research_scoring`, restricted to the judge-eligible fields. Build
the restriction by iterating the exported judge-eligible list, exactly as the existing restricted
data object does — this is what keeps JG-2 true by construction rather than by review: no numeric
firmographic value can appear in the payload because no such field is ever in the list. Do not add
a tools key and do not touch the existing keys.

**(b) The prompt must label the prior honestly (TA-6).** Append to the existing system prompt array
a statement that: the scoring object shows how the research candidate compares to the value already
on file; the recency term is ordering information (higher = fresher evidence) and is NOT a reason to
reject a claim, because a fact can be stable for decades and is not wrong for being old; and the
prior on file is NOT an independent corroborating source — it is what is already recorded, which may
itself derive from an earlier unverified research pass, so agreement with it is not evidence and the
decision must be grounded in the cited urls only. Keep it to the existing prompt's clipped register.

**(c) `n8n/code/mergeCompanies.js` — the additive per-field confidence option (TA-8, re-scoped per D2).**
Read an optional `opts.confidenceByField` map. Inside the per-field loop, that field's entry wins
over the flat `opts.confidence` when present; otherwise the existing flat value and its 80 default
apply exactly as today. Two lines. Every current caller omits the key and is therefore byte-identical.
Use the resolved per-field value everywhere the flat one is used today — the gate threshold, the
provenance entry and the decision record — so the recorded confidence and the confidence that made
the decision can never disagree.

**READ D2 BEFORE WIRING THIS.** The A/R/G/T composite MUST NOT be what flows into this map. It is a
0-1 value against 0-100 thresholds calibrated on model self-reported confidence, and it contains the
recency term — routing it into the gate would both violate the locked "recency is ordering bias only"
decision and, arithmetically, stop nearly every research promotion in the pipeline. What flows in is
the JUDGE VERDICT's confidence for the single field the judge adjudicated: correct scale, per-field
by construction, and currently discarded outright.

**(d) `scripts/build_cloud_workflows.py` — propagate the verdict confidence.** In the Apply Judge
Verdict wrapper, when a verdict promoted or confirmed a field, record that field and the verdict's
confidence on the row. In the Merge Company wrapper's research fold (anchor: the second
mergeCompanies call, the one whose source is claude_web), pass that as confidenceByField alongside
the existing flat confidence. Everything not adjudicated keeps the flat retrieval confidence. The
verdict-minimum rule already guarantees only sufficiently-confident verdicts reach this point.

**(e) `tests/n8n/judge.test.mjs` — payload assertions.** The scoring key appears in the serialized
body; it contains only judge-eligible fields even when the row's scoring carries an extra field;
none of the size-band or numeric firmographic names appears anywhere in the serialized body (assert
against the full JSON string, not just the object, so a name hiding inside the prompt is caught);
the prompt names the prior-on-file label and says agreement with it is not evidence; there is still
no tools key; and a row with no scoring at all still produces a valid body.

**(f) `tests/n8n/mergeCompanies.test.mjs` — the additive-option proof AND the TS-1 proof.**
- Additive: with the option absent, the result is deep-equal to the Task 1 characterization result
  for the same input (modulo the timestamp) — the waterfall path is unaffected.
- Override: an entry in the map raises one field above its threshold so it promotes while a second
  field, absent from the map, still uses the flat confidence and still does not.
- Recorded confidence matches deciding confidence: the provenance entry and the decision record for
  an overridden field both carry the overridden value, not the flat one.
- **TA-4 / TS-1 / criterion 5 — the load-bearing proof.** Run the same research candidate through
  the merge twice, differing ONLY in synthetic page_age (fresh vs years-stale, hence very different
  composite scores) and assert the two canonicalPatch objects are IDENTICAL — recency changed the
  ranking and changed nothing else. Then assert, across every case in the new fixture, that no field
  anywhere in any canonicalPatch or provenance value is boolean false as a result of scoring or
  recency: a demotion may only move a value toward null.
- **DELIBERATE-BREAK (required):** in the test, wire the composite score (times 100) into
  confidenceByField for the stale row and assert the previously-promoted field STOPS promoting.
  This proves both that the identical-patch assertion above has teeth and that D2's rejection of
  RESEARCH's literal TA-8 was arithmetically necessary, not stylistic. Leave a comment naming D2.

Rebuild and confirm the second run is a byte no-op.
  </action>
  <verify>
    <automated>node --test tests/n8n/judge.test.mjs tests/n8n/mergeCompanies.test.mjs tests/n8n/researchScoring.test.mjs</automated>
    <automated>.venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; .venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; git diff --quiet -- n8n/ &amp;&amp; echo "rebuild byte-no-op OK"</automated>
    <automated>.venv/bin/pytest tests/test_judge_spec.py -x</automated>
  </verify>
  <done>The judge receives the ranked set and its components restricted to judge-eligible fields, with the prior explicitly labeled non-independent in the prompt; mergeCompanies gained one additive per-field confidence option carrying the judge verdict's confidence; recency provably changes ranking and nothing else, proven by an identical-patch assertion plus a deliberate-break that makes the composite gate and shows promotions collapsing.</done>
</task>

<task type="auto">
  <name>Task 6: Spec §8.5 (TA-1..TA-8) + Requirements→Test map + STATE/ROADMAP + full-suite gate</name>
  <files>docs/WEB-RESEARCH-SPEC.md, .planning/STATE.md, .planning/ROADMAP.md</files>
  <action>
No new production code. Close the phase against the repo's own rule — stated in the spec's own
header — that a requirement with no test is a spec bug and a test with no requirement is scope creep.

**docs/WEB-RESEARCH-SPEC.md** — add a `## 8.5 Tiered adjudication` section immediately after §8,
extending JG-1..JG-5 rather than restating them, with these eight requirements (adjust the wording
to match what actually shipped; the requirement is the contract, not the aspiration):
- TA-1: every research candidate for a judge-eligible field MUST be scored by the existing A/R/G/T
  engine before any merge or judge decision, and its components MUST be attached to the row even
  when no escalation trigger fires.
- TA-2: the size/firmographic set MUST NEVER be scored against or routed to the judge; the
  judge-eligible set is exactly the five classification fields; the two sets MUST be disjoint,
  asserted by a static conformance test that reads both lists from their real homes rather than a
  hand-typed copy.
- TA-3: recencyDate MUST come from the Anthropic search result's page_age for the matching evidence
  url — never the model's free-text self-report, never parsed out of the url string. Absent or
  unparseable yields null and inherits the existing neutral recency rule; no new penalty path.
- TA-4: recency is an ordering input to the composite score ONLY (extends TS-1). No code path may
  use recency, page age or staleness to set a field false, to fire the anti-ICP flag, or to move
  the confidence-based promotion gate. Record the arithmetic reason as normative rationale: the
  composite is 0-1 and the promotion thresholds are 0-100 calibrated against model self-reported
  confidence, so the two MUST NOT be mixed.
- TA-5: the judge payload MUST include the scored components and composite for every judge-eligible
  field the escalation carries, restricted to that field set (extends JG-2 to the new key).
- TA-6: the synthetic prior on file is NOT an independent corroborating source. It MUST be labeled
  distinctly in the payload and the prompt, the prompt MUST instruct the judge not to treat
  agreement with it as evidence, and a prior written by this pipeline MUST NOT contribute to the
  agreement component at all. Independence is determined by the provenance source, ambiguity fails
  closed, and a prior with no provenance entry counts as independent legacy data.
- TA-7: judge invocations per run MUST be capped, and the cap logic MUST be a unit-testable pure
  function rather than inline code inside a build-script string, asserted by a test that exceeds the
  cap and checks the exact overflow count falls through the existing unadjudicated fail-safe.
- TA-8: mergeCompanies MUST accept an additive per-field confidence map, used to carry an
  adjudicated per-field confidence on the correct 0-100 scale; the flat whole-candidate confidence
  remains the default, and the waterfall call path is byte-identical.

Then add a `### Requirements → Test map` table under §8.5 listing each TA-ID against the exact test
file and test name that proves it, using the names as they actually exist after Tasks 1-5. Verify
every row by running the named test before writing the row down — Phase 12 shipped two verify bugs
and Phase 15's live run exposed three more that offline tests missed; a map that names a test which
does not exist is the same class of defect.

**.planning/STATE.md** — HAND-EDIT ONLY. Do NOT run the state-update-progress tool; it miscounts
because three concatenated ROADMAP milestones are present. Set the phase forward, record: the two
corrected roadmap premises; decision D1's self-confirmation guard and why it exists; decision D2's
rejection of RESEARCH's literal TA-8 with the 67-versus-80 arithmetic; decision D4's additive
ranked key; and the carried-forward items (dead evidence.last_seen not removed; composite not
persisted into the provenance blob; contacts branch untouched). Update the plan/phase counts to
include this inserted phase.

**.planning/ROADMAP.md** — use scoped Edit, never Write. Check off Phase 15.5's six criteria, set
its Plans line to 1 plan with this file listed, and add its row to the Milestone 3 progress table.

Full-suite gate: pytest and the node suite both green with no regressions against the 200/77
baseline, and no test making a live network call.
  </action>
  <verify>
    <automated>.venv/bin/pytest -q</automated>
    <automated>node --test tests/n8n/*.test.mjs</automated>
    <automated>.venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; .venv/bin/python scripts/build_cloud_workflows.py &amp;&amp; git diff --quiet -- n8n/ &amp;&amp; echo "deterministic OK"</automated>
    <automated>test "$(grep -c '^\*\*TA-[1-8]\.\*\*' docs/WEB-RESEARCH-SPEC.md)" -eq 8 &amp;&amp; echo "TA-1..TA-8 present OK"</automated>
  </verify>
  <done>Spec §8.5 carries TA-1..TA-8 plus a Requirements→Test map whose every named test was run and exists; STATE.md hand-edited with the corrected premises and the four planner decisions; ROADMAP criteria checked off and the progress table updated; full offline suite green with no regressions and no live calls; rebuild deterministic.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Anthropic web_search response → Judge Gate / Validate Research Output Code nodes | untrusted, model-and-crawler-shaped JSON crosses here; block shapes and page_age strings are not schema-guaranteed |
| HubSpot record (lv_enrichment_provenance blob) → scoring | a stored JSON string, possibly stale, truncated at the 60000-char cap, or absent, is parsed and drives a trust decision |
| scoring output → judge payload → Anthropic Messages API | classification-only data crosses to a paid model call; JG-2 forbids numeric firmographics crossing it |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-15.5-01 | Denial of Service | extractPageAgeByField on a malformed/adversarial Anthropic content array | medium | mitigate | Defensive guards at every level + a wrapping catch returning an empty object; an exception in a Code node fails the whole item and breaks the continue-on-error contract this chain relies on. Proven by the Task 3 deliberate-break. |
| T-15.5-02 | Tampering (of the trust model) | prior_on_file agreement read as independent corroboration, silently inflating composite confidence and weakening the effective review threshold | high | mitigate | D1's independence predicate, fail-closed on unrecognized sources; proven by a positive case, a legacy negative control, a fail-closed case and a deliberate-break (Task 4f). |
| T-15.5-03 | Tampering | the composite score becoming a promotion gate, making recency a de-facto staleness veto and collapsing promotions | high | mitigate | D2: the composite never reaches mergeCompanies; the identical-canonicalPatch assertion plus the Task 5f deliberate-break prove both directions. |
| T-15.5-04 | Elevation of Privilege | a size/firmographic disagreement reaching a paid model call | high | mitigate | Structural, not documentary: the fold lands in the node the existing RO-2 graph-ancestry + jsCode-absence test already pins upstream of Merge Company; Task 4's verify additionally greps the built node for size-band names. |
| T-15.5-05 | Denial of Service (cost) | unbounded judge invocations on a large run | medium | mitigate | TA-7's extracted cap function, enforced physically upstream of the HTTP node, asserted numerically at 15-into-10 and at a zero budget. |
| T-15.5-06 | Information Disclosure | a numeric firmographic value leaking into the judge prompt via the new scoring key | medium | mitigate | The payload key is built by iterating the judge-eligible list, so JG-2 holds by construction; asserted against the full serialized body string, not just the object. |
| T-15.5-SC | Tampering | npm/pip installs | low | accept | No new packages. RESEARCH confirms zero new dependencies — no date library (the existing parse-with-guard path covers page_age), no test framework. No install task exists in this phase, so the package-legitimacy checkpoint does not apply. |
</threat_model>

<verification>
- `.venv/bin/pytest -q` and `node --test tests/n8n/*.test.mjs` green, no regressions against the
  200 pytest / 77 node baseline, zero live network calls in any test.
- `.venv/bin/python scripts/build_cloud_workflows.py` twice → `git diff --quiet -- n8n/`.
- `test_top_level_is_exactly_the_deployable_set` green; only wf_enrichment_local_live.json changed.
- `test_ro2_judge_gate_cannot_see_size_conflicts` green UNCHANGED in its existing assertions, with
  the one added cap-location assertion.
- The Judge Gate node's jsCode contains the scoring call and no size-band field name.
- The self-confirmation guard proven by four cases: pipeline-source prior → agreement 0; legacy
  no-provenance prior → agreement 1; unrecognized source → non-independent; deliberate-break
  allowlisting the pipeline source → agreement 1 (guard is load-bearing).
- Fresh-vs-stale page_age produce identical canonicalPatch; the deliberate-break that gates on the
  composite makes promotion collapse.
- Every TA-ID in spec §8.5 names a test that was run and exists.
</verification>

<success_criteria>
- C1 (scoring ranks, never decides): research candidates carry ranked A/R/G/T on every researched
  row regardless of escalation; the composite never touches the promotion gate.
- C2 (tiered routing tested): the judge-eligible and deterministic-only sets asserted disjoint from
  their real sources; no size field in the Judge Gate node.
- C3 (judge grounding): the payload carries the ranked set + components + evidence, restricted to
  judge-eligible fields, with the prior labeled non-independent in payload and prompt.
- C4 (recencyDate): sourced from page_age with observable match rate; unknown stays neutral.
- C5 (TS-1 holds): no recency or scoring path can yield false; identical-patch proof + deliberate-break.
- C6 (cost bounded and proven): cap is a pure tested function asserted at 15-into-10 and at zero;
  size-only disagreement cannot trigger a model call, proven structurally.
- Spec §8.5 TA-1..TA-8 authored with a verified Requirements→Test map; STATE/ROADMAP updated.
</success_criteria>

<output>
Create `.planning/phases/15.5-tiered-candidate-adjudication/15.5-01-SUMMARY.md` when done. Commit
each task atomically as `feat(15.5-01): <task summary>` with trailer
`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
</output>
