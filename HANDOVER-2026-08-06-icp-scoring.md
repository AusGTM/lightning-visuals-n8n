# Handover — ICP scoring is not live (and why)

**Written:** 2026-08-06 · **Portal:** 22617666 `lightning-visuals` (ap1 — `app-ap1.hubspot.com`)
**Status:** investigation complete, nothing implemented, no repo files changed.
**Read this cold.** It is self-contained and does not depend on any `.claude` session data.

> **REMEDIATED — read this before acting on anything below (added 2026-08-08).** Milestone
> v0.7 closed every defect this handover reports. The scoring engine is live and correct in
> HubSpot (16/16 requirements, Phases 39–43); F1–F10 are fixed; 66 companies carry real
> scores with provenance, and the standing parity harness passes with zero real findings.
> The `lv_icp_fit_score` formula in §5/§10 below is **out of date** — it is now null-safe
> (`org_type_score + coalesce(geography_score, 0) + …`), because a bare sum blanks the entire
> score on any null term. Current state: `.planning/STATE.md`; the formula story:
> `.planning/phases/41-validation-data-import-end-to-end-proof/41-NULL-SAFE-FORMULA-FIX.md`.
> This document is kept as the diagnostic record that started the milestone, not as a
> description of the system today.

> **Staleness note (added 2026-08-06):** the investigation behind this document was conducted
> **prior to the Phase 38 quick fix** (unanswered-rows honesty fix, plugin 0.11.1 — commits
> `b8ea…`/`4c40063`/`c2f7b0d`, 2026-08-05 22:30 AEST), although the file itself was written to
> disk after those commits (08:20 the next morning). Phase 38 touched only the operator plugin's
> unanswered-row handling; it did not alter HubSpot properties, `config/`, `src/icp_scoring.py`,
> or the n8n workflows. Re-verify before acting: repo/branch state claims in §0, plugin version
> references (now 0.11.1, not 0.11.0), and that phase number **39 is still free**.
>
> **AMENDED 2026-08-06 (later the same day):** §2's Defect 1 is **superseded**. After
> `automation` scope was granted, four live HubSpot workflows were discovered (all created
> 2026-08-04, invisible to the original investigation because the flows API returned 403).
> Something *does* write the component properties — but from **different input properties than
> the pipeline writes**, and with ten validated defects. See **§10** for the full amended
> evidence. Defect 2 (missing content term) stands. §6's Phase 39 proposal now has a live
> in-place remediation candidate (fix the workflow chain) alongside the lead-scoring-tool
> rebuild; that choice belongs to remediation planning.

---

## 0. How to resume

Nothing is half-done. No branch was cut, no config edited, no HubSpot object created or
deleted. The repo is exactly as you left it (`feat/v0.6-plugin-entrypoint`, clean but for
`.DS_Store`).

Three things carry forward:

1. **A finding** — the ICP scoring implementation dated 2026-08-04 cannot produce a value.
   §2–§3.
2. **A 60-second reproduction** you can run yourself to prove it to whoever built it. §4.
3. **A proposed Phase 39** with decisions already taken. §6. Not written into `.planning/` —
   that needed your approval and did not get it.

Everything below is re-derivable from the commands given. Nothing asks you to trust a summary.

---

## 1. Completed this session — `crm.lists.read` granted

Unrelated to scoring; closes a separate blocker.

The sibling project `lv-n8n-poc` needed the HubSpot Lists API and was getting HTTP 403. The
scope `crm.lists.read` was added to `ausgtm-lightningvisuals-data`'s app manifest and the app
reinstalled. Result:

- `hs project validate` → SUCCESS
- `hs project upload` → build #6, auto-deployed
- `hs project install-app` → reinstalled ("outdated scopes" gate fired, confirming the upload
  carried the change)
- `app-install-status --json` → `isInstalledWithCurrentScopes: true`, `crm.lists.read` (id 29)
  present, 12 scope groups total

