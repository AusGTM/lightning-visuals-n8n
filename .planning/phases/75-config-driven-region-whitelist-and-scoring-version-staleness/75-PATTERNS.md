# Phase 75: Config-driven region whitelist and scoring-version staleness - Pattern Map

**Mapped:** 2026-09-20
**Files analyzed:** 10 (new/modified surfaces named in CONTEXT.md/RESEARCH.md)
**Analogs found:** 10 / 10

All analogs below were verified with `git ls-files` — every path is tracked source, not a
gitignored capability mirror.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/gen_icp_scoring_js.py` (new) | codegen script | transform (yaml→JS) | `scripts/gen_escalation_js.py` | exact |
| `n8n/code/icpScoring.generated.js` (new) | config artifact | transform output | `n8n/code/escalation.generated.js` | exact |
| new currency test for the generated JS | test | transform verification | `tests/test_judge_spec.py` (line 62 pattern) | exact |
| new yaml-vs-JS alias parity test | test | transform verification | `tests/n8n/columnMapIdentityParity.test.mjs` | exact |
| `src/icp_scoring.py` (modify: region-key/veto lookup) | service/scoring engine | CRUD (compute) | itself (existing file, in-place edit) | exact |
| `scripts/build_cloud_workflows.py::ENRICH_DECIDE_CO_CLOUD` (modify: veto reasons, region-key) | n8n Code-node builder | CRUD (compute, mirrors Python) | `src/icp_scoring.py` (Phase 46 parity twin) | exact |
| new IF node splice (`IF Company Skip` version-stale branch) | route/controller (n8n node) | event-driven (workflow routing) | `IF Company Recompute` / `IF Company Skip` (existing) | exact |
| `SJ2_CO_GATE` + `SJ-2 Search` widening | route/controller (n8n node + search) | batch (scheduled scan) | `SJ-1 Search (input-gap scan)` OR'd filter-group pattern | exact |
| `ALLOW_HUBSPOT_RECOMPUTE_WRITES` flag + `_writeSafetyAllows` branch | middleware (authorization gate) | request-response (guard) | `_writeSafetyAllows` itself + `ALLOW_HUBSPOT_REVIEW_WRITES` branch | exact |
| `lv_icp_scoring_version` property create + enum options + `UK` hide | migration/config | file-I/O (HubSpot schema PUT) | `scripts/sync_hubspot_properties.py` (create only — needs NEW update path, see Shared Patterns) | partial (gap) |

## Pattern Assignments

### `scripts/gen_icp_scoring_js.py` (codegen script, transform)

**Analog:** `scripts/gen_escalation_js.py` (full file, 74 lines)

**Full pattern to copy** (verified `scripts/gen_escalation_js.py:1-74`):
```python
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.icp_scoring import load_yaml  # reuse the existing loader, no second parser

OUT = ROOT / "n8n" / "code" / "icpScoring.generated.js"

def render() -> str:
    cfg = load_yaml("config/icp_scoring.yaml")
    lines = [
        "// n8n/code/icpScoring.generated.js",
        "//",
        "// GENERATED FROM config/icp_scoring.yaml — DO NOT EDIT.",
        "// Regenerate with: .venv/bin/python scripts/gen_icp_scoring_js.py",
        "",
        f"const VERSION = {json.dumps(cfg['version'])};",
        f"const REGIONS_HOME = {json.dumps(cfg['regions']['home'], indent=2)};",
        f"const REGION_ALIASES = {json.dumps(cfg['regions']['aliases'], indent=2)};",
        f"const HARD_VETO_REASONS = {json.dumps({k: v['reason'] for k, v in cfg['hard_vetoes'].items()}, indent=2)};",
        f"const GEOGRAPHY_POINTS = {json.dumps(cfg['base_score']['geography'], indent=2)};",
        "",
        "module.exports = { VERSION, REGIONS_HOME, REGION_ALIASES, HARD_VETO_REASONS, GEOGRAPHY_POINTS };",
        "",
    ]
    return "\n".join(lines)

