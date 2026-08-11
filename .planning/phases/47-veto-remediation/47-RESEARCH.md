# Phase 47: Veto Remediation - Research

**Researched:** 2026-08-11
**Domain:** HubSpot CRM property remediation via direct API batch-write + n8n Cloud derived-field pipeline
**Confidence:** MEDIUM (HIGH on code facts verified by direct file read; MEDIUM-LOW on the write-mechanism decision, which contains a BLOCKING FINDING requiring operator/planner resolution)

## Summary

CONTEXT.md's 17 decisions are largely sound and directly executable: the 17 pinned company
IDs are confirmed against `46-SIMULATION-REPORT.md` (exactly 17, not the 21 a sloppy grep first
suggested), the 3 excluded IDs are confirmed absent from that list, `src/web_research.py` and
`config/field_policy.yaml` match CONTEXT.md's characterization closely, and the settled rubric
in `config/icp_scoring.yaml` matches Phase 46's landed decision (`individual_club_team: 15`,
`regulator: -20`, `graduated_deductions: {}`).

**However, this research found one BLOCKING FINDING that CONTEXT.md's D-06/D-07/D-11 did not
account for and that the planner must resolve before sequencing tasks**: the direct
batch-PATCH mechanism D-06 selects (mirroring `scripts/backfill_seed_company_scores.py`) can
settle `lv_icp_fit_score` and `lv_icp_tier` through pure HubSpot-native automation (a
calculated property + two native Automation flows), but **cannot** clear `lv_anti_icp_flag` /
`lv_anti_icp_reason` — VETO-01's literal success bar. Those two fields are written exclusively
by a Code node inside the n8n Cloud enrichment workflow (`n8n/wf_enrichment_cloud.json`'s
"Decide Company Action" node), which only runs when that n8n workflow actually executes. No
currently-deployed HubSpot-native flow writes these two fields (confirmed by reading every
`config/hubspot_flows/*.after.json` file). This is not a hypothesis — it is independently
confirmed by an existing, already-committed test (`tests/test_scoring_parity.py::
test_veto_clear_after_correction`) whose own inline comment states: *"the flag is owned and
cleared by the n8n pipeline, not a HubSpot workflow — correcting the input alone isn't
enough."*

**Primary recommendation:** Do not plan Phase 47 around a pure direct-batch-PATCH-and-settle
cycle for the veto fields. The plan needs an explicit second write surface — some invocation of
the n8n enrichment workflow's Decide step, scoped to exactly the 17 pinned IDs — layered on top
of the direct-PATCH input write. Two viable trigger mechanisms exist in the codebase today (see
BLOCKING FINDING section); the planner (or the operator, via a return trip through
`/gsd-discuss-phase`) must pick one, because picking one changes VETO-02's write-window shape
(D-11 assumed the n8n arming ceremony was irrelevant "surface the write never touches" — it is
not, if any n8n leg is required).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VETO-01 | All 17 companies re-scored under the fixed rubric; `lv_anti_icp_flag`/`lv_anti_icp_reason` reflect the re-score | BLOCKING FINDING below identifies the write mechanism gap; §"The derived-field chain" gives the exact code path that must run; §"17 pinned IDs" gives the literal ID list |
| VETO-02 | Clearing run happens inside a deliberately-armed write window with a record-count cap, disarmed and read back afterward | §"Write-window shape" documents the actual arm/disarm mechanics for BOTH write surfaces (direct-PATCH script's own two-key gate, and — if needed — `n8n_arming`'s `TEST_RECORD_IDS` allowlist, which is the SAME gate the Decide node itself checks) |
| VETO-03 | Operator can confirm from HubSpot alone that no company has a non-ANZ veto reason with blank region | §"VETO-03 acceptance search" gives the verbatim search |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
D-01 through D-17 as recorded in `.planning/phases/47-veto-remediation/47-CONTEXT.md` — see
that file for full text. Key ones this research bears directly on:

- **D-06:** Direct batch PATCH, reusing `backfill_seed_company_scores.py`'s
  `compute_components()` + `batch_update_companies()` path, "costs ~0 n8n executions."
  **Research finding: this claim is incomplete — see BLOCKING FINDING.** It correctly clears
  `lv_icp_fit_score`/`lv_icp_tier` with zero n8n involvement, but cannot clear
  `lv_anti_icp_flag`/`lv_anti_icp_reason` at all.
- **D-07:** `lv_anti_icp_flag`/`lv_anti_icp_reason` are never written directly by the phase's
  own code (confirmed: this is enforced by a real offline guard, `tests/
  test_backfill_seed_company_scores.py`, though not literally "T-40-22" as a test ID — no test
  in this repo is named `T-40-22`; that is a plan-task label from Phase 40 Plan 07, not a test
  function name. See "Provenance correction" below).
- **D-11:** The batch-PATCH script carries its own operator-only arming gate; n8n's own arming
  is "a surface the write never touches." **Research finding: only true if the plan's final
  mechanism excludes any n8n leg.** If a n8n Decide-node invocation is added to clear the veto
  (which this research recommends), n8n's `ALLOW_HUBSPOT_RECORD_WRITES` +
  `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` gate (armed via `n8n_arming.arm_for_dispatch()`, the
  same module `scripts/june_run_arm.py` wraps) becomes a second, necessary write surface inside
  VETO-02's window — not an irrelevant one.
- **D-12:** Volume capped by `HARD_CEILING_RECORDS = 25`; identity capped by a pinned `--ids`
  list. **Research finding: the flag is actually `--company-id` (repeatable), not `--ids`**, and
  the existing script's cap logic checks *count only* — it does not refuse an ID absent from a
  separately-maintained allowlist the way D-12 describes. See "Script surface corrections."
- **D-14:** Never write `lv_produces_content = false` on absent evidence. **Confirmed
  consistent** with the live n8n veto-derivation code, which treats a blank/unset
  `lv_produces_content` as `null` (no veto), not `false`.

### Claude's Discretion
- Exact chunking within the 17 (one chunk of 17 permitted; smaller allowed).
- Dry-run output format (must print exact PATCH payloads).
- Where the per-record "could not establish" note lives (property, run report, or both).
- Polling interval/timeout for the settle step.

