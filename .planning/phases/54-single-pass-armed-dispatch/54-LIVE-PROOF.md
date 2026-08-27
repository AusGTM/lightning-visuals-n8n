# 54-05 Live Proof — one real flagged contact, approved through the deployed endpoint

**Date:** 2026-08-27
**Record:** contact `347569451461` (John Tsatsimas, johnt@footballnsw.com.au, Chief
Executive Officer, Football NSW) — the same record 54-01 measured out of live execution
history (executions `11956`/`11958`/`11960`).
**Endpoint:** `LV Review Decision (Cloud)` (`WBJwoZOo63wzeP69`), `Build Review Decision`
node, running `n8n/code/reviewDecision.js` / `n8n/code/reviewApply.js` deployed by 54-04
and re-deployed by this plan's Task 1 (a blocking bug found live — see below).

## A blocking bug found and fixed before this task could proceed

Before any before/after read could be taken, the first live preview call against this
record threw a real error on the deployed workflow, not a queue or write-safety refusal:

```
ReferenceError: DEFAULT_CONTACT_POLICY is not defined [line 1306]
```
(n8n executions `11992` and `11993`, both `status: error`, both `2026-08-27T01:56`.)

Root cause: `n8n/code/reviewDecision.js`'s contacts branch requires
`DEFAULT_CONTACT_POLICY` directly from `n8n/code/mergeContacts.js` (added in 54-03), but
`scripts/build_cloud_workflows.py`'s `inline()` call for `REVIEW_BUILD_DECISION` (the
Code node this endpoint runs) was never updated to include that module — a gap that
predates 54-03/54-04 and was deployed live without anyone exercising the contacts branch
against a real record until this task did. This is a Rule 1/Rule 3 auto-fix (a genuine
bug blocking this task, directly caused by prior work reachable from this task): added
`"mergeContacts.js"` to the inline list, rebuilt via `scripts/build_cloud_workflows.py`
(source-of-truth, never hand-edited — per this plan's own prohibition), verified
776/776 node tests + 197 relevant pytest + 48/48 architecture guard all green, committed
(`a0d0df5`), then re-deployed the ONE node via the same node-scoped `apply_mutation`
mechanism 54-04 used (deactivate -> PUT -> reactivate, independent post-deploy re-GET):

- pre-deploy node count 26, `Build Review Decision` jsCode 69327 chars, no
  `DEFAULT_CONTACT_POLICY` definition present (confirms the live instance still ran the
  broken pre-fix code)
- `apply_mutation` verdict: `verified`
- independent post-deploy re-GET (a second, separate GET, not the PUT's own echo and not
  `apply_mutation`'s internal read): node count 26 (unchanged), jsCode 85236 chars,
  `DEFAULT_CONTACT_POLICY` definition present, byte-identical to the locally committed
  built file, `active: true`
- `scripts/verify_live_write_safety.py` (disarmed expectation, the default): `VERDICT:
  disarmed PASS` across all 5 live workflows / 15 declaring nodes — both record-write
  flags false, review-write flag false, both allowlists empty, everywhere, including the
  two nodes this deploy touched. `ALLOW_SJ3_DRAIN_WRITES` reads `"true"` everywhere it
  declares, matching its own opposite-polarity PASS expectation.
- 0 n8n executions consumed by the deploy itself (the deactivate/PUT/activate/GET calls
  are administrative API calls, not workflow triggers — confirmed by execution list
  before and after: still `11993` newest immediately after the deploy)

`mergeCompanies.js` and `mergeContacts.js` share several same-named internal helpers
(`_isBlank`, `_gate`, `_statusFor`, etc.) as plain `function` declarations, which
redeclare without a `SyntaxError` in this non-strict eval context rather than colliding.
Confirmed inert for this node: `Build Review Decision` never calls `mergeCompanies()` or
`mergeContacts()` themselves — only the two `DEFAULT_*_POLICY` constants, `stableStringify`
(byte-identical in both files, both delegating to the same `_sortedForStringify` body),
and `reviewApply()` are ever referenced downstream of the require lines.

**This fix is a deviation from the plan's literal task list, documented here and in the
plan's SUMMARY, not silently folded in.** It cost 2 executions before the fix (`11992`,
`11993`, both errors, 0 provider credits, 0 Anthropic calls — this endpoint has no
waterfall node) and is accounted for in this plan's execution budget below.

## BEFORE — independent read, taken before any preview or submit

Read via `operator-claude-plugin/scripts/review_queue.fetch_queue(config, "contacts")`
(the queue's own live HubSpot search, read-only) — `total: 1`, exactly this one record:

| Property | Value |
|---|---|
| `hs_object_id` | `347569451461` |
| `lv_enrichment_needs_review` | `"true"` |
| `lv_enrichment_review_approved` | `null` |
| `lv_enrichment_review_candidate_json` | `null` (empty — not absent; see branch note below) |
| `lv_enrichment_review_reason` | `"email: promoted into a blank field at confidence 85 — verify before relying on it"` |
| `lv_enrichment_reviewed_at` | `null` |
| `lv_enrichment_reviewed_by` | `null` |
| `lastmodifieddate` | `2026-08-25T21:01:17.440Z` |

`lv_contact_enrichment_provenance` on the record carries a full `email`/`jobtitle`
overlay already stamped `human_review_required` for `email` and `jobtitle` — consistent
with the permissive contact lane having already written the enriched value at flag time
(54-03/54-04's stated residual).

## The preview — the backend's own computed patch (dry_run, wrote nothing)

`review_decision.preview_decision(config, "contacts", "347569451461", "approve", "phase
54-05 live proof preview")`, n8n execution `11994`, `status: success`:

```json
{
  "outcome": "applied",
  "message": "acknowledged — this contact's value was already written by the permissive contact enrichment lane at the moment it was flagged, so no field was promoted because none was withheld; the review flag is cleared and the decision is recorded",
  "would_write": {
    "lv_enrichment_needs_review": "false",
    "lv_enrichment_review_approved": "false",
    "lv_enrichment_review_reason": "",
    "lv_enrichment_review_candidate_json": "",
    "lv_enrichment_reviewed_at": "2026-08-27T02:20:45.013Z",
    "lv_enrichment_reviewed_by": "operator (unnamed)"
  }
}
```

## Which branch this record takes — stated plainly

**The already-applied clear branch, not the promote branch.**
`lv_enrichment_review_candidate_json` is empty on this record (no held candidate), so
`reviewDecision.js`'s contacts approve resolves to the no-candidate `applied` outcome:
it clears the review flags and stamps who/when, and promotes no new field, because the
enriched value was already written to HubSpot by the permissive contact enrichment lane
at the moment this record was flagged (54-03/54-04's stated residual — no live contacts
candidate producer exists in this deployment). **This proof does not exercise, and does
not claim to exercise, the promote branch** (a contacts approve with a held candidate) —
that branch remains proven only by 54-03's synthetic-candidate node tests, per the
carry-forward note both 54-03-SUMMARY.md and 54-04-SUMMARY.md already state.

## Nothing armed, nothing submitted by this task

`preview_decision` is deliberately not gated on `ALLOW_REVIEW_SUBMIT` or the session
arm — it is a dry run computed by the backend and writes nothing, which is exactly why
the operator can be shown the exact patch before authorizing it. No call was made into
`review_decision.submit_decision`. `git diff --stat` after this task shows only this
file (`54-LIVE-PROOF.md`) uncommitted — the bug-fix deploy above is its own separate,
already-committed change, per this repo's one-task-one-commit convention; nothing about
the review write flag or either allowlist was touched by anything in this task.

## Execution budget so far (Task 1)

| Execution | What | Provider credits | Anthropic calls |
|---|---|---|---|
| `11992` | broken pre-fix preview attempt (error) | 0 | 0 |
| `11993` | broken pre-fix preview attempt (error) | 0 | 0 |
| `11994` | fixed preview (success) | 0 | 0 |

The deploy itself (deactivate/PUT/reactivate/re-GET) consumed 0 executions — those are
administrative API calls, not workflow triggers. The plan's stated budget (2-4
executions for one preview + one real submit) is exceeded at this point by the 2 errored
executions the bug produced before the fix; that is disclosed here rather than
smoothed over, and Task 3's final accounting will state the total including Task 2's
real submit.

<!-- Task 2 (operator checkpoint) and Task 3 (AFTER read, disarm verdict, limits section)
     append below once the operator has authorized and submitted the real write. -->