def main():
    OUT.write_text(render())
    print(f"wrote {OUT.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
```
`json.dumps(...)` handles all JS-literal escaping — do not hand-build string interpolation
(ponytail rule stated verbatim at `scripts/gen_escalation_js.py:16-17`).

**Build-step registration pattern** (verified `scripts/build_cloud_workflows.py:53,60`):
```python
import gen_escalation_js  # noqa: E402
...
(CODE / "escalation.generated.js").write_text(gen_escalation_js.render())
```
Add the identical pair for `gen_icp_scoring_js` near the top of `build_cloud_workflows.py`,
before any `inline(...)` call references `icpScoring.generated.js`.

---

### `n8n/code/icpScoring.generated.js` (config artifact, transform output)

**Analog:** `n8n/code/escalation.generated.js` — same header/export shape convention: a
`// GENERATED FROM ... — DO NOT EDIT.` banner, `const` declarations per config section,
`module.exports = { ... }`.

**Inlining pattern — this is the load-bearing part.** `inline()` (`scripts/build_cloud_workflows.py:168-170`)
concatenates stripped module source with `require()` stripped out; n8n Code nodes cannot
`require()` a sibling file at all. Any module referencing `REGION_ALIASES`/`REGIONS_HOME`/
`HARD_VETO_REASONS`/`GEOGRAPHY_POINTS`/`VERSION` needs `icpScoring.generated.js` inlined into
the SAME `inline(...)` call, listed BEFORE it (declaration order matters in the concatenated
script). `normalizeProviders.js` is inlined at exactly three call sites, all with the identical
four-module list today (verified, none yet include the new module):
```python
ENRICH_NORMALIZE_SCORE = inline(
    "normalizePhone.js", "normalizeEmail.js", "normalizeProviders.js", "scoreEnrichment.js"
)
```
`[scripts/build_cloud_workflows.py:2703-2705]` — identical list recurs at `:3171-3173`
(`ENRICH_NORMALIZE_SCORE_CLOUD`) and `:3996-3998` (`ENRICH_NORMALIZE_SCORE_CO`). All three need
`"icpScoring.generated.js"` added, placed before `"normalizeProviders.js"`. `ENRICH_DECIDE_CO_CLOUD`'s
own `inline(...)` call already shows the "generated modules first, consumers after" convention:
`inline("taxonomy.generated.js", "hubspotEnums.generated.js", "hubspotEnums.js",
"mergeCompanies.js", "matchProposal.js")` at `scripts/build_cloud_workflows.py:5040-5041`.

---

### New currency test for `icpScoring.generated.js` (test, transform verification)

**Analog:** `tests/test_judge_spec.py:62` pattern:
```python
checked_in = (ROOT / "n8n" / "code" / "escalation.generated.js").read_text()
```
Mirror: read the checked-in `icpScoring.generated.js`, call `gen_icp_scoring_js.render()` fresh,
assert byte-equality. This is the standing "generated artifact is current" guard convention —
every `*.generated.js` in this repo has one (`escalation.generated.js` via `test_judge_spec.py`,
`hubspotEnums.generated.js` via `tests/test_hubspot_enums_generated_currency.py`).

---

### New yaml-vs-JS alias parity test (test, transform verification)

**Analog:** `tests/n8n/columnMapIdentityParity.test.mjs` — asserts a YAML config and its JS
mirror agree on identity-critical keys (same idiom used for `config/column_mapping.yaml` vs
`n8n/code/columnMap.js::requiredIdentity`).

**Pattern to copy:** load `config/icp_scoring.yaml`'s `regions.aliases` directly (Python or a
small YAML-in-JS read), load `n8n/code/normalizeProviders.js`'s existing `_COUNTRY_ISO2` map
(`n8n/code/normalizeProviders.js:21-32`, being superseded), and assert every key of
`_COUNTRY_ISO2` is present in `regions.aliases` (superset check) — per D-75-08's explicit
instruction: *"pin with the yaml-vs-JS parity test."* `_COUNTRY_ISO2`'s existing keys are the
minimum required set: `canada`, `ireland`, `india`, `singapore`, `great britain`, `england`,
`united states of america`, and others verified at `n8n/code/normalizeProviders.js:21-32`.

