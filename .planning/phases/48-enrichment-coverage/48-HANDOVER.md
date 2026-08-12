# 48-HANDOVER.md — Enrichment Coverage

**Written:** 2026-08-12, after phases 47 and 47.5 closed. **Phase 48 is roadmapped, not planned.**
Next action: `/gsd-plan-phase 48`.

This file assumes you remember nothing about today. Everything here is sourced from the
artifacts named beside it; where a number could have moved since, it says so and tells you how to
re-derive it. Do not trust a count in this file over a live read.

---

## 1. Where the project is

| | |
|---|---|
| Milestone | **v0.9 — ICP Rubric Calibration & Veto Remediation** |
| Complete | Phase 46 (rubric decision + engine parity), Phase 47 (veto remediation), Phase 47.5 (veto recompute path) |
| **Next** | **Phase 48 — Enrichment Coverage (COVER-01 / COVER-02)** |
| After | Phase 49 — Re-score Strategy & Reporting (RESCORE-01/02/03) |

**Phase 48's goal, unchanged:** every scored company either has a real `lv_org_type`, or is
individually recorded as un-enrichable **with a stated reason that is distinguishable from
"never attempted"** (COVER-01) — spent through a write window whose cost is estimated before the
run against the 2,500/month n8n allowance and the current Lusha balance, reported after, and
**refused outright rather than truncated** if the estimate exceeds either budget (COVER-02).

Unlike Phase 47.5's recompute (free), this is a **full provider waterfall per record**. It is a
separable spend decision the operator approves on its own terms.

### Bookkeeping the seal will fix — do not be alarmed by it

