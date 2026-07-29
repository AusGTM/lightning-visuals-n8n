---
phase: 14-judge-wiring
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [REQ-evidence-before-judgement]
files_modified:
  - config/escalation_policy.yaml
  - scripts/gen_escalation_js.py
  - n8n/code/escalation.generated.js
  - src/judge.py
  - tests/test_judge_spec.py
  - n8n/code/judge.js
  - tests/fixtures/evidence_sufficiency_cases.json
  - tests/n8n/judge.test.mjs
  - tests/n8n/judgeFailure.test.mjs
  - tests/n8n/parity.test.mjs
  - scripts/build_cloud_workflows.py
  - src/web_research.py
  - n8n/wf_enrichment_local_live.json

must_haves:
  truths:
    - The judge structurally cannot see a size-band disagreement — the Judge Gate node executes UPSTREAM of Merge Company, where that array does not yet exist on the row, and its node body references neither the array nor the watch list (RO-2 proven by topology, not by comment).
    - computeEscalation returns needsJudge:false whenever research_candidate is absent or matched:false, so a company that was never researched can never reach the Judge Call node (RO-1, belt-and-braces on top of the topology).
    - A judge verdict below confidence 80 never promotes — the adjudicated value is demoted to null and needs_review is set (JG-3); a failed/empty/error-shaped Judge Call HTTP response resolves the same way and never throws.
    - isCitationSufficient reproduces the human-adjudicated verdict on all 19 true-claim rows of the real Phase-13 smoke data; an insufficient citation demotes lv_produces_content true->null + needs_review, NEVER to false (JG-4/TS-1).
    - The evidenced-false claim (QRIC) is never evaluated by the sufficiency heuristic — it routes to the judge unconditionally (JG-1).
    - Python and JS agree on is_citation_sufficient for every row of the shared fixture table (NM-6 discipline).
    - The production research prompt requests lv_is_hardware_vendor / lv_is_gambling_operator and the Merge Company research fold no longer drops them, so the vendor-flag INPUT reaches HubSpot; both prompt strings are drift-tested against one another.
    - An unadjudicated vendor-flag `true` never promotes — with the judge disabled or failed, the flag is demoted to null + needs_review rather than written at confidence 85.
    - src/icp_scoring.py vetoes Supertech Electronics on lv_is_hardware_vendor=true with tier D + anti_icp_flag, independently of whether lv_produces_content is true or JG-4-demoted to null (offline dev-oracle proof, no production write path).
    - Escalation thresholds live in config/escalation_policy.yaml only; editing the YAML without regenerating the JS literal fails a currency test.
    - Rebuilding wf_enrichment_local_live.json is deterministic; the only workflow file that changes is that one, and the only pre-existing node bodies that change are Merge Company and Build Research Request.
  artifacts:
    - config/escalation_policy.yaml
    - scripts/gen_escalation_js.py
    - n8n/code/escalation.generated.js
    - n8n/code/judge.js
    - src/judge.py
    - tests/fixtures/evidence_sufficiency_cases.json
    - tests/n8n/judge.test.mjs
    - tests/n8n/judgeFailure.test.mjs
    - tests/test_judge_spec.py
    - n8n/wf_enrichment_local_live.json
  key_links:
    - config/escalation_policy.yaml -> scripts/gen_escalation_js.py -> n8n/code/escalation.generated.js -> n8n/code/judge.js -> Judge Gate node jsCode
    - config/escalation_policy.yaml -> src/judge.py (runtime read, no codegen) -> tests/n8n/parity.test.mjs oracle
    - Validate Research Output -> Judge Gate -> IF Needs Judge -> Build Judge Request -> Judge Call (api.anthropic.com) -> Apply Judge Verdict -> Merge Company
    - Build Research Request required_fields -> Claude Web Research -> research_candidate.data -> ENRICH_MERGE_CO fold whitelist -> mergeCompanies (unchanged) -> lv_is_hardware_vendor in HubSpot
---

# Phase 14 — Judge Wiring

**Goal:** conflicts and high-risk classifications get adjudicated on evidence, not recall.
A deterministic gate settles the ~90% of cases a regex already answers correctly (citation
quality) at zero LLM cost, and a single non-agentic Sonnet call adjudicates the narrow set
JG-1 names: org-type flips, evidenced-`false` content claims, vendor-flag detections, and
mid-confidence-band classifications.

**Requirements:** REQ-evidence-before-judgement (spec RO-1, RO-2, JG-1…JG-5). Regression:
AR-1/AR-2/AR-3/AR-4, TS-1, NM-6 parity discipline.

**Depends on:** Phase 13 (`n8n/code/webResearch.js`, the research node chain,
`research_candidate` contract). **Reversible:** entirely — pure code + git, no HubSpot
writes, no live API calls in any test.

---

## Design decisions (made here, not left to the executor)

### D1 — The judge sits BEFORE Merge Company, not after

RESEARCH proposed inserting the escalation gate *after* `Merge Company` and hand-patching
the merge result. This plan puts the whole judge chain on the research-true lane
**upstream of `Merge Company`** instead. Three reasons, in order of weight:

1. **RO-2 becomes structural, not documentary.** The size-disagreement array and
   `CONFLICT_WATCH` are computed *inside* `ENRICH_MERGE_CO`. A node that runs before it
   cannot read a field that does not exist yet. The user's requirement — "verify this is
   structurally true in the node topology, not just documented" — is satisfied by
   placement, and asserted mechanically in Task 5 (the Judge Gate node body must contain
   neither identifier, and must be a graph ancestor of Merge Company).
2. **No merge-result surgery.** The judge adjudicates the *research candidate*, then
   `mergeCompanies` runs exactly once on the adjudicated values, with its own evidence and
   confidence gates intact. Nothing hand-patches `canonicalPatch`/`decisions` structurally.
3. **Pitfall 6 closes for free.** `lv_is_hardware_vendor` / `lv_is_gambling_operator` have
   no `require_evidence_url` in `field_policy.yaml`, so an unevidenced `true` at confidence
   ≥85 would promote silently — and this phase is what first lets that field reach the merge
   at all. Because the gate is upstream, an unadjudicated vendor flag is demoted to `null`
   before `mergeCompanies` ever sees it. No policy edit, no `mergeCompanies.js` change.

### D2 — `mergeCompanies.js` is NOT modified. Streak intact.

Verified by direct read this session: `DEFAULT_COMPANY_POLICY` (lines 38–39) **already**
carries `lv_is_hardware_vendor` and `lv_is_gambling_operator` as `system_owned`/85. The
hard-coded 3-field whitelist that drops them is in the **`ENRICH_MERGE_CO` n8n wrapper**
(`scripts/build_cloud_workflows.py` ~line 1485), not in the module. Widening that whitelist
is a builder edit. `n8n/code/mergeCompanies.js` stays byte-identical for the third phase
running, and Task 5's node-diff proof asserts it.

### D3 — Thresholds generated, logic hand-written (Phase 12 D2 precedent, verbatim)