---

### `src/icp_scoring.py` (scoring engine, modify in place)

**Analog:** itself — this is a direct edit, verified at `src/icp_scoring.py:124,175-177`:
```python
region_key = region if region in ["AU", "NZ", "ANZ"] else "non_anz"
...
if region_key == "non_anz":
    anti_icp_flag = True
    anti_reasons.append(cfg["hard_vetoes"]["non_anz"]["reason"])
```
Two changes needed here, both verified this session: (1) `region_key` derivation must become a
set-membership check against `cfg["base_score"]["geography"]` (or the loaded `regions.home`),
not the 3-item hard-coded list; (2) the `cfg["hard_vetoes"]["non_anz"]` KEY lookup breaks the
moment the yaml key renames to `outside_home_regions` — this is a yaml-KEY exposure independent
of the STRING-value rename (Pitfall 3 in RESEARCH.md). Both `region_key`'s internal sentinel
value and the yaml key must move together as the same string.

---

### `scripts/build_cloud_workflows.py::ENRICH_DECIDE_CO_CLOUD` (Phase 46 parity twin)

**Analog:** `src/icp_scoring.py` itself — Phase 46's one-commit-both-engines rule (precedent:
commit `f817ec5`, the hardware-veto OR change, CLAUDE.md §10.3.1).

**Current JS to replace** (verified `scripts/build_cloud_workflows.py:5145-5147`):
```javascript
if (region === "non_anz") vetoReasons.push("Non-ANZ geography");
if (producesContent === false) vetoReasons.push("No broadcast or streaming content");
if (isHardwareVendor === true || orgType === "hardware_vendor") vetoReasons.push("Hardware/AV/LED vendor, not sports-media buyer");
```
Target shape: all three literals replaced by `HARD_VETO_REASONS[...]` lookups from the inlined
generated module (D-75-02). The JS `_regionKey` function (`scripts/build_cloud_workflows.py:5116-5120`)
today returns a 5-value enum (`"AU"|"NZ"|"ANZ"|"unknown"|"non_anz"`) via a hand-typed
`if (v === "AU" || v === "NZ" || v === "ANZ") return v;` at line 5118 — replace with
`REGIONS_HOME.includes(v)`-shaped lookup against the same generated set the Python side loads.
The comment at `scripts/build_cloud_workflows.py:5112-5114` states explicitly this logic "must
stay byte-identical to the oracle" — treat any divergence between this file's region logic and
`src/icp_scoring.py`'s as a defect, not a style choice.

---

### New IF node splice — version-stale skip → recompute reroute

**Analog:** `IF Company Recompute` / `IF Company Skip` (existing nodes, same company branch).

**Current wiring** (verified `scripts/build_cloud_workflows.py:8331-8340`):
```python
conns["Company Gate"] = {
    "main": [[{"node": "IF Company Recompute", "type": "main", "index": 0}]]}
conns["IF Company Recompute"] = {"main": [
    [{"node": "Decide Company Action", "type": "main", "index": 0}],  # true
    [{"node": "IF Company Skip", "type": "main", "index": 0}],        # false
]}
conns["IF Company Skip"] = {"main": [
    [{"node": "Build Response", "type": "main", "index": 0}],          # true
    [{"node": "Build Company Requests", "type": "main", "index": 0}],  # false
]}
```
`IF Company Skip` node definition (`scripts/build_cloud_workflows.py:7830-7832`):
```python
nodes.append(_if_bool_expr_node(
    "IF Company Skip", '$json.action === "skip"', hs_co_search_x, crby,
))
```
It reads `$json` bare (not by node name) because its immediate upstream is a Code node with no
HTTP hop in between (own comment, `scripts/build_cloud_workflows.py:8342-8344`) — a new IF
spliced directly downstream of `Company Gate`/`IF Company Skip` can read `$json` bare too under
the same condition. The moment it sits behind a Merge convergence, use the two existing splice
primitives rather than hand-wire a new Merge — do not repeat the Phase 70 G-70-2/G-70-3 defect
class:
- `splice_carry_merge_after` — `scripts/build_cloud_workflows.py:10619-10645`
- `_add_starved_lane_sentinel` — `scripts/build_cloud_workflows.py:10906-10932`