At the time of writing, `.planning/ROADMAP.md`'s progress table still reads `47. Veto
Remediation 3/4 In Progress` and `47.5 6/6 In Progress`, and 47-04-PLAN.md's checkbox is
unticked. Phases 46/47/47.5 are all complete; `STATE.md` is authoritative and says so. This is
`phase.complete`'s job, not yours. **Do not pass `--ws` to `phase.complete`** — v0.8+ phases live
in root `.planning/` and the workstream guard misfires.

---

## 2. What changed under Phase 48's feet today — read this before planning

### 2.1 The recompute lane exists. Completing a record no longer freezes its veto.

Until this morning, `Company Gate` returned `action: "skip"` for any company whose enrichment
inputs were all present, fresh and valid, and `Normalize + Score Company` dropped every skipped
row — so **`Decide Company Action`, the only writer of `lv_anti_icp_flag` / `lv_anti_icp_reason`,
never ran.** A record with complete inputs could not have its veto recomputed by any trigger.
The better a record's data, the less able the system was to correct its scoring.

**This mattered to Phase 48 specifically**, and the old ROADMAP text said so: filling
`lv_org_type` *completes* a record, so Phase 48 was going to **enlarge** the frozen-veto
population. **It no longer does.** Phase 47.5 shipped:

- `IF Company Recompute` — routes a request carrying `recompute: true` straight from
  `Company Gate` to `Decide Company Action`, bypassing providers, research, judge and merge.
- `IF Company Skip` — a skipped record now terminates observably at `Build Response` with its
  gate reason, instead of a silent 200.

The intent is a **request-level boolean on the D-18 webhook POST body**, normalized in
`Parse HubSpot Event` *after* the event spread. It is deliberately **not** a `mode` value:
`isReturnOnly()` treats any non-`"write"` mode as return-only, so a mode-borne intent would
report success and write nothing.

```
POST {N8N_URL}/webhook/hubspot/enrichment/event    header: X-Enrichment-Secret
body: the usual D-18 event + "recompute": true
helper: scripts/remediate_veto_companies.py::post_webhook_event(..., recompute=True)
```

Measured cost over executions 11858–11861: **0 provider credits, 0 Anthropic calls, 1 n8n
execution per POST.**

Three things it does **not** change, each of which has bitten someone:

1. **Arming is still required to PATCH.** Exec `11858` ran the whole lane, derived the correct
   veto, and returned `action: "write_blocked"` on an empty allowlist. Deriving is free; writing
   is not.
2. **The scheduled poller carries no `recompute` intent.** SJ-3 and every other scheduled path
   still gate-skip a complete record. The lane is on-demand only.
3. **`Decide Company Action` is still the single veto writer.** Do not add a second.

Documented in `CLAUDE.md` §13.0 and `docs/OPERATOR-VETO-REFRESH.md`'s 2026-08-12 amendment.

### 2.2 The hardware veto now fires on `lv_org_type`, retroactively

Commit `f817ec5`, in **both** engines (`src/icp_scoring.py` and the `Decide Company Action` node
built by `scripts/build_cloud_workflows.py`), per Phase 46's parity rule:

```js
if (isHardwareVendor === true || orgType === "hardware_vendor") …
```

**Direct consequence for Phase 48:** any record you classify `hardware_vendor` acquires a hard
veto and lands Tier D. That is correct and intended — but it means Phase 48's enrichment can
*create* vetoes, not only fill blanks. Budget your after-report for it. Simtech LED
`18047161864` moved Tier B → D on exec `11861` with **zero input writes**, purely on the new
predicate via the recompute lane.

`lv_is_gambling_operator` was checked and needs no equivalent change (zero divergent records;
gambling is a graduated deduction and `graduated_deductions` is `{}` since Phase 46 D-03).

### 2.3 `lv_org_type` IS an enumeration in HubSpot — several docs said otherwise

Corrected in today's sweep. The text→enumeration migration **ran**
(`config/hubspot_migration/org-type-enum-manifest-5973fa43-*.json`); the newest committed live
schema snapshot, `config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json`
(2026-08-08), reads `type: enumeration` / `fieldType: select` with **9 options**, mirrored by
`config/hubspot_properties.yaml`.

Why this is a Phase 48 trap, not trivia:

- **An out-of-vocabulary `lv_org_type` write 400s, and in a batch it fails the batch.**
  `scripts/remediate_veto_companies.py:142`'s stated reason for its strict allowlist is
  **correct**; the decision record that called it wrong has been amended.
- **`venue` is not one of the nine options.** The LOCKED decision
  `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md` says `venue` implements in
  Phase 48 and that "no portal work is required" — that clause is **false**. Adding `venue`
  requires adding a HubSpot **enum option** to `lv_org_type` first (a property-options PATCH via
  `scripts/sync_hubspot_properties.py` / the yaml). That respects the no-new-**properties**
  constraint but is portal schema work needing its own arming decision. A dated correction block
  now sits at the top of that decision file.
- The three normalization layers (D-V4) are still all required. The CRM guard stops a bad value
  reaching the *record*; it does not stop it reaching the *write* and breaking a batch, and
  `.get(org_type, 0)` still scores an unrecognised key **0, silently**.

**Re-list the live property before writing anything to it.** A committed snapshot is evidence,
not a guarantee.

---

## 3. The records Phase 48 owns

Phase 47 attempted `lv_org_type` on 17 pinned companies and its strict enum gate refused to
guess-map free-text research output. **Four ended Phase 47 with no `lv_org_type`**
(`47-04-SUMMARY.md` § "Not closed here"):

| id | name | note |
|---|---|---|
| `17317381378` | Editix | |
| `17317850381` | **Jam TV** | Italian broadcaster `jamtv.it`. **Correctly vetoed (D-23) and must stay vetoed.** Its blank region is why Phase 46 mislabelled it `false_veto`. Filling its org type must not clear its veto |
| `20538284384` | Waikato | |
| `20943964946` | The Rumble | |

Plus, per D-02 (`REQUIREMENTS.md` COVER-01's own amendment):

| id | name | note |
|---|---|---|
| `15008671672` | Racing NSW | flagged `blank_org_type` only, never in Phase 47's false-veto cohort — explicitly left to Phase 48 |

**COVER-01's "18 scored companies" figure is a stale census.** It predates Phase 47, which
resolved `lv_org_type` for 13 of the 17. Neither "18" nor "5" should be planned against —
**re-derive the population live at planning time** (`lv_org_type` blank across the scored
population) and record the number you got with its date. `47-02-SUMMARY.md` records the D-02
split: neither Phase 47 nor Phase 48 may claim full COVER-01/COVER-02 closure alone.

Phase 47 recorded two remediation options for the low resolution rate, neither taken:
(a) constrain `src/web_research.py`'s `RESEARCH_SYSTEM` prompt to the enum and re-research — a
paid re-run, the operator's cost call; (b) a cheap narrowly-scoped classification pass over the
**already-captured evidence** in `47-RESEARCH-RESULTS.json` — no new web search needed. (b) is
the obvious first move for the four above. See `47-03-SUMMARY.md` § "Coverage is low but honest".

---

## 4. Hard rules that bind Phase 48

| Rule | Detail |
|---|---|
| **D-07** | **Never PATCH `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_icp_fit_score`, `lv_icp_tier`.** Write inputs; let the derived chain settle; read it back. Held absolutely through both of 47.5's windows |
| **No new HubSpot properties** | Standing v0.9 constraint. Adding an *option* to an existing enumeration is not a new property — but it is still portal schema work (see §2.3) |
| **Arming is operator-only again** | `D-47.5-01` and its amendment delegated arming **and** `ALLOW_N8N_DEPLOY` to Claude **for phase 47.5 only**. Both **EXPIRED with the phase.** Do not carry them forward, do not cite them |
| **Deploys are operator-only** | Same expiry. `scripts/deploy_n8n_workflows.py` needs `DRY_RUN=false` **and** `ALLOW_N8N_DEPLOY=true` in one invocation, and a **bounce** after |
| **Never hand-edit `n8n/wf_*.json`** | Edit `scripts/build_cloud_workflows.py` / `n8n/code/*.js`, rebuild, deploy, bounce |
| **Parity rule (Phase 46)** | Any scoring-predicate change lands in **every** engine holding it, in **one** commit |
| **Declare the window count up front** | Phase 47 needed five arm/disarm cycles against a must_have of one and disclosed it in `47-RUN-REPORT.md`. Phase 47.5's correction was declaring "two windows" before opening either, and using exactly two. Do the same |
| **`.env` is Read/Bash permission-blocked** | Drive live work through the dotenv form: `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); …"`. `python-dotenv`'s bare `load_dotenv()` resolves relative to the **calling file**, not the cwd — with no `conftest.py`, live pytest needs a wrapper passing an **absolute** `.env` path or every HubSpot read 401s |
| **Tests** | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` — **glob form**; the directory form is broken on node 24, and system python lacks the deps |
| **`run_scoring_parity.py`'s population sweep is RED BY DESIGN** until Phase 49 | Do not "fix" it. Oracle-vs-live parity is Phase 49's scope |

---

## 5. Traps that cost real time today — do not re-pay them

1. **n8n `status: "success"` lies.** A node can receive a `400` and pass the error object
   downstream **as data**, with `executionStatus: "success"` and zero node-level errors. Judge a
   run by node-level `runData`, never by execution status. (`47-BLOCKED.md`; live exec `11833`.)
2. **A client POST timeout is not a failure.** n8n completes server-side. Phase 47's driver
   hardcoded a 30s read timeout and fired against runs n8n had already finished;
   `post_webhook_event` now defaults to **300s**. Never retry on timeout without reading the
   execution back first — that is how a record gets touched twice.
3. **Stored ≠ running.** A bare `PUT /api/v1/workflows/{id}` stores JSON but does **not** reload
   a running workflow; n8n keeps executing the old in-memory code. Bounce (deactivate →
   reactivate), then prove it with an **independent** GET or, better, one live execution's own
   node list. Reading the stored JSON back proves only that storage changed.
4. **An EMPTY allowlist denies every write and still reports `armed`.** `TEST_RECORD_IDS=""`
   arms successfully and blocks everything. Assert the allowlist is non-empty **and** exactly the
   intended id set, in the driver, at arm time — not by eyeball.
5. **`isReturnOnly()` treats any non-`"write"` mode as return-only.** Anything you carry as a
   `mode` value on a write path will report success and write nothing. Request-level row
   properties, not modes.
6. **Duration is a cheap tell.** A 2.4s enrichment execution against a normal 10–37s means the
   chain died early. Check node counts (a healthy company recompute is 20 nodes disarmed,
   21 armed — the extra one is `HubSpot Company Update`).
7. **`ENRICH_CO_GATE` is shared by three workflows**, only one of which has a
   `Parse HubSpot Event` node. Any `$()` read of a request-level property must be wrapped in the
   repo's `nodeAll` try/catch idiom and **fail closed**, or the SJ-2 daily sweep throws on every
   row.

---

## 6. Open items Phase 48 should know about but does not own

- **`.planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-failure.md` — still open,
  still real.** When `Claude Web Research` gets a 400 (e.g. Anthropic credit exhausted), the
  execution reports success and the error object flows into the merge/normalize path as if it
  were a `ProviderResult`. Observed producing plausible-looking `lv_revenue_band` /
  `lv_employee_band` values for a record research never actually returned. **Phase 48 is a
  research-heavy, armed, budget-bounded run — this is the failure mode most likely to poison it.**
  At minimum, check Anthropic credit before arming and verify each run's research node returned a
  `ProviderResult` shape rather than an `error` shape. Fixing it properly (fail the execution, or
  gate immediately after the node) is not scoped anywhere yet.
- **Phase 49 must still re-examine Entain `10024564084`.** It was excluded from 47.5's window on
  *arithmetic* — `lv_produces_content = false` fires a second veto, so a region flip would spend
  a touch and leave it Tier D — **not** on a geography finding. Its actual ANZ operating presence
  has never been examined.
- **Phase 49 must confirm Jam TV `17317850381` stays vetoed** (D-23). Portal-wide non-ANZ veto
  census stands at **2** (Entain + Jam TV, both correct), down from 4. The VETO-03 bar (non-ANZ
  veto AND blank `lv_country_region_normalized`) reads **0 rows**.
- **A live `D` → non-`D` tier *transition* is still not independently proven** as a transition.
  End states are right; the reads are 1–2s apart. Phase 49's scope, not Phase 48's.
- **Gravity Media `15860277364`'s `ANZ` rests on Australian operating presence alone.** Its NZ
  leg is **UNPROVEN** and recorded as such. `ANZ` denotes the multinational-with-local-operations
  pattern per D-V6, not a count of countries.

### Docs known stale, deliberately not edited (judgement calls)

- **`docs/SYSTEM-CONTRACT.md`** § "Boundary of responsibility" still says computing "ICP scores,
  tiers, or vetoes" is out of scope by design (Approach C). Since Phase 40-05 the n8n pipeline is
  the **sole** writer of `lv_anti_icp_flag` / `lv_anti_icp_reason`. The document's own header says
  "change the contract deliberately, not by drift" — so this needs an operator decision, not a
  sweep edit.
- **`.planning/workstreams/milestone/STATE.md`** (v0.5-era, last touched 2026-07-30) carries the
  same false "`lv_org_type` is `string/text`, not an enumeration" line among many other
  superseded claims. It is a historical workstream state superseded by root `.planning/STATE.md`;
  not worth maintaining. Do not cite it.
- **`CLAUDE.md` §12.7's `compute_icp_score` listing** is the local-MVP prototype: it keys the
  hardware veto off the boolean only and its `graduated_deductions["gambling_operator"]` lookup
  would now `KeyError` against the shipped config. Flagged in §10.3.1 rather than rewritten —
  §11/§12 are deliberately the old local-first prototype.

---

## 7. Source artifacts (ground truth, in reading order)

```
.planning/STATE.md                                     current position, decisions log
.planning/ROADMAP.md                                   Phase 48 / 49 goals and success criteria
.planning/REQUIREMENTS.md                              COVER-01/02 text + the D-02 split
.planning/phases/47.5-veto-recompute-path/
    47.5-CONTEXT.md            the defect, the three workstreams, D-47.5-01 (both waivers, EXPIRED)
    47.5-RUN-REPORT.md         armed window #2: pre-arm guard, per-record outcomes, cost actuals
    47.5-C-DECISION.md         the hardware-veto OR decision + deploy record
    47.5-B-EVIDENCE.md         D-V6 operating-presence research with evidence URLs
    47.5-01..06-SUMMARY.md     per-plan detail
.planning/phases/47-veto-remediation/
    47-04-SUMMARY.md           § "Not closed here" — the four records
    47-RUN-REPORT.md           § "Window accounting" — the five-window disclosure
    47-RESEARCH-RESULTS.json   already-paid research output for all 17 pinned companies
    47-COST-ESTIMATE.md        the ex-ante cost-estimate pattern COVER-02 wants
.planning/decisions/2026-08-12-org-type-venue-and-normalization.md   D-V1..D-V6 (+ 08-12 correction)
.planning/todos/completed/2026-08-12-*.md              the two findings 47.5 closed
CLAUDE.md §4.0, §10.3.1, §13.0, §19.0, §19.1           the as-built deltas
docs/OPERATOR-VETO-REFRESH.md                          amended 2026-08-12
docs/WEB-RESEARCH-SPEC.md                              the research contract (enum note corrected)
docs/ORG-TYPE-ENUM-MIGRATION.md                        rollback runbook (cheap window now CLOSED)
```

Live executions worth diffing if the lane misbehaves: `11845` (healthy enrich) vs `11846` (the
original defect) vs `11858` (recompute, disarmed, `write_blocked`) vs `11859`/`11860`/`11861`
(recompute, armed, wrote).
