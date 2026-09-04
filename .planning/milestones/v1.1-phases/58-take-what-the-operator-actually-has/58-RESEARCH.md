# Phase 58: Take What the Operator Actually Has - Research

**Researched:** 2026-08-26
**Domain:** Extending an existing Claude-as-extractor + n8n-waterfall enrichment plugin
(operator-claude-plugin) from contacts-only input handling to companies, plus a new
confirm-before-write domain-resolution lane.
**Confidence:** MEDIUM — the contact-lane precedent is HIGH confidence (read directly), but
the two load-bearing architectural questions (whether the existing backend research node can
return a domain candidate without a workflow change, and whether "propose mode" already
reaches companies) are traced from code but not executed live. Flagged explicitly below as
Task-0/spike material.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Who researches the domain**
- D-58-01: Claude proposes, backend verifies selectively. Claude in-conversation proposes a
  domain from what it already knows/sees (free, instant, marked unverified). The backend's
  companies-branch `Claude Web Research` node runs only for rows Claude cannot confidently
  propose, or where the operator says "not sure, check it".
- D-58-02: Operator confirmation substitutes for backend verification. A domain the operator
  confirms in the table is written without a research call — consent is the gate, not a
  second model pass.
- D-58-03: A LinkedIn/profile URL may seed research as input only (company name, industry off
  the page). It is never passed through as a domain — the `NOT_A_COMPANY_DOMAIN` guard
  (mirrored Python↔JS) is unchanged. Reversibility: one-way in spirit — weakening this guard
  re-opens the LinkedIn domain-poisoning defect the 2026-08-25 walk found; any change needs an
  operator ruling.

**Confirm-before-write shape**
- D-58-04: Batch table with per-row control. One table: company name, proposed domain, where
  it came from. One scoped approve covers the batch; the operator can pick/deny/correct
  individual rows first. Matches the existing pre-ingest match-proposal-confirm pattern and
  the bulk-approve-with-scope-restated rule. VOCAB-05 consent binding applies: the affirmative
  answers this shown table, ambiguity = not armed.
