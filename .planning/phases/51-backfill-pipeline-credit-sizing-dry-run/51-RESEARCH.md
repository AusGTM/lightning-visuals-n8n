# Phase 51: Backfill Pipeline, Credit Sizing & Dry Run - Research

**Researched:** 2026-08-19
**Domain:** Python-only (zero n8n) HubSpot company backfill: population sizing, ZoomInfo GTM
company enrichment, revenue-unit conversion, and a pre-registered scoring dry run reusing
`src/icp_scoring.py`.
**Confidence:** HIGH (every claim below is grep/Read-verified against this repo's own source this
session; no external library research was needed — this phase composes existing in-repo pieces)

## Summary

This phase has almost no new *concepts* to research — the domain is entirely internal: HubSpot
Search API pagination limits, a ZoomInfo GTM contract that's already been reverse-engineered twice
in this repo (once in Python via `check_provider_credits.py`, once in JS via
`build_cloud_workflows.py`/`normalizeProviders.js`), and `src/icp_scoring.py`'s existing interface.
The work is almost entirely **reuse-by-import**, not new design.

The single biggest risk the phase description asked me to check — "does `src/icp_scoring.py` emit
the six numeric properties by name, or does only the n8n node do that translation" — resolves
favorably: `scripts/backfill_seed_company_scores.py::compute_components()` **already exists** and
is a pure, side-effect-free Python function that turns `compute_icp_score()`'s breakdown into the
exact five named numeric properties (`org_type_score`, `geography_score`, `annual_revenue_score`,
`produces_content_score`, `gambling_score`). `src/icp_scoring.py::anti_icp_flag_properties()`
supplies the sixth (`lv_anti_icp_flag_num`) directly. **Nothing needs to be reimplemented — it
needs to be imported.**

Two real, code-verified landmines surfaced that are *not* in the phase description and must be
designed around, not discovered live:

1. **The live `lv_icp_tier_derived` calculation has no "Needs Review" branch.** Its
   `calculationFormula` (`config/hubspot_properties.yaml:426`) is a four-way `if/elseif` over
   veto/A/B/C/else-"Unscored" — nothing else. `compute_icp_score()`'s Python-only "Needs Review"
   tier (fired when `org_type=="unknown"` or `produces_content is None`, confidence dropped to 55)
   **can never appear as a live value** and must not be used as the pre-registered prediction
   as-is, or every low-confidence record will show a false mismatch. The prediction must be
   derived from `result.score` + `result.anti_icp_flag` directly, replicating the four-branch
   formula, not from `result.tier`.
