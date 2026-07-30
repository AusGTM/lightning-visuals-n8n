# Phase 15.5: Tiered Candidate Adjudication — Research

**Researched:** 2026-07-22
**Domain:** n8n Code-node scoring/merge/judge pipeline (companies branch) — JS-only production logic, Python dev-oracle parity discipline
**Confidence:** HIGH (all core claims verified by reading the actual source + executing the test suite; the two LOW-confidence items are flagged explicitly in the Assumptions Log)

No `CONTEXT.md` exists for this phase (directory was empty) — there are no locked user decisions beyond what the ROADMAP.md phase entry and this task's brief already lock in. Those are treated as binding below and are not re-litigated.

## Summary

The roadmap's diagnosis is correct in spirit but one premise needs a precise correction, and the actual code is closer to done than it looks. `scoreCandidates()` (`n8n/code/scoreEnrichment.js:44-105`) does compute full A/R/G/T components per candidate and does retain them in `best[field]`, discarding only `winners`. But **for companies, the winning-collapse premise is only half true**: `ENRICH_MERGE_CO` (`scripts/build_cloud_workflows.py:1640-1648`) already reads `best[f].normalizedValue`, not `winners` — the waterfall/firmographic path already survived the "raw winner" bug that contacts intentionally keep (`n8n/code/mergeCompanies.js:1-22`'s own comment explains why contacts want raw values). The real, still-open defect is narrower and sharper than "scoring discards evidence": **the research/ICP-semantic path never enters `scoreCandidates` at all.** `rc.data` is merged directly (`build_cloud_workflows.py:1661-1673`) with one flat `rc.confidence` for every field, zero A/R/G/T, zero `recencyDate`. The judge (`buildJudgeRequestBody`, `n8n/code/judge.js:183-225`) receives only `data` + `evidence_by_field` + escalation reason strings — no scoring grounding whatsoever, confirming the roadmap's "judge sees only the research candidate" claim exactly.

The second surprise: **the tier boundary the roadmap asks for already exists in code**, just untested as a boundary. `n8n/code/judge.js:178-181`'s `_JUDGE_DATA_FIELDS` (`lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`) and `build_cloud_workflows.py:1619`'s `CONFLICT_WATCH` (`lv_revenue_band`, `lv_employee_band`) are already disjoint, and RO-2 already proves structurally (`tests/test_judge_spec.py:161-186`) that the judge never sees size disagreements. Phase 15.5's job is not to invent a boundary — it is to (1) score the research candidate using the same unmodified `scoreCandidates()` engine so the judge gets real grounding, (2) source a real `recencyDate` for research (from Anthropic's `page_age`, not the model's self-report or a URL guess), (3) thread the resulting composite confidence into `mergeCompanies` per field instead of one flat number, and (4) make the existing cost cap unit-testable and formally asserted, extending the RO-2 pattern rather than duplicating it.

