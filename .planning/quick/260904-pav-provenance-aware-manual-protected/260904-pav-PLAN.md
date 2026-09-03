---
phase: quick-260904-pav
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - n8n/code/mergeCompanies.js
  - src/merge_policy.py
  - config/field_policy.yaml
  - scripts/build_cloud_workflows.py
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_review_decision_cloud.json   # only if the build regenerates it; commit whatever it emits
  - tests/n8n/mergeCompanies.test.mjs
  - tests/n8n/decideCompanyActionCreateSeedProvenance.test.mjs
  - tests/n8n/parity.test.mjs
  - tests/test_merge_policy.py
  - CLAUDE.md
autonomous: true
requirements: [PAV-01]   # quick-task-local handle, NOT a ROADMAP requirement ID; traces to
                         # .planning/todos/pending/2026-09-04-provenance-aware-manual-protected.md
estimate:
  tokens: 90000
  raw_tokens: 45000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A company whose `domain` provenance entry says the enrichment system seeded it, whose recorded value still equals the current value, on a row with no provider conflict, is corrected by a >=95-confidence candidate."
    - "A company whose `domain` provenance entry names any other source is refused, exactly as today."
    - "A company with no `lv_enrichment_provenance` entry for `domain`, or an unparseable blob, is refused, exactly as today."
    - "A create stamps a `create_seed` provenance entry for the domain it seeds, so the correction path has something to key on."
    - "An enrich run no longer destroys provenance entries for fields it did not touch."
  artifacts:
    - n8n/code/mergeCompanies.js
    - src/merge_policy.py
    - config/field_policy.yaml
    - .planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md
  key_links:
    - "mergeCompanies.js `_gate` manual_protected branch <-> src/merge_policy.py deterministic_gate manual_protected branch (Phase 46 parity, ONE commit)"
    - "ENRICH_DECIDE_CO_CLOUD create branch <-> the provenance blob write (the seed entry must survive serialization)"
    - "ENRICH_MERGE_CO `conflicts` (line ~3048) <-> mergeCompanies `opts.rowConflicted` (the harveynorman guard, reused)"
---

<objective>
Make the `manual_protected` gate ask WHO wrote the existing value before refusing, so a domain
the enrichment system parked itself can be corrected by the system's own later, better answer,
while a human-curated value stays protected exactly as today.

Purpose: a wrong company `domain` is load-bearing downstream — G-62-7's email-domain relatedness
rule holds every correct contact email as `email_domain_mismatch` against it. Today there is no
in-product correction path at all.

Output: a provenance-aware correction path in both merge engines, a `create_seed` provenance
stamp so the path has something to key on, an additive provenance blob so the stamp survives,
and a todo naming the one seam this plan deliberately does NOT close.

**Read `.planning/todos/pending/2026-09-04-provenance-aware-manual-protected.md` first — it is
the source of truth. This plan honours its three grounding findings and adds three more,
verified live by grep against this repo at planning time.**
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/todos/pending/2026-09-04-provenance-aware-manual-protected.md
@n8n/code/mergeCompanies.js
@config/field_policy.yaml
</context>

<planning_findings>
Six findings, all verified by reading the files at planning time. Findings 4-6 are NEW —
they are not in the todo and each one would leave the fix inert if planned around.

**1 (todo finding 1, confirmed).** `ENRICH_DECIDE_CO_CLOUD`'s create branch
(`scripts/build_cloud_workflows.py:3444`) seeds `properties.domain = id.domain` and writes no
provenance. `properties.lv_enrichment_provenance` is written only from `merge.provenance`
(same file, ~3358).

**2 (todo finding 2, confirmed and STRENGTHENED).** `mergeCompanies.js` writes
`provenance[field] = entry` for EVERY field, before the `if (decision === "promote")` branch —
so a *refused* candidate still leaves an entry whose `value` is the refused candidate. The
`entry.value === currentValue` check is therefore load-bearing against a refused candidate
authorising its own later promotion, not only against a human retyping the value.

**3 (todo finding 3, confirmed).** `config/field_policy.yaml:5` — `companies.domain` is the only
`manual_protected` field. `n8n/code/mergeContacts.js:128`'s identical branch is unreachable.
Leave it alone.