2. **`src/normalizer.py::normalize_country_region()` is unsafe to feed a ZoomInfo blank country
   into `compute_icp_score`.** It returns the literal string `"Unknown"` for a blank/falsy input
   (`src/normalizer.py:80-88`) — a non-empty string that isn't in `["AU","NZ","ANZ"]`, which
   `compute_icp_score`'s region-key logic (`src/icp_scoring.py:98-101`) treats as `"non_anz"` and
   fires the hard veto. This is **the exact bug** icp_scoring.py's own comment documents fixing for
   a *missing* key (17 live companies wrongly Tier-D'd on blank region) — but that fix only guards
   `None`/absent, not the string `"Unknown"`. The JS engine already avoids this: its
   `normalizeCountryRegion` (`n8n/code/normalizeProviders.js:96-102`) returns `null` for blank, not
   `"Unknown"`. Any new Python ZoomInfo-country mapper for this phase must mirror the JS contract
   (return `None`/omit-key for blank, never write the literal string `"Unknown"`).

**Primary recommendation:** Build the dry-run driver as a new, small Python script under
`scripts/` that imports `src.icp_scoring.compute_icp_score`, `src.icp_scoring.anti_icp_flag_properties`,
and `scripts.backfill_seed_company_scores.compute_components` directly (never re-derives points),
adds one new small module for the ZoomInfo GTM `companies/enrich` HTTP call (this does not exist in
Python anywhere in the repo today — only as generated JS inside `build_cloud_workflows.py`), and
one new small pure function for THOUSANDS→dollars + revenue-range-string handling (porting
`n8n/code/normalizeProviders.js:37-72` and `:404-415`, which is the *already-fixed* reference
implementation of FILL-03's landmine — just not in Python yet).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Population count / sample selection | HubSpot Search API (read) | Python script | `search_records()`/`total` field is the source of truth; no app-side cache |
| ZoomInfo credit balance + cap | ZoomInfo GTM usage API (read) | Python script | live balance, converted to a record cap by a Python constant |
| ZoomInfo company match/enrich | ZoomInfo GTM `companies/enrich` API | Python script (new) | no Python client exists yet; must be written this phase |
| Revenue unit conversion + banding | Python script (new) | `src/normalizer.py` (existing dollar-banding logic, reused for the second half only) | THOUSANDS conversion must happen before existing banding logic |
| Six numeric scores + predicted tier | `src/icp_scoring.py` (existing, imported) | `scripts/backfill_seed_company_scores.py::compute_components` (existing, imported) | the "never reimplement" constraint from the phase goal |
| Gap-fill research (`lv_org_type` etc.) | `src/web_research.py::claude_web_research()` (existing, imported) | — | native Anthropic web_search tool, no separate endpoint |
| Dry-run artifact / PATCH-payload printing | Python script (new) | `src/hubspot_client.py::patch_record`/`batch_update_companies` (dry_run=True path, existing) | zero writes — reuse the existing dry_run print path, never call with `dry_run=False` |
| Before-snapshot of the 66 scored companies | Python script (new, small) | `scripts/rescore_population.py::select_scored_population` (existing, imported) + `src/hubspot_client.get_record` | reuse the exact `HAS_PROPERTY(lv_icp_fit_score)` population definition already used by 3 other scripts |

## Standard Stack

No new library is required. Every dependency this phase needs is already in `requirements.txt`
(`requests`, `pydantic`, `PyYAML`, `python-dotenv`, `anthropic`) — [VERIFIED: requirements.txt
(Read, full file)]. There is no Package Legitimacy Audit section below because no new package is
being installed.

### Reusable in-repo modules (the real "stack" for this phase)

| Module / function | File:line | What it gives this phase |
|---|---|---|
| `compute_icp_score(record, candidate_patch, cfg=None) -> ICPScoreResult` | `src/icp_scoring.py:47` | The sole oracle. Returns `.score`, `.tier`, `.anti_icp_flag`, `.anti_icp_reason`, `.breakdown` (components + hard_vetoes + graduated_deductions) [VERIFIED: src/icp_scoring.py:47-172, full function read] |
| `anti_icp_flag_properties(flag: bool) -> dict` | `src/icp_scoring.py:36-44` | Returns `{"lv_anti_icp_flag": "true"/"false", "lv_anti_icp_flag_num": "1"/"0"}` — string literals, matching every other PATCH body in the repo [VERIFIED: src/icp_scoring.py:36-44, quoted below] |
| `compute_components(props: dict) -> dict` | `scripts/backfill_seed_company_scores.py:112-136` | Returns the five numeric properties by their EXACT live names: `{"org_type_score":.., "geography_score":.., "annual_revenue_score":.., "produces_content_score":.., "gambling_score":..}`, computed via `compute_icp_score()`'s own breakdown — "never a second, hand-copied point table" per its own docstring [VERIFIED: full function read] |
| `select_scored_population() -> list[str]` | `scripts/rescore_population.py:108-135` | `HAS_PROPERTY(lv_icp_fit_score)` search, sorted ids, **refuses (raises) rather than silently truncates** if HubSpot's `total` exceeds what the single page returned — the exact population this phase's before-snapshot (criterion 6) needs, reused verbatim |
| `_count_never_scored_companies() -> int` | `scripts/check_tier_derived_parity.py:596-604` | Already issues `[{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}]` with `limit=1` and reads `result["total"]` — this is criterion 1's exact filter, already live-proven, and sidesteps pagination entirely because it only needs a count |
| `search_records`, `get_record`, `batch_update_companies` (dry_run only), `patch_record` | `src/hubspot_client.py:16-129` | The only HTTP surface this phase should touch for HubSpot. `batch_update_companies` raises (never truncates) above 100 entries — caller must chunk |
| `claude_web_research(record) -> ProviderResult` | `src/web_research.py` | Live Claude web-research adapter for the gap-fill fields (`lv_org_type`, `lv_produces_content`, hardware/gambling), native `web_search` tool, no separate endpoint |
| `PROVIDER_REGISTRY["zoominfo"]["credit"]` + `_mint_zoominfo_token()` + `_extract_zoominfo()` | `scripts/provider_registry.py:30-38`, `scripts/check_provider_credits.py:88-179` | The live ZoomInfo credit-balance contract: `GET https://api.zoominfo.com/gtm/data/v1/users/usage`, `Accept: application/vnd.api+json`, balance at `data[0].attributes.usage[limitType=uniqueIdLimit].usageRemaining`. Token minted via `POST https://api.zoominfo.com/gtm/oauth/v1/token`, Basic auth (client_id, client_secret), `grant_type=client_credentials` only (a `scope` param 400s) |
| `zoominfo_per_match` cost estimate | `scripts/enrichment_cost_ledger.py:106-111` | `1.08 credits/match` — [CITED: inferred, pre-v3 measurement, carried forward per that file's own confidence note] — use for deriving the cap, but flag it in the artifact as an estimate, not a live-measured constant for the `companies/enrich` endpoint specifically (see Open Questions) |
| `ANTHROPIC_PER_RECORD_ESTIMATE_USD = 0.0686` | `scripts/remediate_veto_companies.py:655` | Measured canary actual for Claude research cost per record — reusable as the research-cost estimate baseline, with the caveat noted in Open Questions (measured under the n8n Haiku+Sonnet pipeline, not a bare `claude_web_research()` call) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New Python `compute_components`-equivalent | Copy the six-number logic inline in the new dry-run script | Forbidden by the phase goal ("never a reimplementation") and by the Phase 46 parity rule this repo already enforces for the JS side — import, don't copy |
| New Python ZoomInfo GTM client | Reuse `scripts/dryrun_batch.mjs` (Node, calls `n8n/code/normalizeProviders.js` directly, zero n8n executions) | Contacts-only harness, and CLAUDE.md's contract requires `src/icp_scoring.py` (Python) as the sole scoring oracle — a Node dry run would need a second cross-language bridge to get a tier prediction. Not worth it for one small HTTP client function; port the JS ZoomInfo call to Python instead |
| Hand-rolled pagination for the full 646-record population | HubSpot's `total`-only `limit=1` trick (`check_tier_derived_parity.py:590-604`) for the **count**; a single bounded page (`limit<=100`) for the **sample** | Full `after`-cursor pagination across ~646 records is only needed for Phase 52's actual write population, not Phase 51's dry run over a *sample*. Building it now is out of this phase's scope — flag it as a Phase 52 prerequisite gap instead (see Common Pitfalls) |

## Package Legitimacy Audit

Not applicable — no new external package is installed by this phase (`requirements.txt` is
unchanged; every function reused above is already an in-repo import). [VERIFIED: requirements.txt,
full file read this session]

## Architecture Patterns

### System Architecture Diagram

```
NOT_HAS_PROPERTY(lv_icp_fit_score) search (limit=1, total-only)
        |
        v
  [population count] --commit--> artifact (criterion 1)
        |
ZoomInfo GTM usage endpoint (credit balance)          Anthropic per-record cost estimate
        |                                                        |
        v                                                        v
   [credit cap = floor(balance / credits_per_match)]  ----+----> artifact (criterion 2)
        |                                                 |
        v                                                 |
  bounded single-page sample search (limit<=N<=100,       |
  same NOT_HAS_PROPERTY filter, ids only)                 |
        |                                                 |
        v                                                 |
  per-record: ZoomInfo companies/enrich (POST, live) ------+
        |                                       \
   matched?                                      no --> skip log entry, reason recorded,
        | yes                                           NO payload emitted (criterion 4)
        v
  revenue THOUSANDS -> dollars -> band (new pinned function, criterion 3)
  country ZoomInfo raw -> normalized region (None-safe, NOT "Unknown")
        |
        v
  gap-fill fields still missing (org_type / produces_content / hardware / gambling)?
        | yes                                    | no
        v                                        |
  claude_web_research() (live, gated by sample <----+
  size / MAX_WEB_RESEARCH_PER_RUN)
        |
        v
  candidate_patch = {lv_org_type, lv_produces_content, lv_country_region_normalized,
                      lv_revenue_band, lv_is_gambling_operator, lv_is_hardware_vendor}
        |
        v
  compute_icp_score(record, candidate_patch)  -->  compute_components(candidate_patch)
        |                                                |
        v                                                v
  predicted_tier = veto? "D" : score>=70 "A" : >=40 "B" : >=15 "C" : "Unscored"
  (NOT result.tier verbatim -- "Needs Review" never appears live, see Pitfall 1)
        |
        v
  exact PATCH payload (lv_* inputs + 6 numeric props) + predicted_tier
        |
        v
  committed dry-run artifact (criterion 5) --- zero HubSpot writes anywhere in this diagram
```

### Recommended Project Structure

No new top-level directory needed. Follow the existing flat `scripts/` convention:

```
scripts/
├── backfill_seed_company_scores.py   # REUSE: compute_components() imported, not copied
├── rescore_population.py             # REUSE: select_scored_population() imported, not copied
├── check_tier_derived_parity.py      # REUSE: _count_never_scored_companies() pattern (import or mirror)
├── check_provider_credits.py         # REUSE: zoominfo credit check (import _check_zoominfo / _mint_zoominfo_token)
├── zoominfo_company_client.py        # NEW: the companies/enrich Python client (does not exist yet)
├── backfill_dry_run.py               # NEW: this phase's driver — read-only, zero writes
src/
├── icp_scoring.py                    # REUSE: compute_icp_score, anti_icp_flag_properties (unchanged)
├── normalizer.py                     # PARTIAL REUSE: normalize_revenue_band (dollars->band) reusable;
│                                      #   normalize_country_region NOT reusable as-is (see Pitfall 2)
tests/
├── test_zoominfo_company_client.py   # NEW: pins THOUSANDS->dollars conversion (FILL-03), mirrors the
│                                      #   existing JS pin at tests/n8n/enrichment.test.mjs:448
├── test_backfill_dry_run.py          # NEW: pins the predicted-tier derivation (score+veto, not .tier),
│                                      #   the skip-log contract, and the payload key-set contract
```

### Pattern 1: "refuse rather than truncate" population guard

**What:** Every existing population-selection function in this repo compares HubSpot's reported
`total` against what a single page actually returned, and raises/refuses rather than silently
operating on a partial set.
**When to use:** Any HubSpot search this phase issues that could plausibly exceed 100 results.
**Example (existing, verbatim contract to mirror):**
```python
# Source: scripts/rescore_population.py:120-135 (read this session)
result = search_records(
    "companies",
    [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}],
    ["lv_icp_fit_score"],
    limit=POPULATION_SEARCH_LIMIT,
)
ids = sorted(r["id"] for r in result.get("results", []))
total = result.get("total")
if total is not None and total > len(ids):
    raise RuntimeError(
        f"REFUSED: the scored population is {total} records but this search returned "
        f"only {len(ids)} (page limit {POPULATION_SEARCH_LIMIT}). ... "
        "Add pagination to select_scored_population() before re-running."
    )
```
This is the ~646-population's exact problem for Phase 52 (not Phase 51, which only needs a bounded
sample) — see Common Pitfalls.

### Pattern 2: two-key arm gate, but Phase 51 needs neither key set

**What:** Every writing script in this repo (`backfill_seed_company_scores.py`,
`enrich_coverage_companies.py`) gates live writes behind `DRY_RUN=false` AND a phase-scoped env
flag (e.g. `ALLOW_SCORE_BACKFILL=true`), checked in a `_writes_allowed()`-style function, with the
default (`DRY_RUN` unset or `true`) always short-circuiting to a printed payload and zero HTTP
calls.
**When to use:** N/A for writes in this phase (SAFE-01/criterion 7 forbid any write in Phase 51) —
but the SAME idiom (`dry_run=True` default, explicit print, no network call) is exactly
`patch_record`/`batch_update_companies`'s existing behavior in `src/hubspot_client.py:24-42,
88-116`, and this phase's driver should call those with `dry_run` hard-coded `True` (not
env-driven) so there is no accidental live-write code path to even misconfigure.

### Anti-Patterns to Avoid

- **Reimplementing the ZoomInfo `companies/enrich` request shape from scratch.** The exact contract
  (endpoint, JSON:API envelope, `outputFields` list, 1-25 companies / 25 outputFields limits) is
  already probed and documented in `scripts/build_cloud_workflows.py:1682-1742` as generated JS.
  Port that contract's *values* (URL, field names, units warning) into the new Python client — do
  not re-probe live from scratch.
- **Feeding `src/normalizer.py::normalize_country_region()`'s output straight into
  `compute_icp_score`.** See Pitfall 2 below — it returns `"Unknown"` for blank input, which is not
  the same as absent, and fires a false hard veto.
- **Using `result.tier` from `compute_icp_score()` as the pre-registered prediction verbatim.** See
  Pitfall 1 — "Needs Review" is a Python-only confidence downgrade that has no live counterpart.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Six numeric scoring properties | A second point-table / a JS-node port | `scripts/backfill_seed_company_scores.py::compute_components()` | Already exists, already the canonical translation, already tested by that module's own test file |
| `lv_anti_icp_flag_num` serialization | Recomputing the veto a second time | `src/icp_scoring.py::anti_icp_flag_properties(result.anti_icp_flag)` | Exists specifically so the two serializations of one veto value never drift (own docstring, `src/icp_scoring.py:31-44`) |
| Scored-population id list (SAFE-04 baseline) | A fresh HAS_PROPERTY search written inline | `scripts/rescore_population.py::select_scored_population()` | Same population definition three other scripts already share; a fourth definition is what 49-RESEARCH.md's own "Don't Hand-Roll" table warns against |
| Never-scored population count | Manual pagination loop | `NOT_HAS_PROPERTY(lv_icp_fit_score)` + `limit=1` + `result["total"]`, exact pattern at `scripts/check_tier_derived_parity.py:596-604` | Total-only count needs no pagination at all |
| ZoomInfo credit-balance auth/parsing | A new OAuth client | `scripts/check_provider_credits.py::_mint_zoominfo_token()` / `_extract_zoominfo()` | Already handles the JSON:API `Accept` header requirement and the `uniqueIdLimit` extraction, live-verified |

**Key insight:** This phase is almost entirely a composition exercise over code that was written in
the last ~10 phases specifically to be reused. The only genuinely new code is (a) the ZoomInfo
`companies/enrich` Python HTTP client (currently JS-only) and (b) the revenue-unit conversion in
Python (currently JS-only, in `normalizeProviders.js`) — both are ports of *already-correct*
existing logic, not new designs.

## Common Pitfalls

### Pitfall 1: `result.tier == "Needs Review"` has no live counterpart

**What goes wrong:** The dry-run artifact predicts `lv_icp_tier_derived` will read "Needs Review"
for a low-confidence record; the live calculated property can only ever be "A"/"B"/"C"/"D"/"Unscored"
per its formula (`config/hubspot_properties.yaml:426`, quoted verbatim: `'if
coalesce(lv_anti_icp_flag_num, 0) = 1 then "D" elseif lv_icp_fit_score >= 70 then "A" elseif
lv_icp_fit_score >= 40 then "B" elseif lv_icp_fit_score >= 15 then "C" else "Unscored"'`). Every
such record reads as a "mismatch" in Phase 52's post-write comparison even though nothing is wrong.
**Why it happens:** `compute_icp_score()`'s confidence-downgrade branch (`src/icp_scoring.py:161-167`)
is a local-MVP-era concept (CLAUDE.md §10.2's "Needs Review" row) that was never wired into the
live calculated-property formula, which only reads `lv_icp_fit_score` and `lv_anti_icp_flag_num` —
two numbers, no confidence.
**How to avoid:** Derive the predicted tier as `"D" if result.anti_icp_flag else ("A" if
result.score>=70 else "B" if result.score>=40 else "C" if result.score>=15 else "Unscored")` —
i.e. replicate the four-branch formula directly from `.score`/`.anti_icp_flag`, both already
returned. Do not read `.tier` for this purpose.
**Warning signs:** Any sample record whose gap-fill research came back `null`/unmatched for
`lv_org_type` or `lv_produces_content` — those are exactly the records that hit the confidence
downgrade.

### Pitfall 2: `normalize_country_region("")` returns `"Unknown"`, not `None`

**What goes wrong:** A ZoomInfo company match with a blank/unrecognized `country` field, if mapped
through `src/normalizer.py::normalize_country_region()` (`src/normalizer.py:80-88`, quoted
verbatim: `if not value: return "Unknown"` ... `return "Other"`) and written into
`candidate_patch["lv_country_region_normalized"] = "Unknown"`, causes `compute_icp_score()` to
treat the record as `region_key == "non_anz"` (since `"Unknown"` is truthy and not in
`["AU","NZ","ANZ"]`) and fire the non-ANZ hard veto — the *same* class of bug icp_scoring.py's own
comment (`src/icp_scoring.py:62-70`) documents having already fixed for a *missing* key, not for
this string.
**Why it happens:** The JS engine's equivalent function returns `null` for blank
(`n8n/code/normalizeProviders.js:96-102`, quoted verbatim: `if (!value) return null;`), so this
divergence was never exercised on the JS side and has no test coverage anywhere.
**How to avoid:** The new ZoomInfo-country mapper must either omit the key entirely for blank/no
match, or explicitly map "no data" to `None` before insertion into `candidate_patch` — never write
the string `"Unknown"` as a scoring input. `"Other"` (a real non-ANZ country) is fine to write; only
the blank case is the trap.
**Warning signs:** Any dry-run sample record with a ZoomInfo match but no `country` in the response
predicting Tier D via the non-ANZ veto — cross-check against the record's HubSpot native `country`
field before trusting that veto.

### Pitfall 3: `search_records()` has no pagination — a real gap, but not this phase's problem

**What goes wrong:** A naive population fetch for the full ~646-record never-scored set, or for
sample selection above 100 records, silently returns only the first 100 (HubSpot's search API page
cap) with no error, because `src/hubspot_client.py::search_records()` (`:119-128`) takes a `limit`
parameter and does nothing else — no `after` cursor loop exists anywhere in this file.
**Why it happens:** Every existing caller of `search_records` in this repo operates on the 66-record
scored population (`<=100`, one page) or uses the `limit=1`/`total`-only count trick — nobody has
needed real pagination yet. `rescore_population.py`'s own `select_scored_population()` docstring
says outright: "Add pagination ... before re-running" (as a raised error message, i.e. a documented,
deliberate gap).
**How to avoid (this phase):** Phase 51 only needs (a) a **count** (use the `limit=1`/`total` trick,
no pagination needed) and (b) a **bounded sample** (choose a sample size `<=100` and use a single
`search_records` call — no pagination needed). Do not build a pagination helper in this phase;
scope it explicitly out and flag it as a **Phase 52 prerequisite** (the "chunked remainder" stage
needs the full population's ids, which will exceed 100).
**Warning signs:** Any code in this phase that calls `search_records` with `limit` set above 100,
or that assumes `result["results"]` contains the full population without checking `total`.

### Pitfall 4: `.env` is Read/Bash-permission-blocked this session

**What goes wrong:** Attempting to `cat .env` or `Read` it to find required var names fails with a
permission error, wasting a turn.
**Why it happens:** Documented project convention (`env-file-permission-blocked` memory entry,
confirmed live this session — `.env` exists but reading it is blocked).
**How to avoid:** Derive every required env var name from source (`os.getenv(...)` call sites):
`HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_PORTAL_ID` (compared against hard-coded `EXPECTED_PORTAL_ID
= "22617666"` in every precedent script), `ZOOMINFO_CLIENT_ID`, `ZOOMINFO_CLIENT_SECRET`,
`ANTHROPIC_API_KEY`. Live calls must be invoked via the documented `load_dotenv()` + `runpy`
one-liner pattern every precedent script's docstring already spells out (e.g.
`scripts/backfill_seed_company_scores.py:44-47`), passing an **absolute** path to `load_dotenv()`.

### Pitfall 5: `config/icp_scoring.yaml` load is CWD-relative

**What goes wrong:** `compute_icp_score()`'s default `cfg=None` path calls `load_yaml("config/icp_scoring.yaml")`
(a relative path, `src/icp_scoring.py:52`) — running the new script from any directory other than
the repo root raises `FileNotFoundError`.
**Why it happens:** Every existing script in this repo shares this convention (`src/icp_scoring.py`'s
own header comment says as much for `src/web_research.py`'s taxonomy loader too).
**How to avoid:** Document "run from repo root" in the new script's own docstring, matching every
existing precedent.

## Code Examples

### Getting the six numeric properties + predicted tier from one candidate_patch (no reimplementation)
```python
# Source: composition of src/icp_scoring.py:47-172 and
# scripts/backfill_seed_company_scores.py:112-136 (both read in full this session)
from src.schemas import HubSpotRecord
from src.icp_scoring import compute_icp_score, anti_icp_flag_properties
from scripts.backfill_seed_company_scores import compute_components

candidate_patch = {
    "lv_org_type": "governing_body_league",
    "lv_produces_content": True,
    "lv_country_region_normalized": "AU",       # never "Unknown" for blank -- see Pitfall 2
    "lv_revenue_band": "5-50M",
    "lv_is_gambling_operator": False,
    "lv_is_hardware_vendor": False,
}

record = HubSpotRecord(object_type="companies", id=company_id, properties={})
result = compute_icp_score(record, candidate_patch)          # the ONE oracle call
six_numbers = {
    **compute_components(candidate_patch),                    # 5 named component scores
    **anti_icp_flag_properties(result.anti_icp_flag),         # lv_anti_icp_flag + _num
}

# Predicted tier -- replicate the LIVE 4-branch formula from score+veto directly.
# Do NOT use result.tier verbatim (see Pitfall 1: "Needs Review" never appears live).
predicted_tier = (
    "D" if result.anti_icp_flag else
    "A" if result.score >= 70 else
    "B" if result.score >= 40 else
    "C" if result.score >= 15 else
    "Unscored"
)
```

### Never-scored population count (no pagination needed)
```python
# Source: scripts/check_tier_derived_parity.py:596-604 (read this session)
from src.hubspot_client import search_records

result = search_records(
    "companies",
    [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
    ["name"],
    limit=1,
)
never_scored_count = result.get("total", 0)   # ~646 expected per MILESTONE-CONTEXT.md
```

### ZoomInfo GTM companies/enrich contract (port from the generated-JS reference)
```python
# Contract source: scripts/build_cloud_workflows.py:1682-1742 (JS, read this session).
# UNITS WARNING (verbatim from that file): "revenue is in THOUSANDS. revenueRange
# ("$250 mil. - $500 mil.") is requested alongside it because normalizeProviders prefers
# the unambiguous string."
ZOOM_ENRICH_URL = "https://api.zoominfo.com/gtm/data/v1/companies/enrich"
ZOOM_CO_OUTPUT_FIELDS = [
    "id", "name", "website", "revenue", "revenueRange", "employeeCount", "employeeRange",
    "country", "primaryIndustry", "naicsCodes", "descriptionList", "foundedYear",
]
# payload shape: {"data": {"type": "CompanyEnrich",
#   "attributes": {"matchCompanyInput": [{"companyWebsite": domain}], "outputFields": ZOOM_CO_OUTPUT_FIELDS}}}
# Auth: reuse scripts/check_provider_credits.py::_mint_zoominfo_token() (Basic auth,
# client_credentials grant, no `scope` param -- a scope 400s per that function's own comment).
```

### Revenue THOUSANDS -> dollars (port from the JS reference that already fixed this)
```python
# Source: n8n/code/normalizeProviders.js:404-415 (read this session, quoted logic):
#   "Prefer the unambiguous revenueRange string; fall back to revenue*1000."
#   const ziRev = raw.revenueRange != null && raw.revenueRange !== ""
#     ? raw.revenueRange
#     : (typeof raw.revenue === "number" ? raw.revenue * 1000 : null);
# A minimal, FILL-03-sufficient Python port (revenueRange-string parsing is a JS refinement,
# not required by FILL-03's own wording -- flag as nice-to-have, not required):
def zoominfo_revenue_to_dollars(raw_revenue_thousands):
    if not isinstance(raw_revenue_thousands, (int, float)):
        return None
    return raw_revenue_thousands * 1000
# Then feed the dollar figure into the EXISTING src/normalizer.py::normalize_revenue_band()
# (src/normalizer.py:30-54), which already expects dollars and already matches
# config/icp_scoring.yaml's band cut points.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| n8n "Decide Company Action" JS node computes score + veto | HubSpot's own `calculation_equation` computes `lv_icp_fit_score`/`lv_icp_tier_derived`; n8n (and now this phase's Python) only writes the six numeric inputs | Phase 50 (2026-08-14) | Zero n8n executions is now structurally possible for scoring — this milestone's whole premise |
| ZoomInfo revenue treated as dollars | ZoomInfo GTM `revenue` confirmed THOUSANDS, converted before banding in the JS engine | Phase 41-era live probe (per `n8n/code/normalizeProviders.js:405-411` comment) | The bug FILL-03 asks to pin is *already fixed in JS* — Phase 51's job is porting the fix to Python, not discovering it |
| n8n recompute POST (`post_webhook_event(..., recompute=True)`) as the write mechanism for scoring inputs | Direct `batch_update_companies` PATCH, no n8n involvement at all | Phase 40 (`backfill_seed_company_scores.py`) predates and coexists with the Phase 47.5 recompute lane | **This phase must use the Phase 40 direct-PATCH pattern, not the Phase 47.5/48 recompute-POST pattern** — the latter consumes an n8n execution, which this milestone forbids. `scripts/enrich_coverage_companies.py` and `scripts/remediate_veto_companies.py::post_webhook_event` are NOT reusable write patterns here despite superficially fitting the domain. |

**Deprecated/outdated for this milestone specifically:** the `lv_enrichment_requested` +
`SJ-3`/recompute-POST trigger family (CLAUDE.md §13.0, §19.1) — correct for other milestones, wrong
for this one (any use of it burns an n8n execution).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `zoominfo_per_match = 1.08 credits/match` applies to the `companies/enrich` endpoint specifically (the cited figure's own confidence note says "pre-v3 measurement... inferred... carried forward", and does not specify company- vs. contact-match) | Standard Stack table, credit-cap derivation | The credit cap (criterion 2) could be sized off the wrong per-call cost; a live 1-2 record probe of `companies/enrich` before sizing the cap would de-risk this cheaply |
| A2 | `ANTHROPIC_PER_RECORD_ESTIMATE_USD = 0.0686` is a reasonable ballpark for a bare `claude_web_research()` call in this phase, even though it was measured under the n8n pipeline's combined Haiku-research + Sonnet-judge nodes, and this milestone's design (per MILESTONE-CONTEXT.md D-01..D-06) has no Sonnet/judge step at all | Standard Stack table, Open Questions | The research-cost estimate (criterion 2) could overstate or understate actual per-record cost; the artifact should label this figure "prior-pipeline estimate, not measured for this call pattern" rather than presenting it as precise |
| A3 | `ANTHROPIC_RESEARCH_MODEL` is `claude-haiku-4-5` per `.env.example` in CLAUDE.md §11.2 — not independently re-verified against the live `.env` this session (permission-blocked) | Environment Availability | Low risk — `.env` is unreadable this session by design; the model name only affects a cost estimate's precision, not correctness |

## Open Questions

1. **Is the ZoomInfo `companies/enrich` per-call credit cost actually 1.08, or something else?**
   - What we know: `1.08 credits/match` is documented for "match" generally, sourced to a
     pre-v3-migration measurement (`scripts/enrichment_cost_ledger.py:106-111`), explicitly not
     re-verified against the current GTM `companies/enrich` endpoint.
   - What's unclear: whether this account's actual live cost per `companies/enrich` call differs
     (the Lusha v3 migration measured a very different actual-vs-documented cost for a sibling
     provider — see `lusha-v3-measured-pricing` memory entry — so a "measure it live" step has
     precedent value here).
   - Recommendation: the plan should include one live, single-record `companies/enrich` call
     (well within budget) bracketed by two credit-balance reads, to replace the inferred 1.08
     figure with a measured one before deriving the population cap — cheap insurance against a
     wrong cap.

2. **What "representative sample" selection rule should the dry run use?**
   - What we know: no existing script defines a stratified/representative sampling rule for this
     purpose; existing precedents (`select_canary` in `rescore_population.py`) pick a single canary
     record by a specific org_type, not a representative *set*.
   - What's unclear: whether "representative" means "covers a spread of org_types/geographies" or
     simply "a bounded slice of the capped population in id order."
   - Recommendation: default to a small, deterministic, sorted-id slice (matches every existing
     population-selection precedent's determinism convention) unless the discuss-phase or planner
     wants explicit stratification — flag this as a planner decision point, not a research gap.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python / `.venv` | All test/script execution | ✓ (system Python present) | 3.14.5 (system `python3`; project's own `.venv` was not found at `.venv/` this session — verify before running `.venv/bin/python`) | Recreate `.venv` from `requirements.txt` if missing |
| Node.js | `node --test tests/n8n/*.test.mjs` (regression check only — this phase writes no JS) | ✓ | v24.10.0 | — |
| `HUBSPOT_PRIVATE_APP_TOKEN` / `HUBSPOT_PORTAL_ID` | All live HubSpot reads | Unknown this session (`.env` exists but is Read/Bash-permission-blocked) | — | Derive var names from source only; do not attempt to read `.env` |
| `ZOOMINFO_CLIENT_ID` / `ZOOMINFO_CLIENT_SECRET` | ZoomInfo credit check + companies/enrich | Unknown this session (same block) | — | Same |
| `ANTHROPIC_API_KEY` | `claude_web_research()` gap-fill calls | Unknown this session (same block) | — | Same |

**Missing dependencies with no fallback:** none identified — every credential gate above already
has an established "skip (no credentials): print and exit 0" convention in every precedent script
(`check_provider_credits.py:186-190` etc.); the new scripts should follow the same convention so a
credential-less environment produces a clean skip, not a crash.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, `.venv/bin/python -m pytest`), `node --test` (JS, glob form only) |
| Config file | none dedicated — plain pytest discovery over `tests/test_*.py`; JS tests run via `node --test tests/n8n/*.test.mjs` (the **glob form**, not the directory form — the directory form is broken on Node 24 per this repo's own memory note, confirmed Node v24.10.0 is what's installed here) |
| Quick run command | `.venv/bin/python -m pytest tests/test_icp_scoring.py tests/test_zoominfo_company_client.py tests/test_backfill_dry_run.py -x` (new files; icp_scoring.py's existing suite is the regression check) |
| Full suite command | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FILL-01 | Credit balance read, cap derivation | unit (mocked HTTP) | `pytest tests/test_backfill_dry_run.py::test_cap_derivation -x` | ❌ Wave 0 |
| FILL-03 | ZoomInfo revenue THOUSANDS→dollars, pinned | unit | `pytest tests/test_zoominfo_company_client.py::test_revenue_thousands_to_dollars -x` | ❌ Wave 0 |
| FILL-04 | Unmatched record -> skip log, no payload | unit | `pytest tests/test_backfill_dry_run.py::test_unmatched_skip_log -x` | ❌ Wave 0 |
| SAFE-01 | Predicted tier derived from score+veto, not `.tier` | unit | `pytest tests/test_backfill_dry_run.py::test_predicted_tier_excludes_needs_review -x` | ❌ Wave 0 |
| SAFE-01 (regression guard) | `compute_components`/`compute_icp_score` are imported, never re-implemented | static/import-based test | `pytest tests/test_backfill_dry_run.py::test_imports_oracle_functions -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant new test file only (`pytest tests/test_backfill_dry_run.py -x` or `tests/test_zoominfo_company_client.py -x`)
- **Per wave merge:** `.venv/bin/python -m pytest` (full Python suite — this phase touches no JS source, so `node --test` is a lower-priority regression check, not a required gate)
- **Phase gate:** Full Python suite green before `/gsd-verify-work`; no live HubSpot/ZoomInfo write exists to verify, since this phase makes zero writes

### Wave 0 Gaps
- [ ] `tests/test_zoominfo_company_client.py` — new file, covers FILL-03 (mirrors the existing JS
      pin at `tests/n8n/enrichment.test.mjs:448`, "toCandidates: ZoomInfo company revenue is
      THOUSANDS, not dollars")
- [ ] `tests/test_backfill_dry_run.py` — new file, covers FILL-01/FILL-04/SAFE-01
- [ ] No shared fixture/conftest gap identified — `tests/scoring_fixtures.py` (existing) already
      supplies `EXPECTED_PORTAL_ID`, `settle()`/`settle_until()` helpers this phase's tests can
      reuse for offline unit tests without needing live credentials

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no (no user-facing auth surface; this is an internal ops script) | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | Portal-id guard (`EXPECTED_PORTAL_ID` hard-coded, asserted before any network call) is this repo's established access-control substitute — reuse it verbatim, do not invent a new guard |
| V5 Input Validation | yes | Every value derived from a provider response must be defensively type-checked before use (mirrors `check_provider_credits.py`'s `_is_number()` pattern) — a malformed ZoomInfo response must never raise into a crash, only degrade to a skip-logged record |
| V6 Cryptography | yes | Never hand-roll the ZoomInfo OAuth token mint — reuse `_mint_zoominfo_token()`'s existing `requests.post(..., auth=(cid, csec), ...)` pattern (never a manually-built `Authorization` header string) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Credential/secret leakage into printed dry-run output | Information Disclosure | Every existing precedent script prints only the payload dict, never headers/tokens — the new scripts must follow the identical discipline (`src/hubspot_client.py`'s `patch_record` dry_run branch is the model to copy) |
| Wrong-portal write | Tampering | `EXPECTED_PORTAL_ID` hard-coded assert before any call — this phase makes zero writes, but the *read* calls should still assert the portal, so a misconfigured `.env` produces a clean refusal rather than reading (and basing a cost/population artifact on) the wrong portal's data |
| Silent population truncation treated as ground truth | Tampering (of the artifact's own integrity) | The refuse-rather-than-truncate pattern (Pattern 1 above) — apply it to any search this phase issues, even the "count-only" ones, by checking `total` is what's expected |

## Sources

### Primary (HIGH confidence — read in full this session)
- `src/icp_scoring.py` — full file
- `src/normalizer.py` — full file
- `src/hubspot_client.py` — full file
- `src/schemas.py` — first ~60 lines (data model)
- `src/web_research.py` — first ~60 lines (research contract)
- `scripts/backfill_seed_company_scores.py` — full file
- `scripts/rescore_population.py` — ~lines 90-250
- `scripts/check_tier_derived_parity.py` — ~lines 1-150, ~575-650
- `scripts/check_provider_credits.py` — full file
- `scripts/provider_registry.py` — full file
- `scripts/build_cloud_workflows.py` — lines ~1670-1820, ~2500-2610
- `n8n/code/normalizeProviders.js` — lines 1-100, 380-439
- `scripts/enrichment_cost_ledger.py` — lines 1-135
- `scripts/enrich_coverage_companies.py` — lines 1-90 (confirmed NOT a zero-n8n precedent)
- `tests/scoring_fixtures.py` — full file
- `tests/test_icp_scoring.py` — first ~50 lines
- `config/hubspot_properties.yaml` — `lv_icp_tier_derived` and the five numeric-property entries
- `.planning/MILESTONE-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` — full files
- `requirements.txt` — full file

### Secondary (MEDIUM confidence)
- `tests/n8n/enrichment.test.mjs` — grep-located line 448 (THOUSANDS pin), not fully read
- `scripts/dryrun_batch.mjs` — first ~50 lines (confirmed as a contacts-only, JS-only precedent, not directly reusable)
- `scripts/canary_record_snapshot.py` — first ~100 lines (single-record snapshot precedent, not batch)

### Tertiary (LOW confidence)
- `zoominfo_per_match = 1.08 credits/match` figure — the ledger's own docstring rates this
  "inferred (measured pre-v3, carried forward)", not a fresh measurement against `companies/enrich`
  — see Open Question 1

## Metadata

**Confidence breakdown:**
- Standard stack (reusable functions): HIGH — every function cited was opened and read this
  session, not assumed from memory
- Architecture (zero-n8n write path): HIGH — the Phase 40 direct-PATCH precedent
  (`backfill_seed_company_scores.py`) is unambiguous, and the Phase 47.5/48 recompute-POST
  precedent was explicitly checked and ruled out as unusable for this milestone
- Pitfalls (tier-formula mismatch, blank-region bug): HIGH — both are backed by verbatim
  cross-file quotes (Python vs. live YAML formula; Python vs. JS normalizer), not inference
- ZoomInfo `companies/enrich` cost-per-call: MEDIUM — figure is documented but explicitly flagged
  stale by its own source

**Research date:** 2026-08-19
**Valid until:** 30 days (stable internal codebase; ZoomInfo API contract changes would be the main
invalidation risk — the credit endpoint and companies/enrich contract were both already probed and
pinned by prior phases, so this is a low-churn domain)
