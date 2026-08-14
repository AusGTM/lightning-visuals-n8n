# Operator procedure: rolling back `lv_icp_tier_derived` to WF1 (D-18)

**Applies from:** Phase 50 Plan 04 (D-18, `.planning/phases/50-derived-tier-property/50-CONTEXT.md`)

## AMENDMENT 2026-08-14 — D-24: WF1 no longer exists; both mechanisms below are GONE

**Read this before anything else in this document.** Everything below this amendment describes
a rollback mechanism that assumed WF1 (`4625147345`) was switched off but kept, per D-08. That
assumption no longer holds: **D-24 (operator, 2026-08-14) explicitly overrode D-08 and WF1 was
DELETED**, not merely disabled, after `lv_icp_tier`'s archive was rejected live
(`CANNOT_DELETE_PROPERTY_IN_USE` while WF1's disabled actions still referenced the property).
`lv_icp_tier` itself is now also archived. Full record: `50-RETIREMENT-RECORD.md`'s "D-24
resolution" section.

**Step 1 below ("re-enable WF1") no longer works — there is nothing to re-enable.** `GET
/automation/v4/flows/4625147345` now returns 404. The one-action restore this runbook was built
around does not exist anymore.

**Step 2's PRIMARY mechanism (portal-UI manual enrolment, proven live 2026-08-14) is ALSO GONE.**
It required WF1 to be on; WF1 does not exist. There is no flow to manually enrol a record into.

**What "rollback" now actually means, stated plainly, not softened:**
1. **Rebuild WF1 from JSON**, not restore it: `POST /automation/v4/flows` with the body archived
   at `config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json`. This creates a **new flow
   id** — HubSpot does not let you recreate a flow at its old id. Every downstream reference to
   `4625147345` (this runbook, `RETIRED_FLOW_IDS` in `scripts/check_schema_drift.py`, any saved
   view or report that referenced the flow by id rather than by name) needs updating to the new
   id.
2. **`lv_icp_tier`'s tier-write actions target a property that is itself now archived.** Rebuilding
   WF1 alone does not restore a working tier-write flow — `lv_icp_tier` must first be restored
   from its archived state. **Whether HubSpot's archived-property restore path actually works for
   this property has NOT been verified by this session or any prior one.** Do not assert it works;
   treat it as unverified until someone runs it. If it does not restore, the rebuilt WF1 has
   nothing to write to and the only path forward is creating `lv_icp_tier` fresh under a new name
   (the original internal name may or may not be reusable after an archive — also unverified).
3. **The proven manual-enrolment mechanism (Step 2 primary, below) cannot be re-proven without
   first completing both 1 and 2** — and even then, it would need a fresh live proof, not a
   citation of the 2026-08-14 drill, because that drill ran against the flow at its *original* id
   before it was deleted.

**What did NOT change:** `lv_icp_tier_derived` is unaffected by any of this. It is a calculated
property that computes itself from live inputs with zero dependency on WF1, rebuilt or not. If
`lv_icp_tier_derived` itself needs correcting, the fix is to the formula
(`scripts/apply_fit_score_formula.py --property lv_icp_tier_derived`) or the underlying pipeline
that writes its inputs — never a WF1-based rollback, rebuilt or original.

**Do not attempt any step below without first re-reading this amendment and confirming which of
the above three gaps you are actually able to close.** The rest of this document is kept
unedited below as the historical record of the mechanism that existed before D-24, and as the
starting point for a future rebuild — not as a runbook you can execute as written today.

---

This runbook exists for one reason: if the derived property (`lv_icp_tier_derived`) turns out
to be wrong after cutover, "just turn WF1 back on" does **not** fix anything by itself. Read
Step 2 before you run Step 1 — Step 1 alone is not the rollback.

---

## Step 1 — re-enable WF1

`PUT /automation/v4/flows/4625147345` with `isEnabled: true`, restoring the state archived in
`config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json`. Per **D-08** the flow's
definition is never deleted while it is off, so this is a one-action restore, not a rebuild.

```bash
ALLOW_HUBSPOT_FLOW_WRITE=true DRY_RUN=false .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
   sys.argv = ['put_hubspot_flow.py', \
               '--file', 'config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json', \
               '--flow-id', '4625147345', '--enable']; \
   runpy.run_path('scripts/put_hubspot_flow.py', run_name='__main__')"
```

Run without the two arm keys first (`ALLOW_HUBSPOT_FLOW_WRITE`/`DRY_RUN=false` omitted) to see
the dry-run payload before arming.

## Step 2 — force the re-grade (the runbook does not stop at Step 1)

**Why Step 1 alone does nothing for most records.** WF1 is an `EVENT_BASED` flow —
`shouldReEnroll: true` notwithstanding, it only evaluates a record when a property-change
*event* fires. A record whose `lv_icp_fit_score` / `lv_anti_icp_flag` values are already
correct produces a value-identical PATCH if anything re-writes them, HubSpot treats a
same-value write as a no-op, and **no property-change event fires at all**
(`50-RESEARCH.md` Pitfall 1, `PORTAL-FACTS.md` 2026-08-13). Re-enrolment needs an event to
re-enrol *on* — there is none. So re-enabling WF1 re-grades exactly nothing for every record
whose values were already right, which by definition is every record the derived property
computed correctly. This is the whole reason D-18 names this step explicitly instead of
treating "toggle it back on" as sufficient.

**Why there is no API shortcut (RESEARCH Q1, recorded here as a finding, not a gap).**
HubSpot's Automation v4 Flows API documents create/read/update/delete for flow
*definitions* only — it exposes **no enrolment endpoint of any kind**. A legacy v2 endpoint
(`PUT /automation/v2/workflows/{workflowId}/enrollments/contacts/{email}`) does exist, but it
is **contacts-only by path** (a company id cannot be substituted) and is flagged for future
deprecation. Neither can force a company back through an Automation v4 flow. This was
searched for specifically and this negative is the answer, not an unexplored gap.

**Why Phase 47.5's `recompute: true` does not transfer.** Phase 47.5 solved the equivalent
problem for the n8n veto lane: a request-level `recompute: true` boolean on the enrichment
webhook's POST body routes straight to `Decide Company Action`, which PATCHes
`lv_anti_icp_flag`/`lv_anti_icp_reason` directly
(`scripts/remediate_veto_companies.py::post_webhook_event(..., recompute=True)`,
`docs/OPERATOR-VETO-REFRESH.md`). That lane never calls HubSpot's Automation platform — it is
n8n's own workflow PATCHing a CRM property over the CRM API, with no code path anywhere that
enrols a record in a HubSpot-native flow. It is a real, live-proven mechanism, and it is the
wrong tool here: it can refresh `lv_anti_icp_flag`, but it cannot make WF1 itself re-run.

**The two real mechanisms, primary chosen:**

- **Primary — portal-UI manual enrolment. PROVEN LIVE, 2026-08-14.** A human selects the
  record(s) needing a re-grade on the companies index page, or from inside WF1 itself, and
  enrols them manually. Proof: `.planning/phases/50-derived-tier-property/50-ROLLBACK-DRILL.md`
  — Melbourne Racing Club `9604614548`, WF1 confirmed on, manual enrolment completed per WF1's
  own execution history, tier read `C` before and `C` after (value-identical, as expected for a
  record that was already correctly tiered). Read that artifact's limitations section before
  treating this as a stronger result than it is: the drill proves the mechanism *runs and
  completes*, not that WF1's grading logic re-tiers a stale record — that logic was never in
  doubt and a genuinely stale record (Coffs Harbour `14752488879`) was deliberately excluded
  because enrolling it would have broken a separate, already-settled parity gate (D-23).
  — **Precondition, stated plainly — this is the rollback's own catch-22:** this mechanism
  requires WF1 to be **on** (Step 1 must have already run). HubSpot's own documentation states a
  workflow "must be turned on" to accept a manual enrolment. **Once WF1 is off, this mechanism
  is unavailable until Step 1 re-enables it.** That is exactly why the drill had to run *before*
  Plan 05 switches WF1 off — there is no window afterward in which it could be proven, or used,
  without first completing Step 1.

- **Fallback — armed, capped, disarm-verified perturb-then-restore double-write. Unexercised
  secondary.** For a record needing a forced re-grade, write a different value to the trigger
  property (`lv_icp_fit_score` or `lv_anti_icp_flag`), let WF1 enrol and evaluate on that
  genuine property-change event, then restore the original value. This is **labelled a
  deliberate D-16 deviation requiring justification** the moment it is ever exercised — D-16
  declares zero company write windows for the whole of Phase 50, and this fallback is two real
  company writes per record. It is available only on the emergency path, never the happy path,
  and only under the same armed/capped/disarm-and-read-back discipline every write window in
  Phases 47-49 already used. **Not exercised in this plan or any plan to date — documented
  only.** Exercising it later requires its own fresh D-16 authorisation at the time; the drill
  in `50-ROLLBACK-DRILL.md` proves the primary mechanism only and spends none of this fallback's
  write budget.

No third mechanism is named. A "poke" that PATCHes an unrelated property hoping it cascades,
or any workaround with no live-proven precedent in this portal, does not belong in a rollback
runbook — this portal's own history (WINDOWS.md #2, #3, #8) is full of exactly that failure
mode breaking silently.

---

## What this costs

- Step 1 (re-enable WF1): one `PUT /automation/v4/flows/4625147345` call. Free — no per-record
  cost.
- Step 2 primary (manual UI enrolment): a human's time per record, no API calls, no n8n
  executions, no Anthropic calls, no provider credits. Measured live in the 2026-08-14 drill:
  zero company writes (value-identical enrolment), zero Anthropic calls, zero provider credits.
- Step 2 fallback (perturb-then-restore, if ever exercised): two HubSpot company writes per
  record, run under an armed/capped window exactly like Phase 47-49's write windows. No n8n
  execution, no Anthropic call, no provider credit — the cost is entirely the two writes
  themselves and the deviation disclosure they require.

## What this does not change

- Neither step touches `lv_icp_tier_derived` — the calculated property keeps computing itself
  from live inputs regardless of WF1's state; the rollback only restores WF1 as a second writer
  of the old `lv_icp_tier` enum.
- Re-enabling WF1 does not retroactively fix any record on its own (see Step 2's whole point).
- The fallback in Step 2 is not a substitute for portal-UI enrolment when WF1 is available — it
  exists for the case where manual enrolment is refused or unavailable, not as a routine
  alternative.
- This runbook does not decide *whether* to roll back — that decision, and the record of
  whether it was ever exercised, lives in Plan 05.

---

## AMENDMENT-block convention

Corrections to this document are **appended** as a dated block at the top (matching
`docs/OPERATOR-VETO-REFRESH.md`'s and `docs/OPERATOR-RESCORE.md`'s house style), never
silently rewritten into the body.