### Deferred Ideas (OUT OF SCOPE)
- The 1 remaining blank-`lv_org_type` record outside the 17 (Phase 48).
- Full-population re-score (Phase 49, RESCORE-01/02/03).
- `lv_icp_scoring_version` property (rejected, no-new-properties constraint).
- A needs-review queue for un-enrichable records.
</user_constraints>

## BLOCKING FINDING: the veto fields cannot be cleared by a pure direct-PATCH cycle

### Evidence chain (every claim below verified by direct file read this session)

**1. No currently-deployed HubSpot-native flow writes `lv_anti_icp_flag` or `lv_anti_icp_reason`.**
Every `config/hubspot_flows/*.after.json` file (the live, deployed shape) was checked for a
`SET_PROPERTY`/`SINGLE_CONNECTION` action targeting either field:

```
[VERIFIED: config/hubspot_flows/4626722240-geography-score.after.json:1-70]
```
The live "Geography Score" flow (id `4626722240`) only writes `geography_score` (10 or 0),
gated on `lv_country_region_normalized` in `["AU","NZ","ANZ"]`. There is no veto branch — it
was deleted in Phase 40-05 (per STATE.md's own Phase 40-05 entry: "Geography flow's veto branch
deleted").

```
[VERIFIED: config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json:1-236]
```
WF1 (id `4625147345`, "WF1 Set ICP Tier based on ICP Score") reads `lv_anti_icp_flag` as a
branch filter (`IS_EQUAL_TO "true"` → write `lv_icp_tier = "D"`) but the flow's only
`SINGLE_CONNECTION` write actions target `lv_icp_tier` (actionIds 4-8, static values
`A`/`B`/`C`/`Unscored`/`D`). It never writes `lv_anti_icp_flag` or `lv_anti_icp_reason`.
Enrollment fires on either `lv_anti_icp_flag` OR `lv_icp_fit_score` becoming known (lines
240-298), confirming WF1 is a pure *reader* of the veto flag, not its writer.

A sweep of all 8 `*.after.json` files in `config/hubspot_flows/` for either property name found
only this one reference (WF1's read). Nothing else references them.

**2. The one place both fields ARE written is an n8n Code node, and it runs unconditionally on
every workflow execution — not only when a veto fires.**

```
[VERIFIED: n8n/wf_enrichment_cloud.json, "Decide Company Action" node's jsCode]
```
Quoted verbatim from the node's compiled JS (found by grepping the node's `jsCode` string for
the literal `"Non-ANZ geography"`):

```js
function _regionKey(v) {
  if (v === "AU" || v === "NZ" || v === "ANZ") return v;
  if (v === undefined || v === null || v === "") return "unknown";
  return "non_anz";
}
...
const vetoReasons = [];
if (region === "non_anz") vetoReasons.push("Non-ANZ geography");
if (producesContent === false) vetoReasons.push("No broadcast or streaming content");
if (isHardwareVendor === true) vetoReasons.push("Hardware/AV/LED vendor, not sports-media buyer");

properties.lv_anti_icp_flag = vetoReasons.length > 0 ? "true" : "false";
properties.lv_anti_icp_reason = vetoReasons.length > 0 ? vetoReasons.join("; ") : "";
```

Two facts this establishes:
- **The blank-region fix IS already ported to this JS** (`_regionKey` treats
  `undefined`/`null`/`""` as `"unknown"`, distinct from `"non_anz"`) — dated 2026-08-10 per the
  node's own inline comment citing "17 real companies (13 AU racing clubs + 1 NZ club)" patched
  false by this exact node. So a record whose region is genuinely left unresolved (D-14's
  "could not establish" case) will NOT be re-vetoed if this node runs again — it computes
  `"unknown"`, not `"non_anz"`.
- **The write is unconditional and always both fields together** — `vetoReasons.length > 0 ?
  "true" : "false"` and the corresponding empty-string branch for the reason. This node
  actively clears a stale `true`/`"Non-ANZ geography"` to `false`/`""` once its three inputs
  (region, produces_content, is_hardware_vendor) no longer justify a veto. It is not a
  write-only-on-true node.

**3. This Code node only executes when the n8n workflow runs, and nothing currently makes a
direct HubSpot CRM API `PATCH` to `lv_country_region_normalized`/`lv_org_type`/
`lv_produces_content` cause that workflow to run.** The n8n Cloud enrichment workflow's entry
point is `n8n-nodes-base.webhook` — a webhook trigger, not a HubSpot-native automation reacting
to the PATCH. HubSpot property-change webhook *subscriptions* would be the only thing that could
auto-fire it on a plain API PATCH, and CLAUDE.md §20.2's "MVP subscriptions" (unprefixed but
correctable per §4.0) list only `lv_enrichment_requested` — not
`lv_country_region_normalized`/`lv_org_type`/`lv_produces_content` — as subscribed properties;
§20.2's "Later subscriptions" list including those properties is explicitly framed as aspirational,
not confirmed live. **This was not independently re-verified against the live portal's actual
webhook subscription list this session — flagged `[ASSUMED]`, verify before planning assumes
either way** (see Open Questions).

**4. Direct, in-repo confirmation this is a known, previously-encountered fact, not a novel
research inference:**

```
[VERIFIED: tests/test_scoring_parity.py:441-466]
```
```python
def test_veto_clear_after_correction():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "US",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "lv_anti_icp_flag")
        vetoed = fetch_for_parity(company_id)
        assert vetoed.get("lv_anti_icp_flag") == "true"

        # D-01/D-02: the flag is owned and cleared by the n8n pipeline, not a HubSpot
        # workflow — correcting the input alone isn't enough. The operator-documented
        # refresh path is lv_enrichment_requested + the 15-min SJ-3 poller (D-02).
        ...
        patch_record("companies", company_id, {"lv_country_region_normalized": "AU"}, dry_run=False)
        patch_record("companies", company_id, {"lv_enrichment_requested": "true"}, dry_run=False)
        settle(company_id, "lv_anti_icp_flag", timeout=900, interval=15)
        cleared = fetch_for_parity(company_id)
        assert cleared.get("lv_anti_icp_flag") == "false"
```

Per STATE.md's Phase 40-07 entry, this exact test (and 4 siblings) are known to **fail today**
for a structural reason: "setting veto-input properties alone never dispatches the n8n
pipeline under this portal's actually-configured webhook subscriptions" — i.e., even the
`lv_enrichment_requested` + SJ-3-poller path this test exercises has never been proven to
reliably dispatch on this portal, independent of the daily-cadence objection D-06 raises.