**Fetch-list gap to close in the same change:** `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`
(`scripts/build_cloud_workflows.py:7068-7100`) does not list `lv_icp_scoring_version` — add it,
or `existingRecord.lv_icp_scoring_version` reads `undefined` and the new IF's comparison always
routes one way. The local-live sibling `HS_CO_SEARCH_BODY_EXPR` (`:3628-3652`) needs the
identical addition, per this repo's own repeated bug history (fix-40 VETO-01/02, 58-05, Phase 66
Plan 02) — audit every `properties_csv`/search-body fetch list this phase touches, not only the
ones CONTEXT.md names.

---

### `SJ2_CO_GATE` + `SJ-2 Search` widening (scheduled backstop)

**Analog:** `SJ-1 Search (input-gap scan)` — the existing OR'd `NOT_HAS_PROPERTY`/`EQ`
filter-group pattern (verified `scripts/build_cloud_workflows.py:11022-11031`):
```python
filter_groups=[
    [{"propertyName": "lv_org_type", "operator": "NOT_HAS_PROPERTY"}],
    [{"propertyName": "lv_org_type", "operator": "EQ", "value": "unknown"}],
    [{"propertyName": "lv_produces_content", "operator": "NOT_HAS_PROPERTY"}],
],
```
Each top-level list entry is OR'd; each entry's own `filters` is AND'd within itself. D-75-15's
target shape (verified pattern-fit, not yet live-tested with this exact combination):
```python
filter_groups=[
    [{"propertyName": "lv_icp_scoring_version", "operator": "NOT_HAS_PROPERTY"},
     {"propertyName": "lv_org_type", "operator": "HAS_PROPERTY"}],
    [{"propertyName": "lv_icp_scoring_version", "operator": "NEQ", "value": "<VERSION>"},
     {"propertyName": "lv_org_type", "operator": "HAS_PROPERTY"}],
    [{"propertyName": "lv_icp_scoring_version", "operator": "NOT_HAS_PROPERTY"},
     {"propertyName": "lv_produces_content", "operator": "HAS_PROPERTY"}],
    [{"propertyName": "lv_icp_scoring_version", "operator": "NEQ", "value": "<VERSION>"},
     {"propertyName": "lv_produces_content", "operator": "HAS_PROPERTY"}],
]
```
Flagged `[ASSUMED]` in RESEARCH.md — verify with a disarmed dry-run search before shipping.

**Blocker to fix in the same change** (verified `scripts/build_cloud_workflows.py:9934-9971` /
`:3934,3940`): `SJ2_CO_GATE`'s `REQUIRED = ["lv_org_type", "lv_produces_content"]` runs before
`"SJ-2 Set Requested"` and gates to `"skip"` on freshness of those two fields alone — a
version-stale-but-input-fresh record never reaches dispatch even if the search selects it. Teach
`SJ2_CO_GATE` to treat a version mismatch as not-skip, and add `lv_icp_scoring_version` to
`"SJ-2 Search"`'s `properties_csv` (currently 6 fields, `scripts/build_cloud_workflows.py:11071-11072`).
Routing reference (`scripts/build_cloud_workflows.py:11079-11098`):
```python
sj2_if_not_skip = _if_node("SJ-2 IF Skip", "skip", x2, y2)
...
conns[sj2_if_not_skip["name"]] = {"main": [
    [{"node": "SJ-2 Skip (NoOp)", "type": "main", "index": 0}],   # true
    [{"node": sj2_dispatch["name"], "type": "main", "index": 0}],  # false
]}
```

---

