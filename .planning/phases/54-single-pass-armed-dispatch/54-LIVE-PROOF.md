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

## Task 2 — operator authorization received; submit blocked by an environmental gate

**Operator authorization, 2026-08-27**, given at this plan's checkpoint: approve, custom
reviewer, contact `347569451461` (this one record only, VOCAB-05), the six-key
clear-and-stamp patch above with exactly one substitution — `lv_enrichment_reviewed_by`
set to `operator (robert li)` (passed through verbatim, not reformatted) in place of the
preview's default `operator (unnamed)`.

**Re-confirmed before submitting.** A second `preview_decision` call against the same
record, in this continuation session, returned the identical outcome as Task 1's: `applied`,
the same clear branch (`lv_enrichment_review_candidate_json` still empty — still no held
candidate), the same six property keys. The record had not changed between Task 1 and this
session. The patch submitted below is the patch the operator saw and approved.

**The submit itself was refused before any request was built.** Called as
`review_decision.submit_decision(config, "contacts", "347569451461", "approve", <reason>,
"operator (robert li)", review_armed=True, preview=preview)`. Result:

```json
{
  "available": false,
  "reason": "submit_not_enabled",
  "outcome": null,
  "would_write": { /* the same six keys, unchanged */ }
}
```

Relayed verbatim, in full, per this module's own `_ENV_REFUSAL` text:

> Review writeback is switched off on this machine: the ALLOW_REVIEW_SUBMIT environment
> variable is not set to exactly `true`. Nothing was sent and no request was even built.
> Your administrator sets that variable — this plugin cannot set it and neither can this
> conversation. Two things still work without it: previewing the exact write, and
> rejecting a record, which records your reason and leaves the record in the queue.

Independently confirmed before calling `submit_decision`: `python3 review_decision.py`
(this module's own diagnostic, which sends nothing) reported `submit_enabled: false`, and
`ALLOW_REVIEW_SUBMIT` is absent from this session's process environment and from every
shell profile checked (`~/.zshrc`, `~/.bashrc`, `~/.zprofile`, `~/.bash_profile`,
`~/.profile`). This env var is a plugin-side kill switch that only an administrator can set
on the machine the plugin runs on (`review_decision.py`'s own docstring, gate 1) — it is
**not** the same variable as the backend's `ALLOW_HUBSPOT_REVIEW_WRITES` allowlist that
Task 1's redeploy verified disarmed, and setting one has never done the work of the other.
Per this plan's own instructions, no attempt was made to set it, work around it, or read
`.env` to find it.

**Nothing was armed and nothing needs disarming.** `submit_enabled()` is checked before any
transport is constructed (by design — `review_decision.py` docstring, property (b)), so the
`available: false` / `submit_not_enabled` response above proves no HTTP request reached
n8n: the record is still flagged, `lv_enrichment_review_candidate_json` is still empty, and
none of the backend's write-safety flags or allowlists were touched by anything in this
session — they stand exactly as Task 1's independent redeploy verification last confirmed
them (`VERDICT: disarmed PASS`, all 5 workflows). No further live read-back was taken to
re-prove this: the refusal firing before any transport call is itself the evidence, and
spending an n8n execution to confirm a no-op would exceed this plan's already-strained
budget for no new information.

## Execution budget, updated through this session

| Execution | What | Provider credits | Anthropic calls |
|---|---|---|---|
| `11992` | broken pre-fix preview attempt (error) | 0 | 0 |
| `11993` | broken pre-fix preview attempt (error) | 0 | 0 |
| `11994` | fixed preview (success, Task 1) | 0 | 0 |
| (unread id) | re-confirm preview, this session, 02:57:39Z | 0 | 0 |
| (unread id) | preview inside the blocked submit call, 02:59:39Z | 0 | 0 |

Execution ids for the last two rows were not captured — this session has no n8n API
credentials configured (`N8N_URL`/`N8N_API_KEY` unset), so `verify_live_write_safety.py`
and any execution-id lookup are unavailable here; they are read-only preview calls (each a
`dry_run: true` POST to the same workflow), not writes. **Running total: 5 executions
consumed by this plan, all previews or pre-fix errors — 0 writes, 0 provider credits, 0
Anthropic calls.** The submit that would have produced the real write consumed 0
executions because it never reached the transport layer.

## Outcome: blocked, not refused by policy

This is an environmental gate, not a decision by the operator, the backend's write-safety
allowlist, or this plan's own scope rules. The operator's one-record authorization stands
and is unexercised. A continuation agent, once an administrator sets
`ALLOW_REVIEW_SUBMIT=true` in this plugin's runtime environment, should re-confirm the
preview once more (the record may have changed in the interim) and submit under the same
authorization before completing Task 3's AFTER read, disarm re-verification, and final
execution count.

**Task 3 (the AFTER read, disarm verdict, and limits section) has not been executed.**
There is no real write yet to read back. Writing that section now would describe a write
that did not happen. This file stops here until the write lands.
