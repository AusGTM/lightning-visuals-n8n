# 58-02 Spike Verdict: propose-mode `Decide Company Action` observation

**Date:** 2026-08-26
**Executed by:** operator (live)
**Execution id:** `11972`

## What was tested

Whether a request-level `mode` key on a companies webhook event survives `Parse HubSpot Event`
onto the company row and is read by `Decide Company Action`'s `isReturnOnly`, forcing a
non-writing `action: "proposed"` before the write-safety allowlist check runs — the trace
`58-RESEARCH.md` made from source but had never observed on a live execution.

Probe: `scripts/probe_company_propose_mode.py --execute`, riding the Phase 47.5 recompute lane
against Melbourne Racing Club (`hs_object_id 9604614548`), event body `{objectId:
9604614548, subscriptionType: "company.propertyChange", propertyName:
"lv_country_region_normalized", recompute: true, mode: "propose"}`.

## Observed answers (from the execution's own runData, not a stored read-back)

| Question | Observed |
|---|---|
| Did `Decide Company Action` run? | Yes — `decide_company_action_ran: true` |
| What `action` value did it produce? | `"proposed"` — the non-writing branch |
| Is `mode` visible on the row `Decide Company Action` received? | Yes — `mode_visible_on_parsed_row: "propose"` |
| What does the response body the caller got contain? | `action="proposed"`, `object_type="companies"`, `hs_object_id="9604614548"`, `gap_flag=false`, `needs_review=false`, `row_id=null`, `mode="propose"`, `match={tier:"unknown", auto:false, reason:"no searchable identity — the row has no email, object id, or name+company pair", candidates:[]}`, `properties={lv_anti_icp_flag:"false", lv_anti_icp_flag_num:"0", lv_anti_icp_reason:""}`, `remaining_credits=[]` |

**Verdict on the traced claim: CONFIRMED.** The `mode` key rides the row spread intact and
`isReturnOnly` reads it, exactly as `58-RESEARCH.md` traced from `build_cloud_workflows.py`
source. No HubSpot record was written — `execution_id 11972`, `status "success"`, all 19 nodes
in the recompute lane ran (no provider, research, judge, merge, or normalize node), and the
response body carries no evidence the record was touched.

**Shape finding (the second question this spike answers):** the returned `match` object is
built for a *contact*-shaped identity check (`email`/`object id`/`name+company pair`) and
returns `reason: "no searchable identity"` for a company row, which has none of those fields.
A caller cannot currently read a proposed *company domain* out of this response body — the
`match`/`candidates` shape as it exists today is contact-oriented, not company-oriented. This
is a structural finding about the current return-only shape, not a defect in the predicate
under test.

## Cost actuals vs cap

| Metric | Cap | Actual |
|---|---|---|
| n8n executions | 3 | 1 |
| Provider credits | 0 | 0 |
| Anthropic calls | 0 | 0 |

Within cap on every dimension.

## Operator decision (Task 3)

**Decision: `defer-residual`** — ship the client (plugin) path this phase; do not extend the
backend research node to seek a domain.

- **Decider:** operator
- **Date:** 2026-08-26
- **Reason:** Claude-in-conversation already proposes a domain from what it sees in most cases,
  free and instant (D-58-01), and the operator confirms, corrects, or denies it (D-58-04/06/07).
  Every row Claude cannot confidently propose already falls to the accept-by-name path shipped
  in 0.16.0. Extending the backend research node's prompt/schema to also seek a domain would
  require a `build_cloud_workflows.py` change, a rebuild, a deploy, a bounce, and a live proof
  execution that spends a real Anthropic call to satisfy this project's "a stored read-back
  proves nothing" standard — cost not justified this phase against a client-side path that
  already covers the common case at zero n8n deploy cost.

**Residual named against INPUT-02:** INPUT-02 ("researching a company's own website from its
name is the same call") does **not** fully close this phase. The gap is rows where Claude
cannot confidently propose a domain from what it already sees in conversation AND the operator
cannot supply one — those rows fall to the accept-by-name lookup path rather than a
backend-researched domain. This residual carries forward to a later phase; `58-04` Task 1 reads
this file and branches on it (deferred, not built).

## No write occurred

Confirmed by the response body (no evidence of a canonical write), the empty
`remaining_credits`, and the recompute lane's own structural guarantee (no HubSpot Update node
on this path when the allowlist is empty — Phase 47.5 precedent, execution `11858`). `git diff
--stat n8n/` reports no change; nothing was deployed or hand-edited by this plan.