**No new access token was issued.** The existing `HUBSPOT_PRIVATE_APP_TOKEN` in this repo's
`.env` is unchanged and still valid — verified live: contacts endpoint 200, lists endpoint
went **403 → 404** (404 = scope granted, list name simply doesn't exist). No `.env` edit
needed, no outage.

**Trap worth recording:** `hs` CLI's default account is `australia-gtm` (443043042), which does
**not** contain this project. Every `hs project *` command needs `--account=22617666`, or run
`hs account create-override 22617666` once. Without it, `hs project upload` offers to *create a
duplicate app in the wrong production portal*.

---

## 2. Core finding — ⚠ Defect 1 SUPERSEDED by §10 (2026-08-06 amendment)

**0 of 712 companies have an ICP score.** Not "hasn't run yet" — the implementation
structurally cannot produce one.

A partial implementation exists and is live. Four company properties, created 2026-08-04:

```
18:40:02  org_type_score        (number)
18:46:37  annual_revenue_score  (number)
18:47:10  geography_score       (number)
18:58:35  lv_icp_fit_score      (calculated_equation, calculated: true, readOnlyValue: true)
          formula: org_type_score + geography_score + annual_revenue_score
```

Two independent defects:

**Defect 1 — nothing writes the three component properties.** Repo-wide grep for
`org_type_score|geography_score|annual_revenue_score` across `*.py *.js *.mjs *.json *.yaml
*.md` returns **zero hits**. 0/712 companies have any of them set. The calculated property
faithfully sums three nulls and yields empty.

**Defect 2 — the content term is missing from the formula.** `produces_content` (+20 in the
rubric, and the strongest validated qualifier in the ICP analysis — 38% win rate vs 17%) is
not referenced. Maximum achievable is 40 + 10 + 10 = **60**. Tier A requires **≥70**.
**No company can ever reach Tier A.**

Worked examples from the ICP validation doc, run through the deployed formula:

| Doc example | Doc score | Deployed | Shift |
|---|---|---|---|
| Harness Racing NZ (gov + content + ANZ + mid-market) | 80 → **A** | 60 | → **B** |
| Producer + content + ANZ | 50 → **B** | 30 | → **C** |
| Club + content + ANZ | 35 → **C** | 15 | → **C** (bottom edge) |

### Why it ended up this way

`config/field_policy.yaml:97`:

```yaml
# lv_icp_fit_score / lv_icp_tier: Approach C (Phase 15 criterion 4) — HubSpot owns
# these derived outputs; the pipeline never writes them.
```

Approach C assigned score derivation to HubSpot. But HubSpot's `calculation_equation` is
arithmetic over numeric properties — it **structurally cannot** map
`lv_org_type = "governing_body_league"` → 40. That enum→points translation was assigned to
neither side. It is the missing link.

`src/icp_scoring.py` implements the rubric completely and correctly — base points, graduated
deductions, three hard vetoes, tier cutoffs, confidence downgrade, veto precedence. It has
**zero production callers**; `grep -rn "compute_icp_score" --include='*.py'` hits only
`tests/`. There is no ICP scoring node in any n8n workflow either. (`Normalize + Score` is the
*provider best-of-breed candidate* scorer — `wA·A + wR·R + wG·G + wT·T` — unrelated to ICP fit.)

---

## 3. Evidence — re-runnable

Set the token first (this exact form avoids nested-quote breakage):

```bash
cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc
TOKEN=$(grep -m1 '^HUBSPOT_PRIVATE_APP_TOKEN=' .env | sed 's/^[^=]*=//' | tr -d '\r' | tr -d '"' | tr -d "'")
echo "len=${#TOKEN} prefix=${TOKEN:0:4}"   # expect len=44 prefix=pat-
```

### 3a. Population counts

```bash
python3 - "$TOKEN" <<'PY'
import sys, json, urllib.request
tok = sys.argv[1]
def post(url, body):
    r = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r))
props = ["lv_icp_fit_score","lv_icp_tier","lv_anti_icp_flag","lv_anti_icp_reason",
         "org_type_score","geography_score","annual_revenue_score",
         "lv_org_type","lv_produces_content","lv_country_region_normalized",
         "lv_revenue_band","lv_is_gambling_operator","name"]
print("populated / 712 companies:")
for p in props:
    t = post("https://api.hubapi.com/crm/v3/objects/companies/search",
        {"limit":1,"filterGroups":[{"filters":[{"propertyName":p,"operator":"HAS_PROPERTY"}]}]})["total"]
    print(f"  {p:32} {t}")
PY
```

Baseline observed 2026-08-05 **and unchanged 2026-08-06**:

```
lv_icp_fit_score               0      lv_org_type                     1
lv_icp_tier                    0      lv_produces_content             0
lv_anti_icp_flag               0      lv_country_region_normalized    1
lv_anti_icp_reason             0      lv_revenue_band                 0
org_type_score                 0      lv_is_gambling_operator         0
geography_score                0      name                          711  ← control: filters work
annual_revenue_score           0
```

The `name` row is the control. It proves the query mechanism is sound and the zeros are real.

### 3b. The formula itself

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.hubapi.com/crm/v3/properties/companies/lv_icp_fit_score" \
  | jq '{type,fieldType,calculated,calculationFormula,updatedAt,modificationMetadata}'
```

### 3c. Nothing writes the components

```bash
grep -rn "org_type_score\|geography_score\|annual_revenue_score" \
  --include='*.py' --include='*.js' --include='*.mjs' --include='*.json' \
  --include='*.yaml' --include='*.md' . | grep -v node_modules
# expect: no output
```

---

## 4. Exercise the scoring workflow

This is the part to run. Two steps, ~60 seconds, uses a throwaway record so nothing real is
touched. It settles "already implemented" vs "not connected" without argument.

```bash
cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc
TOKEN=$(grep -m1 '^HUBSPOT_PRIVATE_APP_TOKEN=' .env | sed 's/^[^=]*=//' | tr -d '\r' | tr -d '"' | tr -d "'")

# --- create a disposable company -------------------------------------------
CO=$(curl -s -X POST "https://api.hubapi.com/crm/v3/objects/companies" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"properties":{"name":"ZZ-SCORING-TEST-DELETE-ME"}}' | jq -r .id)
echo "scratch company: $CO"

# --- STEP 1: set the four inputs the RUBRIC says should score 80 ------------
curl -s -X PATCH "https://api.hubapi.com/crm/v3/objects/companies/$CO" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"properties":{
        "lv_org_type":"governing_body_league",
        "lv_produces_content":"true",
        "lv_country_region_normalized":"AU",
        "lv_revenue_band":"50-500M"}}' > /dev/null