- D-58-05: Evidence per row = source + one-line reason (e.g. "official site linked from their
  LinkedIn"). Evidence URL shown when the backend researched it. No full ProviderResult
  evidence block in the table.
- D-58-06: A denied proposal falls back to the 0.16.0 accept-by-name path: row proceeds with
  blank domain via name lookup / exact-name company search, disclosed in the report. The
  operator may instead type the correct domain in place. Denied never means dropped (INPUT-04).
- D-58-07: An operator-typed domain passes the existing syntax / `NOT_A_COMPANY_DOMAIN` /
  freemail guards only — no research pass. Operator is the highest-trust source (trust_rank
  100, same as the review lane). The guard still refuses linkedin.com, gmail.com, etc. even
  from the operator.

**Research cost consent**
- D-58-08: Backend domain research is its own envelope line — "domain research: N companies ×
  ~$Y" — and names WHICH rows need it. Fits D-53-02 disclosure discipline and cost_guard's
  per-provider breakdown.
- D-58-09: Research is default-on, declinable: rows needing it are priced into the envelope
  automatically and the single batch yes covers it, unless the operator strikes the line
  (INPUT-02: the system finds one rather than asking the operator to).
- D-58-10: Declining the research line gives those rows the same name-only fallback as a
  denied proposal (D-58-06) — one consistent degradation path for every no-domain outcome.

**Company extraction contract**
- D-58-11: Minimum identity for an extracted company row is name alone. Domain is desirable
  and researched when absent. Refuse only when there is literally nothing to act on.
- D-58-12: Extraction captures enrichment seeds only beyond name + domain: country, industry,
  website URL when the source shows them. The no-invention rule (Phase 35, `extraction.md`)
  applies verbatim: a field the source does not supply is left out; the waterfall fills the
  rest. No employee counts / revenue capture.
- D-58-13: Mixed input runs one extraction pass, both lanes. A paste/screenshot holding people
  AND companies is read once; contact rows flow the existing contact lane, company rows the
  new company lane, companies-first ordering (operator ruling 2026-08-25) preserved.
- D-58-14: Source types at parity with the contact lane: pasted text, foreign JSON, public
  URL, screenshots — plus two named explicitly: a bare name list (one per line /
  comma-separated) and a search-results-page screenshot (multiple candidate companies per
  image, each its own row with provenance).

### Claude's Discretion
- Exact table rendering, wording of the confirm question, and how "check it" requests are
  phrased — bound by VOCAB-01..03 (consequence language, no system vocabulary).
- Confidence heuristic for when Claude declines to propose and routes to backend research.
- Handling of an ambiguous company name matching two portal records (existing rule: two
  matches = ambiguity, not a match — extend, don't reinvent).

### Deferred Ideas (OUT OF SCOPE)
- Contact review-flag clearing lane — deferred to Phase 54 (rides with single-pass dispatch
  work).
- Suggested contacts (Phase 59).
- Single-pass dispatch (Phase 54).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INPUT-01 | A company can be named by anything the operator holds: screenshot, pasted text, URL, bare name. | Contact-lane adapters (`extraction.md`) are the verbatim template; §"Extraction machinery" below maps each adapter to its company equivalent and names the one adapter (bare-name list) with no contact-lane analog at all. |
| INPUT-02 | When no usable domain is present, the system finds one rather than asking the operator to. | §"The domain-research call is not a drop-in reuse" is the load-bearing finding: the existing `Claude Web Research` node cannot return a domain today without a schema/prompt extension. §"Propose mode already exists, unplumbed" gives the mechanism for getting a candidate back without writing. |
| INPUT-03 | A researched domain is confirmed before it is written. | §"The pre-ingest match-proposal-confirm pattern" gives the exact reusable shape (`DECLINE_MATCH` sentinel, `apply_match_decisions`); §"No company-side propose lane exists yet" states plainly this is new client-side surface, not a wire-up of an existing one. |
| INPUT-04 | A refusal is a last resort and always names what would make it work. | `build_envelope`'s companies branch already implements this for the no-domain-no-research case (0.16.0, verified — accept-by-name refusal wording read directly). Phase 58 extends the same refusal-with-guidance style to new adapters. |
</phase_requirements>

## Summary

This phase has almost no external-library research surface — it is 100% in-repo extension of
a Claude-as-extractor plugin (`operator-claude-plugin/`) plus one exploratory question about
an existing n8n Cloud workflow's research node. The contact lane this phase must mirror is
fully built, well-documented, and heavily tested (`extraction.md`, `extraction.py`,
`preingest.py`); reading it end to end is the actual research task, and it is now done.

Two verified findings should reshape how the planner scopes this phase, because they
contradict what the phase description and CONTEXT.md imply is a straightforward reuse:

1. **The existing companies-branch `Claude Web Research` node cannot return a domain today.**
   Its system prompt asks for seven ICP signals (`lv_org_type`, `lv_produces_content`, etc.)
   and its trigger (`needsResearch`) fires on those being blank — never on a missing domain.
   `domain` itself is `class: manual_protected` in `config/field_policy.yaml`
   (`promote_to_canonical: false`), and the only place a company's `domain` property is ever
   written is the create path, seeded from `identity_keys.domain` — which comes from the
   caller's own envelope input, never from research. "Researching a company's own website...
   is the same call" (REQUIREMENTS.md, INPUT-02) is the target state, not the current state.
   Making it true needs a small, disclosed n8n prompt/schema extension — not a big one, but a
   real one, and it must be planned and disclosed as such, not assumed free.

2. **There is no existing "propose mode" plumbing for companies on the client side, but the
   backend infrastructure for it already exists and is unused.** `isReturnOnly(mode)`
   (`n8n/code/matchProposal.js`) already gates the companies branch's `Decide Company Action`
   node (verified at two call sites in `build_cloud_workflows.py`) — any `row.mode` other than
   the literal `"write"` makes a company row run the full pipeline (providers, research,
   judge) and return `properties` without a HubSpot PATCH. But `enrichment.build_envelope`'s
   `"companies"` spec form never sets `mode` on an event today. Wiring this through is very
   likely a **plugin-only** change (Python, `enrichment.py`), not an n8n change — this is the
   cheapest path to "research without writing," and the planner should spike-confirm it in
   Task 1 before committing to any workflow edit.

Everything else — the extraction adapter shape, the no-invention rule, the confirm-table
pattern, the cost-envelope shape, the `NOT_A_COMPANY_DOMAIN` guard — is a direct, well-tested
template to extend, not a new design.

**Primary recommendation:** Treat this phase as two work-shapes with very different risk:
(a) extending the extraction contract to companies — low-risk, template-driven, plugin-only;
(b) making the backend return a confirmable domain candidate without writing — genuinely novel,
needs a Task-1 spike to determine whether it is achievable plugin-only (`mode` passthrough) or
requires an n8n workflow change (domain-seeking prompt + schema), and the answer changes the
phase's cost and risk profile materially.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Read pasted/JSON/URL/screenshot input, write company rows | Client (Claude, in-conversation) | — | D-01/D-02: Claude IS the extractor; no API call, no OCR lib. Identical tier to the existing contact lane. |
| Validate extracted rows structurally (provenance, identity, no-invention contradiction) | Client (plugin script, `extraction.py`) | — | Pure Python, no network; mirrors the contact validator exactly. |
| Propose a domain from what Claude already saw | Client (Claude, in-conversation) | — | D-58-01: free, instant, unverified-marked. Zero backend cost. |
| Research a domain Claude could not confidently propose | Backend (n8n Cloud, `Claude Web Research` node) | Client (envelope/cost-guard gate before dispatch) | The call itself must run server-side (Anthropic web_search tool lives in the n8n workflow, not the plugin — D-01/D-02 forbids a second API surface in the plugin). The client's job is deciding *whether* to spend the call (cost consent), not making it. |
| Confirm-before-write batch table (pick/deny/correct) | Client (plugin script + skill prose) | — | Same tier as the existing pre-ingest match-proposal-confirm lane (`preingest.py`) — pure decision-application logic, no network. |
| Write the confirmed domain / create the company | Backend (n8n Cloud, `Decide Company Action` node, `wf_enrichment_cloud`) | — | Unchanged: company creation stays exclusively in the companies branch of `wf_enrichment_cloud` per CLAUDE.md §13.0.1 — this phase feeds it better-resolved inputs, it does not move creation. |
| Cost/consent gate for the research line | Client (`cost_guard.py` + a new envelope-line concept) | — | Every existing cost-disclosure precedent (D-53-02, cost_guard) lives client-side, before dispatch. |

## Extraction machinery — the template being extended

**Read directly:** `operator-claude-plugin/skills/contact-upload/extraction.md` (330 lines)
and `operator-claude-plugin/scripts/extraction.py` (632 lines), in full.

### What exists today (contacts only)

- **No model call, ever.** `extraction.md`: *"There is no Anthropic API call, no API key
  anywhere in this plugin, and no extraction library... you, the assistant already running
  this conversation, are the extraction engine."* [VERIFIED: operator-claude-plugin/skills/contact-upload/extraction.md:10-15]
- **The no-invention rule** (three sub-rules: never fill a blank from world knowledge, put
  unclear values in an ambiguity list rather than the row, never invent a value just to pass
  the identity check). [VERIFIED: operator-claude-plugin/skills/contact-upload/extraction.md:17-34]
- **Handoff-file protocol:** Claude writes one JSON artifact to `scratch/`, then runs
  `python3 scripts/extraction.py <path>` and relays its JSON stdout — never a fenced block in
  chat. [VERIFIED: operator-claude-plugin/skills/contact-upload/extraction.md:36-54]
- **Artifact schema:** `{batch_id, source: {kind, detail}, records: [{row, provenance}],
  ambiguities: [...]}`. `kind` is one of `"prose"|"json"|"url"|"screenshot"`.
  [VERIFIED: operator-claude-plugin/skills/contact-upload/extraction.md:12-13,58-69]
- **Canonical props (contacts):** exactly `company, email, firstname, jobtitle, lastname,
  linkedin_url, phone`, plus the routing-only `company_id` (never written to HubSpot as a
  property). [VERIFIED: operator-claude-plugin/skills/contact-upload/extraction.md:119-133]
  These are sourced from `config/column_mapping.yaml`'s `aliases` map, never hard-coded in
  `extraction.py`: `canonical_props()` reads `data.get("aliases")` and returns the
  deduplicated values. [VERIFIED: operator-claude-plugin/scripts/extraction.py:113-118]
- **Identity rule (contacts):** `required_identity.any_of: [[email], [firstname, lastname,
  company]]` — read verbatim from the same YAML, never retyped in Python.
  [VERIFIED: operator-claude-plugin/config/column_mapping.yaml:59-62]
  [VERIFIED: operator-claude-plugin/scripts/extraction.py:121-126]
- **Four adapters, one per source kind:** pasted freeform text, foreign-shaped JSON, a public
  URL (native `web_fetch` tool only — no HTTP client, no scraping library, with a documented
  escalation ladder via `scripts/url_fallback.py` capped at 5 follow-up fetches), and
  operator-supplied screenshots (Claude reads images directly; **never** drives a browser or
  captures a page itself). [VERIFIED: operator-claude-plugin/skills/contact-upload/extraction.md:135-330]
- **Validator (`extraction.py`) does exactly four things, in order:** per-record structural
  pre-flight (provenance present, non-canonical keys stripped-and-reported, identity rule
  satisfied) → `dedupe()` (exact-match collapse across an identity group, near-duplicate
  ambiguity surfacing, never a similarity score) → ambiguity aggregation → D-07 contradiction
  rejection (a row that flags a field as ambiguous yet still carries a value for it is
  rejected). [VERIFIED: operator-claude-plugin/scripts/extraction.py:393-511]

### What a company adapter set needs that the contact one does not

- **A different identity rule.** D-58-11 sets company identity at "name alone." The contact
  identity rule (`email` OR `firstname+lastname+company`) is a completely different shape and
  is read from ONE shared YAML file (`column_mapping.yaml`) with ONE `required_identity.any_of`
  list. There is no `object_type`-scoped identity concept in `extraction.py` today —
  `identity_groups()` and `canonical_props()` both take a single flat mapping.
  [VERIFIED: operator-claude-plugin/scripts/extraction.py:113-126] The planner must decide
  between: (a) a parallel `config/company_column_mapping.yaml` + a second code path through
  `extraction.py` selected by a `record_type`/`object_type` field on the artifact, or (b) one
  shared file with per-type sections. Given D-58-13 (one extraction pass, both lanes in one
  artifact), option (a) with a per-record discriminator is the more natural fit — but this is
  new validator logic, not a config-only extension, and should be its own task.
- **A different canonical prop set with no overlap risk.** Company props (`name`, `domain`,
  `country`, `industry`, `website` — per D-58-12) share no names with the contact set, so the
  two can coexist in one artifact without collision once the validator is type-aware.
- **Two adapters with no contact-lane precedent:** a bare name list (one name per line/comma)
  and a search-results-page screenshot (multiple companies per image). Both are named
  explicitly in D-58-14 and need new prose in `extraction.md`, but structurally they reuse the
  existing "pasted freeform text" and "screenshot" adapters' mechanics (identity rule is the
  only real difference — a bare name alone already satisfies D-58-11).
- **D-07 (extraction.py)'s contradiction check, `dedupe()`'s exact-match collapse, and the
  ambiguity-aggregation pass are all identity-group-driven** — verified they operate purely
  off `identity_groups()`'s output with no assumption baked in about which fields those groups
  contain [VERIFIED: operator-claude-plugin/scripts/extraction.py:138-338]. This means once a
  company-scoped identity group is definable, these three mechanisms should extend to company
  rows with no rewrite — a genuinely reusable piece of the machinery, not just a template to
  copy.

## The company lane as it exists (backend)

### `build_envelope`'s companies form (0.16.0, already shipped)

Read directly: `operator-claude-plugin/scripts/enrichment.py:319-364`.

- **Domain is desirable, not mandatory, for the general case; mandatory only for create.**
  The comment states plainly: *"a domainless company can neither be deduped nor matched — it
  could only ever be created, which is the duplicate-company shape this form exists to
  avoid... only the CREATE path still needs a domain."*
  [VERIFIED: operator-claude-plugin/scripts/enrichment.py:322-346]
- **A company with a name but an unusable/profile-page domain is accepted, not refused,** and
  routed to the backend's exact-name search: *"a company with no usable domain is ACCEPTED
  when it has a name — the backend's exact-name company search (added 2026-08-25) can resolve
  it."* [VERIFIED: operator-claude-plugin/scripts/enrichment.py:333-338]
- **The refusal message already names what would fix it** (INPUT-04's pattern, already live):
  when a company has neither name nor usable domain, or has an unusable domain and no name,
  the raised `RecordSpecError` states the given value was "a profile page rather than a
  company's own website" and instructs "Give the company's name — the backend can match that
  on its own." [VERIFIED: operator-claude-plugin/scripts/enrichment.py:348-355]
- **`_clean_domain`'s `NOT_A_COMPANY_DOMAIN` guard is the Python mirror of the deployed n8n
  guard**, and the comment records the exact defect this phase's D-58-03 keeps closed: a
  LinkedIn company URL naively reduced to `linkedin.com` would search for and then create a
  company whose domain IS `linkedin.com`, which every future LinkedIn-sourced company would
  then match against — "one bad row swallowing every future company, with no error anywhere."
  [VERIFIED: operator-claude-plugin/scripts/enrichment.py:159-176] The 20-entry frozenset
  (`linkedin.com, lnkd.in, facebook.com, fb.com, instagram.com, twitter.com, x.com,
  youtube.com, youtu.be, tiktok.com, threads.net, medium.com, crunchbase.com, wikipedia.org,
  en.wikipedia.org, bloomberg.com, zoominfo.com, apollo.io, abn.business.gov.au, linktr.ee,
  about.me, sites.google.com, wixsite.com, squarespace.com, godaddysites.com`) is
  byte-identical between `operator-claude-plugin/scripts/enrichment.py:170-176` and
  `n8n/code/companyLink.js:47-53` — both read and diffed line by line, confirmed identical
  membership.

### The domain-research call is not a drop-in reuse

This is the phase's central open technical question, and it is answered here with citations,
not assumed:

- The companies-branch research trigger (`gap_predicate_js` for `COMPANIES_TARGET`) fires
  only on `lv_org_type` unresolved OR `lv_produces_content` blank — **it has no dependency on
  whether `domain` is present.** [VERIFIED: scripts/build_cloud_workflows.py:2333-2342,
  quoted: `"RT-3: fires when lv_org_type is unresolved/evidence-gated, OR
  lv_produces_content blank."`]
- The research request payload sends `company: {name, domain}` **as input** (`id.domain ||
  row.domain || null`) — domain is something the call assumes it already has, not something
  it is asked to produce. [VERIFIED: scripts/build_cloud_workflows.py:2389-2393]
- `required_fields` sent to the model is exactly `["lv_org_type", "lv_produces_content",
  "lv_content_type", "lv_is_hardware_vendor", "lv_is_gambling_operator",
  "lv_sponsorship_reliant", "lv_country_region_normalized"]` — **no domain/website field
  anywhere in this list.** [VERIFIED: scripts/build_cloud_workflows.py:2395-2397]
- The system prompt (`researchSystemPrompt()`) instructs three query intents (identity,
  content, size) and defines the exact JSON shape the model must return — again, no `domain`
  or `website` field in the schema it specifies.
  [VERIFIED: scripts/build_cloud_workflows.py:2354-2382, the literal schema string quoted at
  2377-2381: `'{"data":{"lv_org_type":<str>,"lv_produces_content":<bool|null>,...}'`]
- `validateResearchOutput` (the JS validator, `n8n/code/webResearch.js:21-64`) only
  normalizes five named fields (`lv_org_type`, `lv_content_type`, `lv_produces_content`,
  `lv_country_region_normalized`, `entity_resolution`) but does a **wholesale spread** of
  `raw.data` first (`const data = { ...(raw.data || {}) }`, line 32) — meaning if the prompt
  were extended to ask for a `domain`/`website` field and the model complied, that value would
  survive validation untouched (it is neither stripped nor specially handled). This is the
  cheapest technical lever available: the validator does not need to change to carry a new
  field through; only the **prompt and required_fields list** need to ask for it.
  [VERIFIED: n8n/code/webResearch.js:21-64]
- **`domain` is `class: manual_protected` in the live field policy**
  (`promote_to_canonical: false, stage_only: true, min_confidence: 95`)
  [VERIFIED: config/field_policy.yaml:4-8]. Even if a researched domain flowed through
  `Merge Company`'s candidate set, this field policy would prevent it from ever being written
  to the canonical `domain` property automatically — it can only ever be staged. This is
  actually the correct shape for D-58-02/D-58-03 (never write a domain without operator
  confirmation) but it also means the response would need to surface the STAGED value (e.g.
  a `claude_web_domain`-style key) back to the caller for the confirm table — whether that
  staging key currently exists for companies research responses, and whether it is present in
  the API response body for a non-writing call, is unconfirmed and should be the first thing
  Task 1 checks against a live disarmed call.
- **Conclusion, stated plainly for the planner:** getting a domain candidate out of the
  existing `Claude Web Research` node requires extending `researchSystemPrompt()`'s schema
  and `required_fields` (a `build_cloud_workflows.py` change — n8n build, deploy, bounce), or
  building a second, lighter-weight research call scoped to domain-only. It is NOT already
  "the same call" in practice today, contrary to how REQUIREMENTS.md's INPUT-02 frames it.
  This should be disclosed to the operator as a real (if small) piece of n8n work, not
  described as a wiring exercise.

### Propose mode already exists, unplumbed

- `isReturnOnly(mode)`: *"mode absent/null or the write literal... is false (today's write
  behaviour); every other value — including a typo — is true (return-only). That asymmetry is
  the fail-safe."* [VERIFIED: n8n/code/matchProposal.js:148-158, function body quoted:
  `if (mode === undefined || mode === null) return false; return
  String(mode).trim().toLowerCase() !== "write";`]