`config/escalation_policy.yaml` stops being orphaned prose. `scripts/gen_escalation_js.py`
emits `n8n/code/escalation.generated.js` (data only: the confidence band, the judge minimum,
the required verdict keys, the known-video-host list) behind a DO-NOT-EDIT header, with a
currency test that fails if the YAML is edited without regenerating — the exact
`gen_taxonomy_js.py` pipeline, reused. Python reads the YAML at runtime (`src/judge.py`),
JS reads the generated literal (AR-4). Trigger *conditions* are logic and stay hand-written
in `judge.js`; only numbers and vocabularies are generated.

**One YAML correction, made deliberately:** `confidence_between: [70, 85]` becomes
`[75, 85]`. Spec §8 JG-1 is normative and says 75–85; the YAML's own inline comment admits
its range was reconstructed from CLAUDE.md §15.1's corrupted `[2][3]` markdown artifact and
labels itself "Illustrative". The file has never been parsed by any code, so nothing
regresses. Task 1 asserts the band equals JG-1's stated range, citing the spec ID.

### D4 — Python twin for the sufficiency function only

Per the user's decision: `is_citation_sufficient` gets the full NM-6 treatment (shared
fixture built from the 20 real smoke rows, Python/JS parity test, deliberate-break proof).
It is pure logic, it is the highest-value thing to get right, and it is the one piece with
a genuine dev-oracle consumer (`scripts/smoke_closed_won_research.py` can adopt it later).
The judge's HTTP plumbing — payload build, verdict parse, verdict application — has no
Python counterpart and gets none; a "parity test" against a second hand-written copy of
glue code proves nothing.

### D5 — Kill switches: reuse `ALLOW_SONNET_ESCALATION` / `MAX_SONNET_VALIDATIONS_PER_RUN`

Both already exist in `.env.example` (lines 26, 40) and mean exactly this. No new config
flag. Enforcement mirrors Phase 13 D5: the cap is applied in the Judge Gate node, physically
upstream of the HTTP node, never per-item after it.

**Fail-safe semantics when the judge does not run (off, capped out, HTTP failure, or
verdict confidence <80):**

| Field | Behaviour | Why |
|---|---|---|
| `lv_is_hardware_vendor` / `lv_is_gambling_operator` = `true` | demote to `null`, set needs_review | New to the write path in this phase; an unadjudicated hard-veto INPUT must never promote (Pitfall 6). No prior behaviour to preserve. |
| `lv_produces_content` = `false` | **unchanged** — passes through as today | Phase 13 TS-3 says an evidenced `false` flows. `ALLOW_SONNET_ESCALATION` defaults to `false`, so demoting here would silently neuter a shipped, tested requirement. Not this phase's call to make. |
| `lv_org_type` conflict | keep the *existing* record value, set needs_review | Never flip a promoted org type on an unadjudicated re-research (current-state finding #5). |

### D6 — JG-4 runs always; the model call does not

Sufficiency is deterministic and free, so it runs on every researched company regardless of
`ALLOW_SONNET_ESCALATION`. It applies **only** to `lv_produces_content === true`
(evidence-of-presence). A `false` claim never touches the heuristic — it routes to the judge
unconditionally (Pitfall 3: sufficiency-of-presence and sufficiency-of-absence are not the
same judgement, and QRIC's own-domain non-root citation would score "sufficient" for the
wrong reason).

The rule, validated by hand against all 20 real rows:

> **(citation host, `www.` stripped, equals the company's domain, `www.` stripped — OR is a
> known video host) AND (citation path is not `/` or empty).**

19/20 exact; the 20th (RWWA `racingwa.com.au` vs HubSpot domain `rwwa.com.au`) is an
alias-domain false negative that fails safe to `needs_review`, never to a wrong `false` or a
wrong veto. Exact-string domain match only — no registrable-domain-family fuzzing in v1
(RESEARCH A3).

---

## Tasks

### Task 1 — Escalation policy becomes a real single source + the offline spec assertions

**Files:** `config/escalation_policy.yaml`, `scripts/gen_escalation_js.py` (new),
`n8n/code/escalation.generated.js` (new, generated), `src/judge.py` (new),
`tests/test_judge_spec.py` (new)

**Action:**

1. Edit `config/escalation_policy.yaml`:
   - `sonnet_5.use_when` → change `confidence_between: [70, 85]` to `[75, 85]` and replace
     the "Illustrative range" comment with one citing spec §8 JG-1 as the source of the
     range.
   - Add a new top-level block:
     ```yaml
     evidence_sufficiency:
       # JG-4: a citation on one of these hosts substantiates content output even though
       # the host is not the company's own domain (owned channel). Non-root path still
       # required. Validated against the 20 real rows in the Phase-13 closed-won/lost smoke.
       known_video_hosts:
         - youtube.com
         - youtu.be
         - vimeo.com
         - twitch.tv
     ```
   - Leave `haiku_default`, `human_review` and `output_required` untouched.

2. Create `scripts/gen_escalation_js.py`, modelled directly on `scripts/gen_taxonomy_js.py`
   (same `render() -> str` + `__main__` writer shape, same `json.dumps` escaping rule, no
   timestamp in the output or the currency test fails on every run). It emits
   `n8n/code/escalation.generated.js` containing a DO-NOT-EDIT header naming
   `config/escalation_policy.yaml` and the regeneration command, then:
   - `const ESCALATION_CONFIDENCE_BAND` — `[75, 85]` from `sonnet_5.use_when`'s
     `confidence_between` entry (the block is a list of single-key dicts; write a small
     lookup helper, do not index by position).
   - `const JUDGE_MIN_CONFIDENCE` — from `human_review.use_when`'s `sonnet_confidence_below`
     (80). This is JG-3's threshold.
   - `const JUDGE_OUTPUT_REQUIRED` — `sonnet_5.output_required`, verbatim order.
   - `const KNOWN_VIDEO_HOSTS` — `evidence_sufficiency.known_video_hosts`, sorted.
   - trailing `module.exports = { ... }` (required by `node --test`, stripped by
     `strip_module()` on the way into a Code node).

   Wire the generator into `scripts/build_cloud_workflows.py` beside the existing
   `gen_taxonomy_js` call (~line 29–31), so a rebuild can never emit a stale threshold.

3. Create `src/judge.py` — the Python side reads the YAML at runtime, exactly as
   `src/taxonomy.py` reads `config/taxonomy.yaml` (module-level cache, repo-root-relative
   path). Export `ESCALATION_CONFIDENCE_BAND`, `JUDGE_MIN_CONFIDENCE`,
   `JUDGE_OUTPUT_REQUIRED`, `KNOWN_VIDEO_HOSTS`. `is_citation_sufficient` lands here in
   Task 2 — do not stub it now.

4. Create `tests/test_judge_spec.py`, following `tests/test_web_research_spec.py`'s
   convention of citing spec IDs by name in the test names/docstrings:
   - `test_jg1_confidence_band_matches_spec` — `ESCALATION_CONFIDENCE_BAND == [75, 85]`,
     docstring quoting JG-1's "confidence in 75–85".
   - `test_jg3_judge_minimum_is_80` — `JUDGE_MIN_CONFIDENCE == 80`.
   - `test_escalation_generated_js_is_current` — the currency guard: assert
     `gen_escalation_js.render()` equals the checked-in
     `n8n/code/escalation.generated.js`, with a failure message naming the regeneration
     command (mirrors `test_taxonomy_generated_js_is_current`).
   - `test_jg5_supertech_hardware_veto_independent_of_jg4` — the offline dev-oracle rubric
     proof. Build a `HubSpotRecord(object_type="companies", id="…", properties={...})`
     carrying Supertech's real identity (`name: "Supertech Electronics"`,
     `domain: "www.supertech-electronics.com.au"`, `lv_country_region_normalized: "AU"`),
     then call `compute_icp_score` twice with `lv_is_hardware_vendor=True` and
     `lv_produces_content` set to `True` (the un-demoted false positive) and `None` (the
     JG-4-demoted value). Assert `anti_icp_flag is True` and `tier == "D"` in **both** runs,
     and that `"hardware" in anti_icp_reason.lower()`. Add a docstring stating this
     exercises the unchanged `src/icp_scoring.py` as a dev oracle only (AR-3, Approach C) —
     it asserts nothing about any n8n write path.