**4 (NEW — a second refusal seam the todo does not name).** `mergeCompanies.js:232-233` carries
a hard guard that runs AFTER `_gate`:
`if (field === "domain" && decision === "promote") decision = "stage_only";`
A provenance-aware `_gate` alone changes nothing — this guard would re-refuse the correction.
It is in scope.

**5 (NEW — providers cannot supply a corrected domain, so this plan cannot close the loop).**
No branch of `n8n/code/normalizeProviders.js` pushes a company `domain` candidate at all (the
full `_push` field set is city, country, email, hs_country_region_code, hs_state_code, industry,
jobtitle, lv_country_region_normalized, lv_employee_band, lv_revenue_band, mobilephone,
numberofemployees, persona_group, phone, seniority, state), and the Claude-web research fold
supplies only org_type/produces_content/content_type/hardware/gambling/sponsorship. Worse, the
company providers are looked up BY the record's domain — ZoomInfo `matchCompanyInput:
[{companyWebsite|companyName}]`, Lusha company `?domain=` — so a provider structurally cannot
return a domain that disagrees with the one it was asked about.
**Consequence:** this plan lands the correction MECHANISM, correct and tested; it stays inert
until a domain-candidate source exists. Task 3 records that as a todo rather than inventing one
here — adding a candidate source is new enrichment surface whose provider payload keys cannot be
confirmed without live calls, which this task forbids.

**6 (NEW — the seed would be destroyed before it could be used).** The enrichment lane REPLACES
the blob: `properties.lv_enrichment_provenance = stableStringify(merge.provenance)`, with no
spread of the record's existing blob anywhere on that lane (the "additive: other fields' entries
survive" guarantee is the REVIEW lane's, not this one). `merge.provenance` only ever carries
fields present in this run's candidate set, and per finding 5 that never includes `domain`. So
the first enrich after a create would wipe the `create_seed` entry. Making the write additive is
required for the fix to function, and independently repairs a latent loss affecting every field.
</planning_findings>

<decisions>
The four decisions this task was required to make explicit, with reasons.

**(a) Allowlist of provenance `source` values that count as system-written: `["create_seed"]`.**
Expressed as a per-field policy key `system_correctable_sources`, NOT hardcoded to `domain`.
Reason: `create_seed` is the only source in the entire system that can ever write a canonical
`domain` — the enrich path's `manual_protected` class plus the finding-4 hard guard mean every
other source's `domain` entry is a *staged refusal* (finding 2). Admitting `waterfall`,
`claude_web`, `hubspot_native` or `june_2026` would let a candidate that was refused authorise
its own promotion on the next run. Absent key = no correction, which keeps today's behaviour for
every other field and for the unreachable contacts branch.

**(b) Confidence bar: the field's existing `min_confidence` (95). No new threshold key.**
The correction check goes INSIDE the `manual_protected` branch, which `_gate` only reaches after
the `confidence < minConfidence` check has already passed. So a correction is automatically held
to 95 — the highest bar in the whole policy — with zero new configuration. Explicitly NOT
hoisted above the confidence check, and explicitly NOT tuned down to the waterfall's flat 85:
per finding 5 there is no domain candidate today, so tuning a threshold for a caller that does
not exist would be guesswork. Whoever adds a domain-candidate source owns arguing it down, with
a real candidate in hand.

**(c) A material conflict on the row BLOCKS a correction. Yes.**
Threaded as `opts.rowConflicted` from the `conflicts` array the `ENRICH_MERGE_CO` wrapper
already computes (`scripts/build_cloud_workflows.py:~3047-3048`) immediately before it calls
`mergeCompanies`. Reason: this IS the `harveynorman.com.au` guard, reused rather than
reinvented — the wrapper's own comment establishes that providers disagree on company SIZE
exactly when the domain is a franchisor or holding company, so a size disagreement is the
franchise/subsidiary detector. Requiring a clean row means a franchisor's domain can never win
on confidence alone, which is the constraint this task must not weaken.
Python twin: `deterministic_gate` has no row-level conflict object, only its own candidate list,
so it gates on the `has_conflict(candidates)` it already computes. Different input, same intent —
the executor must state this divergence in a comment rather than fake a shared input.

**(d) Create-seed source marker: `source: "create_seed"`, `validation_status: "request_echo"`,
`confidence: 0`.**
A distinct source because the seed is an identity echo of the caller's own request, not a
researched or provider-supplied value — it must never be mistaken for evidence. `confidence: 0`
is the honest reading of an unverified echo (and is inert: `domain` is not among the fields
`scoreResearchCandidates` scores). `request_echo` is a new entry in CLAUDE.md §6.1's
validation-status vocabulary — that vocabulary is documentation, not code-enforced (verified),
and no registered status honestly describes an unverified request echo; reusing
`provider_only` would assert a provider that never ran.
</decisions>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: Provenance-aware manual_protected in BOTH merge engines, end to end</name>
  <files>n8n/code/mergeCompanies.js, src/merge_policy.py, config/field_policy.yaml, tests/n8n/mergeCompanies.test.mjs, tests/test_merge_policy.py</files>
  <read_first>
    - n8n/code/mergeCompanies.js in full (289 lines) — `_gate` at ~132, the DEFAULT_COMPANY_POLICY `domain` entry at ~35, the finding-4 hard guard at ~232, the provenance-entry write at ~247.
    - src/merge_policy.py lines 100-175 — `deterministic_gate`, whose signature ALREADY receives `record`, so no signature change is needed on the Python side.
    - config/field_policy.yaml lines 1-10.
  </read_first>
  <behavior>
    Write these against the EXPORTED `mergeCompanies(existingProps, candidateRow, policy, opts)`
    and `deterministic_gate(...)`, never against the unexported `_gate` — a test that passes
    must prove the whole path including the finding-4 hard guard.
    - Corrected: existing `domain` = "brisbanelions.com.au"; blob entry
      `{source:"create_seed", value:"brisbanelions.com.au", ...}`; candidate "lions.com.au" at
      confidence 95; `opts.rowConflicted: false` passed EXPLICITLY -> decision `promote`,
      `canonicalPatch.domain` set.
    - Refused, human provenance: same row, entry `source:"human"` -> `stage_only`, no
      `canonicalPatch.domain`.
    - Refused, no provenance: `lv_enrichment_provenance` absent entirely -> `stage_only`.
    - Refused, unparseable blob: `lv_enrichment_provenance` = "{not json" -> `stage_only`,
      and the call does not throw (fail closed, per the constraint).
    - Refused, stale entry (finding 2, the case the todo's three do not cover): entry
      `source:"create_seed"` but `value` != the record's current `domain` -> `stage_only`.
    - Refused, row conflict: everything else valid but `opts.rowConflicted === true` ->
      `stage_only`.
    - Refused, flag ABSENT (fail closed): everything else valid but `opts` omits
      `rowConflicted` entirely -> `stage_only`. A caller that has not opted in does not get
      the correction path with the harveynorman guard silently off.
    - Refused, below bar: everything else valid, candidate confidence 94 -> `needs_review`
      (the existing `min_confidence` branch, unchanged, proves decision (b)).
    - Unchanged: a field with no `system_correctable_sources` key behaves byte-identically —
      assert at least one existing `manual_protected` refusal still refuses.
  </behavior>
  <action>
    Observe RED first: run the new assertions against the unmodified engines and record that
    they fail, before editing either engine.

    Add `system_correctable_sources: ["create_seed"]` to `companies.domain` in
    config/field_policy.yaml AND to the `domain` entry of `DEFAULT_COMPANY_POLICY` in
    mergeCompanies.js (per decision (a)); both carry a comment naming this task and the reason
    the list has exactly one member. Do not change `min_confidence`, `class`,
    `promote_to_canonical` or `stage_only` on that field — decision (b) depends on 95 staying.

    In mergeCompanies.js add a small module-private helper that parses
    `existingProps.lv_enrichment_provenance` inside a try/catch returning `{}` on any failure
    (do NOT import `_parseProvenanceBlob` — it lives in wrapper scope in
    scripts/build_cloud_workflows.py, not in n8n/code/). Parse it once per `mergeCompanies`
    call, not per field. Pass the field's entry as one additional parameter to `_gate`, plus
    `opts.rowConflicted`. **`rowConflicted` has NO permissive default: the correction requires
    `opts.rowConflicted === false` strictly, so `undefined` refuses.** Reason: a default of
    false would be fail-OPEN on decision (c)'s conjunct — any caller that omits the flag,
    including this repo's own state between Task 1's commit and Task 2's, would get the
    correction path with the harveynorman guard off. Explicit opt-in makes the task ordering
    stop mattering.

    Inside `_gate`'s existing `manual_protected` branch only — not hoisted above the confidence
    check, not above the evidence gate — return `promote` when ALL of: the policy carries a
    non-empty `system_correctable_sources`; the entry exists and its `source` is in that list;
    `String(entry.value) === String(currentValue)`; and `rowConflicted === false` strictly.
    Otherwise fall through to today's `stage_only` with today's reason string unchanged. Give the
    promote branch its own distinct reason naming the recorded source, AND set an explicit
    `correction: true` flag on the returned gate object.

    Relax the finding-4 hard guard at ~232 to test that flag — `if (field === "domain" &&
    decision === "promote" && !gate.correction)` — never to string-match the reason, which would
    be fragile. It must still demote every other `domain` promote to `stage_only`. Update its
    comment to say why the exception exists.

    Mirror all of it in `src/merge_policy.py::deterministic_gate`'s `manual_protected` branch,
    reading the blob from `record.properties.get("lv_enrichment_provenance")` — the signature
    already carries `record`, so do not change it. Per decision (c), gate on the
    `has_conflict(candidates)` this function already computes and comment that the two engines
    take different conflict inputs on purpose.

    Both engines land in ONE commit (Phase 46 parity rule). Regenerate `n8n/*.json` with
    `.venv/bin/python scripts/build_cloud_workflows.py` in the same commit — mergeCompanies.js is
    inlined into the workflow JSON. Never hand-edit the JSON.
  </action>
  <verify>
    <automated>node --test tests/n8n/mergeCompanies.test.mjs && .venv/bin/python -m pytest tests/test_merge_policy.py -q</automated>
  </verify>
  <done>All eight behaviours above assert green in both suites; RED was observed and recorded for at least the correction case before any engine edit; `git status` shows mergeCompanies.js, merge_policy.py, field_policy.yaml and the regenerated n8n JSON in one commit.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Stamp the create seed and stop the blob being overwritten</name>
  <files>scripts/build_cloud_workflows.py, tests/n8n/decideCompanyActionCreateSeedProvenance.test.mjs</files>
  <read_first>
    - scripts/build_cloud_workflows.py lines 3340-3372 (the `ENRICH_DECIDE_CO_CLOUD` properties
      and provenance-blob write) and 3440-3460 (the create branch carrying BUG 19's seed).
    - scripts/build_cloud_workflows.py lines 3040-3085 (`ENRICH_MERGE_CO`: `conflicts` /
      `conflicted` are computed at ~3047-3048, before the `mergeCompanies` call at ~3081).
    - tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs — the existing
      FLOW-style pattern that extracts a node's jsCode out of the build script and runs it.
      Task 2's seams live in `ENRICH_DECIDE_CO_CLOUD`'s node jsCode, NOT in the pure
      `mergeCompanies` module, so `mergeCompanies.test.mjs` cannot reach them. Reuse this
      pattern in a new `tests/n8n/decideCompanyActionCreateSeedProvenance.test.mjs`.
      `parity.test.mjs` is Task 3's, not this task's.
  </read_first>
  <behavior>
    - A `create` row with `identity_keys.domain` produces a `lv_enrichment_provenance` whose
      `domain` entry carries `source: "create_seed"`, `validation_status: "request_echo"`,
      `confidence: 0`, and `value` equal to the seeded domain (decision (d)).
    - A `create` row in return-only mode still stamps nothing — the existing `!returnOnly` gate
      is unchanged.
    - An enrich run whose candidate set does not include a field preserves that field's existing
      provenance entry (finding 6), while this run's entries win on collision.
    - An existing blob that is unparseable is treated as empty and the run does not throw.
    - The `mergeCompanies` call in `ENRICH_MERGE_CO` receives `rowConflicted` reflecting the
      already-computed `conflicts` array.
  </behavior>
  <action>
    Observe RED first for the seed-stamp and blob-preservation assertions.

    In `ENRICH_DECIDE_CO_CLOUD`: build the outgoing provenance ONCE into a single local object —
    the record's existing parsed blob spread first, this run's `merge.provenance` spread over it
    (per decision, this run wins on collision) — and serialize it ONCE, after the create branch
    has had its chance to add the seed entry, so the seed cannot be clobbered by an earlier
    serialization. Add a local try/catch parse helper returning `{}` on any failure. Keep the
    existing "only write the property when there is something to write" condition.

    In the same node's create branch, where `properties.domain = id.domain` is set, add the
    matching entry to that provenance object using decision (d)'s exact literals. Do not touch
    the `name` seed and do not move the `!returnOnly` gate.

    In `ENRICH_MERGE_CO`, pass `rowConflicted: conflicts.length > 0` in the `opts` of the
    `mergeCompanies` call at ~3081. Also pass it on the native-band, June and research folds
    if and only if reading the code shows they can carry a `domain` candidate — per finding 5
    none of them can today, so the expected outcome is the first call only; state which you
    chose and why in the commit body.

    Before making the blob additive, grep every reader of `lv_enrichment_provenance` — Judge
    Gate's `_parseProvenanceBlob` (~2571), the review lane's own additive stamp, and the
    operator plugin — and confirm two things in the commit body: (i) no consumer treats the mere
    PRESENCE of an entry as "this run wrote it" (a stale entry now survives where it previously
    vanished), and (ii) the spread order matches the review lane's, so the two additive lanes
    agree on who wins a collision.

    Regenerate `n8n/*.json` with `.venv/bin/python scripts/build_cloud_workflows.py`. Commit
    every JSON the build touches, not only the enrichment one. Expect the committed JSON to be
    ahead of the live instance and undeployed — the CLAUDE.md §13.0.2 pattern; this task arms
    and deploys nothing.

    Out of scope, one line in the summary: `ENRICH_DECIDE_CO_LOCAL`'s dry-run echo reports
    `row.merge.provenance` rather than the outgoing blob, so its echo will not show the seed
    entry. It writes nothing to HubSpot; note it, do not chase it.

    Second caveat for the SUMMARY, also one line, also not to be chased: memory
    `companies-research-lane-rowloss` records that HTTP hops may strip `existingRecord` on the
    research path. If they do, the additive spread there sees `{}` and replaces exactly as
    today — so the seed survives non-research enrich runs and possibly not research ones. State
    that rather than claiming finding 6 is closed on every path.
  </action>
  <verify>
    <automated>node --test tests/n8n/*.test.mjs</automated>
  </verify>
  <done>Seed-stamp and blob-preservation assertions green; RED recorded before the edit; `git diff --stat n8n/` shows only regenerated JSON; the full n8n suite has no new failures against its pre-task baseline.</done>
</task>

<task type="auto">
  <name>Task 3: Parity fixture, vocabulary, and the todo for the seam this plan does not close</name>
  <files>tests/n8n/parity.test.mjs, CLAUDE.md, .planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md</files>
  <read_first>
    - tests/n8n/parity.test.mjs — find the existing fixture-row shape and add to it rather than
      inventing a second harness.
    - CLAUDE.md §6.1 (validation statuses) and §17.2 (the PROMOTE list).
  </read_first>
  <action>
    Add one `create_seed` row to the JS/Python parity fixture so the two engines are pinned equal
    on the correction path, not only on the paths they already shared.

    In CLAUDE.md: add `request_echo` to §6.1's recommended validation statuses with a one-line
    gloss ("identity echo of the caller's own request; never evidence"). In §17.2, annotate the
    existing PROMOTE clause "Existing value was previously written by the enrichment system and
    the new candidate has higher confidence" to record that it is now implemented, name the
    `system_correctable_sources` policy key, and state the three additional conjuncts (value
    match, no row conflict, the field's own `min_confidence`). Do not restate the whole rule
    elsewhere — one place.

    Write `.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md`
    recording finding 5 as its own gap: no `normalizeProviders.js` branch pushes a company
    `domain`, the research fold does not supply one, and the company providers are looked up BY
    the record's domain (ZoomInfo `matchCompanyInput:[{companyWebsite|companyName}]`, Lusha
    `?domain=`) so they cannot contradict it — therefore the correction mechanism this plan lands
    has nothing to correct WITH, and the live Brisbane Lions record (`285583534546`) stays stuck
    until a source exists. Name the plausible directions without choosing one (a provider raw
    field confirmed against a live payload; a research question that returns a domain; the
    plugin's own held `@lions.com.au` evidence) and say plainly that each needs live verification
    this task forbade. Reference this plan by path.

    Mark `.planning/todos/pending/2026-09-04-provenance-aware-manual-protected.md` resolved by
    this quick task, with a Closure section naming what landed and what did not — do not claim
    the live record is fixed.
  </action>
  <verify>
    <automated>node --test tests/n8n/parity.test.mjs && test -f .planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md && grep -q 'request_echo' CLAUDE.md</automated>
  </verify>
  <done>Parity fixture green; both CLAUDE.md edits present; the new todo exists and names finding 5 with its evidence; the original todo carries an honest Closure section.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| candidate -> canonical HubSpot `domain` | this task opens a previously-closed write path on a `manual_protected` field |
| caller request -> `create_seed` provenance entry | the seed records a caller-supplied string as system-authored |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-PAV-01 | Tampering | `_gate` manual_protected correction branch | high | mitigate | Four conjuncts required (allowlisted source, value match, no row conflict, >=95). Task 1 asserts each one refuses independently. |
| T-PAV-02 | Elevation of Privilege | provenance blob as an authorisation token | high | mitigate | A refused candidate leaves an entry whose `value` != currentValue (finding 2); the value-match conjunct denies it. Test asserted in Task 1. |
| T-PAV-03 | Spoofing | `create_seed` marker on a caller-supplied domain | medium | mitigate | Distinct source + `confidence: 0` + `request_echo` status; the seed can only ever authorise replacing ITSELF, never a human or provider value. |
| T-PAV-04 | Tampering | franchisor/parent domain wins on confidence | high | mitigate | Decision (c): any row conflict refuses, reusing the existing size-conflict franchise detector. |
| T-PAV-05 | Denial of Service | malformed `lv_enrichment_provenance` | low | mitigate | try/catch -> `{}` in both engines and in the wrapper; fail closed, asserted not to throw. |
| T-PAV-06 | Repudiation | additive blob hides who wrote what | low | accept | Additive is strictly more audit information than today's destructive replace; entries keep their own `source`/`verified_at`. |
| T-PAV-SC | Tampering | npm/pip/cargo installs | high | mitigate | No package installs in this task; if any appears, the package-legitimacy gate and a blocking human checkpoint apply. |
</threat_model>

<verification>
- `node --test tests/n8n/*.test.mjs` — no new failures against the pre-task baseline.
- `.venv/bin/python -m pytest tests/test_merge_policy.py -q`.
- `git diff --stat n8n/` shows regenerated JSON only, produced by
  `.venv/bin/python scripts/build_cloud_workflows.py`, never hand-edited.
- Zero live HubSpot calls, zero provider credits, zero n8n executions, nothing armed.
</verification>

<success_criteria>
A `create_seed`-provenanced domain whose recorded value still matches the record is corrected by
a >=95 candidate on a conflict-free row; human-provenanced, unprovenanced, unparseable, stale-value,
conflicted and below-bar rows all refuse exactly as today; the seed is stamped on create and
survives subsequent enrich runs; both engines land in one commit with the JSON regenerated; and
the one seam this plan does not close is recorded as a todo rather than implied to be working.
</success_criteria>

<output>
Create `.planning/quick/260904-pav-provenance-aware-manual-protected/260904-pav-SUMMARY.md` when done.
</output>