### The two viable trigger mechanisms (present both, do not pre-choose)

**(a) Direct webhook POST per record, bypassing the SJ-3 schedule entirely.**
Proven live in Phase 40-03 ("Attempt 2/3", per `40-03-SUMMARY.md` lines 241-281): a direct
`POST {N8N_URL}/webhook/hubspot/enrichment/event` with header `X-Enrichment-Secret` and a body
shaped like a HubSpot property-change event array (`objectId`, `objectType: "company"`,
`subscriptionType`, `propertyName`, `occurredAt`) reaches the same workflow and — per the
topology this research read (`IF Company Bare Event` → `HubSpot Company Fetch By Id` nodes) —
supports a bare-object-id event that doesn't require a `domain` match. `40-03-SUMMARY.md` also
records a live-discovered race condition: a `domain` PATCH immediately followed by the webhook
POST can race the HubSpot search index (~20s indexing lag elsewhere in this codebase,
`WINDOWS.md` id 6) — worth a settle-before-trigger step if domain is touched in the same run
(it is not, in this phase). Cost: one n8n execution per record POSTed = up to 17 executions
against the 2,500/month allowance (trivial). **Caveat found this session, not in
`40-03-SUMMARY.md`:** the "Research Trigger Gate" node's `needsResearch()` predicate (quoted
below) will re-trigger a *second* Claude web-research call for any of the 17 whose `lv_org_type`
lands on `hardware_vendor`/`content_producer`/`governing_body_league`/`gambling_operator` — see
"Cost estimate" section.

**(b) `operator-claude-plugin/scripts/scheduled_arm.py`'s established drain path.**
This is the mechanism `VETO-WRITE-EVIDENCE.md` (2026-08-06/07, cited in STATE.md's Phase 40-05
entry) already live-proved: a real HubSpot PATCH landing `lv_anti_icp_flag="true"` via "the
scheduled-arm companion." It arms via `n8n_arming.arm_for_dispatch()` (the same module
`scripts/june_run_arm.py` wraps), supplies `TEST_RECORD_IDS` as an allowlist, and chunks
dispatch via `chunking.plan_chunks()`/`chunking.chunk_ceiling(config)` — a **config-driven**
ceiling, not the hardcoded "2-record chunk cap" STATE.md's Phase 44 note describes (that was
this repo's *observed* config value at the time, not a hardcoded constant in the script; the
planner must read the live `chunk_ceiling` config value before assuming any specific number).
Already carries allowlist + read-back machinery VETO-02 wants, at the cost of being a second,
separate ceremony from the direct-PATCH script.

### The D-11 inversion this creates

`Decide Company Action`'s own gate — found in the same node, immediately preceding the veto
logic quoted above — is:

```js
if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
...
const allowedIds = String(TEST_RECORD_IDS).split(",").map((s) => s.trim()).filter(Boolean);
if (!allowedDomains.length && !allowedIds.length) return false;  // empty allowlist denies everything
if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
```

`[VERIFIED: n8n/wf_enrichment_cloud.json, "Decide Company Action" node's jsCode]`

This is **exactly** the gate `n8n_arming.arm_for_dispatch()` / `scripts/june_run_arm.py` toggle
(`ALLOW_HUBSPOT_RECORD_WRITES` baked `"false"` at rest per `OVERLAY_DISABLED_LITERALS` in
`operator-claude-plugin/scripts/n8n_arming.py`). If the plan adopts trigger mechanism (a) or
(b) above, **this is a second write surface the write genuinely does touch**, contradicting
D-11's premise that n8n arming is "a surface the write never touches." The plan must arm this
gate with `TEST_RECORD_IDS` = the 17 pinned IDs (mirroring `june_run_arm.py`'s pattern exactly:
operator-only `ALLOW_N8N_ARM`, `--ids`/allowlist, disarm ungated) as part of VETO-02's window —
not treat it as irrelevant.

### What the planner should do with this

Flag D-06 and D-11 for explicit re-confirmation (ideally a short loop back through
`/gsd-discuss-phase`, since this changes the write-window's shape, which D-11 marked
"costly — reversibility"). Do not silently substitute a fix in the plan without the operator
seeing this tradeoff: mechanism (a) is cheaper/faster but risks a second research call on ~4
records; mechanism (b) reuses proven, gated infrastructure but is a second ceremony layered on
top of the direct-PATCH script, with its own config-driven chunk size to verify live before the
plan's cost estimate is written.

## The 17 pinned company IDs

`[VERIFIED: .planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md]`
— exact grep count confirmed **17** (a stray double-count during this research's own
intermediate `wc -l` was a tooling artifact; the direct row listing below is the ground truth).
Rows are shown exactly as `46-SIMULATION-REPORT.md` prints them: Name | HubSpot ID |
`lv_org_type` (all blank) | Flags | Live Score/Tier.

| Name | HubSpot ID | Live Score/Tier |
|---|---|---|
| Tweed Valley Jockey Club | `9604732797` | 0/D |
| Sapphire Coast Turf Club (Bega Valley) | `9604794661` | 0/D |
| Port Macquarie Race Club | `9605273630` | 0/D |
| Rockhampton Jockey Club | `9604732795` | 10/D |
| Bunbury Turf Club | `9604738976` | 0/D |
| The Alice Springs Turf Club | `9604787229` | 10/D |
| Thoroughbred Park | `10152138518` | 10/D |
| Wyong | `10215097384` | 10/D |
| Coffs Harbour Racing Club | `14752488879` | 0/D |
| Editix | `17317381378` | 0/D |
| Jam TV | `17317850381` | 0/D |
| Pinjarra Park | `17696004613` | 0/D |
| Simtech LED | `18047161864` | 10/D |
| The Kalgoorlie-Boulder Racing Club | `18796602894` | 10/D |
| Newcastle Harness Racing Club | `19100977027` | 0/D |
| Waikato Racing Club Inc | `20538284384` | 0/D |
| The Rumble / Pacific Action Sports | `20943964946` | 10/D |

**Confirmed excluded** (not present in the above list, cross-checked by name and ID): Entain
(`10024564084`), Gravity Media (`15860277364`), Ironman (`17317184159`).