### `ALLOW_HUBSPOT_RECOMPUTE_WRITES` flag + `_writeSafetyAllows` branch (authorization gate)

**Analog:** `_writeSafetyAllows` itself, specifically the existing `"review"` branch pattern —
a distinct action classification checking ONE flag with no allowlist, contrasted against the
default else-branch which IS allowlist-gated (verified full function,
`scripts/build_cloud_workflows.py:2547-2565`):
```javascript
function _writeSafetyAllows(action, hsObjectId, domain) {
  if (action === "review") {
    if (String(ALLOW_HUBSPOT_REVIEW_WRITES).toLowerCase() !== "true") return false;
  } else {
    if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
    if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
  }
  const allowedDomains = String(TEST_RECORD_DOMAINS).split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const allowedIds = String(TEST_RECORD_IDS).split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowedDomains.length && !allowedIds.length) return false;
  if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
  if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
  return false;
}
```
Target shape: add a `"recompute"` branch that returns
`String(ALLOW_HUBSPOT_RECOMPUTE_WRITES).toLowerCase() === "true"` directly, bypassing the
`allowedDomains`/`allowedIds` allowlist check entirely (D-75-16's explicit ask: "checks this
flag ALONE"). There is no `"recompute"` action value today — the plan needs its own signal
(new action value, or a `row.recompute === true` short-circuit read before this function).

**Default-literal registration:** `WRITE_SAFETY_DEFAULTS` (`scripts/build_cloud_workflows.py:174-182`)
is where every flag's disabled-default literal is baked; add
`"ALLOW_HUBSPOT_RECOMPUTE_WRITES": "false"` there (ships `"false"` per D-75-17).

**Tooling consequences — three call sites to extend, not create:**
1. `operator-claude-plugin/scripts/n8n_arming.py`'s `OVERLAY_DISABLED_LITERALS`/
   `OVERLAYABLE_FLAGS`/`WRITE_ENABLING_FLAGS` — the new flag must NOT be added to any of these,
   so `disarm()`/`arm_for_dispatch()` never touch it (deliberate exclusion, not an oversight).
2. `scripts/bounce_n8n_workflows.py:34` — `WRITE_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES",
   "ALLOW_HUBSPOT_CREATE")` and `_row_ok` (`:56-68`) assert `all(v in ([], ["false"]) ...)`.
   This tuple already omits `ALLOW_HUBSPOT_REVIEW_WRITES` (pre-existing gap). Add a SEPARATE
   allowed-true tracking set for `ALLOW_HUBSPOT_RECOMPUTE_WRITES` so the script can assert it
   correctly reads `"true"` post-flip rather than silently ignoring it or falsely failing.
3. `scripts/deploy_n8n_workflows.py` and any UAT read-back scripts asserting "all `ALLOW_*`
   literals read false" — same enumeration update.

---

### `lv_icp_scoring_version` property + enum options + `UK` hide (HubSpot schema migration)

**Analog:** `scripts/sync_hubspot_properties.py` — covers the property CREATE half only.

**Gap (not a clean analog — flag this to the planner as new code needed):** `compute_property_diff`
(`scripts/sync_hubspot_properties.py:72-91`) classifies any existing property whose `options`
differ from desired as `drift` (report-only, never auto-fixed — docstring at `:73-74`). The
ONLY live-write path in the file is `_create_property_live` (`:126-133`), a
`POST /crm/v3/properties/{object_type}` CREATE call — zero `PATCH`/`PUT` anywhere (`grep -n
"PATCH\|patch"` returns one hit, a code comment, not a call). `hidden` appears 0 times in the
file. The `lv_icp_scoring_version` property itself (new, no existing options) can ship through
this tool completely unmodified via the existing CREATE path — only the `UK`-hide and the
`GB/IE/CA/ZA/HK/SG/AE/IN` enum-option additions to the EXISTING `lv_country_region_normalized`
property need a new `_update_property_options_live` function
(`PATCH /crm/v3/properties/{objectType}/{propertyName}` with a full desired `options` array —
verify HubSpot's exact contract before writing it; flagged `[ASSUMED]` in RESEARCH.md
Assumption A1).

**Downstream artifact dependency (Pitfall 2):** `scripts/gen_hubspot_enums_js.py:27` reads a
pinned SNAPSHOT file (`config/hubspot_migration/baseline/portal-schema-companies-post-orgtype-enum.json`),
not `config/hubspot_properties.yaml` directly. After the live enum-option PUT, run
`scripts/snapshot_hubspot_schema.py --label <new-suffix>`, repoint/overwrite the pinned
`SNAPSHOT` constant, then regenerate `n8n/code/hubspotEnums.generated.js`. A green
`tests/test_hubspot_enums_generated_currency.py` before this refresh step proves nothing (it
would compare the generated file against the same stale snapshot).

**Flow regeneration analog:** `scripts/put_hubspot_flow.py` / `scripts/fetch_hubspot_flow.py` —
existing PUT/GET-with-before/after-JSON mechanism, reused unmodified for the `4626722240
Geography Score` flow body regeneration (branch values derived from `regions.home`, never
hand-edited).

## Shared Patterns

### Codegen currency guard (applies to every `*.generated.js` this phase touches)
**Source:** `tests/test_judge_spec.py:62` (pattern), `tests/test_hubspot_enums_generated_currency.py` (sibling)
**Apply to:** `icpScoring.generated.js` (new test) and `hubspotEnums.generated.js` (existing
test, re-run after the snapshot refresh)

### Phase 46 one-commit-both-engines parity
**Source:** CLAUDE.md §10.3.1 (commit `f817ec5` precedent); enforced by `tests/test_scoring_parity.py`
**Apply to:** `src/icp_scoring.py` and `scripts/build_cloud_workflows.py::ENRICH_DECIDE_CO_CLOUD`
— any predicate/veto/region change lands in both, in one commit, never independently.

### v1 execution-order Merge/sentinel discipline
**Source:** CLAUDE.md §13.0.3; primitives at `scripts/build_cloud_workflows.py:10619` and `:10906`
**Apply to:** the `IF Company Skip` version-stale splice — a node fed zero items never executes
under v1; every branch reaching a Merge input must be guaranteed a delivery or that Merge's
downstream never runs.

### Write-safety flag enumeration
**Source:** `_writeSafetyAllows` (`scripts/build_cloud_workflows.py:2547-2565`),
`WRITE_SAFETY_DEFAULTS` (`:174-182`)
**Apply to:** every gated write; the new `ALLOW_HUBSPOT_RECOMPUTE_WRITES` flag joins this family
but is deliberately excluded from the arming/disarming tooling (V4 access-control boundary,
operator-ruled exception).

### "Property omitted from a fetch list reads as undefined" — recurring bug class
**Source:** RESEARCH.md "Don't Hand-Roll" key insight; prior incidents fix-40 VETO-01/02, 58-05,
Phase 66 Plan 02
**Apply to:** every `properties_csv`/`HS_CO_SEARCH_BODY_EXPR`/`SJ-2 Search` fetch list this
phase touches — `lv_icp_scoring_version` must be added everywhere it is read, not only where
CONTEXT.md explicitly names it.

## No Analog Found

None — every file/surface in scope has at least a partial analog. The one genuine gap
(HubSpot enum-option live UPDATE) is documented above under its own entry rather than listed
here, since `sync_hubspot_properties.py` is still the correct file to extend (new function
inside the existing tool), not a wholly new tool.

## Metadata

**Analog search scope:** `scripts/`, `n8n/code/`, `src/`, `tests/`, `tests/n8n/`,
`operator-claude-plugin/scripts/`, `config/hubspot_flows/`
**Files scanned:** ~25 files directly opened/grepped across CONTEXT.md/RESEARCH.md's own
research session plus this mapping pass; all analog paths confirmed tracked via `git ls-files`
**Pattern extraction date:** 2026-09-20

## PATTERN MAPPING COMPLETE