**Do NOT:** port any part of `icp_scoring.py`'s veto into JS; create
`n8n/code/icpScoring.js`; add a HubSpot write path for `lv_anti_icp_flag` / `lv_icp_tier`;
touch `src/icp_scoring.py`, `config/icp_scoring.yaml` or any score number.

**Acceptance criteria:**

- `n8n/code/escalation.generated.js` passes `node --check` and `require()`s cleanly.
- Running the generator twice is a byte-for-byte no-op.
- Editing the YAML band without regenerating makes the currency test FAIL (scripted below).
- The JG-5 test passes in both the `True` and `None` content branches — if it passes in only
  one, the veto is not independent and the plan's premise is wrong; stop and report.
- `.venv/bin/pytest -q` → 139 baseline + the new tests, 0 failed.

**Verify:**

```bash
.venv/bin/python scripts/gen_escalation_js.py && node --check n8n/code/escalation.generated.js
node -e 'const e=require("./n8n/code/escalation.generated.js");
if(JSON.stringify(e.ESCALATION_CONFIDENCE_BAND)!=="[75,85]"){console.error("band mismatch",e.ESCALATION_CONFIDENCE_BAND);process.exit(1)}
if(e.JUDGE_MIN_CONFIDENCE!==80){console.error("min mismatch",e.JUDGE_MIN_CONFIDENCE);process.exit(1)}
console.log("escalation.generated.js OK")'
.venv/bin/pytest tests/test_judge_spec.py -q
.venv/bin/pytest -q

# Currency guard actually fires. File-copy backup/restore, never `git checkout --`.
cp config/escalation_policy.yaml /tmp/escalation.bak
trap 'cp /tmp/escalation.bak config/escalation_policy.yaml' EXIT
perl -0pi -e 's/confidence_between: \[75, 85\]/confidence_between: [70, 85]/' config/escalation_policy.yaml
if .venv/bin/pytest tests/test_judge_spec.py -q -k current 2>/dev/null; then
  echo "FAIL: currency test passed with a stale generated file" >&2; exit 1
fi
echo "escalation currency guard fires as expected"
cp /tmp/escalation.bak config/escalation_policy.yaml; trap - EXIT
git diff --exit-code config/escalation_policy.yaml   # proves the revert landed (pre-commit)
```

> If the `perl` substitution does not match (check the exact YAML spacing you wrote), edit
> the band by hand instead, run the same `-k current` check, confirm a genuine
> `AssertionError`, then restore from `/tmp/escalation.bak`.

**Commit:** `feat(14-01): escalation policy single-source + JG-1/JG-3/JG-5 offline assertions`

---

### Task 2 — JG-4 citation sufficiency: 20-row real fixture, JS + Python twin, parity

**Files:** `tests/fixtures/evidence_sufficiency_cases.json` (new), `n8n/code/judge.js`
(new), `src/judge.py`, `tests/n8n/judge.test.mjs` (new), `tests/n8n/parity.test.mjs`

**Action:**