**Confirmed adjacent but out-of-scope:** Racing NSW (`15008671672`) is flagged `blank_org_type`
only (no `false_veto` flag) at line 80 of `46-SIMULATION-REPORT.md`, Live 40/B — this is Phase
48's 1 remaining record, correctly excluded from the 17.

D-17's specific claims about org-type composition are confirmed against this table: Simtech LED,
Editix, Jam TV, The Rumble/Pacific Action Sports, Thoroughbred Park, Wyong, Pinjarra Park, and
Waikato Racing Club Inc are all present with the exact IDs D-17 cites.

## Script surface corrections (verified against current source)

### `scripts/backfill_seed_company_scores.py`

```
[VERIFIED: scripts/backfill_seed_company_scores.py:93-117]
```
```python
def compute_components(props: dict) -> dict:
    canonical = {k: props.get(k) for k in CANONICAL_INPUT_PROPS if props.get(k) not in (None, "")}
    record = HubSpotRecord(object_type="companies", id="0", properties=canonical)
    result = compute_icp_score(record, {})
    by_signal = {c["signal"]: c["points"] for c in result.breakdown["components"]}
    ...
    return {
        "org_type_score": by_signal.get("org_type", 0),
        "geography_score": by_signal.get("geography", 0),
        "annual_revenue_score": by_signal.get("revenue_band", 0),
        "produces_content_score": by_signal.get("produces_content", 0),
        "gambling_score": gambling_points,
    }
```
This writes **only the 5 component-score properties**
(`org_type_score`/`geography_score`/`annual_revenue_score`/`produces_content_score`/
`gambling_score`) — it does **not** write `lv_org_type`/`lv_produces_content`/
`lv_country_region_normalized` themselves. Those three canonical inputs must be written by a
*separate* step this phase adds (the Claude web-research write, per D-08) before
`compute_components()` has anything meaningful to read.

```
[VERIFIED: scripts/backfill_seed_company_scores.py:88, "batch_update_companies" import; 236-237 call site]
```
`batch_update_companies()` itself lives in `src/hubspot_client.py:88-116`, not in the backfill
script — the backfill script only imports and calls it (line 50 import, lines 236-237 call
site inside a `_chunked()` loop, `BATCH_CHUNK_SIZE = 100`).

```
[VERIFIED: scripts/backfill_seed_company_scores.py:85]
```
`HARD_CEILING_RECORDS = 25` — confirmed, exact line.

```
[VERIFIED: scripts/backfill_seed_company_scores.py:19-22]
```
```
It NEVER computes or writes `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag` or
`lv_anti_icp_reason` — the calculated property, WF1, and the n8n pipeline already own those
respectively; a second producer on a field that already has one is exactly what D-01's veto
handover in 40-05 removed.
```
Matches D-07's characterization. Note the docstring's own phrasing already distinguishes "the
calculated property, WF1" (which own `lv_icp_fit_score`/`lv_icp_tier`) from "the n8n pipeline"
(which owns the veto pair) — this is the same split the BLOCKING FINDING documents in more
detail; CONTEXT.md's D-07 collapsed the three into one undifferentiated "derived by X, Y, Z."

```
[VERIFIED: scripts/backfill_seed_company_scores.py:69-71]
```
```
# The five writable component properties this script is the ONLY thing in this plan
# allowed to write. lv_icp_fit_score/_tier/_flag/_reason are derived elsewhere and must
# never appear in a payload this script builds.
```
Matches D-07's "lines 19-20 and 70" citation (off-by-one on the exact line number, immaterial).

**`--ids` does not exist as a flag.** The actual CLI surface is:
```
[VERIFIED: scripts/backfill_seed_company_scores.py:198-203]
```
```python
parser.add_argument("--company-id", action="append", default=[], dest="company_ids",
                     help="Explicit company id to seed (repeatable). If omitted, the "
                          "sample is selected via search_records for companies with "
                          "at least one canonical lv_* input populated.")
```
`--company-id` is repeatable (append), not a single comma-separated `--ids` value. Passing it
17 times (or extending the script to also accept a comma-separated `--ids` alias) both work;
the flag name in CONTEXT.md's canonical references is imprecise and the plan should not assume
`--ids` exists literally.

**The count cap is a pure count check — it does not enforce identity.**
```
[VERIFIED: scripts/backfill_seed_company_scores.py:138-151]
```
```python
DEFAULT_MAX_RECORDS = 10
HARD_CEILING_RECORDS = 25
...
def enforce_sample_cap(sample_ids: list) -> bool:
    return len(sample_ids) <= _resolved_max_records()
```
Two load-bearing consequences for the plan:
1. Passing 17 explicit `--company-id` args will be **refused** unless `BACKFILL_MAX_RECORDS`
   is set to `>=17` (default is 10; clamped at the hard ceiling 25 either way).
2. This function checks *count*, not *membership*. D-12's claim that "the script refuses any
   ID not on the list" describes behavior the script does not currently have — when
   `--company-id` args are supplied they entirely *replace* the default HAS_PROPERTY search
   selection (`sample_ids = args.company_ids or _select_default_sample_ids()`), so the
   pinning D-12 wants is achieved structurally (only the 17 IDs given are ever fetched/PATCHed)
   but not via a refusal mechanism — there is no separate allowlist the script cross-checks
   IDs against. This distinction matters only if the plan literally claims "refuses any ID not
   on the list" as a tested behavior; it should describe the actual mechanism (explicit-args
   replaces search, nothing else is touched) instead.

**`_settle()` is a stability poll with no expected-value assertion.**
```
[VERIFIED: scripts/backfill_seed_company_scores.py:252-271]
```
```python
def _settle(company_id: str, prop: str, timeout: float = 120, interval: float = 5) -> None:
    """... Prints the final value -- this script has no assertion of its own on the
    result, Task 3's parity sweep is what checks correctness."""
```
It returns after two consecutive identical reads (a "stopped changing" signal, not a "reached
the right value" signal) or after `timeout`, printing either way — it never raises, and the
caller (`main()`) does not check the printed value. **D-10's "fail loudly on any record that
never settles" is not satisfied by reusing `_settle()` as-is.** The plan must wrap it (or the
near-identical `tests/scoring_fixtures.py::settle()`, same signature) with an explicit
post-poll assertion against the record's expected `lv_anti_icp_flag`/`lv_icp_tier` value, and
treat "settled to the wrong / still-stale value" (not just "timed out") as the failure
condition to raise on. This is new logic, not a drop-in reuse.