- This predicate gates the companies branch's own `Decide Company Action` node, called at
  `const returnOnly = isReturnOnly(row.mode);` at two sites.
  [VERIFIED: scripts/build_cloud_workflows.py:1566, 3130]
- When `returnOnly` is true, action is forced to `"proposed"` **before** the write-safety
  allowlist check runs, and the comment explicitly notes companies have no match-tier
  concept to demote: *"No medium-tier guard here: the companies branch has no match lane
  (Task 1's is contacts-only)."* [VERIFIED: scripts/build_cloud_workflows.py:3234-3242]
- `Build Company Identity` and every node after it spreads the row (`{...row, ...}`) rather
  than reconstructing a fixed object [VERIFIED: scripts/build_cloud_workflows.py:2024-2038,
  the spread pattern `return { json: { ...row, object_type: "companies", identity_keys: {...}
  } };`], which means an arbitrary key present on the initial event — including a `mode` field
  — would very likely survive unchanged all the way to `Decide Company Action`. **This chain
  was traced through the generator source, not observed on a live execution** — confirming it
  end-to-end (does the webhook's initial parse/route step forward an unrecognized `mode` key
  from the incoming JSON event onto the row at all?) is exactly the kind of one-shot,
  low-cost spike Task 1 of this phase should do before design commits to it.
- `enrichment.build_envelope`'s `"companies"` form does not set `mode` on any event today
  [VERIFIED: operator-claude-plugin/scripts/enrichment.py:319-364 — no `mode` key appears in
  the constructed `event` dict]. Adding it (a client-only change, a few lines) is the
  cheapest path to "run research, get properties back, don't write" — **if** the trace above
  is confirmed live.
- **No company-side propose/match lane exists client-side at all.** Confirmed by exhaustive
  grep: no function, dataclass, or test references a companies analog of
  `preingest.py`'s `classify_matches`/`apply_match_decisions`. The domain confirm table this
  phase needs is genuinely new client-side surface, built in the spirit of the existing
  pattern (below) but not a wire-up of existing code.

## The pre-ingest match-proposal-confirm pattern (the template to extend, contacts-only today)

Read directly: `operator-claude-plugin/scripts/preingest.py` (in relevant part).

- **Declared contacts-only, in the code itself:** *"This lane is contacts-only (37-CONTEXT §2
  decision 6; there is no company canonical set)."* [VERIFIED: operator-claude-plugin/scripts/preingest.py:63-64]
