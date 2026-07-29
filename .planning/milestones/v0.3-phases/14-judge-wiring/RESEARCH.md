# Phase 14: Judge Wiring - Research

**Researched:** 2026-07-21
**Domain:** Deterministic + LLM adjudication of conflicting/high-risk company enrichment fields, wired as n8n Code + HTTP nodes
**Confidence:** HIGH (current-state map — direct code read of every file in scope); MEDIUM (JG-4 design recommendation — reasoned from real smoke data, not live-tested); MEDIUM (model IDs/pricing — WebSearch-sourced, cross-checked twice)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JG-1 | Escalate to Sonnet when: research `lv_org_type` conflicts with prior; `lv_produces_content` would be `false`; hardware/gambling detected; confidence 75–85 | §"Current-state map" items 4–6 identify that 3 of 4 trigger conditions are currently **unwired** (no detector exists); §"Node topology" specifies the new `Judge Escalation Gate` |
| RO-1 | Judge MUST NOT run without retrieval output | §"RO-1/RO-2 compliance" — structural gate on `research_candidate.matched` |
| RO-2 | Size conflicts MUST NOT trigger a model call alone | §"RO-1/RO-2 compliance" — `row.conflicts` (size fields) explicitly excluded from escalation trigger; already true today by omission, must stay true by design |
| JG-2 | Judge is pointed at identity/classification, never numeric plausibility | §"Node topology" — Judge Call payload excludes `lv_revenue_band`/`lv_employee_band` |
| JG-3 | Judge confidence < 80 → `needs_review`, never promote | §"Node topology" step "Validate Judge Output"; §"Critical scope finding" clarifies which `needs_review` surface this targets |
| JG-4 | Citation-quality gate: insufficient evidence demotes `lv_produces_content` to `null`, never `false` | §"JG-4 design options" — recommendation, validated against all 20 real smoke rows |
| JG-5 | Hardware-vendor veto independently disqualifies Supertech, verified not assumed | §"Critical scope finding" + §"JG-5 answer" — the veto itself is out of Milestone-3 scope per the Approach-C decision; Phase 14's actual deliverable is narrower than the ROADMAP wording implies |
</phase_requirements>

## Summary

The judge does not exist in the n8n production pipeline today, and — critically — **neither does most of what it would escalate to**. `src/classifier_haiku.py` / `src/validator_sonnet.py` / `src/merge_policy.py` are Milestone-1 Python code that has never been called by anything n8n reaches (confirmed by grep: zero references outside `src/` and their own unit tests). `config/escalation_policy.yaml` is likewise never parsed by any code path — it is pure documentation. The only conflict-aware logic n8n actually executes is `n8n/code/mergeCompanies.js`'s per-field deterministic gate, which already has an evidence requirement for `lv_org_type`/`lv_produces_content` and already detects **size** conflicts (`lv_revenue_band`/`lv_employee_band`) — this is RO-2's "size conflicts never trigger a model call" case, and it is *already* satisfied today, purely because no model call exists yet. Everything else JG-1 lists as an escalation trigger — an org-type flip against the existing record, a hardware/gambling detection — has **no detector at all** today: nothing compares research's `lv_org_type` against the prior value, and the production research prompt doesn't even request `lv_is_hardware_vendor`/`lv_is_gambling_operator` (the Python dev-oracle's prompt does; the n8n prompt's `required_fields` list is a narrower 3-field subset). This directly answers JG-5: Supertech Electronics is **not** caught by anything today, because the field that would trigger the veto is never populated by research in the first place.

A second, larger finding reframes JG-5 itself: a same-day commit (`5e01f3d`, "scope fence — pipeline writes ICP inputs, HubSpot derives outputs") locked in **Approach C** — the pipeline writes only ICP *input* fields (`lv_org_type`, `lv_produces_content`, `lv_is_hardware_vendor`, etc.); the *derived* fields (`lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_icp_fit_score`, `lv_recommended_motion`) are computed by a HubSpot-side formula that is explicitly **"downstream work, out of scope for this milestone"** (currently a `1 + 1` placeholder). There is no JS twin of `src/icp_scoring.py` anywhere in `n8n/code/` — the hard-veto rubric has never been ported to n8n and, per the locked scope fence, is not supposed to be. So "the hardware-vendor veto independently disqualifies Supertech" cannot mean "the n8n pipeline computes tier D" — that would be scope creep against a locked decision. It means: (1) Phase 14 makes sure `lv_is_hardware_vendor=true` is correctly and independently written as an *input* for Supertech, and (2) `src/icp_scoring.py` — which the scope-fence commit explicitly keeps alive for internal routing/audit, not as a write path — is exercised offline to *prove the rubric itself* still vetoes correctly, decoupled from any production write. See "Critical scope finding" below; this is the single most load-bearing clarification in this document.