curl -s "https://api.hubapi.com/crm/v3/objects/companies/$CO?properties=lv_icp_fit_score,lv_icp_tier" \
  -H "Authorization: Bearer $TOKEN" | jq '.properties | {step:"1 — rubric inputs only", lv_icp_fit_score, lv_icp_tier}'

# --- STEP 2: set what the FORMULA actually reads ----------------------------
curl -s -X PATCH "https://api.hubapi.com/crm/v3/objects/companies/$CO" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"properties":{"org_type_score":"40","geography_score":"10","annual_revenue_score":"10"}}' > /dev/null

curl -s "https://api.hubapi.com/crm/v3/objects/companies/$CO?properties=lv_icp_fit_score" \
  -H "Authorization: Bearer $TOKEN" | jq '.properties | {step:"2 — component scores set", lv_icp_fit_score}'

# --- clean up ---------------------------------------------------------------
curl -s -X DELETE "https://api.hubapi.com/crm/v3/objects/companies/$CO" \
  -H "Authorization: Bearer $TOKEN" -w 'delete: %{http_code}\n'
```

### What you should see, and what each step proves

| Step | Expected | Proves |
|---|---|---|
| 1 | `lv_icp_fit_score` **empty**, `lv_icp_tier` null | A textbook Tier-A company with every rubric input set correctly scores **nothing**. The formula reads no property the pipeline writes. No run, schedule, or backfill will ever change this. |
| 2 | `lv_icp_fit_score` = **60** | The calculated property works. The arithmetic is wrong — 60, not the rubric's 80. The missing 20 is `produces_content`. Tier A (≥70) is unreachable. |

Step 1 is the one to show the team. It is the difference between *"scoring hasn't been run
yet"* and *"scoring is not connected to anything."*

`lv_icp_fit_score` is `readOnlyValue: true` (it is calculated), so you cannot write it
directly — the PATCH in step 2 targets its inputs. That read-only flag is also why any future
pipeline-writes-the-score design requires converting the property first.

### Exercising the enrichment pipeline (the part that *is* live)

Separate from scoring, and genuinely working: `POST /webhook/hubspot/enrichment/event`, header
auth `X-Enrichment-Secret` (see `n8n/README.md:315`). Caveats before firing:

- It writes ICP **inputs** only, never scores — Approach C by design.
- Write gates ship disarmed at rest, so an unarmed run proves reachability, not writeback.
- 5 workflows are deployed on n8n Cloud; SJ-1/2/3 schedules ship `active: false`.

---

## 5. Decisions taken this session

Both were explicit operator decisions, not defaults.

**1. HubSpot stays the scoring engine, via the lead scoring tool — no workflows.**

Legacy `calculation_score` properties are **sunset** (stopped updating 2025-08-31, removed
2026-01-10), so the lead scoring tool is the only supported native mechanism. It fits well:
criteria score enum values *individually* (so `lv_org_type → 40/20/20/5/5` is one rule),
supports negative points for the graduated deductions, auto-generates an A/B/C grade property,
and its *engagement score* half would deliver the intent/pixel block the ICP doc specs but
nothing has built. Requires Professional of any hub — **Sales Hub Pro qualifies. Data Hub Pro
is not required.**

Rejected alternative: custom equation properties. Viable (string output and `if()` conditionals
are both supported, 70-open-paren ceiling) and would keep the rubric generated from
`config/icp_scoring.yaml` in git — but not RevOps-editable, and formula-fragile.

**2. Hard vetoes stay pipeline-owned.**

n8n keeps writing `lv_anti_icp_flag` / `lv_anti_icp_reason`; HubSpot scores only additive
points. Tier D becomes a view filter on the flag. This preserves the
veto-vs-graduated-deduction distinction the ICP analysis worked hardest to establish — hardware
vendor is a veto, gambling operator is a *targetable* deduction — and keeps the reason string
for reps.

### The rubric config is already correct

`config/icp_scoring.yaml` matches the ICP validation doc almost exactly (org-type points,
content +20, ANZ +10, revenue bands, decay −5/−15/−30/−50, gambling −20, three hard vetoes,
tier cutoffs A≥70 / B 40–69 / C 15–39 / D veto). It adds `broadcaster: 20` and `regulator: 5`,
the latter answering the doc's own QRIC caveat.

**Every HubSpot enum option value already matches the config exactly** — verified for
`lv_org_type`, `lv_country_region_normalized`, `lv_revenue_band`. No mapping layer is needed
when transcribing criteria into the UI.

Absent from both: the intent/pixel scoring block (+3/+7/+5/+10). No property, no config entry,
no node.

---

## 6. Proposed Phase 39 — not written, needs approval

**Phase number:** 39. Phase 38 was consumed 2026-08-05 (*"unanswered rows honesty fix, 0.11.1
cut"*); 36, 37 and 38 all sealed that day. **Re-confirm 39 is free before writing** — the
sequence moves fast.

**Workstream:** `milestone` (backend — phases 1–10, 20–22). Not `plugin-entrypoint`, whose own
Notes for Planning state *"Backend directories (`n8n/`, `config/`, `scripts/`, and the
enrichment modules in `src/`) are not this milestone's to edit"* and list company-object work
as out of scope. Opens **Milestone 6 / v0.7**.

**This is a promotion, not a new orphan.** `REQUIREMENTS.md` → *Future Requirements (deferred
to v0.7)* already carries *"HubSpot-side ICP formula — replace the `1 + 1` calculated-property
placeholder (downstream-owner decision)"*. Note the placeholder has since changed from `1 + 1`
to the three-term sum — correct that line in place.

### Three files to write, all under `.planning/workstreams/milestone/`

**`REQUIREMENTS.md`** — append a `## v0.7 Requirements` section. Move (do not copy) the
deferred items up. Use this workstream's `REQ-kebab` convention, **not** plugin-entrypoint's
`INGEST-02` style:

- `REQ-hubspot-native-fit-score` — company fit score configured, criteria transcribed from
  `config/icp_scoring.yaml`, grades A ≥ 70 / B 40–69 / C < 40
- `REQ-veto-ownership` — `lv_anti_icp_flag` / `lv_anti_icp_reason` verified to actually emit
- `REQ-retire-calc-placeholder` — archive `lv_icp_fit_score`, the three `*_score` orphans, and
  `lv_icp_tier`; reconcile `config/hubspot_properties.yaml`
- `REQ-scoring-input-coverage` — inputs populated beyond 1/712
- `REQ-scoring-parity-guard` — `compute_icp_score` asserted against HubSpot's live score
- `REQ-signoff-gate` — already in the deferred list; JTBD 2 rubric weights need the business
  owner. **A gate on Phase 39, not work inside it.**

**`ROADMAP.md`** — append a milestone block in the existing stacked shape (`## Overview` →
`## Phases` → `## Phase Details` → `## Milestone 6 Progress`). Phase Details entry:

> ### Phase 39: HubSpot-Native ICP Scoring
>
> **Goal**: The ICP rubric executes natively in HubSpot's lead scoring tool with no workflows
> and no pipeline scoring code — a governing body producing content in ANZ at mid-market
> revenue scores 80 and grades A, which the 2026-08-04 calculated-property implementation
> could never do.
> **Depends on**: Phase 22 (armed enrichment proven), REQ-signoff-gate (rubric weights)
> **Requirements**: REQ-hubspot-native-fit-score, REQ-veto-ownership,
> REQ-retire-calc-placeholder, REQ-scoring-input-coverage, REQ-scoring-parity-guard
>
> **Success Criteria** (what must be TRUE):
> 1. A company with `lv_org_type=governing_body_league`, `lv_produces_content=true`,
>    `lv_country_region_normalized=AU`, `lv_revenue_band=50-500M` scores **80** and grades
>    **A**. The retired implementation returns empty for this exact record today, and 60 once
>    its component properties are hand-populated (see §4).
> 2. Scores recalculate on input change **without any workflow**. Undocumented by HubSpot;
>    prove empirically, do not assume.
> 3. Negative criteria fire: gambling −20 and revenue decay −5/−15/−30/−50, without setting
>    `lv_anti_icp_flag`. Graduated deductions never veto.
> 4. `lv_anti_icp_flag` / `lv_anti_icp_reason` emit from the pipeline for a vetoed record, and
>    that record drops out of working views regardless of score. Both are 0/712 today despite
>    being classed `veto_output` + `recompute_always`.
> 5. Retired artifacts archived, not deleted, with `snapshot_hubspot_schema.py` run first;
>    `config/hubspot_properties.yaml` reconciles clean.
> 6. A parity test recomputes expected scores via `compute_icp_score` and asserts them against
>    HubSpot's live score for a sample — catching UI drift.
> 7. Input coverage materially above 1/712, and the sample in (6) drawn from real records.
>
> **Plans**: TBD

