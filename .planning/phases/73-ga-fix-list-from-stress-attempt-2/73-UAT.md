# Phase 73 Plan 07 — Operator Gate Record (73-UAT.md)

This file is the single gate record for phase 73: Task 1's pre-flight (Claude, offline),
Task 2's release cut, and Task 3's live attempt-3 record (operator only, per D-73-18).

---

## Pre-flight (Task 1 — Claude, 2026-09-16, offline)

### 1. Idempotent regeneration

```
.venv/bin/python scripts/build_cloud_workflows.py
git status --porcelain -- n8n/
```

Regeneration ran clean; `git status --porcelain -- n8n/` printed nothing. **Zero diff —
the committed tree is exactly what the builder produces.**

### 2. Node counts, reconciled against the six SUMMARYs

| Workflow | Node count (this run) | Reconciliation |
|---|---|---|
| `wf_backend_status_cloud.json` | 30 | Unchanged from the pre-phase-73 baseline (CLAUDE.md §13.0.2, Phase 72 gate: 30). 73-05 (F-B6) added a second outbound edge on `Build Credit Status` to an existing node — an edge, not a node — matching 73-05-SUMMARY.md's own description ("`Build Credit Status` now has two outbound edges instead of one"). |
| `wf_contact_ingest_cloud.json` | 80 | +2 from the pre-phase-73 baseline (69 → 78 at Phase 72 gate). Verified by walking `git log` per-commit node counts on this file: 78 held through 73-02's throttle widen and 73-03's companies-domain-IN-query change (param/logic edits, no new nodes), then 79 after 73-06's "identity-join HubSpot Create's outcome, replacing positional pairing" commit (+1, the pair node) and 80 after 73-06's "the create_failed refusal lane (D-73-01)" commit (+1, the failure-row node) — exactly the two nodes 73-06-SUMMARY.md names ("the pair node, the failure-row node, and the `alwaysOutputData` fix", the last of which is a property flag, not a node). |
| `wf_contact_ingest_local.json` | 13 | Unchanged (stable baseline; no plan in this phase modified the local ingest lane). |
| `wf_enrichment_cloud.json` | 287 | Unchanged from the pre-phase-73 baseline (287, Phase 72 gate). 73-03 touched this file for the companies freemail refusal and the domain IN-query, but reused existing conflict-detection/decide nodes rather than adding new ones — consistent with 73-03-SUMMARY.md recording no node-count claim and describing only jsCode/config changes. |
| `wf_enrichment_local.json` | 10 | Unchanged (stable baseline). |
| `wf_enrichment_local_live.json` | 82 | Unchanged from the pre-phase-73 baseline (82, Phase 72 gate). 73-03-SUMMARY.md explicitly records this file was touched by shared-constant changes only in Tasks 1–2 and NOT by Task 3 (its own `ENRICH_DECIDE_CO_LOCAL` node is a dry-run echo), so no node-count change is expected. |
| `wf_review_decision_cloud.json` | 55 | Unchanged (stable baseline, Phase 72 gate: 55). 73-02's `reviewApply()` array-serialization fix (F-E1) is a jsCode edit inside the existing node, not a new node — matches 73-02-SUMMARY.md's description of the fix location. |
| `wf_scheduled_maintenance_cloud.json` | 43 | Unchanged (stable baseline, Phase 72 gate: 43). 73-02 regenerated this file only because it inlines the same `reviewApply.js` source as the review-decision lane. |

Every count reconciles to a named change from a specific plan/commit in this phase, or to the
pre-phase-73 baseline where no plan claimed a node-level change. No unexplained count.

### 3. Execution order and armed-write check

```
.venv/bin/python -c "import json,glob,sys; bad=[p for p in glob.glob('n8n/wf_*.json') if json.load(open(p)).get('settings',{}).get('executionOrder')!='v1']; print('NON_V1:',bad); sys.exit(1 if bad else 0)"
# -> NON_V1: []  (exit 0)

/usr/bin/grep -c 'ALLOW_HUBSPOT_RECORD_WRITES = "true"' n8n/wf_contact_ingest_cloud.json n8n/wf_enrichment_cloud.json
# -> both 0

/usr/bin/grep -oE 'ALLOW_[A-Z_]+ = .true.' n8n/wf_*.json | sort -u
# -> (no output — no ALLOW_* flag is true anywhere in any generated body)
```

