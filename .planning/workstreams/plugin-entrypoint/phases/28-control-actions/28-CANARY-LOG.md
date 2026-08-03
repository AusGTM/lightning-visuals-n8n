# 28-CANARY-LOG — RB-7 / plan 28-06, the armed arm→dispatch→disarm cycle

**Status: RUN 2026-08-03. The cycle PASSED — armed, dispatched, disarmed, all read-back verified,
bounded to one record.** Step 6 alone was not observed and is recorded as a miss rather than
inferred. Four findings below, one of which raises the priority of a known open bug.

**Verdicts at a glance:** arm **verified** · dispatch **execution 1152, success** · disarm
**verified** · armed window **54.37 s** · after-state **disarmed PASS, 5 workflows / 11 nodes** ·
decline path **proven from the execution trail** · only the allowlisted record written.

---

## Pre-flight — established read-only, 2026-08-03, before any arming

GETs only. No arm, no deploy, no write.

| Item | Value |
|---|---|
| Lane | **enrichment** (step 1's preferred branch; `enrichment.dispatch_enrichment` shipped in Phase 25) |
| Target workflow | `950HPb7a1GgSAIyZ` — `LV Enrichment (Cloud template)`, `active=true` |
| Record allowlist | `9604614548` — one HubSpot **company** id, the test company Probe B4 and the Phase 22 canary used |
| Domain allowlist | *(empty)* |
| `allow_create` | `false` — an update to an existing company, not a create |
| `control` capability | passes against the installed `operator.local.json` |
| Tenant | `https://alexherman.app.n8n.cloud` |

**Flag state BEFORE, read live via `n8n_read.read_write_safety` across every deployed workflow.**
`(Nn)` is the count of declaring nodes.

```
Cj83mOgrIm59oxcX  active=True   'LV Backend Status (Cloud template)'   — no write-safety declarations
AwbBeShdPgV48eiY  active=True   'LV Contact Ingest (Cloud template)'
      ALLOW_HUBSPOT_RECORD_WRITES='false'(2n)  ALLOW_HUBSPOT_CREATE='false'(3n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(2n)  TEST_RECORD_IDS=''(2n)  TEST_RECORD_DOMAINS=''(2n)
950HPb7a1GgSAIyZ  active=True   'LV Enrichment (Cloud template)'        <-- TARGET
      ALLOW_HUBSPOT_RECORD_WRITES='false'(2n)  ALLOW_HUBSPOT_CREATE='false'(2n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(2n)  TEST_RECORD_IDS=''(2n)  TEST_RECORD_DOMAINS=''(2n)
WBJwoZOo63wzeP69  active=False  'LV Review Decision (Cloud)'
      ALLOW_HUBSPOT_RECORD_WRITES='false'(2n)  ALLOW_HUBSPOT_CREATE='false'(2n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(2n)  TEST_RECORD_IDS=''(2n)  TEST_RECORD_DOMAINS=''(2n)
1fXPuIabz3RsAHgn  active=True   'LV Scheduled Maintenance (Cloud)'
      ALLOW_HUBSPOT_RECORD_WRITES='false'(4n)  ALLOW_HUBSPOT_CREATE='false'(4n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(4n)  TEST_RECORD_IDS=''(4n)  TEST_RECORD_DOMAINS=''(4n)
```

No disagreement was reported on any flag in any workflow.

### Two things the operator should expect, recorded before the run so they are not mistaken for defects

1. **The reload gap does not bite on this path.** `n8n_control.apply_mutation` brackets its PUT with
   deactivate → PUT → restore-prior-active, and the target is active, so the arm's activate forces
   the running instance to reload the armed content *before* the verify GET. The disarm uses the same
   bracket. The gap found under RB-3 was in `deploy_n8n_workflows.py`, which never activates.
2. **`dispatch_fn` is not wired by the surface.** `plan_action(kind="arm_dispatch")` composes the
   proposal; `execute_action` calls `proposal["dispatch_fn"]`; neither `control_actions.py` nor
   `backend-control/SKILL.md` says who sets it. The plugin session has to. **This is a finding about
   the shipped surface** — record below whether the session wired it unaided, needed the runbook's
   snippet, or got it wrong.

**Step 6, pre-computed from source (still to be confirmed live):** the plugin's
`_render_literal(True)` produces `"true"` and the deploy script's `_OVERLAY_FLAG_SPEC` enabled
literal is `"true"` — identical by construction. Allowlist values: plugin `json.dumps("9604614548")`
vs deploy's comma-separated quoted string — also identical for a single id. A difference here would
be a genuine surprise.

---

## The run — to be filled in by the operator

### Step 0 — installed plugin refreshed
- Plugin updated: ☐ / verdict:
- `skills/backend-control/SKILL.md` opens with the "Where commands run" note: ☐

### Step 2 — flag state BEFORE, re-read fresh — **DONE 2026-08-03T03:27:46Z**

**A. Phase 27 status surface, target workflow** (`python3 scripts/status.py 950HPb7a1GgSAIyZ`):

```
LV Enrichment (Cloud template)   active: true
  ALLOW_HUBSPOT_RECORD_WRITES = "false"  nodes: [Decide Action, Decide Company Action]  disagreement: null
  ALLOW_HUBSPOT_CREATE        = "false"  nodes: [Decide Action, Decide Company Action]  disagreement: null
  last_run: 1116  success  2026-08-03T01:11:53.127Z → 01:11:55.846Z   in_flight: false  stuck: false
```

The same call's `backend` block returned `"available": false, "reason":
"unrecognized_response_shape"` with every count `unknown` — **the known open client-side bug** (the
webhook array-wraps its answer; curl shows real data). Recorded so it is not read as a sick backend.

**B. Full-tenant flag inventory**, all five overlayable flags, every deployed workflow. `(Nn)` =
declaring-node count; no `disagreement` on any flag in any workflow:

```
Cj83mOgrIm59oxcX  active=True   'LV Backend Status (Cloud template)'   — no declarations
AwbBeShdPgV48eiY  active=True   'LV Contact Ingest (Cloud template)'
      RECORD_WRITES='false'(2n)  CREATE='false'(3n)  REVIEW_WRITES='false'(2n)  IDS=''(2n)  DOMAINS=''(2n)
950HPb7a1GgSAIyZ  active=True   'LV Enrichment (Cloud template)'        <-- TARGET
      RECORD_WRITES='false'(2n)  CREATE='false'(2n)  REVIEW_WRITES='false'(2n)  IDS=''(2n)  DOMAINS=''(2n)
WBJwoZOo63wzeP69  active=False  'LV Review Decision (Cloud)'
      RECORD_WRITES='false'(2n)  CREATE='false'(2n)  REVIEW_WRITES='false'(2n)  IDS=''(2n)  DOMAINS=''(2n)
1fXPuIabz3RsAHgn  active=True   'LV Scheduled Maintenance (Cloud)'
      RECORD_WRITES='false'(4n)  CREATE='false'(4n)  REVIEW_WRITES='false'(4n)  IDS=''(4n)  DOMAINS=''(4n)
```

**C. Execution baseline — the line that makes "nothing was sent" checkable.**
Highest execution id at 03:27:48Z is **1147**. Ids 1144–1147 are `Cj83mOgrIm59oxcX` (LV Backend
Status) and are this read's own `status.py` calls, not backend activity. The target workflow
`950HPb7a1GgSAIyZ` has had **no execution since 1116** (01:11:53Z).

> **Therefore: any execution on `950HPb7a1GgSAIyZ` with an id above 1147 belongs to this canary.
> The decline path must produce none.**

### Step 3 — the decline path — **PASSED**

The consequence named both required things before any confirmation was possible:

> Action: enable live writes on `LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`) for one send.
> Before → After: live writes off → live writes on for this send only.
> Bounded to: exactly 1 record id — `9604614548` (0 domains). The backend cannot write any record
> outside that list. `allow_create: false`. Auto-disarm: writes turn off the moment the send
> finishes. If disarm fails, you'll be told explicitly and an admin must check n8n — never assumed.

- Names what live writes permit: **YES**
- Names the single record the grant is bounded to: **YES**
- Declined. **Nothing was sent — proven from the execution trail, not asserted.** The decline was
  ~03:31Z, the approval ~03:38Z, and the only enrichment execution in that interval is **none**;
  `950HPb7a1GgSAIyZ` ran exactly once above the 1147 baseline (id 1152, 03:38:34Z). The two
  executions between them (1150, 1151) are `Cj83mOgrIm59oxcX` backend-status reads from the cost
  preview, which cost nothing and write nothing.
- **`dispatch_fn` wiring: from the runbook snippet.** The session read `28-CANARY-LOG.md` and
  `OPERATOR-RUNBOOK.md` to find it. **The predicted gap is CONFIRMED** — see Findings.

### Step 4 — the accepted run — **VERIFIED**

- **Arm read-back:** verified — record-scoped to `9604614548` only.
- **Dispatch landed:** n8n execution **1152**, `success`, 03:38:34.566Z → 03:39:13.152Z.
- **Disarm read-back:** verified — all flags back to `false`, allowlist empty.
- **Armed-window wall-clock: 54.37 s.** Against the ~100 s n8n Cloud ceiling.

**Derived, and worth keeping:** the dispatch itself took **38.59 s** (execution 1152's own
start→stop, independently observed — and consistent with B4's 37.44 s). So arm + disarm overhead is
**≈ 15.8 s**, which is the figure a future window should budget on top of its dispatch. The bound is
comfortable for one record and would be **tight at the chunk ceiling of 2** (2 × 38.6 + 15.8 ≈ 93 s
against ~100 s).

### Step 5 — the HubSpot outcome

Company `9604614548` = **Melbourne Racing Club**. `hs_lastmodifieddate` moved to 03:39:12Z, inside
execution 1152's window.

| Field | Value | Status |
|---|---|---|
| `lv_org_type` | `individual_club_team` | `provider_only` |
| `lv_content_type` | `live_broadcast` | `provider_only` |
| `lv_country_region_normalized` | `AU` | `provider_only` |
| `lv_employee_band` | `201-500` | `provider_only` |
| `lv_sponsorship_reliant` | `true` | `provider_only` |
| `lv_enrichment_status` | `needs_review` | — |

**Staged, NOT promoted:** `industry` — provider says `arts, entertainment, and recreation` against
the current `SPORTS`. Held as a review candidate ("Refresh candidate requires review in MVP"), current
value untouched. **This is the non-clobber policy working on a real record**, which no stub test can
demonstrate.

No ICP score fields were written: the record landed `needs_review`, so tier/score promotion did not
fire. That is correct behaviour, not a miss.

**No other record touched.** Checked three ways: `950HPb7a1GgSAIyZ` has exactly one execution above
the baseline (1152); the arm was bounded to one id with zero domains; and the disarm read-back shows
`TEST_RECORD_IDS=''`.

### Step 6 — literal-shape comparison — **NOT OBSERVED LIVE (a real miss, recorded as one)**

The armed declaration text was **never fetched while the window was open**, and it is now
unrecoverable: the cycle auto-disarms as one action, so by the time anyone could look the literals
were already back to `"false"`. n8n retains no history reachable with this key —
`/api/v1/workflows/<id>/versions` → `404 {"message":"Version not found"}`,
`/rest/workflow-history/workflow/<id>` → `401 Unauthorized`.

**Do not write "the literal shapes match" in this log.** What IS established:

- **By source:** the plugin's `_render_literal(True)` yields `"true"`; the deploy script's
  `_OVERLAY_FLAG_SPEC` enabled literal is `"true"`. Identical by construction, and pinned by
  `tests/test_control_flag_parity.py`, which reads the deploy table as text.
- **By behaviour:** the write landed for the allowlisted record, which requires the *running*
  workflow's `_writeSafetyAllows()` to have parsed both the enabled flag and the allowlist. That
  proves the arm was *functional*; it does **not** prove the literal was byte-identical, since a
  different-but-parseable literal would also have worked.

**Amendment for the next armed canary:** step 6 as written is unsatisfiable by an operator, because
the cycle it inspects closes itself. To observe it, either read the workflow from a second shell
during the window, or have `arm_for_dispatch` return the raw declaration text it wrote. **Prefer the
second** — it makes the check an artifact of the arm rather than a race against it.

### Step 7 — flag state AFTER — **PASS, three independent reads**

1. **Full-tenant inventory, 03:40:40Z** — every overlayable flag `false`/`''` in all five workflows,
   no declaring-node disagreement.
2. **Phase 27 status surface** on the target — `ALLOW_HUBSPOT_RECORD_WRITES="false"`,
   `ALLOW_HUBSPOT_CREATE="false"`, both nodes, `disagreement: null`.
3. **`verify_live_write_safety.py --expectation disarmed`:**

```
expectation: disarmed
coverage: 5 workflow(s) fetched, 11 declaring node(s) found
  ... every node: ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false'
      ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS=''
VERDICT: disarmed PASS
```

- Disarming redeploy: **deliberately not run — see Findings.** The read-back gate it exists to
  protect already passes on all 11 nodes, and a no-bounce PUT is now a *risk*, not a safety net.
- `ALLOW_N8N_ARM` unset again: ☐ *(operator to confirm)*

---

## Findings

**1. `dispatch_fn` is unwired by the shipped surface — CONFIRMED, as predicted.**
`plan_action(kind="arm_dispatch")` composes the proposal; `execute_action` calls
`proposal["dispatch_fn"]`; neither `control_actions.py` nor `backend-control/SKILL.md` says who sets
it. The session recovered it only by reading the planning artifacts. **A canary should not need the
runbook to drive the surface it is testing.** Either `plan_action` should build the dispatch for a
known lane, or `SKILL.md` must carry the wiring.

**2. The two-skill seam: one operator intent, no cross-reference.** The operator's single sentence —
"enrich company X with live writes on" — is *two* authorities: `enrich-records` dispatches, and only
`backend-control`'s `arm_dispatch` grants live writes. `enrich-records` correctly refused to
overreach, but **nothing in it points at the lane that completes the request**, so the operator had
to re-prompt to reach the armed action. Worth noting that the failure was safe in both directions:
the first pass ended staged-only with nothing armed. **Recommend a forward reference in
`enrich-records/SKILL.md`** naming `backend-control` as the arming lane.

**3. The known `unrecognized_response_shape` bug has an operational cost, not just a cosmetic one.**
During the cost preview it made **all three provider balances unreadable**, so the operator armed
live writes **without confirmed credit headroom**. The preview reported this honestly ("could not be
confirmed — not a report that there is enough"), which is the right behaviour, but the underlying
client-side array-unwrap defect is now demonstrably degrading a **safety** surface rather than a
convenience one. **This raises its priority.** Post-run, Lusha read 3932 credits — so the data was
there the whole time and only the client could not read it.

**4. Step 7's belt-and-braces redeploy is now counter-indicated.** It was written before the
stored-vs-running reload lesson. `deploy_n8n_workflows.py` PUTs without activating, so running a
redeploy now would update *stored* content while the *running* instances keep serving the old body —
manufacturing exactly the divergence that RB-3 was burned by. Its protective value here is nil:
`_assert_only_declaration_lines_changed` structurally bounds an arm to declaration lines, so no
non-declaration drift is possible, and the read-back passes on all 11 nodes. **Either drop the step
for API-side arm/disarm cycles, or require a bounce of every active workflow immediately after it.**
`DRY_RUN=true` cannot settle it either way — it lists all five workflows unconditionally rather than
diffing.