Add the one-liner to that milestone's `## Phases` list and a row to the progress table.

**`phases/39-hubspot-native-icp-scoring/39-CONTEXT.md`** — the handoff doc, shaped like
`37-CONTEXT.md` (*"Written for a context clear. Read this first; it is self-contained."*).
Sections: the problem (with §2–§4 evidence inlined) · the decision · what exists, reuse don't
reinvent (`config/icp_scoring.yaml`, `src/icp_scoring.py` as parity oracle,
`scripts/snapshot_hubspot_schema.py`, `scripts/sync_hubspot_properties.py`, the `veto_output`
policy class) · the criteria table ready to type into the UI · where the work happens · the
coverage trap · open risks.

### Criteria table, ready to transcribe

```
Fit score: Company

Positive
  lv_org_type is any of  (scored INDIVIDUALLY)
    governing_body_league  +40
    content_producer       +20
    broadcaster            +20
    individual_club_team    +5
    regulator               +5
  lv_produces_content = true                       +20
  lv_country_region_normalized is any of AU,NZ,ANZ +10
  lv_revenue_band is any of 5-50M, 50-500M         +10

Negative
  lv_is_gambling_operator = true   -20
  lv_revenue_band 500-750M          -5
  lv_revenue_band 750M-1B          -15
  lv_revenue_band 1B-1.2B          -30
  lv_revenue_band 1.2B+            -50

Grades: A >= 70 · B 40-69 · C < 40
No veto criteria — vetoes are lv_anti_icp_flag.
```