- **Four-way classification** (`classify_matches`): `auto_matched` (HIGH tier), `proposed`
  (MEDIUM tier, carries a `candidates` list projected to exactly six disclosure-safe keys:
  `hs_object_id, firstname, lastname, email, jobtitle, company`), `unmatched` (NONE tier),
  `unchecked` (no verdict / unrecognized tier). [VERIFIED: operator-claude-plugin/scripts/preingest.py:26-30,235-326]
- **The reusable per-row decision mechanism, verbatim, is what D-58-04's table should reuse:**
  `apply_match_decisions(classified, resolved)` where `resolved` maps a `row_id` to either a
  candidate's own `hs_object_id` (confirm) or the sentinel `DECLINE_MATCH = "decline"`
  (decline). A row absent from `resolved` stays proposed — *"never defaulted either way; the
  function never picks a candidate on the operator's behalf."* Declining moves the row into
  `unmatched`, "so it is picked up by enrichment like any other no-match row" — this is the
  exact shape D-58-06's "denied falls back to accept-by-name" needs.
  [VERIFIED: operator-claude-plugin/scripts/preingest.py:349-421, sentinel definition and
  docstring quoted directly]
- **Validation-before-application, in one pass, everything-or-nothing:** every entry in
  `resolved` is checked against both guards (row was actually proposed; candidate id is one
  of that row's own candidates) *before* any decision is applied — a call that raises applies
  nothing at all. [VERIFIED: operator-claude-plugin/scripts/preingest.py:370-408] This is the
  correctness property the new domain-confirm decision-application function must also have.
- **What is genuinely new, not reused:** there is no backend `mediumCandidates()`-equivalent
  for companies today (no match tiers exist there per the comment cited above), so the
  "candidates" a domain-confirm table shows are not backend search results at all — they are
  Claude's in-conversation proposal (D-58-01) or the backend research node's finding, a
  different data source than the six-key HubSpot search projection this pattern was built
  around. The planner should treat `apply_match_decisions`'s SHAPE (row_id → confirm/decline
  sentinel, validate-then-apply-atomically) as the reusable asset, not its wiring to a HubSpot
  search response.