**Primary recommendation:** Add one pure function (`scoreResearchCandidates`, co-located in `judge.js`, reusing the unmodified `scoreCandidates` import from `scoreEnrichment.js`) that scores each `_JUDGE_DATA_FIELDS` value against a synthetic "prior on file" candidate built from the existing record + its Phase-15 provenance blob; extend `webResearch.js`'s validation to extract `recencyDate` from Anthropic's `web_search_tool_result.page_age`; add one additive, backward-compatible option to `mergeCompanies` (`opts.confidenceByField`); and extend `buildJudgeRequestBody` with a `scoring` key restricted to the same five fields. No new n8n nodes, no HTTP calls, no change to `scoreCandidates`' or `mergeCompanies`' existing call signatures for any current caller.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Per-candidate A/R/G/T scoring | n8n Code node (`scoreEnrichment.js`) | — | Pure, deterministic, already exists; reused unmodified |
| Research candidate grounding for the judge | n8n Code node (`judge.js`, new function) | Anthropic Messages API (raw response inspection) | Judge payload construction is judge-domain, not a new module |
| recencyDate extraction | n8n Code node (`webResearch.js`, extended) | Anthropic `web_search` server tool (`page_age` field) | Same node that already owns response validation; no new HTTP call |
| Non-clobber merge / promotion gate | n8n Code node (`mergeCompanies.js`) | — | Deterministic policy engine; gains one additive option only |
| Cost cap enforcement | n8n Code node (`judge.js`, new function) | n8n workflow-level `$env`/`$vars` (`MAX_SONNET_VALIDATIONS_PER_RUN`) | Currently inline-only in the Python-string wrapper; extracted so it is unit-testable |
| Judge adjudication | Anthropic Messages API (Sonnet) | n8n HTTP Request node | Unchanged — Phase 14 wiring stands |
| Dev-oracle parity | Python (`src/*.py`) | — | AR-3: not deployed; recencyDate extraction and judge-request glue are new *infrastructure*, not shared business logic — no Python twin required (same precedent as `src/judge.py`'s documented D4 decision re: judge HTTP glue) |

<phase_requirements>
## Phase Requirements

No formal `REQ-*`/phase-requirement IDs were handed to this research task; the six numbered Success Criteria in `.planning/ROADMAP.md` §"Phase 15.5" are the operative requirements. Mapped to research support:

| # | ROADMAP Success Criterion | Research Support |
|---|---|---|
| 1 | Scoring ranks, never decides; no info discarded before the judge | §"Collapse-Point Analysis" + §"Recommendation" — reuse `scoreCandidates` unmodified, attach `best` to every researched row regardless of escalation |
| 2 | Tiered routing explicit + tested; size fields never reach the judge | §"Tier Boundary" — the boundary already exists (`_JUDGE_DATA_FIELDS` / `CONFLICT_WATCH`); this phase formalizes + tests it |
| 3 | Judge receives full ranked set + scoring components + web-search grounding; cites what it relied on | §"Judge Payload Design" |
| 4 | Research candidates carry `recencyDate`; ordering bias only, neutral when unknown | §"recencyDate Sourcing" |
| 5 | TS-1 holds: no recency/scoring path can turn a value `false` | §"Recommendation" + §"Common Pitfalls" — verified no code path in the proposed design ever rewrites a value, only confidence/routing |
| 6 | Judge invocation count capped AND asserted; no size-only disagreement can ever trigger a model call | §"Cost Bounding + Structural Proof" |

I propose these become formal spec IDs (`TA-1`..`TA-8`) in `docs/WEB-RESEARCH-SPEC.md` — see that section below; the planner should treat that proposal as the requirement set to implement against.
</phase_requirements>

---

## Current-State Map (verified file:line)

### 1. Scoring engine — already correct, already reused unmodified
- `n8n/code/scoreEnrichment.js:44-105` `scoreCandidates(candidates, opts)` groups by canonical field, computes `score = wA·A + wR·R + wG·G + wT·T` (weights `{0.45, 0.20, 0.25, 0.10}`, line 20) per candidate, and returns **both** `best[field]` (full components + `agreedBy`) and `winners[field]` (raw `top.value`).
- `_recency()` (lines 32-37): no `recencyDate` → returns neutral `0.5`. This is the exact mechanism the locked "recency is ordering bias only, unknown stays neutral" decision needs — **it already exists**, it is just never fed a `recencyDate` for research candidates because research never calls this function.
- No Python twin exists for this file (confirmed: no `src/score_enrichment.py`); it is JS-only production logic, consistent with the existing pattern of Code-node-only modules that have no business-logic counterpart to keep in parity with.

### 2. Contacts path — `winners` consumption is intentional, not a bug
- `build_cloud_workflows.py:~733` (`ENRICH_MERGE` wrapper): `const winners = row.scored.winners || {}` — raw values.
- `n8n/code/mergeCompanies.js:1-22`'s own header comment explains why: *"winners raw-ness is load-bearing for contacts (jobtitle casing would be lowercased for every promoted contact)."* Out of scope for this phase; do not touch.

### 3. Companies waterfall path — already uses `best`, not `winners`
- `build_cloud_workflows.py:1640-1648` (inside `ENRICH_MERGE_CO`): builds `candidate[f] = b.normalizedValue` from `best[f]`, **not** `winners`. This directly contradicts the literal wording of the task brief's premise #1 ("only `winners` is consumed downstream") for the companies branch specifically — verified false for this path; true only for contacts. Recorded here per the instruction to verify, not re-derive, the premises.
- `CONFLICT_WATCH = ["lv_revenue_band", "lv_employee_band"]` (line 1619): fields with >1 source and zero agreement are excluded from `candidate` and reported in `conflicts` (never promoted, `needs_review`). This is the existing, working, size-conflict-withholding mechanism (CLAUDE.md §17.2).
- **This path is deterministic-only by construction already** — it never touches the judge, never calls an HTTP node, and RO-2 (`test_ro2_judge_gate_cannot_see_size_conflicts`, see below) already proves the judge cannot see `row.conflicts` or `CONFLICT_WATCH`. No change needed here; Phase 15.5 must not disturb it.

### 4. Companies research path — the actual, confirmed defect
- `build_cloud_workflows.py:1660-1673`: the second `mergeCompanies` call passes `researchData` (raw `rc.data` filtered to non-blank) with **one flat `confidence: rc.confidence || 80`** for every field in the call, and `evidence: rc.evidence_by_field`. `rc.data` is never scored — `scoreCandidates` is never imported or called anywhere in the research/judge chain (confirmed: `grep -n "scoreCandidates" scripts/build_cloud_workflows.py` only matches the two waterfall-branch inlines, `n8n/code/judge.js` never imports `scoreEnrichment.js`).
- **Confirmed: normalizeProviders.js never emits candidates for any of `_JUDGE_DATA_FIELDS`.** `lushaCandidates`/`apolloCandidates`/`zoominfoCandidates` (`n8n/code/normalizeProviders.js:134-296`) only ever push `lv_revenue_band`, `lv_employee_band`, `industry`, `lv_country_region_normalized` (companies) or contact fields — never `lv_org_type`, `lv_produces_content`, or the vendor flags. **This means there is no live "provider vs. research" conflict on ICP-semantic fields today** — providers structurally cannot produce a competing candidate for these fields. The JG-1 "`lv_org_type` conflicts with the provider-derived prior" trigger (`computeEscalation`, `judge.js:100-133`, line 111) is actually comparing research against `existingRecord.lv_org_type` — i.e. **a previously-*written* value** (from an earlier research+merge run, or a manual edit), not a same-run provider candidate. This distinction matters for the design below (§Recommendation).

### 5. Judge payload — confirmed to omit all scoring, exactly as the roadmap states
- `buildJudgeRequestBody` (`judge.js:183-225`): `company.research_candidate = {data: restrictedData (the 5 `_JUDGE_DATA_FIELDS` only), evidence_by_field}`, plus `escalation_reasons`. No confidence breakdown, no recency, no agreement signal, no "what changed" framing beyond the reason string. `_JUDGE_DATA_FIELDS` (lines 178-181) is exactly the 5-field judge-eligible set this phase needs as its tier boundary — it already exists, hand-typed once, in exactly one place.

### 6. Tier boundary — already disjoint, just not asserted as a boundary
- `_JUDGE_DATA_FIELDS` (`judge.js:178-181`): `lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`.
- `CONFLICT_WATCH` (`build_cloud_workflows.py:1619`): `lv_revenue_band`, `lv_employee_band`.
- These two sets are disjoint today. No test currently asserts this disjointness as an invariant (see §Cost Bounding).
- `config/field_policy.yaml` companies block (`config/field_policy.yaml:3-84`) confirms the class split: `domain` (manual_protected), `industry`/`numberofemployees` (stale_refreshable), `annualrevenue` (review_required), `lv_revenue_band`/`lv_employee_band` (system_owned but numeric — never research-eligible), vs. `lv_org_type`/`lv_produces_content`/`lv_content_type`/`lv_is_hardware_vendor`/`lv_is_gambling_operator` (system_owned, `allow_web_research: true`, `allow_sonnet_escalation: true` on the org_type/produces_content/hardware/gambling rows).
- `lv_country_region_normalized` is firmographic (provider-derived only) and is **not** among the research prompt's `required_fields` (`build_cloud_workflows.py:1495-1496` lists exactly the 5 `_JUDGE_DATA_FIELDS`) — confirms it stays deterministic-only and never enters this phase's scope.

### 7. `evidence.last_seen` — confirmed dead, and the production prompt diverges from the dev-oracle prompt
- `src/schemas.py:12-16` declares `ProviderEvidence.last_seen: Optional[str]`; `src/web_research.py:44` asks the model for it in the **dev-oracle** system prompt. **Neither `n8n/code/webResearch.js` nor `build_cloud_workflows.py`'s production `researchSystemPrompt()` (lines 1448-1471) ever request or read `evidence.last_seen`** — the production prompt's JSON schema (lines 1465-1469) has no `evidence` key at all, only `data`, `evidence_by_field`, `entity_resolution`, `matched`, `confidence`. This is a second, previously-undocumented prompt-parity gap (distinct from the `test_prompt_parity_vendor_flags` check at `tests/test_judge_spec.py:75-95`, which only checks the two vendor-flag field names appear in both prompts — it does not check `evidence.last_seen`). Recommendation: do not resurrect `evidence.last_seen` — supersede it entirely with the `page_age`-derived `recencyDate` (§below), and remove the dead field from the dev-oracle prompt/schema in this phase's cleanup so nothing asks for data nobody reads.

### 8. RO-2's structural-proof pattern — the template to extend, not duplicate
- `tests/test_judge_spec.py:161-186` (`test_ro2_judge_gate_cannot_see_size_conflicts`): asserts (a) the Judge Gate node's `jsCode` string contains neither `row.conflicts` nor `CONFLICT_WATCH`, and (b) BFS graph-ancestry (`_reachable`, lines 26-39) proves Judge Gate is upstream of Merge Company and never the reverse. This is the exact mechanism Phase 15.5's cost-bounding criterion needs — extend it, do not re-invent a different proof style.

### 9. Cost-cap enforcement exists but is entirely untested
- `ENRICH_JUDGE_GATE` (`build_cloud_workflows.py:1528-1566`): a `remaining` counter loop enforcing `MAX_SONNET_VALIDATIONS_PER_RUN` (default 10), inline inside the Python-string wrapper — **not** a function in `judge.js`. Confirmed via `grep -rn "MAX_SONNET_VALIDATIONS_PER_RUN" tests/` → zero matches. No test exercises this loop, numerically or otherwise. `tests/n8n/judge.test.mjs` and `tests/n8n/judgeFailure.test.mjs` (both read in full) test every other `judge.js` export but this counter does not exist as an export because it does not exist as a function.
- `mergeCompanies.js` has **zero direct unit tests today** (confirmed: no `tests/n8n/mergeCompanies*.test.mjs`; the only repo reference to `mergeCompanies` inside `tests/` is a docstring mention in `tests/test_web_research_spec.py:78`). Any new `mergeCompanies` option should ship with its first direct test.

### 10. Anthropic `web_search` tool response shape — confirmed via official docs (2026-07-22 fetch)
`https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool` — `web_search_tool_result` content blocks carry, per result: `url`, `title`, `page_age` ("When the site was last updated", example value `"April 30, 2025"` — free-text, not guaranteed ISO), `encrypted_content`. Citation blocks (`web_search_result_location`, attached to the model's final text) carry `url`, `title`, `encrypted_index`, `cited_text` — **no `page_age` on the citation itself**; `page_age` lives only on the originating `web_search_result` block, keyed by `url`. Today, `researchCandidateFromHttpItem` (`n8n/code/webResearch.js:93-107`) reads `item.content` (the full raw Anthropic response body — confirmed available at this node since it is the direct output of the HTTP Request node) but **only extracts `type === "text"` blocks** (`extractFinalJson`, lines 68-81) — every `web_search_tool_result` block, including its `page_age` values, is present in the same array and is silently discarded today.

---

## Collapse-Point Analysis

Three distinct "collapse points" exist in the pipeline; only one is the actual defect this phase must fix:

1. **`scoreCandidates` → `winners` (contacts).** Intentional, documented, out of scope.
2. **`scoreCandidates` → `best[f].normalizedValue` (companies waterfall).** Already correct for its purpose (deterministic firmographic promotion); discards A/R/G/T beyond the 2-field conflict check, but since this path structurally can never reach the judge (RO-2), the discarded information was never going to be used by an adjudicator anyway. **No change recommended here.**
3. **`rc.data` → `mergeCompanies` directly, bypassing `scoreCandidates` entirely (companies research).** This is the real defect. Zero A/R/G/T, one flat confidence for every field in the call, and the judge (when triggered) sees none of it. **This is what Phase 15.5 must fix.**

The fix does not require changing `mergeCompanies`' core contract (`existingProps, candidateRow, fieldPolicy?, opts?` → `{canonicalPatch, provenance, cacheKeys, decisions}`), which has been stable across three phases (Phase 11 introduction, Phase 13 D6 second-call pattern, Phase 15 provenance-blob rewrite). The smallest change that preserves it: add one **optional, additive** key to `opts` — `opts.confidenceByField: {field: number}` — that, when present for a given field, overrides `opts.confidence` for that field only. Every existing caller (the waterfall call at line 1648, and any future direct unit test) is unaffected because the key is simply absent for them.

```js
// n8n/code/mergeCompanies.js — additive change inside mergeCompanies(), ~3 lines
const confidenceByField = (opts && opts.confidenceByField) || {};
// ...inside the per-field loop, replacing the single `confidence` read:
const confidence = confidenceByField[field] != null ? confidenceByField[field]
  : ((opts && opts.confidence != null) ? opts.confidence : 80);
```

---

## Recommendation: Research Candidates and `scoreCandidates`

**Neither pure option (a) nor pure option (b) as posed is quite right; the correct design is a refined version of (a).**

- Option (a) as literally stated ("research joins `scoreCandidates` as a 4th source") implies mixing research into the *same* candidate array as ZoomInfo/Apollo/Lusha. But §"Current-State Map" item 4 established that **no provider ever produces a candidate for any `_JUDGE_DATA_FIELDS` field** — there is no simultaneous 4-source group to join. Implementing (a) literally would be a no-op: `scoreCandidates` would receive a group of size 1 (research only), `G` (agreement) would always be `0`, and nothing would improve over today except that `A`/`R`/`T` become visible.
- Option (b) ("research stays parallel, gains an equivalent recency weight") fixes the recency gap in isolation but leaves the judge exactly as under-grounded as today — no score, no agreement signal, no `A`/`T` breakdown to cite.

**Recommended: construct a genuine second candidate — the "prior on file" — and score research against it using the unmodified `scoreCandidates`.** For each `_JUDGE_DATA_FIELDS` field present in `rc.data`:

```js
// New: n8n/code/judge.js — scoreResearchCandidates(row), calls the existing,
// UNMODIFIED scoreEnrichment.scoreCandidates. No new scoring engine.
const { scoreCandidates } = require("./scoreEnrichment");

function scoreResearchCandidates(researchCandidate, existingRecord, provenance, opts) {
  const rc = researchCandidate || {};
  const data = rc.data || {};
  const existing = existingRecord || {};
  const prov = provenance || {}; // parsed lv_enrichment_provenance blob, if any
  const candidates = [];

  for (const field of _JUDGE_DATA_FIELDS) {
    if (data[field] === undefined || data[field] === null || data[field] === "") continue;
    candidates.push({
      field, source: "claude_web", value: data[field], normalizedValue: data[field],
      accuracy: typeof rc.confidence === "number" ? rc.confidence / 100 : 0.6,
      recencyDate: (rc.recency_by_field && rc.recency_by_field[field]) || null,
    });
    const priorValue = existing[field];
    if (priorValue !== undefined && priorValue !== null && priorValue !== "") {
      const priorEntry = prov[field]; // {confidence, verified_at, ...} from Phase 15's blob
      candidates.push({
        field, source: "prior_on_file", value: priorValue, normalizedValue: priorValue,
        accuracy: (priorEntry && typeof priorEntry.confidence === "number")
          ? priorEntry.confidence / 100 : 0.6,
        recencyDate: (priorEntry && priorEntry.verified_at) || existing[field + "_verified_at"] || null,
      });
    }
  }
  const { best } = scoreCandidates(candidates, {
    trust: { claude_web: 0.78, prior_on_file: 0.9 }, // 0.78 = source_registry.yaml's existing claude_web trust_rank
    now: (opts && opts.now) || new Date().toISOString(),
  });
  return best; // {field: {value, normalizedValue, source, score, components:{A,R,G,T}, agreedBy}}
}
```

Why this is correct and why it is the *smallest* correct design:
- Reuses `scoreCandidates` byte-for-byte — no new scoring formula, no new weights, no parity burden.
- The `T` (trust) value for `prior_on_file` (0.9) and the `A` (accuracy) sourced from the **actual stored provenance confidence** (Phase 15's `lv_enrichment_provenance` blob, `provenance[field].confidence`) — not a guessed constant — means the "does research agree with what's on file" comparison is grounded in a real historical confidence figure already being persisted for exactly this purpose.
- `G` (agreement) now has real meaning: 1.0 if research corroborates the prior, 0.0 if it contradicts it (which is precisely when `computeEscalation`'s `org_type_conflict` trigger already fires) — this is not a coincidence, it is the same signal expressed two ways, and having both together is what lets the judge "cite what it relied on" (criterion 3).
- **Caution required (see Pitfalls):** `prior_on_file` is not an *independent* corroborating source — if the prior was itself written by an earlier research run, "agreement" is partly the model agreeing with its own past output. The judge payload must label this distinctly, not present it as if it were a second live source (see §Judge Payload Design).

### Evaluating against the 20-row smoke set

The 20 rows in `.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md` (10 closed-won, 10 closed-lost) and the parsed fixture `tests/fixtures/evidence_sufficiency_cases.json` (20 rows: `company`, `domain`, `citation_url`, `claim`, `expected`) are the only real, recorded research outputs in the repo. **Important limitation, stated plainly: none of these 20 real runs captured `page_age`** (the field was never extracted at the time) and none has a recorded `existingRecord.lv_org_type` prior (the smoke script reads live HubSpot but the doc does not log what was already on file). Any test against these 20 rows for *this* phase must therefore:
1. Reuse the recorded `citation_url` / `claim` / `expected` fields to prove `applyEvidenceSufficiency` behavior is unaffected (regression-only, already covered by `judge.test.mjs`).
2. **Layer synthetic `recencyDate` and synthetic `prior_on_file` values onto the 20 rows** to exercise the new scoring path — e.g. QRIC (row 19, `claim:false`) with a synthetic fresh `page_age` and a synthetic stale `prior_on_file = "governing_body_league"` should score low agreement + fire `org_type_conflict`-equivalent routing; Supertech Electronics (closed-lost row, hardware-vendor false positive) with no prior on file should score on `A`/`R`/`T` alone (no `prior_on_file` candidate) and still route to the judge via the existing `hardware_vendor_detected` trigger untouched by any of this phase's changes.
3. This is an offline, fixture-driven unit test (extend `evidence_sufficiency_cases.json` or add a sibling fixture with the two new synthetic fields) — it proves the *mechanism* works on real evidence-URL shapes, not that the historical page ages were literally reconstructed (they weren't recorded and cannot be).

**Recommend documenting this limitation in the new test's docstring** so a future reader does not assume `page_age` values in the fixture are historically accurate.

---

## recencyDate Sourcing

Verified 2026-07-22 against `https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool` (official Anthropic docs, fetched directly):

| Option | Verdict | Reason |
|---|---|---|
| Anthropic `web_search_tool_result.page_age` | **Recommended** | Directly returned by Anthropic's server per search result (`url`, `title`, `page_age`, `encrypted_content`); no model reasoning involved, no extra API call — the `content` array is already present at the node that already reads it (`researchCandidateFromHttpItem`, `webResearch.js:93-107`) and is simply not scanned for anything but text blocks today |
| Model self-report (resurrect `evidence.last_seen`) | Rejected | Requires the model to reliably extract and format a date from page content it may not clearly state; redundant with `page_age`, which Anthropic's crawler already computes and which is strictly more reliable than an LLM's read of the same page |
| URL-embedded date parsing | Rejected | Confirmed fragile by the user's own example: Wyong's citation URL contained `20210406` (2021-04-06), which is the URL's own slug date, not necessarily "when this content became true" — no general pattern exists across arbitrary URLs, and most cited URLs in the 20-row set (`.../race-fields-footage/`, `.../news/`, YouTube handles) carry no date at all |

**Injecting "today's date" into the research prompt is NOT required.** The recency computation (`_ageDays`/`_recency`, `scoreEnrichment.js:24-37`) is entirely code-side: it takes an absolute `recencyDate` (from `page_age`) and an `opts.now` (already supplied deterministically by the caller as `new Date().toISOString()`, e.g. `build_cloud_workflows.py:1386,1649`) and computes age in days. The model never needs to know "now" for this calculation to be correct — it only ever needs to answer "when was this page last updated," which is exactly what `page_age` already answers without being asked.

**Implementation location and shape.** Extend `webResearch.js` (parity-relevant surface — but see note below) with a new pure function:

```js
// n8n/code/webResearch.js — new function, called from researchCandidateFromHttpItem
function extractPageAgeByField(content, evidenceByField) {
  const blocks = (Array.isArray(content) ? content : [])
    .filter((b) => b && b.type === "web_search_tool_result" && Array.isArray(b.content));
  const byUrl = {};
  for (const block of blocks) {
    for (const result of block.content) {
      if (result && result.type === "web_search_result" && result.url) {
        byUrl[_normalizeUrlForMatch(result.url)] = result.page_age || null;
      }
    }
  }
  const out = {};
  for (const [field, url] of Object.entries(evidenceByField || {})) {
    const key = _normalizeUrlForMatch(url);
    out[field] = byUrl[key] || null; // unmatched -> null -> scoreCandidates' existing neutral 0.5
  }
  return out;
}
// _normalizeUrlForMatch: strip protocol, leading www., trailing slash, query/fragment —
// tolerant matching because the model may paraphrase the URL slightly when citing it.
```

**Parity note:** this function is HTTP-response-shape glue, not shared business logic — it has no Python counterpart to keep in parity with, following the exact precedent `src/judge.py`'s own header comment already states for judge HTTP plumbing ("a 'parity test' against a second hand-written copy of glue code proves nothing"). No `src/*.py` change is required for the extraction itself; only the dead `evidence.last_seen` field should be removed from `src/web_research.py`'s prompt as cleanup (§Current-State Map item 7).

**Failure mode:** unmatched URL (model paraphrased it) or unparseable `page_age` string → `recencyDate: null` → `scoreCandidates`'s existing `_recency()` already returns neutral `0.5`. No new failure path is introduced; the existing graceful-degradation behavior is inherited for free.

---

## Tier Boundary (precise, testable)

| Field | Tier | Ever a model call? | Basis |
|---|---|---|---|
| `domain` | Deterministic-only | No | `field_policy.yaml` manual_protected; never in research `required_fields` |
| `industry` | Deterministic-only | No | stale_refreshable; provider-only, never researched |
| `numberofemployees` | Deterministic-only | No | native firmographic |
| `annualrevenue` | Deterministic-only | No | review_required |
| `lv_revenue_band` | Deterministic-only (`CONFLICT_WATCH`) | No | JG-2: LLMs poorly calibrated on numeric plausibility |
| `lv_employee_band` | Deterministic-only (`CONFLICT_WATCH`) | No | ditto |
| `lv_country_region_normalized` | Deterministic-only | No | provider-derived only; absent from research `required_fields` (`build_cloud_workflows.py:1495-1496`); a hard-veto INPUT (non-ANZ) but categorical-firmographic, not identity/classification |
| `lv_org_type` | Judge-eligible | Only on JG-1 trigger | `_JUDGE_DATA_FIELDS`; classification |
| `lv_produces_content` | Judge-eligible | Only on JG-1 trigger | ditto; hard-veto field |
| `lv_content_type` | Judge-eligible | Only on JG-1 trigger | ditto |
| `lv_is_hardware_vendor` | Judge-eligible | Only on JG-1 trigger | ditto; hard-veto input |
| `lv_is_gambling_operator` | Judge-eligible | Only on JG-1 trigger | ditto; graduated-deduction input |

**Mechanically assertable test** (new, static — no pipeline execution needed, mirrors `tests/test_taxonomy_conformance.py`'s TX-* style):
```python
def test_ta2_judge_eligible_and_deterministic_fields_are_disjoint():
    from n8n... # via a small JS-reading helper, or duplicate the two literals from
                # judge.js / build_cloud_workflows.py and assert no overlap + exact set membership
    JUDGE_ELIGIBLE = {"lv_org_type", "lv_produces_content", "lv_content_type",
                       "lv_is_hardware_vendor", "lv_is_gambling_operator"}
    CONFLICT_WATCH = {"lv_revenue_band", "lv_employee_band"}
    DETERMINISTIC_ONLY = CONFLICT_WATCH | {"domain", "industry", "numberofemployees",
                                            "annualrevenue", "lv_country_region_normalized"}
    assert JUDGE_ELIGIBLE.isdisjoint(DETERMINISTIC_ONLY)
```
Prefer reading `_JUDGE_DATA_FIELDS` out of the actual `n8n/code/judge.js` source text (regex, same style `test_prompt_parity_vendor_flags` already uses at `tests/test_judge_spec.py:75-95`) rather than hand-retyping the list a third time — one more hand-typed copy of this list is exactly the drift TX-4 already exists to prevent for the taxonomy; do not reintroduce that pattern here.

---

## Judge Payload Design

Extend `buildJudgeRequestBody` (`judge.js:183-225`) with one additive key, still satisfying JG-2 (identity/classification only — the new key is built exclusively from `_JUDGE_DATA_FIELDS`, so no numeric firmographic value can ever appear in it):

```js
const company = {
  name: id.companyName || existing.name || null,
  domain: id.domain || existing.domain || null,
  existing_lv_org_type: existing.lv_org_type || null,
  research_candidate: { data: restrictedData, evidence_by_field: rc.evidence_by_field || {} },
  // NEW — scoring grounding, restricted to _JUDGE_DATA_FIELDS only (JG-2 preserved):
  scoring: (row.research_scoring || {}),  // {field: {value, source, score, components:{A,R,G,T}, agreedBy}}
  escalation_reasons: (row && row.judge_reasons) || [],
};
```

System-prompt addition (one sentence, appended to the existing `system` array in `buildJudgeRequestBody`):

> "The `scoring` object shows how the research candidate compares to the value already on file (`prior_on_file`), including a recency-derived term (higher = fresher evidence). `prior_on_file` is not an independent corroborating source — it is what is already recorded, which may itself derive from an earlier, unverified research pass. Do not treat agreement with `prior_on_file` as evidence; ground the decision in the cited URLs only."

This directly satisfies criterion 3 ("the judge receives the full ranked candidate set + scoring components + web-search grounding, and its verdict cites which it relied on") while explicitly guarding against the one new risk the design introduces (§Common Pitfalls, item 2).

No change to `_JUDGE_DATA_FIELDS`, no `tools` key added (Pitfall 5 stays satisfied — the scoring computation happens in the Judge Gate node, upstream of Build Judge Request / Judge Call, not inside them).

---

## Cost Bounding + Structural Proof

**Existing mechanism (verified, works today):** `ENRICH_JUDGE_GATE`'s inline `remaining` counter (`build_cloud_workflows.py:1539-1564`) already enforces `MAX_SONNET_VALIDATIONS_PER_RUN` and `ALLOW_SONNET_ESCALATION` upstream of the Judge Call HTTP node — physically, not just by convention, matching the RO-2/Pitfall-4 precedent.

**Gap (confirmed):** this loop is untestable today because it lives only inside a Python multi-line string, never as an exported, callable function. `grep -rn "MAX_SONNET_VALIDATIONS_PER_RUN" tests/` returns zero matches.

**Fix:** extract the loop into a pure, exported function in `judge.js`:

```js
// n8n/code/judge.js — new function, called by the ENRICH_JUDGE_GATE wrapper instead of
// an inline loop. Same semantics, now independently unit-testable.
function applyCostCap(rows, maxPerRun) {
  let remaining = maxPerRun;
  return rows.map((row) => {
    if (!row.needsJudge) return row;
    if (remaining <= 0) return { ...row, needsJudge: false, capped: true };
    remaining -= 1;
    return row;
  });
}
```

**New tests (both required for criterion 6):**
1. `test_cost_cap_asserted` (`tests/n8n/judge.test.mjs`): feed 15 synthetic trigger-firing rows through `applyCostCap(rows, 10)`; assert exactly 10 have `needsJudge: true` and the remaining 5 have `capped: true` and (via the existing `applyUnadjudicated` fail-safe path, unchanged) never carry an unadjudicated hard-veto `true`.
2. **Extend, do not duplicate, `test_ro2_judge_gate_cannot_see_size_conflicts`** (`tests/test_judge_spec.py:161-186`): add the same two assertions (no `row.conflicts`/`CONFLICT_WATCH` string reference, BFS graph-ancestry) against whichever node now hosts `scoreResearchCandidates` — if folded into the existing Judge Gate node (recommended, see below), this is the *same* test, no new one needed; if implemented as a separate node, duplicate the pattern verbatim against the new node's `jsCode`.

**Recommended wiring: fold `scoreResearchCandidates` into the existing Judge Gate node** (`ENRICH_JUDGE_GATE`), called immediately after `applyEvidenceSufficiency` and before `computeEscalation`, attaching `row.research_scoring = best` to **every** researched row regardless of whether `needsJudge` fires (criterion 1: "no information is discarded before the judge" — even non-escalated rows keep their scoring, available to `ENRICH_MERGE_CO` for `confidenceByField`). This is the smallest possible diff: **zero new n8n nodes, zero new wiring/connections, zero new HTTP calls** — one more function call inside a node that already runs `applyEvidenceSufficiency` and `computeEscalation` on the same row.

**Boundary that must hold and should be commented in the code:** the new scoring step is strictly additive to the judge's *input* and to `mergeCompanies`' *confidence*. It must **never** be wired as an alternate escalation gate — i.e., a high composite score must never suppress an already-fired `computeEscalation` reason. `computeEscalation`'s existing `reasons` list stays the sole, unchanged gate for whether the judge is invoked at all.

---

## Proposed Spec Requirements (`docs/WEB-RESEARCH-SPEC.md`)

`§8` (Judgement) already has `JG-1`..`JG-5`. Propose a new `§8.5 Tiered adjudication` section, extending rather than duplicating:

**TA-1.** Every research candidate for a `_JUDGE_DATA_FIELDS` field MUST be scored via the existing A/R/G/T formula (`scoreEnrichment.js`'s `scoreCandidates`, unmodified) before any merge or judge decision. The resulting components MUST be attached to the row for inspection/audit even when no escalation trigger fires (extends §1's resolution-order framing: scoring now runs between retrieval and judgement unconditionally, not only on escalation).

**TA-2.** Size/firmographic fields (`domain`, `industry`, `numberofemployees`, `annualrevenue`, `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`) MUST NEVER be scored against, or routed to, the judge. Judge-eligible fields are exactly `_JUDGE_DATA_FIELDS`. The two sets MUST be disjoint, asserted by a static conformance test (mirrors TX-4's generated-single-source pattern; no hand-retyped second copy of either list).

**TA-3.** A research candidate's `recencyDate` MUST be sourced from the Anthropic `web_search_tool_result.page_age` field for the matching evidence URL, never from the model's free-text self-report and never parsed out of the URL string. Absent/unparseable `page_age` yields `recencyDate: null`, handled by `scoreCandidates`' existing neutral-`0.5` rule — no new penalty path may be introduced.

**TA-4.** Recency is an ordering input to the composite score only (extends TS-1). No code path may use `recencyDate`, `page_age`, or staleness to set any field to `false`, to fire `lv_anti_icp_flag`, or to bypass the confidence-based promotion gate already governing `mergeCompanies`.

**TA-5.** The judge payload MUST include the scored components (`A`, `R`, `G`, `T`, composite score, `agreedBy`) for every `_JUDGE_DATA_FIELDS` field carried by the escalation, restricted to that field set (extends JG-2 to the new payload key — no numeric firmographic value may ever appear in it).

**TA-6.** The synthetic "prior on file" candidate (the company's current stored value plus its Phase-15 provenance-blob confidence and cache-key `_verified_at`) is NOT an independent corroborating source. The judge payload and system prompt MUST label it distinctly (`prior_on_file`) and MUST instruct the judge not to treat agreement with it as evidence.

**TA-7.** Judge invocation count per run MUST be capped by `MAX_SONNET_VALIDATIONS_PER_RUN`, and the cap-enforcement logic MUST be a unit-testable pure function (not inline-only code inside a build-script string), asserted by a test that exceeds the cap and checks the exact overflow count falls back to the existing `applyUnadjudicated` fail-safe.

**TA-8.** `mergeCompanies`, when a scored composite is available for a `_JUDGE_DATA_FIELDS` field, MUST use that composite (via the additive `opts.confidenceByField` map) rather than the flat whole-candidate confidence. The existing flat `opts.confidence` remains the default/fallback; the waterfall call path (size/firmographic fields) is byte-identical and unaffected.

---

## Standard Stack

No new dependencies. This phase is entirely additive functions inside three existing, already-imported files (`scoreEnrichment.js` reused unmodified as an import; `judge.js`, `webResearch.js`, `mergeCompanies.js` extended) plus one new spec section and new tests. `npm`/`pip` package surface is unchanged — do not add a date-parsing library; native `Date.parse` already handles the documented `page_age` example format (`"April 30, 2025"`), and a parse failure already degrades safely to `null` via the existing `_ageDays` guard (`scoreEnrichment.js:24-30`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Scoring research candidates | A second scoring engine/formula for research | The existing `scoreCandidates` (`scoreEnrichment.js`), imported unmodified | One formula, one set of weights, one place that could have a bug |
| "What changed" grounding for the judge | A bespoke diff/comparison algorithm | `scoreCandidates`' existing `G` (agreement) term against a synthetic `prior_on_file` candidate | Reuses the exact same agreement logic providers already get |
| Recency parsing | A custom date-freshness heuristic keyed off URL slugs | Anthropic's own `page_age` field, already computed server-side | More reliable than any heuristic this project could write; zero extra API calls |
| Cost cap testing | A new mocking framework for n8n node execution | Extract the existing counter loop into one plain exported function, unit-test it directly (same pattern every other `judge.js` function already uses) | The repo's whole testing convention is "export pure functions, test them directly," not "execute jsCode strings" |

**Key insight:** every piece needed for this phase already exists somewhere in the codebase in a slightly wrong location (provenance blob confidence, `page_age` in the raw HTTP response, the tier boundary as two disjoint constants, the RO-2 BFS test pattern). The work is wiring and testing, not invention.

## Common Pitfalls

### Pitfall 1: Treating "research joins scoreCandidates" as literally mixing providers and research in one array
**What goes wrong:** implementer builds a single `toCandidates()`-style call mixing Lusha/Apollo/ZoomInfo output with research output for `lv_org_type`, expecting real multi-source agreement.
**Why it happens:** the roadmap phrasing ("a 4th source") reads that way at first glance.
**How to avoid:** confirmed no provider ever emits a candidate for any `_JUDGE_DATA_FIELDS` field (§Current-State Map item 4) — the second candidate must be the *existing record* (`prior_on_file`), not a provider.
**Warning signs:** a `G` (agreement) term that is always `0` in every test case — a sign the "second source" was never actually populated.

### Pitfall 2: `prior_on_file` agreement misread as independent corroboration
**What goes wrong:** a company gets re-researched, the model repeats its own earlier (possibly wrong) classification, `G=1.0` (perfect "agreement"), composite score looks strong, and either a human reviewer or the judge treats this as two-source consensus when it is really one source echoing itself.
**Why it happens:** `scoreCandidates`' `G` term was designed for genuinely independent providers; reusing it against a value that may have been written by an earlier research run blurs that assumption.
**How to avoid:** TA-6 — label `prior_on_file` distinctly in the judge payload and system prompt; never let this composite score suppress an already-fired `computeEscalation` trigger (§Cost Bounding, "Boundary that must hold").
**Warning signs:** a needs_review rate that drops sharply after this phase ships with no corresponding increase in evidence quality — a sign the new scoring is being used to bypass escalation rather than ground it.

### Pitfall 3: Recency silently degrading coverage instead of failing loud
**What goes wrong:** URL-matching between `evidence_by_field` and `web_search_tool_result.url` fails more often than expected (trailing slashes, `www.`, tracking params, or the model paraphrasing the cited URL), so `recencyDate` is `null` far more often than genuinely "unknown," and nobody notices because `null` degrades gracefully to neutral `0.5` rather than erroring.
**Why it happens:** the model's final JSON citation and the raw search-result `url` are two independently-generated strings that happen to usually, not always, match exactly.
**How to avoid:** normalize both sides the same way (`isCitationSufficient`'s existing `www.`-stripping is a precedent) before comparing; surface a `research_scoring[field].recency_source: "page_age" | "unmatched"` flag in the row so match-rate is observable in future smoke runs, not silently invisible.
**Warning signs:** every researched company's `recencyDate` is `null` in a live run — check the URL-matching function before assuming Anthropic stopped returning `page_age`.

### Pitfall 4: Reintroducing a hand-typed second copy of the tier-boundary lists
**What goes wrong:** a new test or a new node hand-retypes `_JUDGE_DATA_FIELDS` or `CONFLICT_WATCH` as a literal array a second time, and the two copies drift silently exactly the way TX-4 already exists to prevent for the taxonomy.
**Why it happens:** it is faster to type five strings than to import/regex-extract them from the other file.
**How to avoid:** import `_JUDGE_DATA_FIELDS` from `judge.js` everywhere it is needed (it is not currently exported — export it); read `CONFLICT_WATCH` out of the built workflow JSON via regex in the test (already the pattern `test_prompt_parity_vendor_flags` uses), do not hand-copy it into a Python list.

### Pitfall 5: `mergeCompanies.js` shipping its first behavioral change with zero direct tests
**What goes wrong:** `opts.confidenceByField` lands with only indirect coverage via the built-workflow JSON, same as today (§Current-State Map item 9 confirms zero direct tests exist currently).
**Why it happens:** the module has survived three phases without a direct unit test, so there is no existing pattern to copy from within this file's own test history.
**How to avoid:** add `tests/n8n/mergeCompanies.test.mjs` (does not exist today) covering: (a) `opts.confidenceByField` overrides `opts.confidence` for the specified field only, (b) absent `confidenceByField` reproduces today's exact behavior byte-for-byte (regression guard for the waterfall call path), (c) the `domain` hard-guard and evidence-gate behavior already documented in the file's header comments, currently untested directly.

## Risks

- **Scope creep risk:** the "smallest diff" design still touches four files (`judge.js`, `webResearch.js`, `mergeCompanies.js`, `build_cloud_workflows.py`'s `ENRICH_JUDGE_GATE`/`ENRICH_MERGE_CO`/`ENRICH_BUILD_JUDGE_REQUEST` string constants) plus one spec section and multiple new tests. The planner should sequence this as: (1) scoring function + tests, (2) recencyDate extraction + tests, (3) `mergeCompanies` additive option + first-ever direct test, (4) judge payload extension, (5) cost-cap extraction + test, (6) spec section, in that dependency order — each step independently offline-testable before the next.
- **`page_age` format risk:** Anthropic's documented example (`"April 30, 2025"`) is human-readable text, not a guaranteed ISO 8601 string across all indexed sources; `Date.parse` handles common English formats but is not guaranteed for every locale Anthropic's crawler might return. Low risk given the existing graceful-null-fallback, but worth a defensive `try/catch` around the parse (mirroring `_ageDays`'s existing `Number.isNaN` guard).
- **Provenance blob dependency:** using `provenance[field].confidence` as the `prior_on_file` accuracy assumes the Phase 15 provenance blob is actually populated on the existing record by the time a re-research runs. On a company's *first* research pass (no prior blob), there is no `prior_on_file` candidate at all — this degrades gracefully to a single-candidate score (`G=0`), which is correct and already the common case (most companies are unscored today per the Milestone 3 overview's "0/5" and "3/5" resolution rates).

## Explicit Out of Scope

- n8n Cloud deployment and `$env` → credentials conversion (Phase 16).
- Scheduled-job wiring (SJ-1/SJ-2/SJ-3) and `dedupeSweep.js` activation (Phase 16).
- RT-5 live caching activation (the two cache-key properties exist per Phase 15; actual TTL-based cache-hit skip logic is Phase 16 per `docs/WEB-RESEARCH-SPEC.md` §4 RT-5's own "Phase 16" note).
- The HubSpot-side `lv_icp_fit_score`/`lv_icp_tier` formula (downstream of this pipeline entirely, per the Milestone 3 scope fence — this pipeline writes inputs only).
- Re-running the 20-row smoke against live Anthropic to capture real `page_age` values — tests in this repo are offline-only (constraint stated in the task brief); any recency test in this phase uses synthetic dates layered onto the recorded fixture, not a live replay.
- Contacts-branch scoring changes — `mergeContacts`'s intentional raw-`winners` behavior is untouched (§Current-State Map item 2).
- Removing `evidence.last_seen`/`ProviderEvidence.last_seen` from `src/schemas.py` — recommended as cleanup above but not load-bearing for any of the six criteria; the planner may defer this to a follow-up if it wants to keep this phase's diff minimal.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | `Date.parse` reliably parses every `page_age` format Anthropic's crawler returns, beyond the one documented example (`"April 30, 2025"`) | recencyDate Sourcing | LOW — falls back to `null`/neutral 0.5 on any parse failure, matching existing `_ageDays` behavior; worst case is reduced recency coverage, never a correctness bug |
| A2 | Folding `scoreResearchCandidates` into the existing Judge Gate node (rather than a new node) is acceptable to the planner's preferred node-per-responsibility style elsewhere in this workflow | Cost Bounding + Structural Proof | MEDIUM — if the planner prefers a dedicated node for testability/observability, the RO-2-style test must be duplicated against that new node rather than reusing the existing one; functionally equivalent either way |

**Everything else in this document is `[VERIFIED]`** by direct file read (file:line cited throughout), by running the actual test suite (200 pytest / 77 node, both green, confirmed live in this session), or by fetching the official Anthropic documentation directly (`platform.claude.com`, fetched 2026-07-22, `page_age` field confirmed present in the actual documented response shape, quoted verbatim above).

## Open Questions

1. **Should `prior_on_file`'s accuracy fall back to a fixed constant (proposed: 0.6, matching every other "ungraded" provider default in `normalizeProviders.js`) when no provenance blob exists yet, or should an unscored prior simply be excluded entirely (current proposal)?**
   - What we know: the current design excludes `prior_on_file` entirely when the field is blank on the existing record — this is the common case (first research pass) and degrades correctly to single-candidate scoring.
   - What's unclear: whether a *non-blank* existing value with no parseable provenance entry (e.g. a manually-entered `lv_org_type` from before Phase 15, or a value written by a process that predates the provenance blob) should get a fixed default accuracy (0.6, matching `normalizeProviders.js`'s ungraded-field convention) or be excluded like a blank value.
   - Recommendation: default to 0.6 (matches the existing `normalizeProviders.js` "no per-field grade → base 0.6" convention already used for Lusha/Apollo firmographics) rather than excluding — this is more conservative (a real, unscored prior on file is still informative) and reuses an existing numeric convention rather than inventing a new one.

## Environment Availability

No new external dependencies. All required infrastructure (Anthropic `web_search` tool, HubSpot properties, the `MAX_SONNET_VALIDATIONS_PER_RUN`/`ALLOW_SONNET_ESCALATION` env gates) already exists and is already exercised by the Phase 14 wiring this phase extends.

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest 9.1.1 (Python, `.venv/bin/pytest`) + Node's built-in test runner (`node --test`) |
| Config file | none dedicated — `tests/` convention only |
| Quick run command | `.venv/bin/pytest tests/test_judge_spec.py -x` / `node --test tests/n8n/judge.test.mjs` |
| Full suite command | `.venv/bin/pytest -q` (baseline: 200 passed) + `node --test tests/n8n/*.test.mjs` (baseline: 77 passed) — both confirmed green in this research session |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| TA-1 | Research candidate scored via unmodified `scoreCandidates`, components attached regardless of escalation | unit | `node --test tests/n8n/judge.test.mjs` | ❌ Wave 0 — new `scoreResearchCandidates` test cases |
| TA-2 | Judge-eligible / deterministic-only field sets disjoint | unit (static) | `node --test tests/n8n/judge.test.mjs` or `.venv/bin/pytest tests/test_judge_spec.py` | ❌ Wave 0 |
| TA-3/TA-4 | `recencyDate` sourced from `page_age`, never penalizes/vetoes | unit | `node --test tests/n8n/webResearchFailure.test.mjs` (extend) or new `tests/n8n/recency.test.mjs` | ❌ Wave 0 |
| TA-5/TA-6 | Judge payload carries `scoring` + `prior_on_file` labeling, restricted to `_JUDGE_DATA_FIELDS` | unit | `node --test tests/n8n/judge.test.mjs` | ❌ Wave 0 |
| TA-7 | Cost cap is a pure function, asserted numerically | unit | `node --test tests/n8n/judge.test.mjs` | ❌ Wave 0 — `applyCostCap` does not exist yet |
| TA-7 (structural) | Extend RO-2's BFS+regex proof to the new scoring location | functional | `.venv/bin/pytest tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts` | ✅ exists, extend in place |
| TA-8 | `mergeCompanies.confidenceByField` additive, waterfall path byte-identical | unit | new `node --test tests/n8n/mergeCompanies.test.mjs` | ❌ Wave 0 — file does not exist at all today |

### Sampling Rate
- **Per task commit:** the specific new/extended test file for that task.
- **Per wave merge:** `.venv/bin/pytest -q && node --test tests/n8n/*.test.mjs` (full baseline).
- **Phase gate:** full suite green (expect 200+N pytest / 77+M node, both passing) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/n8n/mergeCompanies.test.mjs` — does not exist; `mergeCompanies.js` has zero direct unit tests today (confirmed).
- [ ] `_JUDGE_DATA_FIELDS` export from `judge.js` — not currently exported (used only internally); needed so tests and the tier-boundary conformance check can import it rather than hand-retype it.
- [ ] Synthetic recency/prior-on-file fixture (extends or sits alongside `tests/fixtures/evidence_sufficiency_cases.json`) — the 20 real rows carry no recorded `page_age` or prior-on-file values (§Recommendation, "Evaluating against the 20-row smoke set").
- [ ] `applyCostCap` function — does not exist; the cap logic is inline-only today.

## Security Domain

`security_enforcement` is not set to `false` in `.planning/config.json` (the config file has only a `workflow` key); treat as enabled.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | No | No auth surface changes in this phase |
| V3 Session Management | No | n/a |
| V4 Access Control | No | n/a |
| V5 Input Validation | Yes | `page_age` extraction and URL-matching must never `throw` on malformed input — mirror `isCitationSufficient`'s existing try/catch-returns-false pattern (`judge.js:24-37`); a malformed Anthropic response must degrade to `recencyDate: null`, never propagate an exception into the Code node (n8n Code node exceptions fail the whole item, breaking the `onError: continueRegularOutput` graceful-degradation contract every other node in this chain relies on) |
| V6 Cryptography | No | n/a |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Malformed/adversarial Anthropic response content (unexpected block shapes) breaking the new `extractPageAgeByField` | Denial of Service (a thrown exception fails the item) | Defensive array/type guards identical to the existing `researchCandidateFromHttpItem`'s never-throws contract; wrap in try/catch, default to `{}` |
| Composite-score inflation via `prior_on_file` agreement being read as independent evidence, silently weakening the effective review threshold | Tampering (of the trust model, not data) | TA-6 — explicit labeling + prompt instruction; `computeEscalation`'s reasons remain the sole judge-invocation gate, never overridable by a high composite score |

## Sources

### Primary (HIGH confidence)
- Direct file reads, this session: `n8n/code/scoreEnrichment.js`, `n8n/code/judge.js`, `n8n/code/normalizeProviders.js`, `n8n/code/mergeCompanies.js`, `n8n/code/webResearch.js`, `n8n/code/escalation.generated.js`, `scripts/build_cloud_workflows.py` (lines 1173-1962), `scripts/gen_escalation_js.py`, `src/judge.py`, `src/web_research.py`, `src/schemas.py`, `config/field_policy.yaml`, `config/escalation_policy.yaml`, `config/taxonomy.yaml`, `docs/WEB-RESEARCH-SPEC.md` (full), `tests/test_judge_spec.py` (full), `tests/n8n/judge.test.mjs` (partial), `.planning/ROADMAP.md`.
- Live test-suite execution, this session: `.venv/bin/pytest -q` → 200 passed; `node --test tests/n8n/*.test.mjs` → 77 passed.
- Anthropic official docs, fetched 2026-07-22: `https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool` — `page_age` field on `web_search_tool_result` result blocks, confirmed verbatim in the documented response example.

### Secondary (MEDIUM confidence)
- `.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md` (full, 171 lines) — the 20 real research-output rows, used for the recommendation's test-design discussion; these are recorded operator-run outputs, not independently re-verified live in this session (offline-only constraint).
- `tests/fixtures/evidence_sufficiency_cases.json` — confirmed shape (`company`, `domain`, `citation_url`, `claim`, `expected`), 20 entries, read directly.

### Tertiary (LOW confidence)
- None — every claim in this document traces to a direct file read, a live test-suite run, or a directly-fetched official doc page.

## Metadata

**Confidence breakdown:**
- Current-state map: HIGH — every claim cites file:line, and the two "verify, don't re-derive" premises from the task brief were checked against source and one was found to be more nuanced than stated (companies-waterfall already uses `best`, not `winners`).
- recencyDate sourcing: HIGH — confirmed via official Anthropic documentation, fetched directly this session, not from training-data recall.
- Judge payload / tier boundary / cost bounding: HIGH — all existing mechanisms (`_JUDGE_DATA_FIELDS`, `CONFLICT_WATCH`, RO-2 test, cost-cap loop) read directly from source; the extension design reuses them without alteration.
- Recommendation on scoring design (prior_on_file candidate): MEDIUM-HIGH — the mechanism (`scoreCandidates` reuse) is verified correct and minimal; the specific accuracy-default choice for an un-provenanced prior (Open Question 1) is a genuine judgment call, flagged as such.

**Research date:** 2026-07-22
**Valid until:** 30 days (stable internal codebase; the one external dependency, Anthropic's `web_search` tool response shape, is a documented, versioned API surface unlikely to change silently — re-verify if `WEB-RESEARCH-SPEC.md` cites a newer `web_search_2026xxxx` tool version by the time this phase executes).