Every generated body carries `settings.executionOrder: "v1"` and zero armed write flags.

### 4. Both suites, against HEAD baselines

| Suite | Baseline | This run |
|---|---|---|
| `node --test tests/n8n/*.test.mjs` | 1170 pass / 0 fail | **1215 pass / 0 fail** |
| `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` | 4952 passed / 154 skipped | **4990 passed / 154 skipped** |

Both suites are at or above baseline. Zero failures.

### 5. Todo triage (CLAUDE.md §31 zero-inbox)

```
.venv/bin/python scripts/todo_triage.py
```

```
question   major    2026-08-04-enrichment-throughput-ceiling.md
design     major    2026-09-04-company-domain-has-no-candidate-source.md
question   major    2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md
design     minor    2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md
defect     minor    2026-09-12-rows-to-resume-current-outcomes-never-wired-fingerprint-branch-dead.md
counts: {'question': 2, 'design': 2, 'defect': 1} | debt (defect): 1
```

Exit code 0, `.venv/bin/python -m pytest -q tests/test_todo_triage.py` passes (2/2). All five
pending todos are typed (`question`/`design`/`defect`) and pre-date this phase — none was
opened by phase 73's own plans, and none requires a decision to reach this gate.
**`.planning/todos/pending/` contains no untriaged file.**

### Pre-flight verdict

All five checks pass. The tree is deployable, idempotent, disarmed, green, and zero-inbox.
Handed to the operator for Task 3.

---

## Release (Task 2 — Claude, 2026-09-16)

`operator-claude-plugin/.claude-plugin/plugin.json` bumped to `0.50.0`; matching
`CHANGELOG.md` entry added in the same commit. `tests/stress-tests/RUNBOOK.md` restart step 4
corrected: two of the three companies-CSV known-gap rows (freemail, LinkedIn-only/name-only)
now exercise this phase's fixes rather than documenting open gaps; only the name+TLD case
(Perth Racing, F-B2, D-73-07) remains a documented known gap. Nothing pushed.

---

## Attempt 3, Stages A–F (Task 3 — operator-driven, 2026-09-17/18)