## Cost/consent envelope — the shape to extend, no declinable-line precedent yet

Read directly: `operator-claude-plugin/scripts/cost_guard.py` (full file, 273 lines) and
`operator-claude-plugin/config/cost_rates.json`.

- **Rate table shape:** `config/cost_rates.json` is a flat `{version, measured_on, rates:
  {<key>: {value, unit, citation, confidence}}}` structure, with `value: null` reserved for
  "genuinely unknown, never render as zero" (Apollo's per-match rate is `null` today — no
  committed figure exists for this account). [VERIFIED: operator-claude-plugin/config/cost_rates.json:1-35]
  A new "domain research" rate line would follow this exact shape:
  `{"claude_web_domain_research": {"value": <usd or null>, "unit": "...", "citation": "...",
  "confidence": "..."}}`. **No measured actual exists for a domain-only research call today**
  (the only measured Anthropic figure, `anthropic_usd_per_record: 0.068624`, is "the all-in
  observed figure... full provider + Haiku research + Sonnet judge chain"
  [VERIFIED: operator-claude-plugin/config/cost_rates.json:36-41] for the EXISTING
  multi-signal research call, not a domain-only one) — this rate must be measured live before
  it can be disclosed as anything but `confidence: unknown`.
- **Tri-state comparison discipline** (`compare()`): a balance is `unknown` (unreadable),
  `insufficient` (readable, magnitude fails), or `ok` — readability is checked strictly before
  magnitude, "comparing an unreadable balance numerically is how an unknown becomes a
  confident wrong answer in either direction." [VERIFIED: operator-claude-plugin/scripts/cost_guard.py:212-254]
  A domain-research cost line inherits this discipline directly — Anthropic dollar cost has no
  known-balance concept today in this codebase at all (only provider *credits* are balance-checked;
  Anthropic spend is estimated, never balance-verified against a live account figure), so a
  domain-research line is disclosure-only in the same way D-53-02 records GRANT-02's ceiling
  is disclosure-only, not a hard stop.