---

## 7. The two things not to bury

**Configuration is ~1 hour. Coverage is the work.** Inputs are populated on **1 of 712**
companies. Scores will compute correctly and be near-universally zero until enrichment runs at
volume. Cheapest first move: the ICP validation analysis web-enriched **66 companies** (49
high-confidence) and **that research never landed in the CRM** — only Melbourne Racing Club has
`lv_org_type`. Importing those 66 gives scoreable population for zero provider spend, and
enough records to validate end-to-end before a full backfill.

**The review queue will swamp a naive backfill.** `src/icp_scoring.py` drops confidence to 55
and routes to review whenever `org_type` is unknown *or* `produces_content` is null —
**currently 711 of 712 companies**. The queue holds one record today (Melbourne Racing Club,
`lv_enrichment_status: needs_review`) and has never run at volume. Decide the review policy
before arming schedules, not after.

---

## 8. Open items

- **Blocking:** confirm company fit scores are available on **Sales Hub Pro**. Contact-based
  scores are Marketing Hub only; company support must be verified in-portal (Settings →
  Account & Billing → Products & Add-ons, then the lead scoring tool). If unavailable, fall
  back to custom equation properties. Everything else in Phase 39 depends on this.
- **Branch:** repo is on `feat/v0.6-plugin-entrypoint`; Phase 39 is v0.7 backend work. Fresh
  branch or not — undecided.
- **Undocumented:** HubSpot's fit-score recalculation cadence. Scores may lag enrichment writes.
- **Rubric drift risk:** moving the rubric into the HubSpot UI removes it from version control.
  `REQ-scoring-parity-guard` is the mitigation and is not optional garnish.
- **Unverified:** whether `lv_anti_icp_flag` genuinely emits from `src/merge_policy.py`. It is
  declared `veto_output` + `recompute_always` in `config/field_policy.yaml` yet is 0/712. It is
  Tier D's only source under the chosen design.
- **Which portal did the team build in?** All probes here target 22617666, and the four
  property timestamps match that portal exactly — but if part of the work went to a sandbox,
  that would explain a genuine disagreement rather than a broken build.

## 9. Gotchas

- `hs` CLI defaults to the **wrong account**. Always `--account=22617666`.
- Portal is **ap1** — URLs are `app-ap1.hubspot.com`, not `app.hubspot.com`.
- `lv_icp_scored_at` appears in `wf_scheduled_maintenance_cloud.json` but **does not exist** in
  HubSpot (404). Harmless — it is only named in a sticky note stating SJ predicates never
  reference it.