Backend state at start: Phase 73 bodies deployed + bounced disarmed 2026-09-16, node counts
30/80/287/55/43, all `executionOrder: v1`; portal reset confirmed (21 protected). Plugin
0.50.0. Write autonomy on; every send armed/dispatched/disarmed in-session. Every "verified"
claim below is a re-read (dispatch reconciliation against the write node output, or the
review skill's own post-write re-read), never a bare 200. No Webhook Trigger runData block is
reproduced anywhere.

### Baseline — "What's the backend doing?"

- Latest execution id: **12521**. All five workflows on, nothing running, every last run
  `success`, every declaring node disarmed.
- Provider balances: **Lusha 3714, ZoomInfo 9358** (both numeric — **F-B6 PASS**), Apollo
  `unknown` (accepted).
- Queues: companies awaiting review 37, contacts queued for enrichment 12.

### Stage A — contact-upload, no providers

- run_id `56ee1e8fb641415095457e82f5f0c10e`; ingest execution **12522** (single, `success`,
  `finished: true`).
- Preview: 48 rows → **46 sent** after within-batch dedupe collapsed data-rows 37 & 38
  (spreadsheet 38/39) onto row 3 (spreadsheet 4), key `email`, `duplicate_in_csv` — only the
  deduped file was sent (**F-A5 PASS**). 14 headers mapped, `UAT Marker` unresolved/dropped,
  `Mobile → mobilephone`. Grant priced **0 provider credits, 1 execution/POST, $0 model**
  (**F-A1/A2 PASS**).
- Outcomes (46): **21 created, 1 updated (1251), 23 held-for-review, 1 skip** — accounts to 46.
- **F-A6 PASS**: single execution ended `success`, no aborted batch. The `create_failed` lane
  was **NOT exercised** — F-A5's dedupe removed its within-batch-duplicate trigger; it stays
  offline-proven only (`tests/n8n/ingestCreateErrorLane.test.mjs`), never tagged observed-live.
- **F-A3r PASS**: 0 rows carry `lookup_failed`; 0 real HubSpot 429s (0 "secondly limit",
  0 `statusCode 429` in exec 12522 — the only "429" strings are jsCode comments); all three
  search nodes 0 run-level errors at the 400 ms throttle.
- **SAFE-01 PASS**: contact 1251 update wrote only `company` + `lv_contact_enrichment_provenance`;
  `phone` and `jobtitle` were not in the patch (untouched).
- Dense rows 3–14 created and associated (Priya, Ngaire, etc.); the two Perth Racing contacts
  held (domain `perthracing.com.au` ≠ portal `perthracing.org.au`) — held, not orphaned.
  Sparse/malformed/name-only/linkedin/gmail/Wagga rows all held with individual reasons.
- Created ids (21): 353468302798, 353544844756, 353559902704, 353575266784, 353706835398,
  353706835399, 353711755740, 353711755742, 353713485274, 353713485275, 353726313951,
  353727612384, 353729426917, 353731275233, 353731545539, 353764608448, 353764608449,
  353764608450, 353801897456, 353808039368, 353808039371.
- Boundary: disarmed (all flags false, allowlist cleared).

### Stage B — enrich-records companies, full waterfall

- run_id `ca0537929b26401384f361902039ce7e`; enrichment executions **12523–12545** (Decide
  Company Action on 12526–12542), all `success`.
- Domain table: 34 companies sent (33 domain + Illawarra name-only). Hawkesbury duplicate
  deduped; `vrc.com.au` / `thevalley.com.au` normalised; Gosford researched to
  `theentertainmentgrounds.com.au`; **gmail row refused client-side with the freemail reason**
  ("personal mailbox domain, not the company's own website") — never sent (**F-B3 PASS**);
  Illawarra LinkedIn declined to name-only.
- Outcomes (from runData): **6 created, 25 enriched-in-place, 1 review, 2 gate-skip** — 34,
  zero unaccounted (**F-B5 PASS**; the run report accounts every enrich/create per-record with
  real ids, and the 12 `research_failed` rows are intermediate lane markers, not counted as
  outcomes, never rendered unjoinable).
- **F-B1 PASS**: grant envelope priced Lusha **66 credits / 33 companies = 2 credits/company**.
- **F-B7 PASS**: Racing Victoria `18756544380`, Wyong `10215097384`, Canberra RC `10152138518`
  all matched (enriched in place), not recreated; HRNSW matched `10204524171` by name; Gosford
  matched `10021111653` under `www.theentertainmentgrounds.com.au`.
- **F-B2 (known gap, recorded, did not stop)**: Perth Racing **duplicated** as `288792344018`
  (CSV `perthracing.com.au` vs portal record `9604794662` under `perthracing.org.au` — name+TLD
  variant, D-73-07).
- **F-B4 PASS**: Illawarra held for review — "name-only row: no existing company matched by
  exact name; no domain — supply one" (names the match outcome, "no domain", and "supply one";
  no 400, no skip).
- Created ids (6): Perth Racing 288792344018, Pakenham Racing Club 288792344027, Murray Bridge
  Racing Club 288680762864, New Zealand Thoroughbred Racing 288590388676, Sky Racing
  288593932757, Wagga Wagga Rowing Club 288746741239.
- Veto cross-check (Decide properties): Daktronics + NYRA (`region=Other`) `lv_anti_icp_flag=true`
  Tier D; Tabcorp `lv_org_type=gambling_operator`, veto **false** (deduction only); Sky Racing
  `content_producer`, veto false; NZ Thoroughbred Racing `region=NZ`, veto false.
- Spend 51 executions, ceiling ok, disarmed at boundary.

