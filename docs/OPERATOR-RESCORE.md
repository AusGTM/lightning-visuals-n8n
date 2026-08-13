# Operator procedure: re-scoring the population after an ICP rubric change

## AS-BUILT AMENDMENT — 2026-08-13 (Phase 49)

**Corrects the `## Acceptance` section's line:** *"if it is red, the rubric and the live
records still disagree, and the fix is to finish the re-score, not to loosen the
comparison."*

The first half stands; **the prescribed fix is incomplete**, and W1's live exercise proved
it. A red sweep has two distinct causes, and only one of them is cured by finishing the
re-score:

1. **Records not yet written** — re-running `--execute` fixes these. This is the case the
   original line assumed, and for it the original line is correct.
2. **Records whose components were already correct before the window opened** — re-running
   `--execute` can **never** fix these, no matter how many times it runs. Their PATCH is
   value-identical, HubSpot treats a same-value write as a no-op, no property-change event
   fires, and the workflow that grades `lv_icp_tier` from the score never re-enrolls. The
   score is right and the tier is stale, permanently, from this mechanism's point of view.

W1 hit case 2 on four records (`9605273630`, `9604738976`, `17696004613`, `19100977027` —
logged as `.planning/WINDOWS.md` entries 9–12). **If a sweep is red and the affected
records' components already match the oracle, stop — do not re-run `--execute` expecting a
different result.** That is the signature of case 2, and the durable fix is to make the
tier derive from the score rather than be written by a workflow — a design proved viable in
`.planning/TIER-DERIVATION-SPIKE-2026-08-13.md` and scheduled as its own phase, since it
requires a new CRM property.

The sweep is still never edited to make it pass. That part of the original line is
unconditional and unchanged.

---

**Applies from:** Phase 49 Plan 02 (RESCORE-01/RESCORE-02, D-07/D-08,
`.planning/phases/49-re-score-strategy-reporting/49-CONTEXT.md`)

Read this document **before** deciding whether to re-score, and before running anything.
Every number below is copied verbatim from a committed, code-produced capture — never
hand-typed — so the doc and the capture cannot silently drift apart (D-07). The capture
this document cites: `.planning/phases/49-re-score-strategy-reporting/49-PLAN-OUTPUT.json`,
produced by `scripts/rescore_population.py --plan` against the live portal.

---

## Step 1 — classify the change (do this first, before any write)

Did the rubric change touch a **hard-veto predicate** — non-ANZ geography, no
broadcast/streaming content, or hardware-vendor?

```
Did the change touch a VETO predicate?  (non-ANZ / no-content / hardware-vendor)

  NO  → weight branch:  component backfill only
                        0 n8n exec | 0 Anthropic | 0 provider credits
  YES → veto branch:    backfill + one recompute POST per record
                        ~66 n8n exec (2.6% of the 2,500/month allowance)
                        0 Anthropic | 0 provider credits
```

**Weight branch (NO).** A rubric edit to `base_score` (org type, geography, revenue band,
produces-content weights) or `graduated_deductions` that does not touch a hard-veto
predicate. Cost: component backfill only — **0 n8n executions, 0 Anthropic calls, 0
provider credits**. This is the branch this document's procedure below actually runs.

