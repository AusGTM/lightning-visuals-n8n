---
phase: 18-normalization-copy-loop-fixes
plan: 03
subsystem: enrichment-research-normalization
tags: [n8n, code-node, claude-web-research, provider-mapper, hubspot-properties, copy-loop, gap-closure]

# Dependency graph
requires:
  - phase: 18-02
    provides: copy-loop WIRING for lv_sponsorship_reliant (companies researchData fold) and lv_persona_group (contacts winners loop) — both correctly wired but structurally unreachable in production
provides:
  - "GAP 1 (COPY-01) closed end-to-end: the shipped Build Research Request prompt now asks for lv_sponsorship_reliant in both required_fields and the forced JSON schema, proven to survive Validate Research Output's frozen data spread into research_candidate.data"
  - "WR-01 closed: ENRICH_COMPANY_SEARCH_PROPERTIES_CSV now fetches lv_sponsorship_reliant into existingRecord, restoring the merge decision's current_value audit trail"
  - "GAP 2 (COPY-02) closed end-to-end: a new _personaGroup() provider-mapper producer in normalizeProviders.js emits a persona_group candidate from Apollo's and Lusha's own department fields, proven through the compiled Normalize + Score -> Merge Winners chain"
  - "tests/n8n/researchRequestSponsorshipContract.test.mjs — GAP 1 request-contract + validation-hop-survival proof (5 tests)"
  - "tests/n8n/personaGroupProducer.test.mjs — GAP 2 mapper-level + compiled-row-flow proof (6 tests)"
  - "tests/fixtures/companies_jscode_frozen.json re-baselined (Build Research Request, cloud + local_live) under a bounded, recorded diff, isolated commit"
affects: [future-icp-scoring-phases, ship-gate-carry-forward]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Research-prompt field addition: append to BOTH required_fields array and the forced JSON schema string, with its own guidance clause (never folded into an unrelated hard-veto sentence when the new field carries no veto)"
    - "Provider-mapper persona/department producer: read the provider's own raw field, treat a semantically-empty label as a non-signal (null, not fabricated), mirror the accuracy/recencyDate of the adjacent sibling push"

key-files:
  created:
    - tests/n8n/researchRequestSponsorshipContract.test.mjs
    - tests/n8n/personaGroupProducer.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - src/web_research.py
    - n8n/code/normalizeProviders.js
    - tests/fixtures/companies_jscode_frozen.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json

key-decisions:
  - "D-GAP1-scope: fixed the n8n request contract for lv_sponsorship_reliant ONLY — did not bring n8n's required_fields to full parity with src/web_research.py's 9-field REQUIRED_FIELDS. The 3 extra Python-only fields remain a deliberate scope difference."
  - "D-GAP1-noparitytest: no builder-vs-Python parity test was added (a superset assertion fails by design today; a subset assertion cannot catch the drift that actually occurred). The executed request-contract test pins the n8n side directly instead."
  - "D-GAP1-order: within Task 1, the prompt fix + bounded re-baseline landed BEFORE the WR-01 CSV edit, in a separate rebuild, so the CSV edit's zero-frozen-diff result is independently attributable."
  - "D-GAP2-provider: chose the provider-mapper option (Apollo's/Lusha's own department field) over a hand-written title-to-persona heuristic (would fabricate a taxonomy) or a research/judge-prompt extension (costs live tokens, collides with the Phase 16.2 contacts allowlist decision)."
  - "D-GAP2-othervalue: Lusha's live departments:[\"Other\"] is treated as a non-signal (case-insensitive compare), mirroring _industryText's null-rather-than-fabricate precedent from Plan 18-01. A persona group of \"Other\" is not a classification."
  - "D-GAP2-rawvalue: the promoted value is the provider's raw department string (no prettifier/normalizer), matching how seniority already behaves with three mutually inconsistent provider formats."
  - "D-GAP2-nozoominfo: no ZoomInfo persona push — no department field exists in any recorded ZoomInfo shape."
  - "Test-harness self-correction: the first Layer-2 harness attempt for GAP 2 fed the seed row through $input directly, but the CLOUD 'Normalize + Score' node recovers its row via $('Enrichment Gate') and each provider response via $('Lusha Enrich')/$('Apollo Match')/$('ZoomInfo Enrich') by node name (never $input). That mismatch produced a false TypeError-shaped 'red' rather than a real assertion failure. Corrected by reverting the (uncommitted) source fix with `git checkout --` on the two affected files, re-capturing faithful red evidence against the corrected harness, then reapplying the identical source fix — see Deviations."