- **No "declinable cost line" mechanism exists anywhere in the plugin today.** Exhaustive grep
  for `declin*` across `scripts/*.py` surfaces only: `config_gate.py`'s admin-level capability
  opt-out (a whole capability, not a line item), and `preingest.py`'s `DECLINE_MATCH` sentinel
  (a per-row match decision, not a cost line). [VERIFIED via grep, both call sites read] The
  planner should design D-58-09/D-58-10 ("strike a line") as a **new mechanism**, most
  naturally as a per-row decision (reusing `DECLINE_MATCH`'s sentinel shape: a row's research
  decision is `research` or `DECLINE_MATCH`, defaulting to `research` when unaddressed per
  D-58-09's "default-on"), rather than searching for an existing "strike this line" primitive
  that does not exist.

## Common Pitfalls

### Pitfall 1: Treating "same call" language in REQUIREMENTS.md as a fact already verified
**What goes wrong:** Planning tasks as if extending the research node to return a domain is a
one-line change, because INPUT-02's requirement text says "the same call."
**Why it happens:** The requirement was written from the operator's-eye view of what the
system *should* do, not from a code read of what the research node's schema currently asks
for.
**How to avoid:** Budget a real (if small) task for extending `researchSystemPrompt()` +
`required_fields` in `build_cloud_workflows.py`, plus a build/deploy/bounce cycle and a live
disarmed proof read, exactly as every other n8n-side change in this project's history has
needed (see `n8n-stored-vs-running-content.md` project memory: a stored read-back proves
nothing).
**Warning signs:** A task plan that has zero n8n-side line items for INPUT-02.

### Pitfall 2: Assuming the contact-lane identity rule generalizes to companies
**What goes wrong:** Trying to add company canonical props into `column_mapping.yaml`'s
existing flat `aliases`/`required_identity` shape, which has no type discriminator.
**Why it happens:** It is the path of least resistance — one file, one function
(`canonical_props()`) already exists.
**How to avoid:** Design a `record_type`-aware (or artifact-shape-aware) extension point in
`extraction.py` deliberately, as its own task, before writing company adapter prose. The
existing `identity_groups()`/`_group_presence()`/`dedupe()` machinery is reusable once a
company-scoped identity group can be selected — but "which group set applies" needs a real
answer.

### Pitfall 3: Believing arming/dispatch already supports a company propose call
**What goes wrong:** Assuming `dispatch_enrichment` + an armed=False call already gets a
usable "preview" response for companies the way it might for contacts' `mode: propose`.
**Why it happens:** `armed=False` on `dispatch_enrichment` raises `NotArmedError` before any
network call is made [VERIFIED: operator-claude-plugin/scripts/enrichment.py — `if not armed:
raise NotArmedError(...)` guards the whole POST]; it is not the same axis as the backend's
`isReturnOnly(mode)` returnOnly/write distinction. A confirm-before-write research call must
be armed at the transport level (so the backend actually runs providers/research/judge and
returns a body) while ALSO carrying `mode != "write"` so the backend's own gate refuses the
PATCH. These are two independent gates and both must be understood and wired correctly, or
the phase will either burn research cost that never surfaces a confirmable candidate, or
accidentally write an unconfirmed domain.
**Warning signs:** A plan that treats "unarmed" and "research-only" as the same state.

### Pitfall 4: Weakening `NOT_A_COMPANY_DOMAIN` to make LinkedIn URLs "just work"
**What goes wrong:** Someone notices a LinkedIn company page is a common input and is tempted
to extract a slug-derived domain from it directly.
**Why it happens:** It feels like it would close more rows with less research spend.
**How to avoid:** D-58-03 is explicit and CONTEXT.md marks this reversibility as "one-way in
spirit" — the guard exists because of a real, previously-shipped defect (the LinkedIn-URL-
became-a-domain poisoning case). A LinkedIn URL may only ever seed research input (name,
industry text on the page), never a domain value.
**Warning signs:** Any code path that assigns a value from a LinkedIn/social host directly to
a `domain` field without passing through `_clean_domain`/`cleanCompanyDomain`.