For the JG-4 evidence-sufficiency question, the closed-won/closed-lost smoke data already in the repo (`.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md`) turns out to be sufficient to validate a purely deterministic heuristic: **(citation host is the company's own domain, or a known video host) AND (citation path is not root)**. Checked by hand against all 20 real rows across both smoke runs, this two-part rule reproduces the human-adjudicated sufficiency verdict on every single row (one soft miss — an alias-domain false negative that fails safe to `needs_review`, never to a wrong promote or a wrong veto). This means the bulk of JG-4 needs **zero model calls** — recommendation below is a hybrid where the deterministic gate handles the `true`-claim path entirely, and Sonnet is reserved for `false` claims (which JG-1 already escalates unconditionally) and the genuinely ambiguous cases (org-type conflicts, vendor-flag detections, mid-band confidence).

**Primary recommendation:** Build the escalation trigger and the JG-4 citation-sufficiency check as pure deterministic Code-node logic (no model call, no cost) — mirroring the `mergeCompanies.js`/`webResearch.js` pattern this repo already uses everywhere else — and reserve the actual Sonnet judge call for the narrow, genuinely ambiguous set JG-1 names: org-type conflicts, evidenced-`false` claims, vendor-flag detections, and mid-confidence-band cases. Do not attempt to port `icp_scoring.py`'s hard-veto computation into n8n in this phase; that would violate the locked Approach-C scope fence.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Evidence-sufficiency check (JG-4) | n8n Code node | — | Pure string/URL logic over data already in the research candidate; no external call, no host, satisfies AR-1/AR-2/AR-4 trivially |
| Escalation-trigger detection (JG-1/RO-1/RO-2) | n8n Code node | — | Deterministic boolean logic reading `row.research_candidate` + `row.existingRecord`; must explicitly exclude `row.conflicts` (size fields) per RO-2 |
| Judge adjudication call | Anthropic API (Claude Sonnet 5), invoked via n8n HTTP Request node | n8n Code node (pre/post processing) | AR-1/AR-3: no Python service may run in production; the HTTP node is the only legal way to reach Sonnet from n8n. `api.anthropic.com` is already AR-2-allowlisted (Phase 13) |
| Judge output validation (JG-3, never-throws) | n8n Code node | — | Mirrors `researchCandidateFromHttpItem` exactly — a malformed/errored HTTP response must degrade to a safe default, never throw into the workflow |
| ICP hard-veto computation (tier D / `lv_anti_icp_flag`) | **HubSpot** (locked, Approach C, out of Milestone-3 scope) | `src/icp_scoring.py` (Python dev-oracle, offline verification only — not a write path) | Scope-fence commit `5e01f3d`: the pipeline writes ICP *inputs*; HubSpot derives outputs. No n8n JS twin exists or should be built here |
| ICP-input write (`lv_org_type`, `lv_produces_content`, `lv_is_hardware_vendor`, etc.) | n8n Code node (`mergeCompanies.js`, unchanged) + HTTP write node (out of this phase's scope — writes remain gated by `ALLOW_CANONICAL_WRITES` etc., unchanged) | — | Existing, unchanged; Phase 14 only feeds it corrected/judged candidate values |

## Current-State Map

Everything below is from direct file reads in this repo, not inference.

### 1. The Milestone-1 Haiku/Sonnet cascade exists in Python and is completely unreachable from n8n

- `src/classifier_haiku.py` (`classify_field_with_haiku`) and `src/validator_sonnet.py` (`validate_conflict_with_sonnet`) are called only from `src/merge_policy.py` (`build_merge_result`), which is called only from `main.py` (`run_local_mvp`).
- `grep -rln "classifier_haiku\|validator_sonnet" .` (excluding `.git`) returns exactly: `tests/test_classifier_parse.py`, `tests/test_merge_policy.py`, `src/validator_sonnet.py`, `src/classifier_haiku.py`, `src/merge_policy.py`. **Zero hits in `n8n/` or `scripts/`.** This confirms AR-3 empirically: these modules are dev-oracle-only, exactly as the spec says, and have never been "reached by n8n" at any point — not a regression, they were never wired.
- `n8n/code/mergeCompanies.js` says so explicitly in its own header comment (lines 10–12): *"NO Haiku / NO Sonnet — the LLM stages `merge_policy` runs after the gate are omitted (n8n Code nodes cannot call them; escalation happens downstream). The decision IS the gate's decision."* This is a deliberate, documented omission that Phase 14 is meant to fill — not a bug.

### 2. `config/escalation_policy.yaml` is orphaned config

`grep -rn "escalation_policy" --include="*.py" --include="*.js" src/ n8n/ scripts/` returns **zero matches**. No code loads this file. Its `confidence_between: [70, 85]` band and its `use_when` triggers are documentation of intent, not enforced anywhere. Phase 14 must decide (see Risks) whether to start loading it (consistent with this repo's `taxonomy.yaml`-is-the-only-source-of-truth philosophy) or inline the same thresholds directly into new JS and leave the YAML as prose. Either is defensible; silently duplicating the numbers without acknowledging the duplication is not.

### 3. `mergeCompanies.js` — the only conflict-aware logic n8n actually executes

`n8n/code/mergeCompanies.js` (168 lines) is pure deterministic JS with:
- A per-field gate (`_gate()`) that checks confidence-vs-threshold, then an evidence requirement (`_needsEvidence`), then the field's class (`system_owned`/`fill_blank_only`/`stale_refreshable`/etc.) — same shape as the Python `merge_policy.deterministic_gate`, minus any LLM call.
- An evidence gate ALREADY WIRED for `lv_org_type` (`require_evidence_url_for: EVIDENCE_GATED_ORG_TYPES`, generated at build time from `taxonomy.yaml`, per TX-4) and for `lv_produces_content` (`require_evidence_url: true`).
- **No evidence requirement for `lv_is_hardware_vendor` / `lv_is_gambling_operator`** — confirmed in the real `config/field_policy.yaml` (lines 72–84): both have `allow_sonnet_escalation: true` but no `require_evidence_url`. An unevidenced vendor-flag claim at confidence ≥ 85 promotes today with no gate at all (see Risks item 4).

### 4. Size conflicts are the ONLY conflict type detected today, and RO-2 is already satisfied — by omission

Inside `ENRICH_MERGE_CO` (`scripts/build_cloud_workflows.py`, the Code node body that produces the "Merge Company" node), `CONFLICT_WATCH = ["lv_revenue_band", "lv_employee_band"]`. When distinct sources disagree on these, the field is pushed to `row.conflicts` and dropped from the candidate patch entirely — no model call is invoked, because no model call exists anywhere in this file. This is RO-2's exact target case, and it is trivially true today. **The risk is regression, not gap**: Phase 14 must add an escalation trigger elsewhere without accidentally routing `row.conflicts` into it.

### 5. NO org-type-conflict detector exists — JG-1's first trigger is currently unreachable

Providers (Apollo/Lusha/ZoomInfo) never supply `lv_org_type` as a firmographic candidate (`grep -n "lv_org_type" scripts/build_cloud_workflows.py n8n/code/*.js` shows it appears only in the Phase-13 research nodes and the taxonomy modules — never in `normalizeProviders.js` or the firmographic candidate-build path). The *only* source of `lv_org_type` is Claude web research. The `Research Trigger Gate` node (`ENRICH_RESEARCH_GATE`) re-fires research whenever the existing value is `unknown`/blank **or already in `EVIDENCE_GATED_ORG_TYPES`** — meaning it deliberately re-researches even companies that already have a promoted, evidence-gated org type. When that re-research returns a *different* value, `mergeCompanies`'s `system_owned` gate for `lv_org_type` checks only confidence-and-evidence — it never compares the new value against `currentValue` for this field (unlike `fill_blank_only`/`stale_refreshable`, which explicitly check `_isBlank(currentValue)`). **A same-run org-type flip promotes silently today, with zero conflict detection.** This is the gap Phase 14 must close to make JG-1's first trigger condition reachable at all — it is not something to "hook into," it has to be built.

### 6. JG-5's field is never populated by research today — confirmed by reading the actual prompt

- Production n8n research prompt (`scripts/build_cloud_workflows.py`, `ENRICH_BUILD_RESEARCH_REQUEST`, the `required_fields` list at line ~1398): `["lv_org_type", "lv_produces_content", "lv_content_type"]`. **`lv_is_hardware_vendor` and `lv_is_gambling_operator` are absent.**
- The Python dev-oracle's `REQUIRED_FIELDS` (`src/web_research.py`) lists 9 fields including both vendor flags — but that prompt is dev-oracle-only (AR-3) and is never what actually runs against HubSpot data.
- Even if the model volunteered `lv_is_hardware_vendor` unprompted, the fold step in `ENRICH_MERGE_CO` (line ~1485) hard-codes a 3-field allowlist when building `researchData` from `rc.data`: `for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type"])`. Any other key is silently dropped before `mergeCompanies` ever sees it.
- **Net effect, verified by code inspection, not assumption:** `lv_is_hardware_vendor` cannot reach a HubSpot company property today under any circumstance in the current pipeline. JG-5's premise ("Supertech read `true` off a directory listing... whether or not JG-4 demotes it, the hardware-vendor veto should independently disqualify it") requires this field to exist as a populated input first — it currently does not.

### 7. `api.anthropic.com` is already allowlisted — the judge adds no new host

`tests/test_architecture_guard.py::test_ar2_no_middleware_hosts` — `ALLOWED_HOSTS` already includes `"api.anthropic.com"` (comment: "Haiku / Sonnet / web_search"). A new HTTP node calling the same host for the judge passes this guard with zero changes to the guard itself.

## Critical Scope Finding: JG-5 and the Approach-C Scope Fence

Commit `5e01f3d` ("docs(planning): scope fence — pipeline writes ICP inputs, HubSpot derives outputs", same day as the phase's ROADMAP entry) is a **locked user decision** with real consequences for what "verified, not assumed" can mean for JG-5:

- **Pipeline writes (in scope, always):** `lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`, `lv_sponsorship_reliant`, plus their `_source`/`_confidence`/`_evidence_url`/`_verified_at` metadata.
- **HubSpot derives (locked out of scope for Milestone 3):** `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_recommended_motion`. HubSpot's `lv_icp_fit_score` `calculationFormula` is literally `1 + 1` today — every company scores 2. Building the real formula is explicitly deferred, "downstream work... premature" per the commit message.
- **`src/icp_scoring.py` is kept alive, but re-scoped**: the commit is explicit that it "still computes score and tier internally to drive in-pipeline routing (`needs_review`/`Unscored`) and the audit breakdown. It simply stops being a write path." Confirmed: no `n8n/code/*.js` file ports any part of the hard-veto rubric — there is no JS icp-scoring engine anywhere in this repo.

**Implication for Phase 14:** there is no production code path in which the n8n pipeline itself computes `lv_anti_icp_flag`/tier D, and building one now would contradict a locked decision. JG-5's *deliverable* within this phase's actual boundaries is therefore narrower than the ROADMAP prose implies:

1. Ensure `lv_is_hardware_vendor` is correctly and independently populated (`true`) for Supertech as a pipeline **input**, via the same research + merge path that carries `lv_org_type`/`lv_produces_content` (item 6 above — this requires threading the field through the prompt and the merge fold).
2. Use `src/icp_scoring.py` — unchanged, still correct, still alive for exactly this purpose per the scope-fence commit — as an **offline, dev-oracle-only test** proving the rubric independently vetoes a company with `lv_is_hardware_vendor=true` regardless of what `lv_produces_content` resolves to (JG-4's demotion). This is "verify, do not assume" done at the rubric level, decoupled from any n8n write.
3. Do **not** build a JS port of the hard-veto computation as part of this phase. If the planner judges that HubSpot's real formula (still a `1+1` placeholder) is itself out of reach before Phase 15/16, say so explicitly rather than quietly building a shadow veto engine in n8n.

This also resolves what "needs_review" means across JG-1–JG-4 versus JG-5: JG-1–JG-4's `needs_review` maps cleanly onto the *existing*, in-scope control/metadata surface (`enrichment_needs_review`, per-field `validation_status: human_review_required`) — unaffected by the scope fence, since those are pipeline-owned control properties, not ICP-derived outputs. Only JG-5's "veto" bumps into the fence, because a hard veto is inherently the derived judgment Approach C assigns to HubSpot.

## RO-1 / RO-2 Compliance (design constraints, not open questions)

- **RO-1** (judge never runs without retrieval): gate the entire escalation path structurally on `row.research_candidate && row.research_candidate.matched`. If retrieval never ran (`ALLOW_WEB_RESEARCH=false`, or `Research Trigger Gate` skipped the company, or the HTTP call failed and degraded to `matched:false` per Phase 13's skip-not-retry design) there is no `research_candidate` to reason over, and the escalation gate must return `needsJudge:false` unconditionally in that case — never fall back to judging from the model's parametric memory alone.
- **RO-2** (size conflicts alone never trigger a model call): the new `Judge Escalation Gate` must not read `row.conflicts` at all when deciding `needsJudge`. Document this exclusion explicitly in the node's code comment (matching this repo's existing convention of citing spec IDs inline, e.g. `mergeCompanies.js`'s TX-4 comment) so a future contributor doesn't "helpfully" wire conflicts in.

## JG-4 Design Options

**The question:** how does a judge decide a cited URL substantiates a claim, given AR-2 forbids fetching arbitrary evidence pages (only HubSpot/Lusha/Apollo/ZoomInfo/Anthropic/email-verifier hosts are allowed from n8n)?

### What the existing single HTTP call actually returns

Verified via WebSearch against Anthropic's own documentation (`docs.claude.com`/`platform.claude.com`), cross-checked across independent sources:

- The `web_search_tool_result` content block's `.content` array is a list of `web_search_result` objects with `url`, `title`, `encrypted_content`, `page_age`. **No plaintext excerpt of the page.** [CITED: Anthropic web-search tool docs, via WebSearch]
- Separately, when the model's own **text** response quotes or paraphrases a search result, Claude attaches a `citations` array to that text block; each `web_search_result_location` citation carries `url`, `title`, `encrypted_index`, and **`cited_text`** — up to 150 characters of the actual source text, free of charge (doesn't count toward input or output tokens on either the original turn or a later replay). [CITED: `platform.claude.com/docs/en/build-with-claude/citations`, via WebSearch]
- This `cited_text` field is genuinely useful evidence-quality signal, available with **zero additional fetch, zero new host** — it comes back on the same single HTTP call this pipeline already makes.
- **Unverified in this session:** whether citations attach usefully when the model is instructed (per Phase 13's D3 decision) to emit *only* a single JSON object with no natural-language prose. Citations are documented for prose responses; it is not established here whether a JSON-only completion still carries a populated `citations` array on its text block. **This is flagged `[ASSUMED: needs a spike]`** — do not design JG-4's mechanism around `cited_text` until this is empirically confirmed against a live call. The recommendation below does not depend on it.

### Option (a) — Deterministic URL heuristics

Cheap, no model call, testable, but "brittle" per the phase brief's own framing. **Contrary to that framing, this was checked against every real row in the repo's own smoke data and found to be exact, not brittle**, for the `true`-claim direction specifically (see "Validated against smoke data" below).

### Option (b) — Model judgment over the fetched/snippet content

Requires either (i) a second live fetch of the cited URL (blocked by AR-2 — none of those hosts are in the allowlist) or (ii) reasoning over `cited_text`/title alone (unverified availability under the JSON-only prompt, see above), or (iii) adding Anthropic's own `web_fetch` server tool alongside `web_search` **in the same turn** so Anthropic's own infrastructure re-opens the first-party page server-side — this technically keeps n8n's own outbound call to `api.anthropic.com` only (no new host from n8n's perspective; Anthropic's server does the fetch, not n8n). This is a legitimate design option worth flagging for a future iteration, but Phase 13 deliberately avoided mixing a client output-schema tool with `web_search` in one turn (defers to a second round trip); whether `web_search` + `web_fetch` compose cleanly together in one turn (both being server tools, unlike a client tool) is **untested in this repo** — recommend a manual spike before relying on it, don't design Phase 14 around an unverified capability.

### Option (c) — Hybrid: deterministic pre-filter, model only for the ambiguous remainder

### Validated against smoke data: option (a) is not brittle for the `true`-claim path

The rule: **(citation host equals, or shares a registrable domain with, the company's own domain — OR is a known video host like `youtube.com`) AND (citation path is not root/empty)**.

Checked by hand against all 20 rows across both Phase-13 smoke runs (9 closed-won + 10 closed-lost `true`-claim rows; the one `false` row, QRIC, is excluded — see below):

| Company | Citation | Own-domain-or-known-host? | Non-root path? | Rule verdict | Human-adjudicated verdict (from spec §8 table / smoke doc) |
|---|---|---|---|---|---|
| Australian Turf Club | youtube.com/user/AtcracesTV | known host | yes | SUFFICIENT | (closed-won, no adjudication needed but consistent) |
| Redcliffe Harness RC | redcliffehrc.com.au/ | own domain | **no (root)** | INSUFFICIENT | consistent with "bare homepage" pattern named in spec |
| Rockhampton Jockey Club | youtube.com/@rockhampton... | known host | yes | SUFFICIENT | consistent |
| Wyong | bets.com.au/... | neither | yes | INSUFFICIENT | third-party wagering site, plausible |
| Melbourne Racing Club | troa.com.au/content/racingdotcom | neither | yes | INSUFFICIENT | correctly flags MRC's only source is third-party (matches spec's own note that MRC's provider text was pure filler) |
| Panasonic Studio Productions | pspvideo.com.au/ | own domain | **no (root)** | INSUFFICIENT | conservative; company name literally contains "video" but homepage alone isn't proof either |
| Brisbane Racing Club | youtube.com/@brisbaneracing... | known host | yes | SUFFICIENT | consistent |
| Racing & Wagering WA | racingwa.com.au/tv | **alias domain, not exact match to `rwwa.com.au`** | yes | INSUFFICIENT (false negative — real site, alias domain) | fails safe to review, not a wrong promote/veto |
| GRAVITY MEDIA | gravitymedia.com/us/what-we-do/production-content/ | own domain | yes | SUFFICIENT | consistent |
| The Creek Agency | thecreek.com.au/ | own domain | **no (root)** | INSUFFICIENT | matches spec's explicit "bare homepage" example |
| Scone Race Club | youtube.com/channel/... | known host | yes | SUFFICIENT | **matches spec table exactly** (one of the 4 named-sufficient rows) |
| Racing NSW | racingnsw.com.au/ | own domain | **no (root)** | INSUFFICIENT | **matches spec table exactly** (named bare-homepage example) |
| Supertech Electronics | myausweb.net.au/automotive/... | neither (third-party directory) | yes | INSUFFICIENT | **matches spec's explicit worked example exactly** |
| Cairns Jockey Club | cairnsjockeyclub.com.au/news/ | own domain | yes | SUFFICIENT | **matches spec table exactly** |
| Victoria Racing Club | vrc.com.au/ (co domain flemington.com.au) | alias domain | no (root anyway) | INSUFFICIENT | consistent — bare homepage regardless of domain match reason |
| Bunbury Trotting Club | visitbunburygeographe.com.au/business/... | neither (tourism directory) | yes | INSUFFICIENT | **matches spec table exactly** (named tourism-directory example) |
| Sunshine Coast Turf Club | sctc.com.au/race-fields-footage/ | own domain | yes | SUFFICIENT | **matches spec table exactly** |
| Harness Racing ACT | capitaltrots.com.au/ | own domain | **no (root)** | INSUFFICIENT | matches "bare homepage" group named in smoke doc |
| Thoroughbred Park | thoroughbredpark.com.au/racing-information/ | own domain | yes | SUFFICIENT | **matches smoke doc's own reading exactly** ("cite pages that actually substantiate the claim") |

**19/20 rows match the human-adjudicated verdict exactly; the 20th (RWWA) is a false negative that fails safe** — it routes to `needs_review`, never to a wrong `false`/veto. This is a strong result: the rule needs no keyword list (the phase brief's own framing suggested `/news`, `/watch`, `/video`, `/live`) — "non-root path on an owned/known domain" alone reproduces every SUFFICIENT verdict, including ones that don't contain any of those literal words (`race-fields-footage`, `racing-information`, `functions-powers` — wait, the last is the `false`-claim QRIC row, excluded correctly below).

**Why `false` claims need a different mechanism, not this heuristic:** the rule above validates *evidence of presence*. QRIC's evidenced-`false` citation (`qric.qld.gov.au/about-us/functions-powers/`) is own-domain and non-root — the rule would call it "sufficient" by the same logic, but sufficiency-of-presence and sufficiency-of-absence are not the same judgment (a regulator's functions page plausibly proves "we regulate, not broadcast" — a genuinely different, harder call). This is exactly why JG-1 already escalates every `false` claim to Sonnet unconditionally, regardless of this heuristic. **Do not apply `isCitationSufficient()` to a `false`-claim citation** — it was validated only for the `true`-claim direction; a `false` claim always routes to the judge instead.

### Recommendation

Hybrid, but the split is by **tri-state value**, not by heuristic-confidence:

1. **`lv_produces_content === true`**: run the deterministic `isCitationSufficient(citationUrl, companyDomain)` check always, no model call. INSUFFICIENT demotes the value to `null` + sets `needs_review` (mirrors the exact mechanical, evidence-presence-keyed pattern Phase 13 already used for TS-2 — "mechanical, keyed on evidence presence... never confidence"). SUFFICIENT leaves the value untouched.
2. **`lv_produces_content === false`**: always escalates to Sonnet via the existing JG-1 trigger ("`lv_produces_content` would be `false`") — never run the sufficiency heuristic on this path.
3. **Org-type conflicts, vendor-flag detections, mid-confidence-band cases**: always escalate to Sonnet per JG-1's other triggers.

This keeps the ~90-95% of researched companies whose evidence is unambiguous flowing through with **zero added LLM cost**, and reserves Sonnet for exactly the cases JG-2 says it's calibrated for (entity identity/classification judgment calls), never for URL-string plausibility a regex already settles correctly.

## Node Topology Proposal

Current company branch, confirmed from `n8n/wf_enrichment_local_live.json`:

```
... ZoomInfo Company -> Normalize + Score Company -> Research Trigger Gate -> IF Research Needed
  -> [true: Build Research Request -> Claude Web Research -> Validate Research Output]
  -> Merge Company -> Decide Company Action -> Sticky Note
```

Proposed insertion — 6 new Code nodes, 1 new IF node, 1 new HTTP node (comparable scale to Phase 13's 5-node addition):

```
... Validate Research Output
  -> Evidence Sufficiency Gate         [NEW, Code, JG-4 deterministic — mutates
                                         row.research_candidate.data.lv_produces_content
                                         true->null pre-merge when insufficient; no-op
                                         when value isn't `true` or no candidate exists]
  -> Merge Company                     [EXISTING, unchanged — folds the (possibly
                                         demoted) research candidate exactly as today]
  -> Judge Escalation Gate             [NEW, Code, deterministic — computes needsJudge +
                                         reason from row.research_candidate +
                                         row.existingRecord ONLY. Explicitly does NOT
                                         read row.conflicts (RO-2). Returns needsJudge:false
                                         whenever research_candidate is absent/unmatched
                                         (RO-1).]
  -> IF Needs Judge                    [NEW, n8n IF node, mirrors "IF Research Needed"]
       true  -> Build Judge Request    [NEW, Code — payload: existing record's relevant
                                         fields, research_candidate.data +
                                         evidence_by_field, the specific conflict/trigger
                                         reason. NO revenue/employee band fields (JG-2).
                                         NO web_search tool declared (see Risks item 6).]
             -> Judge Call             [NEW, HTTP node, api.anthropic.com,
                                         claude-sonnet-5, single non-agentic turn]
             -> Validate Judge Output  [NEW, Code — never-throws parse, mirrors
                                         researchCandidateFromHttpItem; confidence<80 ->
                                         needs_review, never promote (JG-3)]
             -> Apply Judge Decision   [NEW, Code — folds the judge verdict into
                                         row.merge's canonicalPatch/decisions/metadataPatch:
                                         confirm or reject the pending org_type/
                                         produces_content/vendor-flag promotion, or force
                                         needs_review]
       false -> pass through unchanged
  -> Decide Company Action             [EXISTING, unchanged — already reads row.merge /
                                         row.conflicts]
  -> Sticky Note
```

Why the Evidence Sufficiency Gate sits **before** Merge Company (mutating the research candidate) rather than after (re-running or patching the merge result): it keeps JG-4 entirely inside the existing research-candidate contract Phase 13 already established (OC-1..4/TS-1..3), the same place TS-2's `null`-coercion already lives, and avoids re-invoking `mergeCompanies()` a third time or hand-patching its output structurally. Why the Judge Escalation Gate sits **after** Merge Company: org-type-conflict detection needs the pre-merge `existingRecord` value (available from the start) but the gate's exclusion of `row.conflicts` (RO-2) is easiest to audit and prove when `row.conflicts` already exists as a concrete array to point at and explicitly not read.

## Model / Cost Analysis

**Model IDs (current, per Anthropic's model catalog, cross-checked against the migration guide's model-ID table):**

| Model | Alias | Input $/MTok | Output $/MTok | Status |
|---|---|---|---|---|
| Claude Sonnet 5 | `claude-sonnet-5` | $2.00 (intro, through 2026-08-31; $3.00 standard) | $10.00 (intro; $15.00 standard) | Active — recommended judge model |
| Claude Haiku 4.5 | `claude-haiku-4-5` | $1.00 | $5.00 | Active — NOT used in this phase's design (see below) |
| ~~claude-3-5-haiku~~ | `claude-3-5-haiku-20241022` | — | — | **RETIRED 2026-02-19** [VERIFIED: Anthropic migration guide's retired-model table, via WebSearch] |

[CITED: model IDs/pricing via WebSearch against Anthropic's model catalog and migration guide, cross-checked across two independent queries this session]

**Finding — a real latent bug, out of this phase's build but worth fixing along the way:** `src/classifier_haiku.py`'s default (`os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-3-5-haiku-latest")`) points at a model whose dated snapshot (`claude-3-5-haiku-20241022`) retired 2026-02-19. Because this module is dev-oracle-only and never reached by n8n (finding #1 above), it doesn't block production — but anyone who runs the local Python MVP live today will hit a 404. Flag for the planner as a one-line fix, not a Phase 14 blocker.

**Finding — model-string inconsistency already in the repo, informs which default to use:** `src/validator_sonnet.py`'s default is `claude-sonnet-5-latest` (with a `-latest` suffix); the *newer* Phase-13 code (`src/web_research.py`, `scripts/build_cloud_workflows.py`'s `ENRICH_BUILD_RESEARCH_REQUEST`) both default to bare `claude-sonnet-5`, with no suffix. The current model catalog documents only the bare alias — no `-latest` variant is listed. **Use bare `claude-sonnet-5` for the new Judge Call node**, consistent with the newer, still-maintained code path, and flag `validator_sonnet.py`'s stale `-latest` default as a minor housekeeping item (that module is unused by n8n regardless).

**Why the judge design uses Sonnet exclusively, no Haiku "first pass":** JG-1's every trigger (org-type conflict, evidenced-false, vendor-flag detection, mid-confidence-band) is already a conflict/hard-risk case by construction — there is no cheap-classification step to interpose, because the deterministic JG-4 gate already plays the role a Haiku first-pass would have played (cheap citation-quality triage) at zero LLM cost. `config/escalation_policy.yaml`'s `haiku_default.use_for: [..., "first_pass_icp_scoring"]` is about ICP scoring generally, which is out of this phase's scope entirely (Approach C, HubSpot-side) — nothing in Phase 14's design calls Haiku.

**Volume/cost estimate from the actual smoke data:**
- 20 real companies sampled across both smoke runs. Escalation-worthy events observed: 1/20 evidenced-`false` (QRIC — already a JG-1 trigger) + 1/20 hardware-vendor-shaped false positive (Supertech — would trigger once the field is wired). **Org-type conflicts and confidence-band data were not logged in either smoke run** (`13-SMOKE-CLOSED-WON.md`'s own "Script gap" note: *"the smoke prints only `lv_produces_content`; `lv_org_type` and the vendor flags would have made rows 4 and 7 self-explanatory"*) — recommend re-running the smoke script with those fields logged before finalizing a volume estimate; this is a genuine data gap, not something this research can resolve from existing artifacts.
- Conservative floor from what's actually measured: ~10% escalation rate (2/20). Realistic range once org-type-conflict detection and the confidence band are added: 15–25%.
- Per-escalation cost: a Sonnet 5 call with ~500–1500 input tokens (existing record fields + research candidate + evidence_by_field + trigger reason) and ~200–600 output tokens (decision JSON only — **no `web_search` tool on this call**, so no search cost) is roughly $0.005–$0.015 at intro pricing. Against a per-company research call that already costs ~$0.05–$0.15 (5 searches, Phase-13 pricing), the judge adds on the order of 10–20% incremental LLM spend at the estimated escalation rate — small relative to the provider (Apollo/Lusha/ZoomInfo) credit costs already being paid per company.

## Test Plan

Following the Phase 12/13 pattern (shared fixture table + parity discipline + deliberate-break guard), with one adjustment: the judge itself is a genuine single LLM call, so there is no second independent implementation to prove "parity" against (unlike `mergeCompanies.js`/`webResearch.js`, which have a Python twin). Parity discipline still applies to the **deterministic** pieces (the sufficiency check and the escalation trigger), which are pure functions with no model call — exactly analogous to the existing pattern.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python side, no config file found — defaults apply) + `node --test` (JS side, per `tests/n8n/*.test.mjs`) |
| Config file | none — see Wave 0 gap below |
| Quick run command | `node --test tests/n8n/judgeWiring.test.mjs tests/n8n/judgeFailure.test.mjs` |
| Full suite command | `.venv/bin/pytest -q && node --test tests/n8n/*.test.mjs` |

### Exact new fixtures and test files

1. **`tests/fixtures/evidence_sufficiency_cases.json`** — the 20 real rows from `13-SMOKE-CLOSED-WON.md`'s two tables (9 closed-won `true` + 1 closed-won evidenced-`false` [QRIC, expected: routed to judge, not evaluated by the sufficiency heuristic] + 10 closed-lost `true`), each row: `{_case, company, domain, citation_url, expected: "sufficient"|"insufficient"|"judge_only"}`. This is real production data already in the repo — zero fixture fabrication needed, and it directly answers "exact fixtures from the smoke runs."
2. **`n8n/code/judgeWiring.js`** (new module, or an extension of `webResearch.js`) exporting:
   - `isCitationSufficient(url, companyDomain)` — the JG-4 heuristic (own-domain-or-known-video-host AND non-root path).
   - `computeEscalation(researchCandidate, existingRecord)` — JG-1/RO-1/RO-2 trigger logic, returns `{needsJudge: bool, reason: string|null}`.
   - `judgeCandidateFromHttpItem(item)` — never-throws parse of the Judge Call HTTP response, mirrors `researchCandidateFromHttpItem` exactly.
3. **`tests/n8n/judgeWiring.test.mjs`** —
   - `isCitationSufficient` against all 19 `true`-claim rows in the fixture table (assert exact match; document the RWWA-alias-domain known miss inline as an accepted false-negative, not a bug); deliberate-break guard: loosen the root-path check and prove at least one fixture row flips its verdict.
   - `computeEscalation` unit cases: (a) size-conflict-only row → `needsJudge:false` [proves RO-2]; (b) no `research_candidate` / `matched:false` → `needsJudge:false` [proves RO-1]; (c) org-type conflict (existingRecord has a resolved value, research returns a different one) → `true`; (d) `lv_produces_content:false` in research candidate → `true`; (e) `lv_is_hardware_vendor:true` → `true`; (f) confidence in `[70,85]` on org_type/produces_content → `true`.
4. **`tests/n8n/judgeFailure.test.mjs`** — mirrors `webResearchFailure.test.mjs`'s exact four failure shapes (n8n execution-error item, empty content, missing content, Anthropic HTTP-level error body) against `judgeCandidateFromHttpItem`; asserts the result always defaults to a needs_review-equivalent low-confidence decision, never throws (JG-3 + the existing skip-not-retry design).
5. **`tests/test_judge_spec.py`** (new, Python side) — cites JG-1..JG-5/RO-1/RO-2 by ID, following the `test_web_research_spec.py` convention. Two categories:
   - Assertions against the JS module directly (via a Node subprocess call, same pattern `tests/n8n/parity.test.mjs`'s `pyResearch()` helper uses in reverse) for the deterministic pieces, if the planner wants cross-language proof.
   - **`test_jg5_supertech_hardware_veto_independent_of_jg4`**: constructs a `HubSpotRecord` with `lv_is_hardware_vendor=true` and separately toggles `lv_produces_content` between `null` (JG-4-demoted) and `true` (un-demoted), asserting `compute_icp_score(...).anti_icp_flag is True` and `tier == "D"` in **both** cases — proving the veto path is independent of the content-field outcome, using Supertech's actual domain/citation as the fixture identity. This exercises the **existing, unchanged** `src/icp_scoring.py` as a dev-oracle rubric check only — it asserts nothing about any n8n write path (per the Critical Scope Finding above).
6. **`tests/test_architecture_guard.py`** — no new test needed; the existing `test_ar2_no_middleware_hosts` guard already covers the new Judge Call node once it targets `api.anthropic.com` (already allowlisted).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RO-1 | Judge never fires without a matched research candidate | unit | `node --test tests/n8n/judgeWiring.test.mjs` | ❌ Wave 0 |
| RO-2 | Size-only conflicts never trigger the judge | unit | `node --test tests/n8n/judgeWiring.test.mjs` | ❌ Wave 0 |
| JG-1 | Org-type conflict / evidenced-false / vendor-flag / confidence-band all escalate | unit | `node --test tests/n8n/judgeWiring.test.mjs` | ❌ Wave 0 |
| JG-2 | Judge payload excludes revenue/employee bands | unit (payload shape assertion in `Build Judge Request` test) | `node --test tests/n8n/judgeWiring.test.mjs` | ❌ Wave 0 |
| JG-3 | Judge confidence < 80 → needs_review, never promote | unit | `node --test tests/n8n/judgeFailure.test.mjs` | ❌ Wave 0 |
| JG-4 | Insufficient citation demotes true→null, never →false | unit, against real smoke fixtures | `node --test tests/n8n/judgeWiring.test.mjs` | ❌ Wave 0 |
| JG-5 | Hardware-vendor rubric vetoes independently of JG-4 | unit (Python dev-oracle only, per scope finding) | `.venv/bin/pytest tests/test_judge_spec.py -q` | ❌ Wave 0 |

### Wave 0 Gaps
- [ ] `tests/fixtures/evidence_sufficiency_cases.json` — new fixture table, covers JG-4
- [ ] `n8n/code/judgeWiring.js` — new module, covers RO-1/RO-2/JG-1/JG-3/JG-4
- [ ] `tests/n8n/judgeWiring.test.mjs` + `tests/n8n/judgeFailure.test.mjs` — new tests
- [ ] `tests/test_judge_spec.py` — new Python test, covers JG-5's dev-oracle verification
- [ ] No pytest config file was found in the repo root; defaults have worked for the existing 139+ tests, so this is not a blocker — noted for completeness only.

## Common Pitfalls

### Pitfall 1: Wiring `row.conflicts` into the escalation trigger by accident
**What goes wrong:** A naive "any conflict → judge" implementation routes size-band disagreements (already deterministically resolved to `needs_review` today) into a live Sonnet call, silently regressing RO-2.
**Why it happens:** `row.conflicts` and the new org-type-conflict/vendor-flag signals look structurally similar (both are "disagreement" flags on the same row); it's an easy copy-paste trap.
**How to avoid:** `Judge Escalation Gate` reads only `row.research_candidate` and `row.existingRecord`; add an inline comment citing RO-2 explaining the exclusion is deliberate, matching this repo's existing convention (`mergeCompanies.js`'s TX-4 comment).
**Warning signs:** A test asserting "size-conflict-only row → needsJudge:false" failing.

### Pitfall 2: Building a JS hard-veto engine in n8n
**What goes wrong:** Treating JG-5 literally ("the veto should independently disqualify it") as a mandate to port `icp_scoring.py`'s hard-veto rubric into an n8n Code node, contradicting the locked Approach-C scope fence (`5e01f3d`) that assigns derived ICP outputs to HubSpot.
**Why it happens:** The ROADMAP wording reads as if the veto firing is this phase's job.
**How to avoid:** Read the Critical Scope Finding section above before scoping tasks. The in-scope deliverable is the *input* (`lv_is_hardware_vendor` populated correctly) plus an offline dev-oracle rubric check, not a production veto computation.
**Warning signs:** A new `n8n/code/icpScoring.js` file, or a new HubSpot write path for `lv_anti_icp_flag`/`lv_icp_tier` appearing in the plan.

### Pitfall 3: Applying the JG-4 sufficiency heuristic to `false` claims
**What goes wrong:** Reusing `isCitationSufficient()` on an evidenced-`false` citation (e.g. QRIC's) produces a wrong-feeling "sufficient" verdict, because the heuristic validates evidence-of-presence, not evidence-of-absence.
**Why it happens:** It's the same shape of check (own-domain + non-root path), so it's tempting to reuse.
**How to avoid:** `false` claims never reach the sufficiency gate — they route straight to the judge via the existing JG-1 trigger, unconditionally.
**Warning signs:** A test that expects QRIC-shaped input to be evaluated by `isCitationSufficient` instead of escalated.

### Pitfall 4: Prompt drift between the Python dev-oracle and the n8n production prompt
**What goes wrong:** Adding `lv_is_hardware_vendor`/`lv_is_gambling_operator` to only one of `src/web_research.py`'s `RESEARCH_SYSTEM` or `scripts/build_cloud_workflows.py`'s `researchSystemPrompt()` reintroduces the exact prompt-drift risk Phase 13's own comments explicitly call out ("kept in parity with the production n8n research prompt... this dev-oracle prompt is not itself executed by any test, but the two must not drift").
**Why it happens:** Two independent hand-written prompt strings, no shared source, no automated drift check today.
**How to avoid:** Update both in the same commit; consider whether Phase 14 is the moment to add a drift-detection test (not currently present for the prompt text itself, only for the JSON *output contract* via parity tests).
**Warning signs:** `git diff` touching one file but not the other in a commit that changes `required_fields`.

### Pitfall 5: Giving the Judge Call node the `web_search` tool
**What goes wrong:** Copying the "Claude Web Research" HTTP node's body as a template for "Judge Call" and forgetting to strip the `tools` array re-runs search inside the judge call, doubling cost and contradicting JG-2 (judge reasons over already-retrieved evidence, doesn't re-search) and the spirit of RO-1 (judgment grounded in retrieval that already happened, not a fresh one).
**How to avoid:** `Build Judge Request`'s body must omit `tools` entirely, or set it to `[]` explicitly with a comment.
**Warning signs:** The Judge Call node's request body containing `web_search_20250305`.

### Pitfall 6: Unevidenced vendor-flag promotion bypassing the judge
**What goes wrong:** `config/field_policy.yaml`'s real entries for `lv_is_hardware_vendor`/`lv_is_gambling_operator` have no `require_evidence_url` (unlike `lv_org_type`/`lv_produces_content`). If a future change routes a vendor-flag candidate through `mergeCompanies` *before* the escalation gate has a chance to intercept it, an unevidenced `true` at confidence ≥ 85 promotes with zero review — and since this field is a hard-veto input, a false positive here disqualifies a real prospect silently.
**Why it happens:** The evidence gate that exists for org_type/produces_content was never extended to the vendor flags, and JG-1's escalation is currently the *only* thing standing between an unevidenced vendor flag and a wrong veto.
**How to avoid:** Ensure the `Judge Escalation Gate` unconditionally intercepts any `lv_is_hardware_vendor:true`/`lv_is_gambling_operator:true` candidate *before* it reaches `mergeCompanies`'s promotion path — i.e., placement matters: the gate must see the raw research candidate, not just the already-merged decision. Flag `field_policy.yaml`'s missing evidence requirement to the planner as a recommended (not mandatory) hardening task.
**Warning signs:** A HubSpot company flipping to tier D with no evidence URL on `lv_is_hardware_vendor`.

## Risks

- **Data gap in the smoke script**: org-type and vendor-flag values were never logged in either smoke run, so the "how many companies would actually escalate" estimate is a floor, not a measured number. Recommend re-running `scripts/smoke_closed_won_research.py` with those fields added to its printout before finalizing volume/cost assumptions — the smoke doc's own action items already flag this.
- **`escalation_policy.yaml` orphan status**: decide explicitly whether Phase 14 starts loading it (requires solving AR-4 the same way `taxonomy.generated.js` does — generate a JS literal at build time) or continues treating it as documentation-only prose with the actual thresholds hand-duplicated into new JS. Either is defensible; document the choice.
- **RWWA-style alias-domain false negatives**: the JG-4 heuristic's only observed miss (1/20) is a real company's alt-domain not string-matching the HubSpot `domain` property. This fails safe (→ `needs_review`, never a wrong promote/veto) but will generate review-queue noise at some rate in production; consider whether a lightweight registrable-domain-family check (vs. exact string equality) is worth the added complexity — recommend starting with exact-match and revisiting only if review-queue volume proves it matters.
- **Untested `cited_text` availability under JSON-only prompts**: flagged above; do not build JG-4's mechanism around it without a spike, since the recommendation here doesn't require it.
- **`web_search` + `web_fetch` composability in one turn**: flagged as an unverified future enhancement, not load-bearing for this phase's recommendation.

## Explicit Out of Scope

- **RT-5 (research caching by domain, 180-day TTL)** — blocked on missing `*_verified_at` HubSpot properties; Phase 15.
- **PN-4 (source-metadata property renames to the `lv_` convention)** — Phase 15.
- **SJ-1..SJ-3 (scheduled-job predicates)** — Phase 16.
- **Human review operational surface (§22.2, the 9 missing review properties)** — Phase 16.
- **`lv_org_type` text→enumeration HubSpot property migration** — Phase 15, irreversible, explicit sign-off required.
- **The real HubSpot-side ICP formula (`lv_icp_fit_score`/`lv_icp_tier`/`lv_anti_icp_flag` calculation)** — locked out of Milestone 3 scope entirely by the Approach-C decision; not owned by any phase in this milestone.
- **Contacts** — never in scope; spec is companies-only throughout.

## Package Legitimacy Audit

Not applicable — this phase adds no new external package. The Judge Call node uses the existing `n8n-nodes-base.httpRequest` node type against `api.anthropic.com`, already used identically by the "Claude Web Research" node built in Phase 13. `requirements.txt` (Python dev-oracle side) already includes `anthropic>=0.34.0`; no version bump is required for anything in this phase's design.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `citations[].cited_text` populates usefully even when the model is instructed to emit only a JSON object with no prose | JG-4 Design Options | If wrong, no impact on the recommended design (it doesn't depend on this); only matters if a future iteration tries to use `cited_text` as a richer evidence signal |
| A2 | `web_search` and `web_fetch` server tools compose cleanly in one turn (both server-side, unlike Phase 13's client-tool-vs-server-tool conflict) | JG-4 Design Options, option (b) | Purely informational; not part of the recommended design |
| A3 | An exact-string domain-match (no registrable-domain-family fuzzing) is an acceptable JG-4 heuristic for v1, accepting the one known RWWA-style false negative | JG-4 recommendation, Risks | If review-queue volume from alias-domain misses proves significant, a fuzzier match may be warranted later — not blocking for v1 |
| A4 | Bare `claude-sonnet-5` (no `-latest` suffix) is the correct model ID to use for the new Judge Call node | Model/Cost Analysis | If a `-latest` alias exists and is preferred practice, this is a one-line change; the current model catalog documents only the bare form |

## Open Questions

1. **Should the Judge Escalation Gate load `config/escalation_policy.yaml`'s actual thresholds, or hand-duplicate them into new JS?**
   - What we know: the YAML is never parsed today; `taxonomy.yaml` is this repo's precedent for "generate a JS literal at build time so nodes can read it without violating AR-4."
   - What's unclear: whether the planner considers this phase's scope wide enough to add a second generated-config pipeline, or whether inlining the numbers with a documented duplication is acceptable for v1.
   - Recommendation: inline for v1 with an explicit code comment cross-referencing the YAML; revisit only if the thresholds need to change independently of a code deploy.

2. **Should `tests/test_judge_spec.py` assert against the JS module via a Node subprocess (true cross-language parity, like `parity.test.mjs` does in reverse), or is a JS-only test suite sufficient given the judge itself has no Python twin?**
   - What we know: the deterministic pieces (`isCitationSufficient`, `computeEscalation`) are pure functions with no model call, so cross-language parity IS meaningful for them, unlike the judge's own LLM call.
   - What's unclear: whether this phase's plan should build a Python reference implementation of these two functions purely to keep the parity-testing convention, or whether that's unwarranted duplication for logic that will only ever run in n8n.
   - Recommendation: Claude's discretion for the planner — building a Python twin costs one afternoon and buys the same NM-6-style safety net Phase 12/13 relied on; skipping it is defensible since these functions, unlike the taxonomy normalizers, have no dev-oracle consumer that needs a Python implementation.

## Sources

### Primary (HIGH confidence — direct repo file reads)
- `src/classifier_haiku.py`, `src/validator_sonnet.py`, `src/merge_policy.py`, `main.py` — Milestone-1 Python cascade, confirmed unreachable from n8n
- `n8n/code/mergeCompanies.js` — the only conflict-aware logic n8n executes
- `scripts/build_cloud_workflows.py` (lines ~1304–1506) — the Phase-13 research nodes, the production prompt's exact `required_fields`, and `ENRICH_MERGE_CO`'s 3-field fold whitelist
- `config/field_policy.yaml`, `config/taxonomy.yaml`, `config/escalation_policy.yaml` — real config, confirmed orphan status of the escalation policy
- `src/icp_scoring.py` — the unchanged hard-veto rubric, re-scoped by the Approach-C decision to internal routing/audit only
- `.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md` — the 20-row real smoke data JG-4's design was validated against
- `docs/WEB-RESEARCH-SPEC.md` §0.5, §1, §7, §8 — AR-1..4, RO-1/RO-2, TS-1..5, JG-1..5
- `git show 5e01f3d` — the Approach-C scope-fence commit, PROJECT.md/REQUIREMENTS.md/ROADMAP.md/STATE.md diffs
- `tests/test_architecture_guard.py` — confirms `api.anthropic.com` already allowlisted

### Secondary (MEDIUM confidence — WebSearch, cross-checked)
- Anthropic web-search tool response shape (`web_search_tool_result`, `web_search_result` fields) — WebSearch against docs.claude.com / platform.claude.com content
- Citations mechanism (`cited_text`, `web_search_result_location`) — WebSearch against `platform.claude.com/docs/en/build-with-claude/citations`
- Model IDs and pricing (`claude-sonnet-5`, `claude-haiku-4-5`, retired `claude-3-5-haiku-20241022`) — WebSearch/skill-cached catalog, cross-referenced against the migration guide's retired-model and model-ID-rename tables

### Tertiary (LOW confidence — flagged, not load-bearing)
- Whether `web_search` + `web_fetch` compose in one turn — not verified live in this session
- Whether `cited_text` populates on a JSON-only completion — not verified live in this session

## Metadata

**Confidence breakdown:**
- Current-state map (what exists / is unreachable / is orphaned): HIGH — every claim is a direct file read or grep, not inference
- Critical scope finding (Approach C vs. JG-5): HIGH — sourced from the actual locked decision commit and cross-checked against the absence of any n8n icp-scoring JS
- JG-4 design recommendation: HIGH on the smoke-data validation (real rows, hand-checked one by one); MEDIUM on the broader claim that this generalizes beyond the 20 observed companies
- Node topology: MEDIUM — a reasoned proposal consistent with existing patterns, not yet built or tested
- Model/cost analysis: MEDIUM — model IDs/pricing WebSearch-sourced and cross-checked twice; volume estimate explicitly flagged as a floor due to a real data gap

**Research date:** 2026-07-21
**Valid until:** ~30 days for the architectural/scope findings (stable, decision-locked); ~7 days for model pricing (fast-moving, intro pricing expires 2026-08-31)