- `lv_icp_tier`'s dropdown has only **A/B/C/D**, but `src/icp_scoring.py` can emit
  `"Needs Review"` and `"Unscored"`. Under the Phase 39 design the property is retired, so this
  stops mattering — but it would have been a live enum-refusal defect under the old one.
- The `.env` token is a 44-char `pat-` private app token. Never echo it; the commands above
  print only length and prefix.

---

## 10. Amendment 2026-08-06 — the workflows exist, and here is exactly how they are broken

**Method:** `automation` scope granted to the private app; four flows read via
`GET /automation/v4/flows/{id}`. Every behavioural claim below was then validated live on
disposable companies (`ZZ-SCORING-TEST-DELETE-ME-*`, created and deleted the same run; zero
real records touched; all deletes returned 204). Baseline §3a re-run first — **unchanged**,
still 0/712 scored, 1/712 inputs.

### 10.1 What actually exists (supersedes §2 Defect 1)

Four enabled company workflows, all created **2026-08-04** (same day as the four properties —
one build session). The original investigation could not see them: the flows API returned 403
without the `automation` scope, and repo grep finds nothing because workflows live only in
HubSpot.

| Flow ID | Name | Trigger (property-change event) | Writes |
|---|---|---|---|
| 4626124224 | Update Score Based on Org Type | `lv_org_type` known | `org_type_score` |
| 4626722240 | Geography Score | **`country`** known | `geography_score`, and `lv_anti_icp_flag` on its default branch |
| 4626722237 | Annual Revenue Score | **`annualrevenue`** known | `annual_revenue_score` |
| 4625147345 | WF1 Set ICP Tier based on ICP Score | `lv_icp_fit_score` known | `lv_icp_tier` (checks `lv_anti_icp_flag` first → D) |

Plus: the three `*_score` properties carry a **property-level default of 0** stamped on newly
created companies only (`sourceType: PROPERTY_DEFAULT_VALUE` in history). All four flows have
`shouldReEnroll: true` and re-fire on later changes. Observed latency: mappers 4–25 s,
calculated sum ~2 s, tier ~3 s after score change.

**The chain genuinely runs.** A company created today with `lv_org_type=governing_body_league`,
`country=Australia`, `annualrevenue=65000000` reaches `lv_icp_fit_score=60`, `lv_icp_tier=B`
within ~30 s, fully automatically. The §4 step-1 experiment showed "empty" only because the
712 existing companies predate the defaults and nothing has re-triggered them.

### 10.2 Validated defects (F1–F10)

Each row: definition evidence (flow JSON) + live validation on a scratch company.