## Runtime State Inventory

Not applicable — this phase adds new client-side surface (extraction adapters, a confirm
table, a cost-line mechanism) and extends an existing backend node's prompt schema. It is not
a rename, refactor, or migration of any existing property, workflow name, or stored
identifier. **None found** — no runtime state category applies.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud (`wf_enrichment_cloud`) | Backend research node, company create | Assumed available (existing deployed workflow; no change to availability posture from this phase) | live, per CLAUDE.md §4.0 as-built delta | none — this is the only production write path for companies |
| Anthropic API (`web_search_20250305` server tool) | Backend domain/ICP research | Assumed available, billed per-call | claude-haiku-4-5 (research model, per `.env.example`) | none for backend research; client-side Claude proposal (D-58-01) is the low-cost primary path and does not depend on this |
| Native `web_fetch` tool (client-side) | URL adapter | Available (already used by contact lane) | n/a (Claude Code built-in) | none needed — already proven |

No new external package or service dependency is introduced by this phase. The
Environment Availability section is included because backend Anthropic call availability is a
genuine cost/consent surface (D-58-08/09/10), not because a new tool needs installing.

## Validation Architecture

`.planning/config.json` carries no `workflow.nyquist_validation` key — treated as enabled per
default.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, plugin scripts) + Node's built-in `node --test` (JS parity tests) |
| Config file | none dedicated — `operator-claude-plugin/tests/` and `tests/n8n/*.test.mjs` are run directly |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py -x` (per-file, per project memory: system python lacks deps) |
| Full suite command | `.venv/bin/python -m pytest` (from repo root) + `node --test tests/n8n/*.test.mjs` (glob form only — directory form is broken on node 24, per project memory) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INPUT-01 | Company row extracted from each of the 6 source kinds (prose, JSON, URL, screenshot, bare-name list, search-results screenshot) satisfies the company identity rule and round-trips through the validator | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py -x` | ✅ existing file, extend — contact-only today |
| INPUT-02 | A row with no usable domain and Claude unable to propose one produces a priced, named research-envelope line | unit | new test file, e.g. `test_company_domain_research_envelope.py` | ❌ Wave 0 |
| INPUT-03 | A backend-researched domain never reaches a HubSpot PATCH without an explicit per-row confirm decision | unit | new test file mirroring `test_preingest_match.py`'s decision-application coverage | ❌ Wave 0 |
| INPUT-04 | Every refusal path in the new adapters names what would make the input work (mirrors existing `RecordSpecError` message-content assertions in `test_enrichment_envelope.py`) | unit | extend `operator-claude-plugin/tests/test_enrichment_envelope.py` | ✅ existing file, extend |
| D-58-03 (guard) | A company row whose only source is a LinkedIn/profile URL never carries that URL as `domain` after extraction+build_envelope, in both the Python and JS mirrors | unit (parity) | `.venv/bin/python -m pytest` (Python side) + `node --test tests/n8n/*.test.mjs` (JS side, if `companyLink.js` gains a company-lane analog) | ✅ `NOT_A_COMPANY_DOMAIN` tests exist for the current guard; extend for the new adapter surface |

### Sampling Rate
- **Per task commit:** the relevant single test file (extraction contract, envelope, or
  preingest-analog), not the whole suite — this repo's own convention per
  `test-suite-run-commands.md` project memory.
- **Per wave merge:** `.venv/bin/python -m pytest` full run + `node --test tests/n8n/*.test.mjs`.
- **Phase gate:** full suite green before `/gsd-verify-work`. Any n8n workflow change (Task-1
  spike outcome) additionally needs a live deploy+bounce+disarmed-execution proof, per this
  project's standing rule that a stored read-back proves nothing
  (`n8n-stored-vs-running-content.md`).

### Wave 0 Gaps
- [ ] A company-scoped identity-rule config (new YAML section or file) — no config file exists
  today for a company identity rule; extraction.py's `identity_groups()`/`canonical_props()`
  need either a second config file or a type-scoped read.
- [ ] `test_company_domain_research_envelope.py` — covers INPUT-02/D-58-08/09/10.
- [ ] A decision-application module/test pair analogous to `preingest.py`'s
  `apply_match_decisions` scoped to domain confirm/decline — covers INPUT-03/D-58-04/06.
- [ ] A one-shot live spike (not a permanent test) proving or disproving whether an
  unrecognized `mode` key on a companies webhook event survives to `Decide Company Action` —
  this determines whether "research without writing" is plugin-only or needs an n8n change.

## Security Domain

`security_enforcement` is absent from `.planning/config.json` — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This phase adds no new auth surface; existing `webhook_secret` header pattern (`X-Enrichment-Secret`) is unchanged. |
| V3 Session Management | No | Not applicable — conversational plugin, no session tokens introduced. |
| V4 Access Control | Yes | The existing record-scoped write-safety allowlist (`_writeSafetyAllows`) and `NOT_A_COMPANY_DOMAIN`/freemail guards are the access-control-equivalent controls here. This phase must not weaken either — extend, never bypass. |
| V5 Input Validation | Yes | The core of this phase. `extraction.py`'s no-invention/provenance/identity validation, extended with a company-scoped identity rule and (new) a domain-confirm decision validator that must reject before applying anything (mirrors `apply_match_decisions`'s validate-then-apply-atomically discipline). |
| V6 Cryptography | No | No new secret material, no new credential type. `webhook_secret` handling is unchanged. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Domain-poisoning via a social/profile-page host mistaken for a company's own site (the concrete, previously-shipped LinkedIn defect) | Tampering (of the CRM's own dedupe anchor) | `NOT_A_COMPANY_DOMAIN` frozenset, checked at both the Python client (`enrichment.py::_clean_domain`) and the n8n backend (`companyLink.js::cleanCompanyDomain`) — verified byte-identical between the two; any change to the set must update both in one commit. |
| Prompt injection via fetched page content (URL adapter) or scraped screenshot text | Tampering (of the extraction step's output) | Already documented and unchanged by this phase: `extraction.md`'s "Trust note" — treat fetched content as data to read, never as direction to follow. Applies identically to a company's about-page fetch. |
| Silent domain write without operator confirmation (the exact failure mode INPUT-03 exists to prevent) | Tampering / Repudiation | `domain`'s `manual_protected`/`stage_only` field policy already prevents an automatic canonical write; this phase's new client-side decision-application layer must independently enforce "no confirm entry, no write" per row, never relying on the backend field policy alone (defense in depth — the field policy could change or the row could reach a different write path in future). |
| Unbounded research spend from a large "no-domain" batch | Denial of Service (of the operator's own budget, not the system) | D-58-08/09/10's priced, named, declinable envelope line — modeled on `cost_guard.py`'s existing disclosure discipline (readability-before-magnitude, never a defaulted number for an unmeasured rate). |

## Sources

### Primary (HIGH confidence — read directly this session)
- `operator-claude-plugin/skills/contact-upload/extraction.md` (full file)
- `operator-claude-plugin/scripts/extraction.py` (full file)
- `operator-claude-plugin/scripts/enrichment.py` (build_envelope, `_clean_domain`,
  `NOT_A_COMPANY_DOMAIN`, dispatch_enrichment sections)
- `operator-claude-plugin/scripts/preingest.py` (build_rows_spec through apply_match_decisions)
- `operator-claude-plugin/scripts/cost_guard.py` (full file)
- `operator-claude-plugin/config/cost_rates.json` (full file)
- `operator-claude-plugin/config/column_mapping.yaml` (aliases + required_identity)
- `n8n/code/companyLink.js` (NOT_A_COMPANY_DOMAIN, cleanCompanyDomain)
- `n8n/code/matchProposal.js` (isReturnOnly)
- `n8n/code/webResearch.js` (validateResearchOutput, toProviderResult)
- `scripts/build_cloud_workflows.py` (COMPANIES_TARGET definition, gap predicate, research
  system prompt, required_fields, Decide Company Action returnOnly wiring, Build Company
  Identity spread pattern)
- `config/field_policy.yaml` (domain's field-policy class)
- `.planning/phases/58-take-what-the-operator-actually-has/58-CONTEXT.md`
- `.planning/phases/53-operator-openable-write-grant/53-CONTEXT.md`
- `.planning/milestones/v1.1-REQUIREMENTS.md`, `v1.1-ROADMAP.md`
- `.planning/STATE.md` (project history and prior findings, e.g. hardware-veto retroactivity,
  n8n stored-vs-running content)
- `CLAUDE.md` §13.0.1 (contact→company association), §4.0/§10.3.1 (as-built deltas)

### Secondary (MEDIUM confidence)
- None used — no web search was performed for this phase; the entire research surface is
  in-repo.

### Tertiary (LOW confidence — traced from code, not executed live this session)
- Whether an unrecognized `mode` key on the initial companies webhook event actually survives
  to `Decide Company Action` (the spread-pattern trace is strong but unconfirmed live).
- Whether a `domain`/`website` field added to the research prompt's schema would actually
  surface in the API response body for a `returnOnly` call in a shape the client can read
  (whether a `claude_web_domain`-style staging key is already computed/returned for a
  non-writing companies research call).
- The actual USD cost of a domain-only (or domain-added) research call — no measured rate
  exists in `config/cost_rates.json` for this shape of call.

## Metadata

**Confidence breakdown:**
- Contact-lane extraction template (what to copy): HIGH — read start to finish, no
  interpretation required.
- Backend research/propose-mode architecture (what must change to support domain discovery
  without writing): MEDIUM — traced precisely through generator source with line citations,
  but not proven against a live execution this session; flagged explicitly as Task-1 spike
  material rather than presented as settled.
- Cost/consent mechanism for a new declinable line: MEDIUM — the disclosure discipline to
  follow is HIGH confidence (cost_guard.py read in full), but the specific "declinable line"
  mechanism does not exist anywhere in the codebase yet and must be designed, not found.
- Security/threat model: HIGH — directly extends existing, well-documented guards; no new
  attack surface introduced beyond what those guards already cover.

**Research date:** 2026-08-26
**Valid until:** ~14 days (this repo's n8n workflows and plugin surface change frequently —
see STATE.md's phase cadence; re-verify `build_cloud_workflows.py`'s COMPANIES_TARGET and
`enrichment.py`'s build_envelope against HEAD before planning if more than ~2 weeks elapse).