requirements-completed: [COPY-01, COPY-02]

coverage:
  - id: D1
    description: "The shipped Build Research Request body asks a live model for lv_sponsorship_reliant in both required_fields and the forced JSON response schema, in both variants, and the field survives the frozen Validate Research Output validator into research_candidate.data untouched."
    requirement: "COPY-01"
    verification:
      - kind: unit
        ref: "tests/n8n/researchRequestSponsorshipContract.test.mjs#(b) GREEN: required_fields contains lv_sponsorship_reliant"
        status: pass
      - kind: unit
        ref: "tests/n8n/researchRequestSponsorshipContract.test.mjs#(c) GREEN: the forced JSON response schema declares lv_sponsorship_reliant inside the data shape"
        status: pass
      - kind: unit
        ref: "tests/n8n/researchRequestSponsorshipContract.test.mjs#(d) GREEN: the local_live variant's compiled body also requests the field"
        status: pass
      - kind: unit
        ref: "tests/n8n/researchRequestSponsorshipContract.test.mjs#(e) CHAIN SURVIVAL: research response carrying the field survives Validate Research Output untouched"
        status: pass
      - kind: unit
        ref: "tests/test_companies_factory_frozen.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "ENRICH_COMPANY_SEARCH_PROPERTIES_CSV fetches lv_sponsorship_reliant into existingRecord (WR-01), and the CSV edit moves zero frozen companies Code-node pairs."
    requirement: "COPY-01"
    verification:
      - kind: unit
        ref: "tests/test_fetch_by_id_topology.py"
        status: pass
      - kind: unit
        ref: "tests/test_bug10_company_search_transport.py"
        status: pass
      - kind: unit
        ref: "tests/test_companies_factory_frozen.py (0 diff after CSV edit)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A recorded Apollo contact response produces a persona candidate that wins the waterfall and lands in merge.canonicalPatch through the COMPILED Normalize + Score and Merge Winners bodies, with the persona value never hand-written onto scored.winners by the test; the live Lusha 'Other' label correctly produces no candidate."
    requirement: "COPY-02"
    verification:
      - kind: unit
        ref: "tests/n8n/personaGroupProducer.test.mjs#(b) GREEN: Apollo contacts candidates include a persona candidate"
        status: pass
      - kind: unit
        ref: "tests/n8n/personaGroupProducer.test.mjs#(c) Lusha's live 'Other' label produces NO persona candidate"
        status: pass
      - kind: unit
        ref: "tests/n8n/personaGroupProducer.test.mjs#(e) compiled Normalize + Score yields a non-null persona entry in scored.winners"
        status: pass
      - kind: unit
        ref: "tests/n8n/personaGroupProducer.test.mjs#(f) produced row reaches lv_persona_group in canonicalPatch via compiled Merge Winners"
        status: pass
      - kind: unit
        ref: "tests/n8n/enrichment.test.mjs (no existing contacts assertion broken)"
        status: pass

duration: ~50min
completed: 2026-07-29
status: complete
---

# Phase 18 Plan 03: GAP 1/GAP 2 producers (COPY-01, COPY-02) Summary

**Both Phase-18 verification gaps closed end-to-end: the research prompt now actually asks for `lv_sponsorship_reliant` and a new provider-mapper producer actually emits `lv_persona_group` — both proven live-reachable through compiled node bodies fed by recorded fixtures, not hand-constructed test rows.**

## Performance

- **Duration:** ~50 min
- **Completed:** 2026-07-29
- **Tasks:** 3
- **Files modified:** 9 (2 created, 7 modified)

## Accomplishments