### Stage C — suggest-contacts

- Run bounded to a representative eligible subset (full ~24-eligible-company crawl scoped for
  cost; eligibility auto-computation limited offline — see F-S3). Crawl dispositions: **HRV**
  cross-host redirect (hrv.org.au → thetrots.com.au) → refused, not chased; **RWWA** HTTP 429 →
  refused; **Moonee Valley** 404 → empty; **Greyhound Racing NSW** → own host served a board
  page, 5 people found.
- GRNSW: role filter (full offered list) + cap 2 → 2 proposals (Greg Johnson, Paul Gentle,
  Directors, board page as source). Stage-2 enrichment revealed `gjohnson@grnsw.com.au` /
  `pgentle@grnsw.com.au`; both email domains match `grnsw.com.au` → **2 sendable, 0 held**.
- Sent (run_id `ff9273df697346cb997e8660ac49f86a`) → **2 created and associated**, verified by
  re-read: **Greg Johnson `353745909199`** and **Paul Gentle `353575790047`**, both associated
  to GRNSW `9604630690`, both email domains equal the company domain.
- Boundary: disarmed.

### Stage D — enrich-before-ingest, providers ON

- match run_id `2950009377574a6cb1bfcb3ad4079795`; enrich run_id
  `34af8805e09245448034aa91fc547c4d`; match executions 12549–12551, enrich legs following.
- Match (48 rows): 18 auto-matched (handed to enrich-records, not re-ingested), 2 proposed,
  11 unmatched, 17 unchecked.