### `scripts/june_run_arm.py`

```
[VERIFIED: scripts/june_run_arm.py:12-29]
```
Confirmed pattern: `ALLOW_N8N_ARM` env-var kill switch checked inside `n8n_arming` (not
duplicated here); `--ids` (comma-separated, **this script does use `--ids`**, unlike the
backfill script) parsed by `_parse_ids()`; disarm mode (`--disarm`) calls
`n8n_arming.disarm()` and is **not gated on `ALLOW_N8N_ARM`** — confirmed at lines 80-97 (the
`disarm()` function takes no `ALLOW_N8N_ARM` check at all, only `arm()` does implicitly via
`n8n_arming.arm_for_dispatch()`). An empty `--ids` at arm time is refused before any network
call (lines 54-62). This is the ceremony D-11 wants to mirror if the plan needs to arm n8n at
all (see BLOCKING FINDING).

### `src/hubspot_client.py`

```
[VERIFIED: src/hubspot_client.py:16-21, 88-116, 119-128]
```
- `get_record(object_type, record_id, properties: list[str])` → single record fetch.
- `batch_update_companies(updates: list[dict], dry_run=True)` → raises `ValueError` for
  `len(updates) > 100`; an empty list or `dry_run=True` short-circuits with no network call
  (prints the payload, no headers/token ever printed).