**Veto branch (YES).** A rubric edit that changes which category fires a hard veto (for
example, adding a new hardware-vendor org type, or changing what counts as ANZ). Cost:
the same component backfill **plus one recompute POST per record**. That per-record cost
is **measured, not estimated** — Phase 47.5 clocked the recompute lane at exactly 1 n8n
execution per POST, 0 provider credits, 0 Anthropic calls, across executions `11858`
through `11861` (`.planning/phases/47.5-veto-recompute-path/47.5-RUN-REPORT.md`;
`docs/OPERATOR-VETO-REFRESH.md`'s AS-BUILT AMENDMENT). Applied to this document's own
66-record population that unit cost totals **66 n8n executions (2.6% of the 2,500/month
allowance)** — see `veto_branch_cost_documented_not_exercised` in the committed capture.
**This branch is documented here, and has not been run.** No live recompute POST has been
sent as part of writing this document. If you are on the veto branch, the vehicle is
`scripts/remediate_veto_companies.py::post_webhook_event(..., recompute=True)` — read
`docs/OPERATOR-VETO-REFRESH.md` before using it; do not improvise a POST body.

**Why this phase's own rubric change is NO.** Phase 46 changed three weights
(`individual_club_team` 5→15, `regulator` 0→−20, and removed the gambling graduated
deduction). None of the three touches hard-veto category membership — veto derivation
lives entirely in the n8n `Decide Company Action` node, keyed on `lv_country_region_normalized`,
`lv_produces_content`, and `lv_is_hardware_vendor` / `lv_org_type == "hardware_vendor"`, none
of which Phase 46 edited. **This NO answer is specific to Phase 46's own change. It is not
a general rule.** A different rubric edit — adding an org type, changing what counts as
ANZ, changing the no-content or hardware-vendor logic — must be re-classified against
Step 1 above; do not assume NO by default.

---

## Why the whole population, every time

There is no `lv_icp_scoring_version` property on any company record, and there will not
be one — a standing no-new-properties constraint for this project. That means a record
scored under a superseded rubric cannot be segmented out in a HubSpot list; there is no
field to filter on that says "scored before the last weight change." Any rubric change
therefore re-scores the **entire scored population**, wholesale, every time. That is the
reason RESCORE-02 exists, stated in plain language rather than left as a cross-reference.

---

## Which records

The scored population is every company that carries `lv_icp_fit_score` at all — a single
live HubSpot search (`HAS_PROPERTY(lv_icp_fit_score)`). This is the **same** definition
`scripts/run_scoring_parity.py` and `scripts/simulate_rubric_weights.py` deliberately
share; there is no second definition anywhere in this codebase, and this document does
not introduce one.

The population is **re-derived live on every run** — it is never carried as a saved list
or a cached id set. The most recent capture, read live and stamped at run time:

- **Population count: 66** (`population_count` in the capture, `derived_at`
  `2026-08-13T04:01:11.038812+00:00`).

The portal holds 712 companies. Only 66 have ever carried a score. **Every count in a
re-score report describes that fraction of 66 — not the full portal of 712.** Say this
once, plainly, because it is easy to misread a re-score report as describing the whole
CRM.

---

## Chunk size and window shape

From the same capture:

- `chunk_size`: **100** — HubSpot's batch-update endpoint accepts at most 100 updates per
  call.
- `chunks`: **1** — the 66-record population fits in a single batch call.
- `max_records`: **100** — the resolved safety ceiling for this invocation
  (`BACKFILL_MAX_RECORDS`, defaulted to the driver's `HARD_CEILING_RECORDS`).
- `window`: **W1** — the re-score's own declared write window (see D-05 in
  `49-CONTEXT.md`); this document only covers W1.
- `arm_keys`: **`DRY_RUN=false`, `ALLOW_SCORE_BACKFILL=true`** — both required together.
- `arms_n8n_allowlist`: **false**.

That last line is worth explaining operationally: the weight branch's write authority is
a Python-side environment gate on a **direct HubSpot CRM batch call** — no n8n allowlist
is armed, no n8n execution is spent, because the write never goes near n8n at all. Arming
an n8n record-write allowlist for a weight re-score would widen the blast radius for no
reason (D-05) — do not do it, and do not expect the driver to ask for it.

---

## The exact-set gate — stronger than a count cap

The driver refuses to write to anything except the **exact** live-derived scored
population — not a count under a ceiling, the exact set. A count cap of 100 would permit
*any* ≤100-record sample, including a stale snapshot, a hand-typed list missing a few
records, or a search result caught mid-race. The exact-set gate refuses everything except
the live-derived population, including a smaller subset of it. If you see the raised
ceiling (25 → 100) in the code, do not read it as a relaxation — it is paired with this
stronger gate, which is the actual enforcement mechanism now.

---

## Engines first, then re-score

The backfill computes the five component scores from the Python oracle
(`config/icp_scoring.yaml` via `src/icp_scoring.py`). If a HubSpot flow is still carrying
the **old** weights when this re-score runs, that flow will silently overwrite the
correct, freshly-backfilled components with old-weight ones the next time any input
changes on that record. So a weight change must land in **both** engines —
`config/icp_scoring.yaml` **and** the HubSpot org-type score flow (`4626124224`) — in one
commit, with a running-content read-back confirming the deploy actually took effect,
**before** the re-score runs.

No work is owed on this today: Phase 46 already landed both engines for the weight change
this document's own capture reflects. This is a sequencing rule for the **next**
weight-changer to follow, not a step this run needs to repeat.

---

## The canary step

Before releasing the write to the whole population, the driver writes **one** record
first — chosen by rule at run time, never a hard-coded id — inside the same window,
settles it, and reads back `lv_icp_fit_score` and `lv_icp_tier` to confirm the write
landed correctly. Only then does it release the remainder.

Why this matters: HubSpot's default-value stamp on a property is not readable through the
API. Whether overwriting an already-stamped component behaves the same as writing a
never-set one is a question that can only be answered live — no amount of code reading
resolves it. The canary means that if there is a stamp-related surprise, it surfaces on
one record, not on the whole population.

---

## Invocation

`.env` is permission-blocked to read directly, and `python-dotenv`'s bare `load_dotenv()`
resolves relative to the *calling file* — with no `conftest.py` in play here, every live
invocation below passes `.env`'s **absolute path** explicitly. The driver defaults to
`--plan` (dry) when no mode flag is given, and the two arm variables
(`DRY_RUN=false`, `ALLOW_SCORE_BACKFILL=true`) are set **per-shell only** — never written
into `.env`, never exported into a profile, never left set in a shell that outlives the
window.

**Plan (dry, default, no arming, no writes):**
```bash
.venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env'); import runpy; \
   runpy.run_path('scripts/rescore_population.py', run_name='__main__')" --plan
```

**Snapshot (dry, read-only census, no arming, no writes — for P1/P2/P3 report points):**
```bash
.venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env'); import runpy; \
   runpy.run_path('scripts/rescore_population.py', run_name='__main__')" --snapshot
```

**Canary (armed — writes exactly one record, then settles and reads it back):**
```bash
ALLOW_SCORE_BACKFILL=true DRY_RUN=false .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env'); import runpy; \
   runpy.run_path('scripts/rescore_population.py', run_name='__main__')" --canary
```

**Execute (armed — writes the remainder, excluding the canary id already written):**
```bash
ALLOW_SCORE_BACKFILL=true DRY_RUN=false .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env'); import runpy; \
   runpy.run_path('scripts/rescore_population.py', run_name='__main__')" --execute --already-written <canary_id_from_the_canary_step_above>
```

Run `--plan` first, always, and review its printed output before arming anything.

---

## Acceptance

The proof that a re-score landed is `scripts/run_scoring_parity.py`'s live population
sweep exiting **green**. That sweep is the acceptance gate for every re-score, not just
this one, and it is **never edited to make it pass** — if it is red, the rubric and the
live records still disagree, and the fix is to finish the re-score, not to loosen the
comparison.

---

## AMENDMENT-block convention

Corrections to this document are **appended** as a dated block at the top (matching
`docs/OPERATOR-VETO-REFRESH.md`'s house style), never silently rewritten into the body.
If something below turns out to be wrong or incomplete once exercised live, add a new
`## AS-BUILT AMENDMENT — <date> (Phase <n>)` section immediately below this document's
title, state plainly which line(s) it corrects, and leave the original prose in place
underneath so the history of what was believed at each point stays readable.

One amendment has been made: **2026-08-13 (Phase 49)**, at the top of this document —
correcting the `## Acceptance` section's prescribed fix for a red sweep, after W1's live
exercise found a second cause the original line did not anticipate.