1. Create `tests/fixtures/evidence_sufficiency_cases.json` — the single shared table both
   languages read (NM-6 discipline; neither side carries its own case list). Transcribe all
   20 rows from `.planning/phases/13-web-research-retrieval-validation/13-SMOKE-CLOSED-WON.md`
   (the **second** closed-won run's table, which carries real URLs, plus the closed-lost
   control table). Shape: a top-level `evidence_cases` list of
   `{company, domain, citation_url, claim, expected}` where `domain` is the HubSpot domain
   verbatim (`www.` prefixes included — the heuristic must strip them itself) and `expected`
   is one of `sufficient` / `insufficient` / `judge_only`.

   Expected verdicts (transcribe exactly; these are hand-derived from the human adjudication
   in the smoke doc's "Reading" sections and re-checked this session):

   | # | Company | Domain | Citation | expected |
   |---|---|---|---|---|
   | 1 | Australian Turf Club | australianturfclub.com.au | https://www.youtube.com/user/AtcracesTV?cbrd=1 | sufficient |
   | 2 | Redcliffe Harness RC | redcliffehrc.com.au | https://redcliffehrc.com.au/ | insufficient |
   | 3 | Rockhampton Jockey Club | callaghanpark.com.au | https://www.youtube.com/@rockhamptonjockeyclub6459 | sufficient |
   | 4 | Wyong | www.wyongraceclub.com.au | https://www.bets.com.au/horse-racing/race-courses/wyong-races-live-stream-20210406-0030/ | insufficient |
   | 5 | Melbourne Racing Club | mrc.racing.com | https://www.troa.com.au/content/racingdotcom | insufficient |
   | 6 | Panasonic Studio Productions | www.pspvideo.com.au | https://pspvideo.com.au/ | insufficient |
   | 7 | Brisbane Racing Club | brc.com.au | https://www.youtube.com/@brisbaneracingclub427 | sufficient |
   | 8 | Racing and Wagering WA | rwwa.com.au | https://racingwa.com.au/tv | insufficient |
   | 9 | Queensland Racing Integrity Commission | www.qric.qld.gov.au | https://qric.qld.gov.au/about-us/functions-powers/ | judge_only |
   | 10 | GRAVITY MEDIA | www.gravitymedia.com | https://www.gravitymedia.com/us/what-we-do/production-content/ | sufficient |
   | 11 | The Creek Agency | thecreek.com.au | https://www.thecreek.com.au/ | insufficient |
   | 12 | Scone Race Club | www.sconeraceclub.com.au | https://www.youtube.com/channel/UC1AqN0yBcRhDo_Mgr4CMPTg | sufficient |
   | 13 | Racing NSW | www.racingnsw.com.au | https://www.racingnsw.com.au/ | insufficient |
   | 14 | Supertech Electronics | www.supertech-electronics.com.au | https://myausweb.net.au/automotive/supertech-electronics/ | insufficient |
   | 15 | Cairns Jockey Club | www.cairnsjockeyclub.com.au | https://www.cairnsjockeyclub.com.au/news/ | sufficient |
   | 16 | Victoria Racing Club | flemington.com.au | https://www.vrc.com.au/ | insufficient |
   | 17 | Bunbury Trotting Club | www.bunburytrottingclub.com.au | https://visitbunburygeographe.com.au/business/bunbury-trotting-club/ | insufficient |
   | 18 | Sunshine Coast Turf Club | sctc.com.au | https://www.sctc.com.au/race-fields-footage/ | sufficient |
   | 19 | Harness Racing ACT | www.capitaltrots.com.au | https://capitaltrots.com.au/ | insufficient |
   | 20 | Thoroughbred Park | www.thoroughbredpark.com.au | https://thoroughbredpark.com.au/racing-information/ | sufficient |

   Row 9 is the only `claim: false` row and is `judge_only`; every other row is
   `claim: true`. Row 8 carries a `note` field recording the accepted alias-domain false
   negative (RWWA, RESEARCH A3) so a future reader does not "fix" it into a bug.

2. Create `n8n/code/judge.js`. This task adds only the sufficiency half:
   - `const { KNOWN_VIDEO_HOSTS } = require("./escalation.generated");` in
     `strip_module`-compatible single-line destructure form (check against
     `scripts/build_cloud_workflows.py`'s `_REQUIRE_RE`).
   - `isCitationSufficient(url, companyDomain)` — parse the URL defensively (no `new URL`
     throw escaping: any parse failure returns `false`); lowercase host and company domain;
     strip a single leading `www.` from each; sufficient iff
     `(host === companyDomain || KNOWN_VIDEO_HOSTS.includes(host))` **and** the path is
     neither `""` nor `"/"`. Query strings and fragments are ignored (row 1 carries
     `?cbrd=1`).
   - `applyEvidenceSufficiency(researchCandidate, companyDomain)` — returns a NEW candidate
     (no in-place mutation of the caller's object). No-op unless
     `data.lv_produces_content === true`. When it is `true`: if
     `evidence_by_field.lv_produces_content` is missing, or `isCitationSufficient` is false,
     set `data.lv_produces_content = null`, drop that evidence key, and set
     `judge_flags.insufficient_content_evidence = true`. **Never write `false`** (TS-1).
   - Header comment citing JG-4 and TS-1, and stating explicitly that this function must
     never be applied to a `false` claim (Pitfall 3), with the QRIC row named as the reason.
   - `module.exports` both functions (Task 3 and 4 append to this list).

3. Add `is_citation_sufficient(url, company_domain)` to `src/judge.py` — same contract, same
   `www.`-stripping, same root-path rule, reading `KNOWN_VIDEO_HOSTS` from the YAML. Use
   `urllib.parse.urlsplit`; any exception returns `False`. This is the D4 twin; do NOT port
   `applyEvidenceSufficiency`.

4. Create `tests/n8n/judge.test.mjs` (`createRequire` harness, same as
   `webResearchFailure.test.mjs`):
   - Drive `isCitationSufficient` over every `claim: true` row of the fixture, asserting the
     `expected` verdict, with the company name in the assertion message. Assert the
     `judge_only` row is **excluded** from this loop by construction (assert the loop ran
     exactly 19 times).
   - Assert `applyEvidenceSufficiency` on a Supertech-shaped candidate yields
     `data.lv_produces_content === null` — and explicitly `!== false`.
   - Assert a sufficient row (Sunshine Coast) is left untouched, value still `true`,
     evidence key intact.
   - Assert a candidate with `lv_produces_content: false` is returned unchanged (the
     heuristic must not touch it).

5. Append a JG-4 parity test to `tests/n8n/parity.test.mjs`, following the existing
   `pyTaxonomy` / `pyResearch` oracle pattern: one `execFileSync` subprocess for the whole
   table, importing `is_citation_sufficient` from `src.judge`, returning a list of booleans;
   `assert.deepStrictEqual` against the JS results. Name it so
   `--test-name-pattern="judge.*parity"` targets it.

**Acceptance criteria:**

- All 19 `true`-claim rows match their expected verdict; 8 sufficient / 11 insufficient.
- `node --check n8n/code/judge.js` passes.
- Deliberate-break proof: loosening the root-path check makes at least one fixture row flip
  and the test fail, naming it.
- Deliberate-break proof: diverging the Python twin makes the parity test fail.
- `.venv/bin/pytest -q` and `node --test tests/n8n/*.test.mjs` green.

**Verify:**

```bash
node --check n8n/code/judge.js
node --test tests/n8n/judge.test.mjs
node --test tests/n8n/*.test.mjs
.venv/bin/pytest -q

# Sanity: the fixture really carries 20 rows, exactly one of them judge_only.
.venv/bin/python -c "
import json; c=json.load(open('tests/fixtures/evidence_sufficiency_cases.json'))['evidence_cases']
assert len(c)==20, len(c)
from collections import Counter; k=Counter(r['expected'] for r in c)
assert k=={'sufficient':8,'insufficient':11,'judge_only':1}, k
print('fixture shape OK', dict(k))"

# JG-4 guard actually fires. File-copy backup/restore, never git checkout --.
cp n8n/code/judge.js /tmp/judge.bak
trap 'cp /tmp/judge.bak n8n/code/judge.js' EXIT
# break the non-root requirement: accept any path
perl -0pi -e 's/path !== "\/" && path !== ""/true/' n8n/code/judge.js
if node --test tests/n8n/judge.test.mjs 2>/dev/null; then
  echo "FAIL: JG-4 test passed with the root-path check removed" >&2; exit 1
fi
echo "JG-4 root-path guard fires as expected"
cp /tmp/judge.bak n8n/code/judge.js; trap - EXIT

# Parity guard actually fires (diverge Python, not JS).
cp src/judge.py /tmp/judge_py.bak
trap 'cp /tmp/judge_py.bak src/judge.py' EXIT
perl -0pi -e 's/^(\s*)host = host/$1host = "zzz"  # deliberate divergence\n$1host = host/m' src/judge.py
if node --test --test-name-pattern="judge.*parity" tests/n8n/parity.test.mjs 2>/dev/null; then
  echo "FAIL: parity passed with a deliberately divergent Python twin" >&2; exit 1
fi
echo "JG-4 parity guard fires as expected"
cp /tmp/judge_py.bak src/judge.py; trap - EXIT
```

> Both `perl` substitutions target the exact source you just wrote — if either does not
> match, make the equivalent one-line break by hand, run the same targeted test, confirm a
> genuine `AssertionError` (not a zero-collected no-op), then restore from the `/tmp` copy.

**Commit:** `feat(14-02): JG-4 citation sufficiency over the 20 real smoke rows + Python parity`

---

### Task 3 — JG-1 / RO-1 / RO-2 escalation trigger + the unadjudicated-claim fail-safe

**Files:** `n8n/code/judge.js`, `tests/n8n/judge.test.mjs`

**Action:**

1. Add to `n8n/code/judge.js` (extend the existing `require` destructure to pull
   `ESCALATION_CONFIDENCE_BAND` as well):

   - `normalizeVendorFlag(v)` → strict `true` / `false` / `null`. The model may answer
     `"true"` / `"yes"` / `1`; `lv_is_hardware_vendor` is a HubSpot boolean and a hard-veto
     input, so anything unrecognised becomes `null`, never `false`.

   - `computeEscalation(researchCandidate, existingRecord)` → `{ needsJudge, reasons }`
     (`reasons` is an array of stable string codes so the payload and the tests can name
     them). Rules, in order:
     - **RO-1 first:** `if (!researchCandidate || !researchCandidate.matched) return
       { needsJudge: false, reasons: [] }`. No retrieval → no judgement, ever.
     - `org_type_conflict` — `existingRecord.lv_org_type` is a non-blank, non-`unknown`
       value AND the research candidate's `lv_org_type` differs from it. This detector does
       not exist anywhere today (current-state finding #5) and is JG-1's first trigger.
     - `produces_content_false` — candidate `lv_produces_content === false`.
     - `hardware_vendor_detected` / `gambling_operator_detected` — the respective flag
       normalizes to `true`.
     - `confidence_band` — `researchCandidate.confidence` falls inside
       `ESCALATION_CONFIDENCE_BAND` **inclusive** on both ends, AND the candidate actually
       carries `lv_org_type` or `lv_produces_content` (JG-2: the band is about
       classification confidence, not about a size guess).

     **RO-2 discipline — read carefully.** This function takes exactly two arguments and
     must not grow a third. It must contain no reference to the size-disagreement array that
     `ENRICH_MERGE_CO` builds, nor to that node's watch-list constant. Task 5 asserts both
     identifiers are absent from the built Judge Gate node body, so **do not name either of
     them in a comment either** — a comment naming the identifier is indistinguishable from
     a reference to a grep. Cite the requirement ID and describe the exclusion in words
     instead: *"RO-2: size-band disagreement is detected downstream inside Merge Company and
     is deliberately invisible here — this gate runs before that node, so no model call can
     ever be triggered by a size disagreement alone."*

   - `applyUnadjudicated(researchCandidate, reasons)` → the D5 fail-safe, applied when a
     trigger fired but the judge did not run (kill switch off, cap exhausted) or did not
     confirm. Demote `lv_is_hardware_vendor` / `lv_is_gambling_operator` to `null` when they
     were `true`; on `org_type_conflict`, drop `lv_org_type` from the candidate entirely so
     the existing record value stands; leave `lv_produces_content` untouched (D5 table —
     TS-3 stays as shipped). Set `judge_flags.unadjudicated = true` and record `reasons`.

2. Extend `tests/n8n/judge.test.mjs` with the trigger matrix (each its own `test()` so a
   failure names the requirement):
   - **RO-1(a):** `computeEscalation(null, {...})` → `needsJudge:false`.
   - **RO-1(b):** `computeEscalation({matched:false, data:{lv_produces_content:false}}, {})`
     → `needsJudge:false` — an unmatched candidate cannot escalate even carrying a trigger
     value.
   - **RO-2:** a row object carrying a populated size-disagreement array *and* a benign
     research candidate → `needsJudge:false`. Pass the row's fields explicitly so the test
     proves the function never receives the array in the first place; assert the function's
     `length` is 2 (arity) as the mechanical half of the claim.
   - **JG-1(a):** existing `lv_org_type: "governing_body_league"`, research says
     `"content_producer"` → `needsJudge:true`, reasons include `org_type_conflict`.
   - **JG-1(b):** existing `lv_org_type` blank/`unknown`, research says anything → NOT an
     org-type conflict (first-time resolution is not a flip).
   - **JG-1(c):** `lv_produces_content: false` → true, reason `produces_content_false`.
   - **JG-1(d):** `lv_is_hardware_vendor: "true"` (string) → true, reason
     `hardware_vendor_detected` — proves `normalizeVendorFlag` feeds the trigger.
   - **JG-1(e):** confidence 75, 80, 85 → true; 74 and 86 → false. Boundary cases both ends.
   - **Fail-safe:** `applyUnadjudicated` on a hardware-vendor candidate yields
     `lv_is_hardware_vendor === null` (explicitly `!== false`) and leaves an evidenced
     `lv_produces_content: false` untouched.

**Acceptance criteria:**

- Every case above passes; `node --test tests/n8n/*.test.mjs` green.
- Deliberate-break proof: making the trigger fire on a size disagreement fails the RO-2 test.
- No new argument on `computeEscalation`; arity assertion passes.

**Verify:**

```bash
node --check n8n/code/judge.js
node --test tests/n8n/judge.test.mjs
node --test tests/n8n/*.test.mjs
.venv/bin/pytest -q

# RO-2 guard actually fires: give computeEscalation a third argument it must not have.
cp n8n/code/judge.js /tmp/judge.bak
trap 'cp /tmp/judge.bak n8n/code/judge.js' EXIT
perl -0pi -e 's/function computeEscalation\(researchCandidate, existingRecord\)\s*\{/function computeEscalation(researchCandidate, existingRecord, sizeDisagreements) {\n  if ((sizeDisagreements || []).length) return { needsJudge: true, reasons: ["size"] };/' n8n/code/judge.js
if node --test tests/n8n/judge.test.mjs 2>/dev/null; then
  echo "FAIL: RO-2 test passed with a size-triggered escalation wired in" >&2; exit 1
fi
echo "RO-2 guard fires as expected"
cp /tmp/judge.bak n8n/code/judge.js; trap - EXIT
```

**Commit:** `feat(14-03): JG-1 escalation triggers with RO-1/RO-2 structural exclusions`

---

### Task 4 — JG-2 judge payload + JG-3 never-throws verdict handling

**Files:** `n8n/code/judge.js`, `tests/n8n/judgeFailure.test.mjs` (new)

**Action:**

1. Add to `n8n/code/judge.js` (extend the destructure with `JUDGE_MIN_CONFIDENCE` and
   `JUDGE_OUTPUT_REQUIRED`):

   - `buildJudgeRequestBody(row, model, maxTokens)` → the Anthropic Messages body.
     **JG-2 constraints, each of which Task 4's tests assert:**
     - the payload's company block carries identity + classification only: name, domain,
       the existing record's `lv_org_type`, the research candidate's `data` restricted to
       `lv_org_type` / `lv_produces_content` / `lv_content_type` / the two vendor flags, its
       `evidence_by_field`, and the escalation `reasons`;
     - **no** `lv_revenue_band`, `lv_employee_band`, `annualrevenue`, `numberofemployees`
       anywhere in the serialized body;
     - **no `tools` key at all** (Pitfall 5 — copying the research node's body and forgetting
       to strip the search tool doubles cost and re-searches inside the judge, contradicting
       JG-2 and the spirit of RO-1). The judge reasons over evidence already retrieved.
     - system prompt: adjudicate identity/classification from the supplied evidence only,
       never re-research, never assert a fact no cited URL supports; return ONLY one JSON
       object with the keys in `JUDGE_OUTPUT_REQUIRED` plus `chosen_field`; state explicitly
       that "no evidence for the claim" must produce a `needs_review` decision with a null
       chosen value, never a `false` value (TS-1).
     - `max_tokens` default 4096 (same reasoning as Phase 13: extended thinking plus the
       JSON payload; 2000 truncated live responses).

   - `judgeVerdictFromHttpItem(item)` → mirrors `researchCandidateFromHttpItem` in
     `webResearch.js` exactly, including reusing its `extractFinalJson`-shaped tolerance
     (import it via `require("./webResearch")` if the `strip_module` require form permits a
     second module in the inline list — it does; otherwise duplicate the ~12-line extractor
     and say so in a comment). **Never throws.** Every failure shape — n8n execution-error
     item, missing/empty `content`, Anthropic HTTP-level error body, unparseable text,
     verdict missing a `JUDGE_OUTPUT_REQUIRED` key — resolves to
     `{ decision: "needs_review", chosen_value: null, confidence: 0, reason: "<shape>" }`.
     **JG-3:** any verdict whose `confidence < JUDGE_MIN_CONFIDENCE` is rewritten to
     `decision: "needs_review"` before returning, regardless of what the model said.

   - `applyJudgeVerdict(researchCandidate, verdict, reasons)` → returns a new candidate.
     `decision === "promote"` (or `"confirm"`) with confidence ≥ 80 keeps the adjudicated
     value (writing `verdict.chosen_value` when present). Anything else routes through
     `applyUnadjudicated` and sets `judge_flags.needs_review = true` with the verdict's
     reason. There is no path in which a sub-80 verdict produces a promoted value — assert
     it directly.

2. Create `tests/n8n/judgeFailure.test.mjs`, mirroring
   `tests/n8n/webResearchFailure.test.mjs`'s structure and its four failure shapes:
   `{error: "ETIMEDOUT…"}`, `{content: []}`, `{}`, and
   `{type:"error", error:{type:"overloaded_error"}}`. Plus: a text block that is not JSON,
   and a well-formed verdict at confidence 79 vs 80 (the JG-3 boundary). For every failure
   shape assert no throw, `decision === "needs_review"`, `confidence === 0`. For the 79 case
   assert the decision is rewritten to `needs_review` even though the model said `promote`,
   and that `applyJudgeVerdict` leaves no promoted vendor flag behind.

**Acceptance criteria:**

- `JSON.stringify(buildJudgeRequestBody(...))` contains none of `revenue`, `employee`,
  `web_search`, `tools` — asserted as a single substring check per token.
- Every failure shape returns a needs_review verdict and never throws.
- Confidence 79 → `needs_review`; 80 → `promote` survives.
- Deliberate-break proof: making the parser rethrow on the error-key shape fails the test.

**Verify:**

```bash
node --check n8n/code/judge.js
node --test tests/n8n/judgeFailure.test.mjs
node --test tests/n8n/*.test.mjs
.venv/bin/pytest -q

# JG-3 / never-throws guard actually fires.
cp n8n/code/judge.js /tmp/judge.bak
trap 'cp /tmp/judge.bak n8n/code/judge.js' EXIT
perl -0pi -e 's/(function judgeVerdictFromHttpItem\(item\)\s*\{)/$1\n  if (item \&\& item.error) throw new Error("deliberate break");/' n8n/code/judge.js
if node --test tests/n8n/judgeFailure.test.mjs 2>/dev/null; then
  echo "FAIL: failure test passed with a rethrowing verdict parser" >&2; exit 1
fi
echo "never-throws guard fires as expected"
cp /tmp/judge.bak n8n/code/judge.js; trap - EXIT
```

**Commit:** `feat(14-04): JG-2 judge payload + JG-3 never-throws verdict handling`

---

### Task 5 — Wire the judge into n8n; vendor-flag inputs reach HubSpot

**Files:** `scripts/build_cloud_workflows.py`, `src/web_research.py`,
`tests/test_judge_spec.py`, `n8n/wf_enrichment_local_live.json` (regenerated)

**Action:**

1. **Prompt widening (criterion 5, first half).** In `scripts/build_cloud_workflows.py`'s
   `ENRICH_BUILD_RESEARCH_REQUEST`:
   - `required_fields` becomes
     `["lv_org_type", "lv_produces_content", "lv_content_type", "lv_is_hardware_vendor", "lv_is_gambling_operator"]`.
   - the system prompt's JSON schema line gains
     `"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>` inside
     `data`, and one sentence: these two are hard-veto inputs — answer `null` unless a cited
     source directly supports the classification.

   In `src/web_research.py`'s `RESEARCH_SYSTEM`, make the same two additions to the schema
   string (Pitfall 4: the two prompts are independently hand-written and must not drift —
   `REQUIRED_FIELDS` in that file already lists both flags, only the schema string lags).

   Add `test_prompt_parity_vendor_flags` to `tests/test_judge_spec.py`: read both source
   files as text and assert each of `lv_is_hardware_vendor` and `lv_is_gambling_operator`
   appears in `src/web_research.py`'s `RESEARCH_SYSTEM` **and** in
   `scripts/build_cloud_workflows.py`'s `ENRICH_BUILD_RESEARCH_REQUEST` block. This is the
   drift check that does not exist today.

2. **Merge fold widening (criterion 5, second half).** In `ENRICH_MERGE_CO`'s n8n wrapper,
   the research fold's hard-coded whitelist gains the two vendor flags:
   `["lv_org_type", "lv_produces_content", "lv_content_type", "lv_is_hardware_vendor", "lv_is_gambling_operator"]`.
   Nothing else in that node changes — the second `mergeCompanies()` call, its opts, and the
   shallow-merge already handle them, and `DEFAULT_COMPANY_POLICY` already carries both
   fields. **`n8n/code/mergeCompanies.js` is not edited** (D2).

3. **Four new node bodies**, placed next to the Phase-13 `ENRICH_*` research constants and
   following the same style:

   - **`ENRICH_JUDGE_GATE`** = `inline("escalation.generated.js", "judge.js")` + a
     `runOnceForAllItems` wrapper. Per item: read `row.identity_keys.domain` (falling back to
     `row.existingRecord.domain`); run `applyEvidenceSufficiency` (D6 — always, no kill
     switch); then `computeEscalation(row.research_candidate, row.existingRecord || {})`.
     Apply the D5 gates: `ALLOW_SONNET_ESCALATION` (off → `needs_judge:false`) and
     `MAX_SONNET_VALIDATIONS_PER_RUN` (a run-local counter, same shape as the Research
     Trigger Gate's `remaining`). When a trigger fired but the judge will not run, apply
     `applyUnadjudicated` here. Emit every row (pass-through) with the possibly-demoted
     `research_candidate`, `needs_judge`, and `judge_reasons`.
     **This node body must not name the size-disagreement array or the watch-list constant,
     in code OR in comments** — see Task 3's discipline note; step 5 below greps for both.
   - **`ENRICH_BUILD_JUDGE_REQUEST`** = `inline("escalation.generated.js", "judge.js")` +
     wrapper attaching `judge_request_body = buildJudgeRequestBody(row, model, 4096)` for
     `needs_judge` rows (`null` otherwise), model resolved with the same
     `($vars && $vars.ANTHROPIC_SONNET_MODEL) || $env… || "claude-sonnet-5"` idiom. Bare
     `claude-sonnet-5`, no `-latest` suffix (RESEARCH A4, matches the Phase-13 research node).
   - **`ENRICH_APPLY_JUDGE_VERDICT`** = `inline("escalation.generated.js", "judge.js")` +
     wrapper: `judgeVerdictFromHttpItem(row)` then
     `applyJudgeVerdict(row.research_candidate, verdict, row.judge_reasons)`; attach
     `judge_verdict` for the audit trail and pass through.
   - **`ENRICH_DECIDE_CO_LOCAL`** — one line only: `needs_review` becomes
     `(row.conflicts || []).length > 0 || !!(row.judge_flags && row.judge_flags.needs_review)
     || !!(row.research_candidate && row.research_candidate.judge_flags)` (use whichever
     single flag location `judge.js` actually writes; keep it to one expression). Also echo
     `judge_reasons` and `judge_verdict` in the emitted object so a dry run is inspectable.

4. **Wiring** in `build_enrichment_local_live()`, extending the Phase-13 `research_conns`
   dict (do not rebuild the existing entries):

   ```
   Validate Research Output -> Judge Gate -> IF Needs Judge
        true  -> Build Judge Request -> Judge Call -> Apply Judge Verdict -> Merge Company
        false -> ---------------------------------------------------------> Merge Company
   ```

   `Validate Research Output`'s existing connection to `Merge Company` moves to
   `Judge Gate`. The `IF Research Needed` false lane keeps going straight to `Merge Company`
   untouched (so an unresearched company still never reaches the judge — RO-1 by topology).
   Use `_if_bool_node("IF Needs Judge", "needs_judge", …)` and `_live_http("Judge Call", …)`
   with `POST https://api.anthropic.com/v1/messages`, the same three headers as
   `Claude Web Research`, `json_body="={{ JSON.stringify($json.judge_request_body) }}"`,
   `timeout=60000`. No `retryOnFail` (Pitfall 3 — silently ignored under
   `onError: continueRegularOutput`; a failed judge call is a skip, and Task 4 proved the
   skip resolves to `needs_review`). Place `Judge Gate` / `IF Needs Judge` on the `cy - 100`
   research lane and the three judge-call nodes on `cy - 200`; positions are cosmetic.

5. **New assertions in `tests/test_judge_spec.py`** (all read the regenerated workflow JSON):
   - `test_ro2_judge_gate_cannot_see_size_conflicts` — locate the `Judge Gate` node, assert
     its `jsCode` matches neither `row\.conflicts` nor `CONFLICT_WATCH`, AND assert the graph
     ancestry: `Judge Gate` reaches `Merge Company` through the connections map, and
     `Merge Company` does not reach `Judge Gate`. Failure message must name RO-2 and explain
     that the size array is computed downstream.
   - `test_jg2_judge_call_declares_no_search_tool` — assert `web_search` does not appear in
     the `Build Judge Request` node's `jsCode` (Pitfall 5).
   - `test_ar2_judge_call_host` — the `Judge Call` node's URL host is `api.anthropic.com`
     (already allowlisted; `tests/test_architecture_guard.py` needs no change, but assert it
     here too so a host typo fails loudly in this phase's own file).

**Do NOT touch:** `n8n/code/mergeCompanies.js`, `n8n/code/webResearch.js`'s existing
functions, the contacts branch, `build_enrichment_cloud()` / `build_enrichment_local()`
(no companies branch there — Phase 13 D4 still holds), or any scoring number.

**Acceptance criteria:**

- `.venv/bin/python scripts/build_cloud_workflows.py` runs clean; a second rebuild is a
  byte-for-byte no-op (`git diff --exit-code n8n/`).
- Across all five workflow JSONs vs `HEAD`, the only file with node changes is
  `wf_enrichment_local_live.json`; within it the only **pre-existing** nodes whose `jsCode`
  changes are `Merge Company`, `Build Research Request` and `Decide Company Action` — the
  five judge nodes are additions, and the contacts branch is byte-identical.
- `git diff --exit-code n8n/code/mergeCompanies.js` is clean (D2 — the streak).
- Every `n8n/code/*.js` passes `node --check`.
- Full offline suite green: `.venv/bin/pytest -q` and `node --test tests/n8n/*.test.mjs`,
  zero regressions against the 139 / 51 baseline.

**Verify:**

```bash
.venv/bin/python scripts/build_cloud_workflows.py
git diff --exit-code n8n/                       # clean rebuild is a no-op
git diff --exit-code n8n/code/mergeCompanies.js # D2: untouched
for f in n8n/code/*.js; do node --check "$f" || exit 1; done

.venv/bin/pytest tests/test_judge_spec.py -q
.venv/bin/pytest tests/test_architecture_guard.py -q
.venv/bin/pytest -q
node --test tests/n8n/*.test.mjs

# Only local-live gains nodes; only the three named pre-existing nodes change.
.venv/bin/python - <<'PY'
import json, subprocess
FILES = ["n8n/wf_contact_ingest_cloud.json", "n8n/wf_contact_ingest_local.json",
         "n8n/wf_enrichment_cloud.json", "n8n/wf_enrichment_local.json",
         "n8n/wf_enrichment_local_live.json"]
ALLOWED = {"Merge Company", "Build Research Request", "Decide Company Action"}
def codes(text):
    return {n["name"]: n.get("parameters", {}).get("jsCode")
            for n in json.loads(text)["nodes"]}
for f in FILES:
    old = codes(subprocess.run(["git","show",f"HEAD:{f}"],capture_output=True,text=True).stdout)
    new = codes(open(f).read())
    changed = sorted(k for k in new if k in old and old[k] != new[k])
    added   = sorted(k for k in new if k not in old)
    if f.endswith("wf_enrichment_local_live.json"):
        assert set(changed) <= ALLOWED, (f, "unexpected change:", changed)
        print(f"{f}: changed={changed} added={added}")
    else:
        assert changed == [] and added == [], (f, "changed:", changed, "added:", added)
        print(f"{f}: unchanged")
print("OK — only local-live gained nodes; contacts + other workflows untouched")
PY

# RO-2 structural guard actually fires: make the Judge Gate node reference the
# downstream size array, rebuild, and prove the test goes red.
cp scripts/build_cloud_workflows.py /tmp/builder.bak
trap 'cp /tmp/builder.bak scripts/build_cloud_workflows.py && .venv/bin/python scripts/build_cloud_workflows.py' EXIT
perl -0pi -e 's/(ENRICH_JUDGE_GATE = inline\("escalation\.generated\.js", "judge\.js"\) \+ r""")/$1\n\/\/ deliberate break: const _x = row.conflicts;/' scripts/build_cloud_workflows.py
.venv/bin/python scripts/build_cloud_workflows.py
if .venv/bin/pytest tests/test_judge_spec.py -q -k ro2 2>/dev/null; then
  echo "FAIL: RO-2 structural test passed with the size array referenced in Judge Gate" >&2; exit 1
fi
echo "RO-2 structural guard fires as expected"
cp /tmp/builder.bak scripts/build_cloud_workflows.py
.venv/bin/python scripts/build_cloud_workflows.py
trap - EXIT
git diff --exit-code n8n/ scripts/build_cloud_workflows.py 2>/dev/null || \
  echo "NOTE: files still uncommitted at this point — confirm the diff is only this task's intended work"
```

**Commit:** `feat(14-05): wire the judge into the companies branch; vendor-flag inputs reach HubSpot`

---

## Phase verification

```bash
.venv/bin/pytest -q                              # expect: 139 baseline + new, 0 failed, 0 xpassed
node --test tests/n8n/*.test.mjs                 # expect: 51 baseline + new, 0 fail
.venv/bin/python scripts/build_cloud_workflows.py
git diff --exit-code n8n/                        # rebuild after a clean build is a no-op
git diff --exit-code n8n/code/mergeCompanies.js  # untouched for the third phase running
for f in n8n/code/*.js; do node --check "$f" || exit 1; done
```

Note: `node --test tests/n8n/*.test.mjs` — the bare-directory form breaks on Node v24.10.0.

## Operator step (NOT executed by the executor — costs real searches)

After Task 5 lands, an operator may re-run the live smoke to see JG-4/JG-5 against real
data. The script already takes `--dealstage` and already prints `org_type` + both veto flags
(verified this session), so no script change is needed:

```bash
set -a && source .env && set +a
.venv/bin/python scripts/smoke_closed_won_research.py --dealstage closedlost --limit 10
```

Expect: Supertech Electronics now reports `lv_is_hardware_vendor` (the field the prompt
never requested before), and the bare-homepage rows (Racing NSW, VRC, Harness Racing ACT,
The Creek Agency) are the ones JG-4 demotes to `null`. Record the result in a
`14-SMOKE-*.md` note beside the Phase-13 one. This is a paid run; it gates nothing.

## Security (spec V5)

The judge widens the attack surface in exactly one way: a scraped page's injected text now
reaches a second model call. Three existing controls hold it: the vocabulary gate
(`normalizeOrgTypeResult`, unchanged) still runs before the judge, so no adjudicated
`lv_org_type` can be an arbitrary string; the judge call declares **no** tools, so injected
text cannot cause a fetch; and JG-3's sub-80 rewrite plus the unadjudicated fail-safe mean a
confidently-wrong injected classification demotes to `null` + `needs_review` rather than
promoting. `isCitationSufficient` never fetches the cited URL (AR-2, and no SSRF surface).
The cost-DoS bound is `MAX_SONNET_VALIDATIONS_PER_RUN`, enforced in the Judge Gate node
physically upstream of the HTTP node. No new outbound host.

## Success criteria (ROADMAP Phase 14)

1. Escalation triggers match CLAUDE.md §15 / JG-1 — Task 3 (`computeEscalation`), thresholds
   single-sourced from `escalation_policy.yaml` in Task 1.
2. Judge never runs without retrieval (RO-1) — Task 3's RO-1 guard **and** Task 5's topology
   (the research-false lane bypasses the judge entirely). Size conflicts never trigger a
   model call alone (RO-2) — Task 3's arity/exclusion tests plus Task 5's structural
   assertion that the Judge Gate node runs upstream of where the size array is computed.
3. Judge confidence below 80 → `needs_review`, never promotes (JG-3) — Task 4.
4. Evidence sufficiency enforced (JG-4), case set from the Phase-13 closed-lost smoke —
   Task 2 (20 real rows, 19/20 exact, the 20th fails safe), demoting to `null` and never to
   `false`.
5. (JG-5, scope-corrected) The research prompt requests both vendor flags and the merge fold
   stops dropping them, so the INPUT reaches HubSpot — Task 5 steps 1–2. The veto itself is
   proven offline against `src/icp_scoring.py` — Task 1's
   `test_jg5_supertech_hardware_veto_independent_of_jg4`, asserting tier D with
   `lv_produces_content` both `true` and JG-4-demoted to `null`. No veto computation is added
   to production JS (Approach C).

## Out of scope — stated explicitly

- **RT-5 research caching by domain (180-day TTL)** and **PN-4 source-metadata property
  renames** — Phase 15. Every run still re-researches; metadata names stay unprefixed.
- **SJ-1..SJ-3 scheduled workflows and the §22.2 review surface** (the 9 review properties) —
  Phase 16. This phase sets `needs_review` flags; nothing yet routes them to a human.
- **The HubSpot-side veto / tier formula** (`lv_icp_fit_score`, `lv_icp_tier`,
  `lv_anti_icp_flag`, `lv_recommended_motion`) — locked out of Milestone 3 by the Approach-C
  scope fence (`5e01f3d`). `calculationFormula` remains `1 + 1`. Authoring it is not owned by
  any phase in this milestone. **Warning sign that this line was violated:** a new
  `n8n/code/icpScoring.js`, or a write path for any of those four fields.
- **The retired `claude-3-5-haiku-latest` default** in `src/classifier_haiku.py` (snapshot
  retired 2026-02-19) and `src/validator_sonnet.py`'s stale `claude-sonnet-5-latest` — both
  modules are dev-oracle-only and unreachable from n8n (grep-confirmed). One-line
  housekeeping, deliberately NOT bundled here.
- **Wiring the Milestone-1 Python cascade into production** — AR-3 forbids it;
  `classifier_haiku.py` / `validator_sonnet.py` / `merge_policy.py` stay dev-oracle-only.
  The judge is built fresh as n8n Code + HTTP nodes.
- **`web_fetch` alongside `web_search` in one turn**, and using `citations[].cited_text` as
  an evidence signal — both unverified (RESEARCH A1/A2), neither load-bearing here.
- **Contacts** — companies only, throughout.

## Output

Write `.planning/phases/14-judge-wiring/14-01-SUMMARY.md` on completion. Atomic commit per
task, `feat(14-0N): …`, each with the
`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

Do **not** run `gsd-tools query state.update-progress` in this repo — it miscounts, because
ROADMAP.md carries three concatenated milestone sections. Update `.planning/STATE.md` by
hand.