- `search_records(object_type, filters: list[dict], properties: list[str], limit=100)` →
  single `filterGroup` (AND within it; no native OR across properties — matches
  `_select_default_sample_ids()`'s own per-property loop-and-union workaround comment).

### `src/web_research.py`

```
[VERIFIED: src/web_research.py:15-25, 74-116]
```
`REQUIRED_FIELDS` (9 fields): `lv_org_type`, `lv_produces_content`, `lv_content_type`,
`lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`,
`lv_country_region_normalized`, `lv_has_sports_media_fit`,
`lv_has_broadcast_or_streaming_signals`. `USE_MOCK_WEB_RESEARCH` (default `"true"`) switches
between a fixture read and the live path. Live path: `Anthropic()` client (reads
`ANTHROPIC_API_KEY` ambiently), model from `ANTHROPIC_RESEARCH_MODEL` env var (default
`"claude-sonnet-5"`), `max_tokens=4096` (a deliberate bump from 2000 per an inline `ponytail:`
comment — 2000 was observed truncating responses before `evidence_by_field` was written),
`tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": <WEB_RESEARCH_MAX_SEARCHES, default 5>}]`.
Returns a `ProviderResult` (`src/schemas.py:18-28`) with `evidence: ProviderEvidence`
(`evidence_urls: List[str]`, `evidence_summary: Optional[str]`) **and** a separate
`evidence_by_field: Dict[str, str]` (per-field evidence URL, added Phase 13/OC-1) — this is the
shape D-09's per-field evidence stamping should pull from directly (`result.evidence_by_field
.get("lv_org_type")`) rather than only the general `evidence.evidence_urls` list.

### `src/icp_scoring.py`

```
[VERIFIED: src/icp_scoring.py:34]
```
```python
def compute_icp_score(record: HubSpotRecord, candidate_patch: dict, cfg: dict = None) -> ICPScoreResult:
```
Confirmed: `cfg=None` override exists exactly as CONTEXT.md describes (Phase 46 addition, used
by `scripts/simulate_rubric_weights.py`). `backfill_seed_company_scores.py`'s
`compute_components()` calls it with the two-positional-arg form (loads the on-disk
`config/icp_scoring.yaml` by default) — confirmed current, unaffected by this phase.

### `config/field_policy.yaml` / `config/icp_scoring.yaml`

Both confirmed current and matching CONTEXT.md's characterization exactly:
- `lv_org_type.require_evidence_url_for`: `governing_body_league`, `content_producer`,
  `hardware_vendor`, `gambling_operator` — `[VERIFIED: config/field_policy.yaml:52-59]`.
- `lv_produces_content.require_evidence_url: true` — `[VERIFIED: config/field_policy.yaml:61-66]`.
- Rubric of record post-Phase-46: `individual_club_team: 15`, `regulator: -20`,
  `graduated_deductions: {}` (gambling deduction removed) —
  `[VERIFIED: config/icp_scoring.yaml, full file read]`.
- Hard vetoes: `non_anz` ("Non-ANZ geography"), `no_content` ("No broadcast or streaming
  content"), `hardware_vendor` ("Hardware/AV/LED vendor, not sports-media buyer") —
  `[VERIFIED: config/icp_scoring.yaml, hard_vetoes block]`. These three exact strings are what
  the n8n Decide node's `vetoReasons` array pushes verbatim (confirmed identical text in both
  places).

## Provenance correction: "T-40-22"

CONTEXT.md's D-07 and its canonical references cite "a T-40-22 offline guard" by that name. No
test function or file in this repo is literally named `T-40-22` —
```
[VERIFIED: scripts/backfill_seed_company_scores.py:123-124]
```
```
never lv_icp_fit_score/_tier/_flag/_reason (T-40-22's offline guard, asserted in
tests/test_backfill_seed_company_scores.py)."""
```
`T-40-22` is a **plan-task label** (Phase 40 Plan 07's Task 2 verification-criterion ID), not a
test's Python identifier — the actual guard is `tests/test_backfill_seed_company_scores.py`
(module-level; the specific assertions cover `batch_update_companies()`'s dry-run
short-circuit and `build_updates()`'s payload shape — 5 `def test_batch_update_*` functions
confirmed by direct read, none individually named `T-40-22`). The plan should cite the file,
not invent a matching test function name.

## The derived-field chain (D-07 detail, corrected)

```
lv_org_type / lv_produces_content / lv_country_region_normalized  (this phase writes, via web research)
        |
        +--> org_type_score / geography_score / produces_content_score / annual_revenue_score /
        |    gambling_score  (this phase writes, via compute_components() + batch_update_companies();
        |    ALSO independently recomputed by 5 live HubSpot-native Automation flows that enroll
        |    on the same input properties changing — org-type-score 4626124224, geography-score
        |    4626722240, annual-revenue-score 4626722237, produces-content-score, gambling-score.
        |    Both the direct-write and the native-flow re-derivation converge on the SAME values,
        |    so a settle poll may observe one flap before stabilizing -- benign, not a bug.)
        |
        v
lv_icp_fit_score  (HubSpot `calculation_equation` property — sums the 5 component scores;
        |          pure formula, fires the instant all 5 terms are present; no n8n needed)
        v
     WF1 (4625147345)  (HubSpot-native Automation; enrolls on lv_icp_fit_score OR
        |               lv_anti_icp_flag becoming known; buckets score into A/B/C/Unscored,
        |               OR forces D if lv_anti_icp_flag=="true"; WRITES ONLY lv_icp_tier)
        v
   lv_icp_tier   <-- settles via pure HubSpot automation, NO n8n execution required

lv_anti_icp_flag / lv_anti_icp_reason
        ^
        |  ONLY writer: "Decide Company Action" Code node inside n8n/wf_enrichment_cloud.json.
        |  Recomputes unconditionally from (region, produces_content, is_hardware_vendor) on
        |  every execution of that node. Requires the n8n workflow to actually run for the
        |  record -- see BLOCKING FINDING for the two viable trigger mechanisms.
```

**What "settle" observably looks like:** for `lv_icp_fit_score`/`lv_icp_tier`, poll and expect
the value to change once (stale → correct) within roughly the same latency window
`backfill_seed_company_scores.py`'s own defaults assume (120s timeout, 5s interval;
`tests/scoring_fixtures.py::settle()`'s docstring cites "mapper latency at 4-25s and tier at
~3s" as the measured live basis for those defaults). For `lv_anti_icp_flag`/
`lv_anti_icp_reason`, the settle window depends entirely on which trigger mechanism the plan
picks: mechanism (a) (direct webhook POST) should settle within a single n8n execution's
wall-clock time (seconds); mechanism (b) (`scheduled_arm.py`) depends on its own dispatch
timing, not the 5s/120s defaults tuned for the pure-HubSpot chain.

## VETO-03 acceptance search (verbatim)

The hard-veto reason string, confirmed byte-identical in both the Python oracle
(`config/icp_scoring.yaml`'s `hard_vetoes.non_anz.reason`) and the live n8n Decide node
(`vetoReasons.push("Non-ANZ geography")`), is exactly:

```
Non-ANZ geography
```

Because `lv_anti_icp_reason` is a join of however many vetoes fired
(`vetoReasons.join("; ")` / Python `"; ".join(anti_reasons)`), a record with multiple
simultaneous vetoes (plausible here — Simtech LED could plausibly carry both a genuine
`hardware_vendor` veto AND, before remediation, the stale non-ANZ one) will have this substring
*inside* a longer string, not as the whole field value. The HubSpot search a RevOps person runs
must therefore be:

- Filter 1: property `lv_anti_icp_reason`, operator **"contains exactly"** (not "is equal to"),
  value `Non-ANZ geography`.
- Filter 2 (AND): property `lv_country_region_normalized`, operator **"is unknown"** (HubSpot's
  native blank/not-set filter — equivalent to a negated `HAS_PROPERTY`).

Zero results = VETO-03 satisfied. Both property names are confirmed live per CLAUDE.md §4.0's
`lv_`-prefix convention and directly read from `config/icp_scoring.yaml` /
`config/field_policy.yaml` this session — not re-verified against the live portal's property
list in this research pass (reasonable to assume live since both properties are read/written
throughout the confirmed-live scoring chain above), but the plan should have the operator
actually run this search once as its own acceptance step regardless.

## Cost estimate inputs (D-03 / COVER-02)

**The $0.0686/record figure's actual provenance:**
```
[VERIFIED: .planning/workstreams/milestone/phases/20-lusha-v3-migration/20-04-SUMMARY.md]
```
Canary execution 332, 2026-07-30: "full e2e enrich of one company burned 0 provider credits
(repeat records) and $0.0686 Anthropic ($0.052 Haiku research 48k-token prompt + $0.017 Sonnet
judge at intro pricing)."

**This figure is measured on a different code path than the one D-08 selected.** The $0.0686
figure covers the n8n pipeline's Haiku-research-then-Sonnet-judge chain. D-08 chose the
standalone Python `src/web_research.py::claude_web_research()` path — a single
`claude-sonnet-5` call using the native `web_search` tool (`max_uses` default 5), with no
separate Haiku pass. That call's cost has not been separately measured in this repo. Two things
the plan's cost estimate should account for that the $0.0686 figure does not:
1. Anthropic's native `web_search` server tool bills **per search** in addition to token cost
   (up to 5 searches/record at `WEB_RESEARCH_MAX_SEARCHES` default), a cost component the
   Haiku-research path's $0.0686 figure did not incur.
2. **If trigger mechanism (a) or (b) from the BLOCKING FINDING is used to clear the veto**, and
   any of the 17 lands on `lv_org_type` ∈ `{hardware_vendor, content_producer,
   governing_body_league, gambling_operator}`, re-running the n8n workflow's "Research Trigger
   Gate" will independently decide research is still needed for that record — confirmed by
   direct read of the gate's compiled JS:
   ```
   [VERIFIED: n8n/wf_enrichment_cloud.json, "Research Trigger Gate" node's jsCode]
   ```
   ```js
   const EVIDENCE_GATED_ORG_TYPES = ["content_producer", "gambling_operator",
     "governing_body_league", "hardware_vendor"];
   function needsResearch(existingRecord) {
     const rec = existingRecord || {};
     const orgType = rec.lv_org_type;
     const orgUnresolved = !orgType || orgType === "" || orgType === "unknown" ||
                           EVIDENCE_GATED_ORG_TYPES.indexOf(orgType) !== -1;
     const pc = rec.lv_produces_content;
     const contentBlank = pc === undefined || pc === null || pc === "";
     return orgUnresolved || contentBlank;
   }
   const ALLOW_WEB_RESEARCH = true;  // hardcoded true at build time, not an env override
   const MAX_WEB_RESEARCH_PER_RUN = 10;  // per-execution cap; irrelevant when dispatched per-record
   ```
   This gate does **not** check whether evidence is already present for the org type — it
   fires purely on membership in `EVIDENCE_GATED_ORG_TYPES`. Per D-17, Simtech LED
   (`hardware_vendor`), Editix and The Rumble/Pacific Action Sports (plausibly
   `content_producer`) are candidates for a second, redundant research call — a real second
   Anthropic cost, not merely a theoretical one, if mechanism (a)/(b) is invoked after the
   Python-side write already populated `lv_org_type` for those records. `ALLOW_WEB_RESEARCH` is
   a build-time literal (`true`), not something a per-invocation payload can override without a
   workflow redeploy — the plan cannot suppress this per-record via a webhook payload flag.

**Direct batch-PATCH path (input-population + component-score-write) costs ~0 n8n executions,
Anthropic cost only** for the 17 web-research calls (D-08's chosen mechanism) — this part of
D-06/D-08 is confirmed accurate.

**n8n allowance:** 2,500/month (per project memory `n8n-execution-budget.md`). 17 executions
(mechanism a) is trivial against this; verify the actual number if mechanism (b) is chosen,
since `scheduled_arm.py`'s chunk size is config-driven, not fixed.

## Rule 1 fallout risk

Grepped `tests/` for direct references to any of the 17 IDs or to `41-final-population.json`
(the source-of-truth roster these company-level tests key off): no test currently references
any of the 17 pinned IDs by literal value. The only live consumers of
`41-final-population.json`-shaped data are `tests/test_june_candidates.py` and
`tests/test_simulate_rubric_weights.py` (both operate on the full 66-row/712-row population,
not per-ID assertions) and the fixture `tests/fixtures/companies_jscode_frozen.json` (a frozen
byte-identical snapshot — check whether it embeds any of the 17's current blank/D-tier state as
an expected value before this phase changes it live).

The one test class this phase will make **newly relevant** rather than newly broken:
`tests/test_scoring_parity.py::test_veto_clear_after_correction` and its 4 excluded siblings
(`test_veto_set_all_three_hard_vetoes` ×3, `test_veto_set_multiple_reasons_join`) — these were
already known-failing before this phase for the exact structural reason this research
independently rediscovered. **Whichever trigger mechanism the plan picks should make these
pass** (or the plan should explain why not) — that would be a genuine, valuable side-effect
closing a standing gap, not scope creep.

The standing `scripts/run_scoring_parity.py` sweep is confirmed red-by-design per
`46-DECISION.md`'s "Parity red window" section (lines 274-299): it compares old-weight live
score against new-weight oracle for every `individual_club_team` row, independent of this
phase's veto work, and stays red until Phase 49. Expect it to fire during Phase 47; this is not
a new defect, and the plan should not attempt to fix it.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python), `node --test` (n8n JS fixtures) |
| Config file | none dedicated — invoked directly per project memory `test-suite-run-commands.md` |
| Quick run command | `.venv/bin/python -m pytest tests/test_scoring_parity.py -k veto -x` |
| Full suite command | `.venv/bin/python -m pytest` + `node --test tests/n8n/*.test.mjs` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VETO-01 | 17 records' inputs correctly populated, component scores computed correctly | unit (offline) | `.venv/bin/python -m pytest tests/test_backfill_seed_company_scores.py -x` | ✅ |
| VETO-01 | `lv_anti_icp_flag`/`lv_anti_icp_reason` actually clear on a corrected record | integration (live, disposable) | `.venv/bin/python -m pytest tests/test_scoring_parity.py::test_veto_clear_after_correction -x` | ✅ (currently failing — this phase should be expected to make it pass, or the plan must justify why not) |
| VETO-01 | Component-score math matches the oracle for each of the 17's actual data | manual read-back | operator reads each of the 17's post-write `lv_icp_fit_score`/`lv_icp_tier` in HubSpot | ❌ Wave 0 — no automated per-ID assertion exists; the plan should add one keyed to the 17 pinned IDs before/after values |
| VETO-02 | Write window armed with record-count cap, disarmed and read back | manual + script exit code | operator runs the arm/disarm ceremony per D-11/D-13; both `backfill_seed_company_scores.py`'s own two-key gate AND (if mechanism a/b used) `june_run_arm.py --disarm` read-back | ❌ Wave 0 — no test asserts the *disarmed* state was independently re-read; existing `n8n_arming.disarm()` does re-read per its own docstring, confirm this session's plan wires it in for the veto-clearing leg specifically |
| VETO-03 | HubSpot search returns zero | manual (script-free by design) | operator runs the verbatim search in "VETO-03 acceptance search" above | N/A — deliberately non-automatable per the requirement's own text |

### Sampling Rate
- **Per record:** poll-and-assert `lv_icp_fit_score`/`lv_icp_tier` (HubSpot-native, seconds)
  AND `lv_anti_icp_flag`/`lv_anti_icp_reason` (n8n-dependent, latency depends on trigger
  mechanism chosen) separately — they settle via genuinely different mechanisms and should not
  share one poll loop with one timeout.
- **Phase gate:** all 17 records read back with `lv_anti_icp_flag != "true"` OR (for the
  D-16-acknowledged legitimate-Tier-D-after-remediation cases, e.g. Simtech LED) a *different*,
  correct veto reason than "Non-ANZ geography" — before declaring VETO-01 satisfied.

### Wave 0 Gaps
- [ ] A per-ID before/after assertion script for the 17 (none exists; `run_scoring_parity.py`
      samples the wider population, not this specific cohort).
- [ ] An explicit "settled to expected value, not just stopped changing" wrapper around
      `_settle()`/`settle()` — see "Script surface corrections" above.
- [ ] Confirmation of which trigger mechanism (a) or (b) resolves the BLOCKING FINDING — this
      gap blocks writing any settle-assertion for the veto fields until resolved.

## Common Pitfalls

### Pitfall 1: Assuming the direct-PATCH cycle alone clears the veto
**What goes wrong:** Plan writes `lv_org_type`/`lv_produces_content`/
`lv_country_region_normalized` + 5 component scores, waits for `lv_icp_tier` to settle to a
real letter, and declares VETO-01 done — while `lv_anti_icp_flag` silently stays `"true"` and
`lv_anti_icp_reason` stays `"Non-ANZ geography"`, because nothing in the direct-PATCH path ever
touches them.
**Why it happens:** `lv_icp_tier` visibly changes (via pure HubSpot automation) in the same
timeframe, creating a false impression that "the derived chain settled."
**How to avoid:** Poll `lv_anti_icp_flag`/`lv_anti_icp_reason` separately, with an assertion
against the *expected* value, not just "stopped changing" — see BLOCKING FINDING and Validation
Architecture above.
**Warning signs:** VETO-03's HubSpot search still returns non-zero after the write window
closes.

### Pitfall 2: Redundant web research on evidence-gated org types
**What goes wrong:** Triggering the n8n workflow to clear the veto re-runs Claude web research
on records whose `lv_org_type` is `hardware_vendor`/`content_producer`/
`governing_body_league`/`gambling_operator`, doubling the Anthropic spend for those ~4 records
and potentially producing evidence that conflicts with what the Python-side write already
stamped.
**Why it happens:** `Research Trigger Gate`'s `needsResearch()` checks org-type membership, not
evidence presence.
**How to avoid:** Budget for this explicitly in the cost estimate (COVER-02), or find a way to
suppress it (not currently possible via payload — `ALLOW_WEB_RESEARCH` is baked `true` at build
time).
**Warning signs:** A second `Claude Web Research` node execution in the n8n execution log for
one of the 17, with a different evidence URL than the Python-side write recorded.

### Pitfall 3: `--company-id` vs `--ids`, and the default record cap
**What goes wrong:** Plan literally invokes `--ids <17 comma-separated>` (doesn't exist) or
forgets `BACKFILL_MAX_RECORDS=17` (default cap is 10, below 17) and gets refused with no write
performed.
**How to avoid:** Use 17 repeated `--company-id` args (or extend the script with a comma-list
alias) and set `BACKFILL_MAX_RECORDS` explicitly.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Direct HubSpot API PATCH to `lv_country_region_normalized`/`lv_org_type`/`lv_produces_content` does NOT trigger any live HubSpot webhook subscription that dispatches to the n8n enrichment workflow (relies on CLAUDE.md §20.2's "MVP subscriptions" list, which only names `lv_enrichment_requested`, not independently re-checked against the live portal's webhook subscription config this session) | BLOCKING FINDING, point 3 | If wrong (a live subscription on one of these properties already exists), the direct-PATCH write alone might already dispatch n8n — softening but not eliminating the BLOCKING FINDING (the Decide node's `ALLOW_HUBSPOT_RECORD_WRITES`/`TEST_RECORD_IDS` gate would still need arming either way) |
| A2 | `scheduled_arm.py`'s `chunk_ceiling` config value is not "2" as a hardcoded constant, and the plan must read the live config before assuming any specific chunk size | BLOCKING FINDING, mechanism (b) | If the live config value is small (e.g. 2), 17 records would need multiple dispatch cycles inside one armed window — changes VETO-02's window-shape estimate |
| A3 | VETO-03's search property names (`lv_anti_icp_reason`, `lv_country_region_normalized`) exist live in the portal exactly as named in config files — not independently re-confirmed against a live HubSpot properties listing this session (only against `config/*.yaml` and the JS/flow files that reference them) | VETO-03 acceptance search | Low — every source consulted this session agrees on these exact names, and CLAUDE.md §4.0 already establishes the `lv_`-prefix convention as portal-verified |

## Sources

### Primary (HIGH confidence — direct file reads this session)
- `.planning/phases/47-veto-remediation/47-CONTEXT.md` — full read
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — full read
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md` — 17 pinned IDs, tier distribution
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-DECISION.md` (lines 270-300) — parity red window
- `scripts/backfill_seed_company_scores.py` — full read
- `scripts/june_run_arm.py` — full read
- `src/hubspot_client.py` — full read
- `src/web_research.py` — full read
- `src/icp_scoring.py` — full read
- `src/schemas.py` — partial read (class definitions)
- `config/field_policy.yaml`, `config/icp_scoring.yaml` — full read
- `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json` — full read
- `config/hubspot_flows/4626722240-geography-score.after.json` — full read
- `n8n/wf_enrichment_cloud.json` — "Decide Company Action" and "Research Trigger Gate" node jsCode, targeted read
- `tests/test_scoring_parity.py` (lines 441-466) — `test_veto_clear_after_correction`
- `tests/test_backfill_seed_company_scores.py` — partial read (test names)
- `tests/scoring_fixtures.py` (lines 111-129) — `settle()`
- `operator-claude-plugin/scripts/n8n_arming.py` — partial read (OVERLAY_DISABLED_LITERALS, docstring)
- `operator-claude-plugin/scripts/scheduled_arm.py` — grep only (chunk/config references)
- `.planning/workstreams/milestone/phases/20-lusha-v3-migration/20-04-SUMMARY.md` — $0.0686 figure provenance

### Secondary (MEDIUM confidence)
- `.planning/milestones/v0.7-phases/40-scoring-engine-remediation-notes/40-03-SUMMARY.md` — grep-only, direct webhook POST live-validation attempt narrative
- `.planning/STATE.md`'s own Phase 40-03/40-05/40-07 entries — narrative history of the veto write-path's known issues, cross-checked against the code and found consistent

### Tertiary (LOW confidence / not independently re-verified live)
- CLAUDE.md §20.2's webhook subscription list — flagged stale/unverified by CLAUDE.md's own §4.0 delta note; used only as a directional signal for Assumption A1

## Metadata

**Confidence breakdown:**
- 17 pinned IDs and exclusions: HIGH — directly read and recounted from the source table
- Script surfaces (backfill, arm, hubspot_client, web_research, icp_scoring): HIGH — every
  cited line read directly this session
- Write-mechanism BLOCKING FINDING: HIGH on the code facts (multiple independent file reads
  converge); MEDIUM on "these are the only two viable trigger mechanisms" (a reasonable but not
  exhaustive scan of the codebase's arming infrastructure)
- Cost estimate: MEDIUM — the $0.0686 baseline figure's source is solid but is acknowledged
  measured on a different code path than the one this phase uses
- Live webhook subscription state (Assumption A1): LOW — not independently re-verified against
  the live portal

**Research date:** 2026-08-11
**Valid until:** short — this research is tightly coupled to the exact deployed n8n workflow
JSON and HubSpot flow JSON committed as of this date; any Phase 48/49 deploy that touches
`n8n/wf_enrichment_cloud.json`'s "Decide Company Action" or "Research Trigger Gate" nodes
invalidates the BLOCKING FINDING's specifics (re-grep before relying on it if more than a few
days pass, or if any n8n deploy has occurred in the interim).