- Enrich pass recovered; **0 sendable, 11 held**. Sendable = 0 is correct per D-70-11 — a new
  person is never created without an explicit operator reply — so **no new contact landed
  incomplete**. All 11 held with a clear reason ("no match found — not confident enough to act
  without review"), including the Wagga rows (Hamish Ashdown) and the Perth/gmail contacts.
- **D-73-14 PASS**: the run-scoped manifest holds exactly this run's 11 rows; the run report's
  Held-rows section lists those 11 individually and shows the global held backlog (14)
  separately, labelled "NOT attributed to this run".
- Boundary: disarmed.

### Stage E — review triage

- run_id `05f8c46e9aca4e289d23365b969a701b`. Grant `lanes=["review"]`; armed review window
  scoped to `9604614548,9605273630` (`ALLOW_HUBSPOT_REVIEW_WRITES=true`, correct allowlist).
- **Approve** Melbourne Racing Club `9604614548`: backend `applied`; the write patch included
  **`lv_content_type` (the multi-checkbox field that returned a HubSpot 400 in attempt 2)** —
  it landed and verified as taking the approved value, **no 400 (F-E1 PASS)**. Business fields
  (industry, `lv_org_type`, `lv_content_type`, `lv_country_region_normalized`) landed.
- **Reject** Port Macquarie Race Club `9605273630` with a reason — "rejection reason recorded;
  the record stays in the review queue" (confirmed; record stays flagged).
- Left the other 39. written_records scoped to this run (`review_approve` + `review_reject`).
  Boundary: disarmed.

### Stage F — status and sweep

- Status delta: latest execution **12613** (baseline 12521 → **+92**, within the ~60–90 estimate;
  the +overhead is Stage E's read-only array-field scan, which ran 41 `preview_decision` calls).
  Nothing running, nothing running long, **nothing armed**. Lusha 3666 (baseline 3714, −48
  spent), ZoomInfo transiently `unknown (no_response)` (was 9358 numeric at baseline and in the
  Stage B grant), Apollo unknown.
- Sweep: **two named conditions** (a valid "named condition" outcome, not silence) —
  `burn_rate_alarm` (4.0 exec/hr → ~2850/30d vs 2500, inflated by today's UAT load, transient)
  and `review_backlog` (40 companies > 25 threshold). Both benign/expected for a heavy UAT day.

### Close-out — disarmed read-back

- **DISARMED PASS**: all five workflows active, `executionOrder: v1`, node counts
  **43/287/80/55/30** (Maintenance/Enrichment/Ingest/Review/Backend Status), zero armed flags on
  every declaring node. Node counts match Task 1's pre-flight record (30/80/287/55/43).
- The reset was **NOT run** (operator's step, per instruction).

### Findings table

| ID | Sev | Finding |
| --- | --- | --- |
| F-S1 | Low | No-provider ingest withholds `mobilephone` and `lv_linkedin_url`/`hs_linkedin_url`. On a CSV-only ingest every field is `source=csv, confidence 80`; these fields carry `fill_blank_only`@85, so 80 < 85 → `needs_review`, not promoted even into a blank field. By long-standing `field_policy` (not a Phase 73 regression). The Phase 72 live proof used a provider value at confidence 85, never csv/80; a provider pass (Stage D) is what fills them. The RUNBOOK's Stage A "Mobile + LinkedIn land" spot-check is optimistic for a *no-provider* run. |
| F-S2 | Medium | Web-research output validation rejects fenced JSON. The `Claude Web Research` node completes (haiku-4.5, `end_turn`, valid JSON with evidence URLs) but returns it wrapped in a ` ```json ` fence; the backend `Validate Research Output` node does not strip the fence → `research_failed` for ~12/18 companies in Stage B. Enrichment still completed on provider data, but web `lv_org_type`/`lv_produces_content`/`lv_content_type` were discarded → several records left `lv_org_type=None` and some fired spurious `no_content` vetoes (e.g. a `governing_body_league` with `produces_content=false`). The Python oracle's `_extract_json` strips fences; the deployed JS validator does not. |
| F-S3 | Low | suggest-contacts eligibility is not reconstructable outside the live batch response. `num_associated_contacts` is carried on the anonymous response rows but the Decide output carries the company id without the count, so the two cannot be joined from runData; with no direct HubSpot read available to the plugin, per-company eligibility could not be computed offline. Stage C was scoped to a representative eligible subset as a result. |
| F-S4 | Info | Stage D held the Wagga rows (41–42) as new-person creates rather than auto-associating them to the Wagga company created in Stage B — correct D-70-11 behaviour (a create needs an explicit operator "create N" reply), but newer than the RUNBOOK's "rows 41–42 now associate" expectation. Also: 17 of 48 match rows came back `unchecked` (a match chunk did not settle inside the recovery bound) — safely bucketed, not misclassified, re-checked on retry. |
| F-S5 | Medium | Review-approve verify reports overall `failed` on booleancheckbox fields set to `false`. Approving MRC landed every business field but `verify_decision` flagged `lv_is_hardware_vendor` and `lv_is_gambling_operator` as "did not take the approved value", because HubSpot stores an unchecked booleancheckbox as empty and returns empty (not "false") on re-read. This is a verify false-negative (false-vs-empty), not a real write failure — but it makes a successful approve read as `failed`, which would mislead an operator. |
| F-S6 | Low | F-E1's exact 2-element-array serialization case was not reproducible live. No review candidate in the reset portal's queue carries a multi-value array (`lv_content_type` was `unknown` or scalar everywhere — tied to F-S2's research failure), and D-73-19 forbids engineering a trigger. The `lv_content_type` multi-checkbox write path landed and verified (F-E1 PASS on its field), but the multi-element semicolon-join stays offline-proven only (`tests/n8n/reviewLoop.test.mjs`). |

### Verdict

Stage A and Stage E — the two that failed/partialled in attempt 2 — both **pass** in attempt 3:
Stage A wrote 21 creates + 1 update with no aborted execution, no 429, and the dedupe collapse
that made the batch safe; Stage E's array-field approve landed where attempt 2 took a 400.
Every stage boundary read disarmed, and the final read-back is DISARMED PASS on the v1 bodies
at the Task-1 node counts. Six findings recorded (two Medium: the web-research fence defect
F-S2 and the review-approve false-boolean verify false-negative F-S5); none blocked a stage.
The create-error lane (F-A6) and F-E1's multi-element array remain offline-proven only, by
design (D-73-19). Reset deferred to the operator.