- **GAP 1 / CR-01 closed:** `scripts/build_cloud_workflows.py`'s `COMPANIES_TARGET.research_system_prompt_fn_js` and `research_payload_body_js` now name `lv_sponsorship_reliant` in both the forced JSON response schema and the `required_fields` array, with its own guidance clause (not folded into the existing hard-veto sentence, since sponsorship reliance fires no veto). `src/web_research.py`'s `RESEARCH_SYSTEM` schema string got the matching field so the Python oracle no longer contradicts its own header comment's parity claim.
- **WR-01 closed:** `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` now fetches `lv_sponsorship_reliant` into `existingRecord`, so the merge decision's `current_value` audit field stops being unconditionally misreported as null for this one field. Verified to move zero frozen companies Code-node pairs (feeds only `_hs_http_search_node` HTTP nodes).
- **GAP 2 / COPY-02 closed:** a new `_personaGroup(departments)` helper in `n8n/code/normalizeProviders.js` (mirrors `_industryText`'s null-rather-than-fabricate contract) is wired into `lushaCandidates`' and `apolloCandidates`' contacts branches, immediately after each mapper's existing `seniority` push. Apollo's `departments` and Lusha's live `jobTitle.departments` are the two recorded provider shapes that actually carry a signal; Lusha's live `"Other"` label is deliberately treated as a non-signal.
- Executed the bounded Phase-16.3 frozen-fixture re-baseline procedure for `tests/fixtures/companies_jscode_frozen.json` a second time in this repo's history: confirmed exactly 2 of the 14 `{variant, node}` pairs differ (cloud + local_live, both `Build Research Request`), confirmed a comment-stripped diff of each is confined to the added `required_fields` entry plus the added schema-string key and its own guidance clause, THEN wrote the re-baseline as its own isolated commit — all BEFORE the WR-01 CSV edit landed in a separate rebuild.
- Zero regressions: 596 pytest / 309 node (298 baseline + 11 new: 5 from `researchRequestSponsorshipContract.test.mjs` + 6 from `personaGroupProducer.test.mjs`) all green. All five frozen shared JS modules (`judge.js`, `webResearch.js`, `scoreEnrichment.js`, `mergeCompanies.js`, `mergeContacts.js`), the contacts judge `chosen_field` allowlist (`contactJudge.js`), the write-once pre-fix fixture, and `config/` all git-unchanged across this plan. Confirmed via two consecutive builder runs (byte-identical md5) that the rebuild is deterministic.

## Task Commits

Each task was committed atomically:

1. **Task 1: GAP 1 (COPY-01) — research request contract + WR-01** — `a757e52` (test, RED), `371fe9d` (feat, prompt fix), `b9a6394` (chore, isolated fixture re-baseline), `bd515e7` (fix, WR-01 CSV + Python oracle parity)
2. **Task 2: GAP 2 (COPY-02) — persona provider-mapper producer** — `08b6695` (test, RED), `a45c662` (test, harness self-correction — see Deviations), `d251880` (feat, GREEN)
3. **Task 3: Gap-closure gate** — this SUMMARY + metadata commit

_Note: both Task 1 and Task 2 are `tdd="true"` in the plan. Task 1's fixture re-baseline is a required THIRD commit per the plan's explicit isolation requirement (Phase 16.3 precedent), and its WR-01 CSV edit is a required FOURTH commit per D-GAP1-order (a separate rebuild, so its zero-frozen-diff result is independently attributable). Task 2 required an extra harness-correction commit before its GREEN commit — see Deviations._

## Files Created/Modified

- `tests/n8n/researchRequestSponsorshipContract.test.mjs` — New GAP 1 proof (5 tests): vacuity guard, required_fields contains the field, forced schema declares it, local_live parity, chain-survival through the frozen validator.
- `tests/n8n/personaGroupProducer.test.mjs` — New GAP 2 proof (6 tests): mapper-level over 4 recorded fixtures (Apollo/Lusha present/absent), plus a two-node compiled row-flow (Normalize + Score → Merge Winners).
- `scripts/build_cloud_workflows.py` — `COMPANIES_TARGET.research_system_prompt_fn_js`/`research_payload_body_js`: sponsorship field added. `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`: sponsorship field added (WR-01), comment updated.
- `src/web_research.py` — `RESEARCH_SYSTEM` schema string: sponsorship field added (Python-oracle parity).
- `n8n/code/normalizeProviders.js` — New `_personaGroup()` helper + one `_push` call each in `lushaCandidates`/`apolloCandidates` contacts branches.
- `tests/fixtures/companies_jscode_frozen.json` — Re-baselined `Build Research Request` entries (cloud + local_live) only, isolated commit `b9a6394`.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json` — Regenerated build artifacts.

## Verbatim GAP 1 RED output (before the source edit, Task 1)

```
✔ (a) VACUITY GUARD: the executed cloud Build Research Request body returns a real request whose required_fields already contains the control field (2.343458ms)
✖ (b) GREEN (RED until the fix lands): required_fields contains lv_sponsorship_reliant (1.623ms)
✖ (c) GREEN (RED until the fix lands): the forced JSON response schema declares lv_sponsorship_reliant inside the data shape (1.150625ms)
✖ (d) GREEN (RED until the fix lands): the local_live variant's compiled Build Research Request body also requests the field (both variants share one factory) (1.352209ms)
✔ (e) CHAIN SURVIVAL: a research response carrying lv_sponsorship_reliant survives Validate Research Output into research_candidate.data untouched (1.839208ms)
ℹ tests 5
ℹ suites 0
ℹ pass 2
ℹ fail 3

✖ failing tests:

test at tests/n8n/researchRequestSponsorshipContract.test.mjs:90:1
✖ (b) GREEN (RED until the fix lands): required_fields contains lv_sponsorship_reliant
  AssertionError [ERR_ASSERTION]: COPY-01/CR-01: the research request must ask for lv_sponsorship_reliant
  actual: false, expected: true

test at tests/n8n/researchRequestSponsorshipContract.test.mjs:98:1
✖ (c) GREEN (RED until the fix lands): the forced JSON response schema declares lv_sponsorship_reliant inside the data shape
  AssertionError [ERR_ASSERTION]: the sponsorship field must be declared INSIDE the forced response schema's data shape, not merely mentioned in prose
  actual: false, expected: true

test at tests/n8n/researchRequestSponsorshipContract.test.mjs:114:1
✖ (d) GREEN (RED until the fix lands): the local_live variant's compiled Build Research Request body also requests the field
  AssertionError [ERR_ASSERTION]: the local_live variant must carry the same fix as cloud (_enrich_build_research_request_js is shared)
  actual: false, expected: true
```

Only (b)/(c)/(d) failed as required; (a)/(e) passed, proving the harness and row were wired correctly before the fix — (e) in particular is a permanent regression guard on the frozen `webResearch.js` spread semantic, valuable whether it passes pre- or post-fix.

## Verbatim GAP 2 RED output (before the source edit, faithful re-capture, Task 2)

```
✔ (a) VACUITY GUARD: Apollo contacts candidates over the recorded fixture still contain jobtitle/seniority unchanged (0.604166ms)
✖ (b) GREEN (RED until the fix lands): Apollo contacts candidates include a persona candidate carrying the recorded department string (0.322292ms)
✔ (c) GREEN (RED until the fix lands, then asserts absence permanently): Lusha's live 'Other' department label produces NO persona candidate, jobtitle/seniority still present (0.165792ms)
✔ (d) EDGE: recorded shapes with no department field at all emit no persona candidate and do not throw (0.124ms)
✖ (e) GREEN (RED until the fix lands): the compiled Normalize + Score body, given the recorded Apollo response, yields a non-null persona entry in scored.winners (3.181667ms)
✖ (f) GREEN (RED until the fix lands): feeding that produced row into the compiled Merge Winners body yields lv_persona_group in canonicalPatch, with every other promoted field unchanged (2.111ms)
ℹ tests 6
ℹ suites 0
ℹ pass 3
ℹ fail 3

✖ failing tests:

test at tests/n8n/personaGroupProducer.test.mjs
✖ (e) GREEN (RED until the fix lands): the compiled Normalize + Score body, given the recorded Apollo response, yields a non-null persona entry in scored.winners
  AssertionError [ERR_ASSERTION]: COPY-02: the recorded Apollo department must win the waterfall for persona_group
  actual: undefined, expected: 'media_and_communication'

test at tests/n8n/personaGroupProducer.test.mjs
✖ (f) GREEN (RED until the fix lands): feeding that produced row into the compiled Merge Winners body yields lv_persona_group in canonicalPatch, with every other promoted field unchanged
  AssertionError [ERR_ASSERTION]: COPY-02: the produced persona value must reach the lv_-prefixed canonical key
  actual: undefined, expected: 'media_and_communication'
```

Only (b)/(e)/(f) failed as required; (a)/(c)/(d) passed. Note (per plan instruction): (c) passes trivially pre-fix, since the "Other" non-signal behaviour is the ABSENCE of a candidate either way — its permanent value is as a regression guard once the fix lands. This is the SECOND, corrected capture of this red run — see Deviations for why the first capture was discarded.

## Bounded frozen-fixture re-baseline evidence (Task 1)

Computed BEFORE writing the fixture, per the Phase 16.3 procedure (this is the third time this exact procedure has been executed in this repo's history — Phase 16.3-01 and Plan 18-02 are the prior two):

- All 14 `{variant, node}` pairs `tests/test_companies_factory_frozen.py` covers (7 `FROZEN_NODE_NAMES` x 2 variants) were freshly built and diffed against the then-committed fixture.
- **Exactly 2 pairs differed**, both `Build Research Request`: `("cloud", "Build Research Request")` and `("local_live", "Build Research Request")`.
- A **comment-stripped textual diff** of each showed the only remaining change is:
  ```diff
      "lv_is_hardware_vendor and lv_is_gambling_operator are hard-veto inputs - answer null",
      "unless a cited source directly supports the classification.",
  +   "lv_sponsorship_reliant is a sponsorship-reliance signal, not a hard-veto input - answer",
  +   "null unless a cited source directly supports the classification.",
      "Return ONLY one JSON object, no prose, no markdown fences, matching:",
      '{"data":{"lv_org_type":<str>,"lv_produces_content":<bool|null>,"lv_content_type":[<str>],',
  -   '"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>},',
  +   '"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>,',
  +   '"lv_sponsorship_reliant":<bool|null>},',
      '"evidence_by_field":{"<field>":"<url>"},"entity_resolution":{...},',
      '"matched":<bool>,"confidence":<int 0-100>}',
    ].join(" ");
  }
  ...
      required_fields: ["lv_org_type", "lv_produces_content", "lv_content_type",
  -                     "lv_is_hardware_vendor", "lv_is_gambling_operator"],
  +                     "lv_is_hardware_vendor", "lv_is_gambling_operator",
  +                     "lv_sponsorship_reliant"],
  ```
  identical for both variants.
- Both checks passed, so the re-baseline proceeded and landed as its own isolated commit (`b9a6394`), stating this bounded-diff result in the commit message.
- Post-re-baseline: `tests/test_companies_factory_frozen.py -q` → 4 passed.

## WR-01 zero-frozen-diff proof (Task 1, separate rebuild after the re-baseline)

Per D-GAP1-order, the WR-01 CSV edit (`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` in `scripts/build_cloud_workflows.py`) and the `src/web_research.py` parity edit landed as their OWN separate commit (`bd515e7`), after a SEPARATE rebuild from the re-baseline commit above:

- `git status --short n8n/` after this rebuild showed only `n8n/wf_enrichment_cloud.json` changed (the CSV feeds only `_hs_http_search_node` HTTP nodes in the cloud variant's Company Search/Fetch-By-Id nodes — never a Code node, and never present in `local_live`).
- `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` → still **4 passed**, `git status --porcelain tests/fixtures/companies_jscode_frozen.json` → **empty** (zero further fixture diff) — the CSV edit moved zero frozen `{variant, node}` pairs, confirming the edit is confined to HTTP-node parameters.
- `git log --oneline -3 -- tests/fixtures/companies_jscode_frozen.json` confirms the re-baseline landed as its own commit, separate from both the prompt-fix commit (`371fe9d`) and the WR-01 commit (`bd515e7`).

## Final suite counts against the floor (Task 3)

- Floor from `18-02-SUMMARY.md`: 596 pytest / 298 node, 0 regressions.
- `.venv/bin/python -m pytest -q` — **596 passed**, 0 failures (unchanged — this plan added no new Python tests).
- `node --test tests/n8n/*.test.mjs` — **309 passed**, 0 failures (298 baseline + 11 new: 5 from `researchRequestSponsorshipContract.test.mjs` + 6 from `personaGroupProducer.test.mjs`).
- `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` — 4 passed (guard green again post-re-baseline, and again after the WR-01 CSV edit).
- `.venv/bin/python -m pytest tests/test_architecture_guard.py -q` — 38 passed (PN-1 guard green; no forbidden bare-quoted `linkedin_url`/`persona_group` literal was introduced anywhere in `scripts/build_cloud_workflows.py`, including comments).

## Two-run determinism result (Task 3)

Ran `scripts/build_cloud_workflows.py` twice in a row at the phase gate (after all source edits landed) and md5-compared every `n8n/*.json` output between the two runs: byte-identical. Also confirmed `git diff --quiet n8n/` passes against the committed state after a fresh rebuild — the working tree matches what is committed.

## Prohibition check results (Task 3)

- **Five shared JS modules unchanged across this plan:** `git diff --quiet 8e1be31 -- n8n/code/judge.js n8n/code/webResearch.js n8n/code/scoreEnrichment.js n8n/code/mergeCompanies.js n8n/code/mergeContacts.js` (`8e1be31` = this plan's PLAN.md commit, its start point) — exit 0.
- **PN-1 architecture guard:** `tests/test_architecture_guard.py -q` — 38 passed.
- **Write-once pre-fix fixture unmodified:** `git status --porcelain tests/fixtures/merge_company_prefix_jscode.json` — empty.
- **No policy class/threshold/evidence-requirement change:** `git diff --quiet 8e1be31 -- config/` — exit 0 (config/ entirely untouched this plan; only Python prompt/CSV strings and the JS mapper changed).
- **Contacts judge `chosen_field` allowlist unwidened:** `git diff --quiet n8n/code/contactJudge.js` — exit 0 (this plan's persona producer is a provider mapper, never touches the judge path — D-GAP2-provider).
- **No live HubSpot, n8n, or Anthropic API call:** every command run this plan was `.venv/bin/python -m pytest`, `node --test`, or `.venv/bin/python scripts/build_cloud_workflows.py` — all offline.

## Reachability record (per 18-VERIFICATION.md's two gap truths)

### `lv_sponsorship_reliant` (GAP 1 / COPY-01)

- **Producer:** the shipped `Build Research Request` node body (both cloud and local_live variants, sharing `_enrich_build_research_request_js`) now asks the model for `lv_sponsorship_reliant` in both `required_fields` and the forced JSON response schema.
- **Proving test:** `tests/n8n/researchRequestSponsorshipContract.test.mjs` — executes the committed node body directly, proves the field is requested (b/c/d), and proves it survives the frozen `Validate Research Output` validator's wholesale `{...raw.data}` spread into `research_candidate.data` untouched (e). This feeds the Merge Company copy step Plan 18-02 already proved (`tests/n8n/sponsorshipReliantCopyLoop.test.mjs`).
- **Honest scope limit:** this populates only on rows where the research gate fires (`needsResearch`, `scripts/build_cloud_workflows.py` — `lv_org_type` unresolved OR `lv_produces_content` blank) AND where research is enabled at deploy time (`ALLOW_WEB_RESEARCH`, disabled by default per `16.5-01-SUMMARY.md`'s baked-flag overlay). That is a real narrowing versus "every company on every run" — it is still the difference between structurally unreachable (no live invocation could EVER populate the field, regardless of gate/flag state) and reachable (a live invocation on a gated, research-enabled row now can).

### `lv_persona_group` (GAP 2 / COPY-02)

- **Producer:** `_personaGroup()` in `n8n/code/normalizeProviders.js`, wired into both `lushaCandidates` and `apolloCandidates`' contacts branches.
- **Proving test:** `tests/n8n/personaGroupProducer.test.mjs` — mapper-level proof over 4 recorded fixtures (b/c/d), and a compiled row-flow proof (e/f) driving the RECORDED `apollo_contact.json` response through the COMPILED `Normalize + Score` then `Merge Winners` node bodies, with the persona value reaching `canonicalPatch` only via `Normalize + Score`'s own produced row — never hand-written onto `scored.winners` anywhere in the test.
- **Honest scope limit:** only Apollo and Lusha carry a department field in any recorded shape; ZoomInfo carries none (confirmed by reading `zoominfoCandidates` — no department field is read anywhere, and none appears in either recorded ZoomInfo fixture). Lusha's only recorded LIVE value (`"Other"`) is deliberately treated as a non-signal per D-GAP2-othervalue. So **today the realistic live producer is Apollo alone** — a Lusha-sourced persona value would require a future live capture carrying a real (non-"Other") department string, which has not yet been observed. This is stated plainly, not rounded up to "two providers."

## Carry-forward supersession

**This plan supersedes** `18-02-SUMMARY.md`'s "Missing-producer carry-forward" section and the matching `.planning/STATE.md` entry:

> NEW 2026-07-29 (Phase 18 Plan 02, carried forward, explicitly out of scope): both copy-loop fields still have no live producer.

Both fields now have a real, recorded-fixture-proven producer reaching their merge call end-to-end, not merely a wired-but-empty copy step. **What genuinely remains open, stated plainly (not a clean sweep):**

1. `lv_sponsorship_reliant` only populates on research-gated, research-enabled rows (see scope limit above) — this is inherent to the field's design (RT-3 gap predicate + the deploy-time `ALLOW_WEB_RESEARCH` kill switch), not a defect this plan could or should close.
2. `lv_persona_group`'s realistic live producer is Apollo alone today; Lusha's producer exists in code but has never actually fired against a real (non-"Other") live value, and ZoomInfo has no producer at all because no recorded ZoomInfo shape has ever carried a department signal.
3. Neither field has been proven live against the actual n8n Cloud deployment or a real HubSpot write — this plan's proof is offline-compiled-node-body only, matching every other Phase-13 through Phase-18 producer proof in this repo (live canary proofs are a separate, later operational step per the CLAUDE.md rollout plan §25).

## 18-REVIEW.md closure statement

- **CR-01 (Critical) — CLOSED.** "The Claude Web Research request contract ... was never updated to ask for or accept `lv_sponsorship_reliant`." Fixed by Task 1's prompt edit; proven by `tests/n8n/researchRequestSponsorshipContract.test.mjs` tests (b)/(c)/(d), and the fix's exact bounded scope is documented in the re-baseline evidence above.
- **WR-01 (Warning) — CLOSED.** "`lv_sponsorship_reliant` is never fetched into `existingRecord` for companies." Fixed by Task 1's CSV edit; proven to move zero frozen node pairs (`test_companies_factory_frozen.py` still 4 passed, fixture untouched by this edit) and by `tests/test_fetch_by_id_topology.py`/`tests/test_bug10_company_search_transport.py` staying green (both import the CSV constant rather than hardcoding it).

## Decisions Made

All planner decisions from the PLAN (D-GAP1-scope, D-GAP1-noparitytest, D-GAP1-pyoracle, D-GAP2-provider, D-GAP2-othervalue, D-GAP2-rawvalue, D-GAP2-nozoominfo, D-GAP1-order) were implemented exactly as specified — see frontmatter `key-decisions` for the operative summary of each.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 2's first Layer-2 harness attempt produced a false-positive red (TypeError, not a real assertion failure)**
- **Found during:** Task 2, first `node --test tests/n8n/personaGroupProducer.test.mjs` run after writing the test, before the source fix.
- **Issue:** The test's `runNormalizeAndScore` (originally just the shared `runJsCode` helper) fed the seed row through `$input.all()`. The CLOUD `Normalize + Score` node's actual compiled body (`ENRICH_NORMALIZE_SCORE_CLOUD`) does NOT read `$input` at all — it recovers its row by NAME from `$('Enrichment Gate')` and each provider's response from `$('Lusha Enrich')`/`$('Apollo Match')`/`$('ZoomInfo Enrich')` (the row-recovery discipline every HTTP-adjacent Code node in this chain follows, since n8n HTTP nodes replace `$json`/`$input` with their own response). With a harness that never populates those node-name lookups, the node's `rows.map(...)` iterated zero items, so `out[0]` was `undefined` — tests (e)/(f) failed with a `TypeError: Cannot read properties of undefined`, not the intended `AssertionError` on a missing persona value. This is exactly the class of failure the plan's own read-first list warned about (`tests/n8n/bareEventChainFlow.test.mjs`'s node-name-lookup idiom), and it would have made the captured "red evidence" unfaithful — a harness bug masquerading as the gap.
- **Fix:** Rewrote the Layer-2 harness as `runNormalizeAndScore()`, modelled on `bareEventChainFlow.test.mjs`'s `$(name)` stub, supplying `Enrichment Gate`/`Lusha Enrich`/`Apollo Match`/`ZoomInfo Enrich` outputs by node name. Then, because the source fix (`_personaGroup` + its two call sites) was ALREADY applied and uncommitted at the point this was caught, reverted ONLY that uncommitted source edit with `git checkout -- n8n/code/normalizeProviders.js n8n/wf_enrichment_cloud.json n8n/wf_enrichment_local.json n8n/wf_enrichment_local_live.json` (a targeted single-file discard of uncommitted work — never a blanket reset, and never touching the test file or any committed history), re-ran the corrected harness to capture FAITHFUL red evidence (real `AssertionError`s, `actual: undefined` vs `expected: 'media_and_communication'`), committed that harness fix, then reapplied the identical `_personaGroup` source edit from scratch and confirmed GREEN.
- **Files modified:** `tests/n8n/personaGroupProducer.test.mjs` only (harness correction); `n8n/code/normalizeProviders.js` and the three `n8n/wf_enrichment_*.json` artifacts were reverted-then-reapplied byte-identically (confirmed by the final `git diff` matching the original edit).
- **Verification:** `node --test tests/n8n/personaGroupProducer.test.mjs` — 6/6 pass after the reapplied fix; the corrected-harness red run (3 pass / 3 fail, real AssertionErrors) is recorded above as the plan's official GAP 2 red evidence, superseding the discarded TypeError-shaped first attempt.
- **Committed in:** `a45c662` (harness correction, its own commit before the GREEN fix), `d251880` (GREEN, reapplied fix).

---

**Total deviations:** 1 auto-fixed (1 harness bug in the test itself, caught before any false claim was made, corrected with faithful red evidence re-captured before the fix was reapplied).
**Impact on plan:** No scope creep and no weakening of any acceptance criterion — the underlying `_personaGroup` producer fix landed exactly as the plan specified, byte-for-byte identical between the discarded first application and the final committed one. The extra commit exists solely to keep the red-before-green discipline honest.

## Issues Encountered

None beyond the auto-fixed harness issue above, caught and corrected within Task 2 before the GREEN commit landed.

## User Setup Required

None — no external service configuration required. This is an offline-only fix; no live HubSpot, n8n, or Anthropic API call was made anywhere in this plan.

## Next Phase Readiness

- Both Phase 18 verification gaps (SC-3, SC-4 in `18-VERIFICATION.md`) are now closed at the OUTCOME level, not merely the wiring level — the phase's own GOAL prose ("two ICP/persona properties stop being permanently empty") is satisfied for the first time, subject to the honestly-stated scope limits above (research-gate/flag narrowing for sponsorship; Apollo-only realistic live producer for persona).
- `scripts/build_cloud_workflows.py`, `src/web_research.py`, `n8n/code/normalizeProviders.js`, both new test files, the re-baselined frozen fixture, and the three regenerated `wf_enrichment_*.json` artifacts are committed and stable.
- The full offline suite is at 596 pytest / 309 node with 0 regressions.
- **Genuinely still open (not a blocker for this phase's close, named per the plan's Task 3 instruction):** neither field has been proven against a real n8n Cloud execution or a real HubSpot write — that is a live-canary/operational step, matching the pattern every other producer in this repo has followed (proven offline first, canaried live later, e.g. Phase 17's BUG 23 resolution). Also: `lv_persona_group`'s Lusha branch has never actually fired against a real (non-"Other") live department value — it exists in code, proven only against the one recorded fixture that happens to carry "Other".
- No other blockers.

---
*Phase: 18-normalization-copy-loop-fixes*
*Completed: 2026-07-29*

## Self-Check: PASSED

All created/modified files verified present on disk; all task commit hashes
(`a757e52`, `371fe9d`, `b9a6394`, `bd515e7`, `08b6695`, `a45c662`, `d251880`)
verified present in `git log`.