| # | Defect | Rubric says | Live behaviour (validated) |
|---|---|---|---|
| F1 | **Content term absent everywhere** — no component property, no workflow, no formula term | `produces_content` +20; also a no-content **hard veto** | Setting `lv_produces_content=true` moves nothing. Max achievable = 40+10+10 = **60** → textbook Tier-A record grades **B**. Tier A (≥70) unreachable |
| F2 | **Geography reads native `country` (free text), not `lv_country_region_normalized`** | Pipeline canonical is `lv_country_region_normalized` | `lv_country_region_normalized=AU` never scores (40 s poll); `country=Australia` scores 10 in ≤25 s. **Enrichment writes can never trigger geography scoring** |
| F3 | **Revenue reads native `annualrevenue`, not `lv_revenue_band`** | Pipeline canonical is `lv_revenue_band`; `annualrevenue` is on the MVP **never-write** list (§29) | `lv_revenue_band=50-500M` never scores; `annualrevenue=65000000` scores 10. **Enrichment can never drive the revenue component under current write policy** |
| F4 | **Non-ANZ veto match list misses `AU`** — values are `[Australia, ANZ, New Zealand, NZ, Aus]` | AU is ICP-core | Clean company with `country=AU` → **`lv_anti_icp_flag=true`, geography_score=0**. An Australian company is vetoed by spelling |
| F5 | **Veto path writes no `geography_score`** — default branch sets only the flag | — | Flip AU→US: flag=true but geography_score **stays 10** (stale points persist) |
| F6 | **Veto is a one-way latch** — nothing ever writes `lv_anti_icp_flag=false`; `lv_anti_icp_reason` never written by anything | Pipeline owns veto + reason | Country corrected US→Australia: geography re-scores 10 but **flag stays true, tier stays D at score 60**. `lv_anti_icp_reason` was None in every run (and is 0/712) |
| F7 | **Tier recomputes only on score change** — trigger is `lv_icp_fit_score` known | Veto should take effect when it fires | US flip set flag=true but **tier stayed B** (score unchanged); only a later org_type poke flipped it to D. Wrong tier persists until the score next moves |
| F8 | **Score <15 → Tier D** (WF1's else branch), no veto required | D = hard-veto only; low score = C floor / Unscored | Score 10 → D, score −20 → D (boundary probes). Conflates "low fit" with "disqualify" |
| F9 | **Gambling wired as org-type points, not a deduction** — `lv_org_type=gambling_operator` → `org_type_score=-20`; **no flow references `lv_is_gambling_operator`** | org points 0 + separate −20 via `lv_is_gambling_operator`; explicitly *targetable*, never a veto | Enum sweep confirmed −20. A broadcaster that also operates gambling gets 20 (rubric: 0). A pure gambling operator lands −20 → Tier D via F8, i.e. **treated as a veto**, contradicting §5 decision 2 |
| F10 | **Revenue boundaries overlap** — inclusive `IS_BETWEEN` branches, first match wins; **`regulator` → 0** (config says 5); **hardware-vendor hard veto absent** (0 points, no flag) | −5 / −15 / −30 / −50 decay; regulator 5; hardware veto | Exactly 750,000,000 → **−5** (rubric −15) on a clean record. By the same branch order: 500M→+10 (not −5), 1B→−15 (not −30), 1.2B→−30 (not −50). Regulator → 0 (enum sweep). Hardware vendor → 0 points, no veto, D only coincidentally |

Cross-cutting: **backfill gap** — defaults apply to new records only; the 712 existing
companies have no components, so their score is null and WF1 never fires. No mechanism
re-enrolls them. Coverage (1/712 inputs) still gates everything, as §7 said.

### 10.3 What this means for remediation (input to Phase 39 planning — no action taken)

The scoring engine stays in HubSpot (operator decision, reaffirmed 2026-08-06). Two paths now
exist and the choice is a planning decision, not a foregone conclusion:

1. **Fix the existing workflow chain in place** — now viable, was thought nonexistent.
   Smallest set: add a `produces_content_score` component + formula term (F1); retarget
   triggers to the `lv_*` canonical inputs (F2, F3); rebuild the veto as symmetric set/clear
   with reason strings (F4–F6); re-order/exclusive-bound the revenue branches (F10); move
   gambling to `lv_is_gambling_operator` (F9); fix regulator points and add missing vetoes
   (F8, F10); pick a backfill trigger for the 712.
2. **Lead scoring tool rebuild** (§5 decision 1) — replaces the chain wholesale; §8's
   Sales-Hub-Pro availability check is still the blocking open item.

Either way `REQ-scoring-parity-guard` (§6) is proven necessary: every defect above is
invisible in the HubSpot UI and was found only by asserting live behaviour against
`src/icp_scoring.py`'s rubric. The worked examples in §2's table remain the acceptance
fixtures; add the F4/F7/F9/F10 scratch-company scenarios from this section as regression
cases.

Flow definitions archived for the planning phase at
`scratchpad/flows_full.json` (session scratch — re-fetch with
`GET /automation/v4/flows/{4625147345,4626124224,4626722237,4626722240}` if gone).
