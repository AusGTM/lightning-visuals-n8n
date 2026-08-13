# 49-W2-RECORD — Entain `10024564084` W2 window: authorisation, transition proof, disarm, census

Phase 49, Plan 06, Task 3. Workflow **LV Enrichment (Cloud template)**, id
`950HPb7a1GgSAIyZ`. Everything network-facing below is read from the live n8n Public API
and the live HubSpot CRM v3 API. Neither the n8n API key, the webhook secret, nor the
HubSpot private-app token appears anywhere in this file (T-49-36).

**W2 OPENED.** Both of Entain's veto inputs cleared `config/field_policy.yaml`'s bar
(`49-ENTAIN-EVIDENCE.json`, Task 1). The operator authorised opening the phase's second
and final declared window.

---

## 1. Authorisation

**Checkpoint:** Task 49-06-02, "Authorise or decline the conditional W2 window."
**Operator response:** `open-w2`
**Date:** 2026-08-13

The checkpoint was an arming authorisation, not a re-judgment of the evidence —
`config/field_policy.yaml`'s bar had already decided the write was permitted
(`lv_produces_content`: confidence 95 ≥ 85 required, evidence URL present;
`lv_country_region_normalized`: confidence 95 ≥ 75 required). D-14's override of
`CLAUDE.md` §21.3 / §15.1 (human review / Sonnet-escalation triggers) stands, recorded
in `49-ENTAIN-EVIDENCE.json` and `.planning/phases/49-re-score-strategy-reporting/49-CONTEXT.md`
and left intact, not rewritten. Arming authority for this window comes from the waiver
`D-49-01` (`49-CONTEXT.md` D-06), a Phase-49-only delegation of both arming surfaces and
the deploy+bounce, expiring with this phase; it was not exercised for a deploy this task
(the folded todo's deploy was Wave 3/4's concern, independent of this window).

---

## 2. Pre-window state (disarmed, independently read)

`scripts/verify_live_write_safety.py --expectation disarmed --json` — full node scan,
every declaring node across every deployed workflow:

```json
{ "ok": true, "reasons": [] }
```

Entain `10024564084`, read directly (unchanged since Task 1's evidence file):

```json
{
  "lv_anti_icp_flag": "true",
  "lv_anti_icp_reason": "Non-ANZ geography; No broadcast or streaming content",
  "lv_country_region_normalized": "Other",
  "lv_icp_fit_score": "-50",
  "lv_icp_tier": "D",
  "lv_org_type": "gambling_operator",
  "lv_produces_content": "false",
  "lv_revenue_band": "1.2B+"
}
```

---

## 3. t0 — independent tier read, before any write in this window

Read `2026-08-13T06:38:49Z` — `lv_icp_tier: "D"`, as expected.

---

## 4. Arm attempt 1 — by DOMAIN (failed to reach the write; zero writes made)

`ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --domains www.entaingroup.com`

```json
{
  "outcome": "armed",
  "observed": {
    "ALLOW_HUBSPOT_RECORD_WRITES": "true",
    "TEST_RECORD_IDS": "",
    "TEST_RECORD_DOMAINS": "www.entaingroup.com"
  },
  "record_ids": [],
  "record_domains": ["www.entaingroup.com"]
}
```

Allowlist asserted non-empty and exactly the one intended domain before trusting the
armed state, per the plan's requirement.

**Input PATCH (D-07 — inputs only), sent immediately after arming:**

```json
{ "lv_country_region_normalized": "ANZ", "lv_produces_content": "true" }
```

HTTP 200, independently read back 3 seconds later: both properties confirmed landed
(`hs_lastmodifieddate: "2026-08-13T06:38:52.899Z"`). No derived field (`lv_icp_fit_score`,
`lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`) was in this PATCH payload.

**D-18 recompute POST — routed by domain, refused.**
`post_webhook_event('10024564084', True, cfg, recompute=True, domain='www.entaingroup.com')`

- Sent `06:38:58Z`, HTTP 200, client elapsed well inside the 300s timeout.
- **Execution `11872`** — 06:38:58.937Z → 06:39:02.516Z, `status: success`, `finished: true`.
- Node-level (not the top-level status) proof of what actually happened:
  - `Adapt Company Search` normalized the domain to `identity_keys.domain: "entaingroup.com"`
    (www-stripped) and searched `HubSpot Company Search` (domain EQ) — **0 results**.
  - `Company Gate` verdict: `action: "create"`, reason *"a recompute was requested for a
    company that did not resolve to an existing record — refused rather than created (no
    existing record)"*.
  - `Decide Company Action` output: `action: "recompute_refused"`, `hs_object_id: null`.
  - **No `HubSpot Company Update` node in `runData` at all.** Zero HubSpot writes from
    this execution.

**Root cause.** Entain's live `domain` property is stored as `"www.entaingroup.com"`
(confirmed by a direct read: `name: "Entain"`, `domain: "www.entaingroup.com"`,
`website: "www.entaingroup.com"`). n8n's `Adapt Company Search` node strips the `www.`
prefix before searching, so its EQ search for `"entaingroup.com"` could never match a
record whose stored domain literally carries the prefix. This is a live domain-string
mismatch, not a credentials or arming failure — the allowlist, the arm, and the PATCH of
the two inputs all worked exactly as intended; only the *search* used to locate the
record for the recompute failed.

**Classification: Rule 1 auto-fix, disclosed.** `scripts/june_run_arm.py`'s own docstring
distinguishes the two allowlist mechanisms: a domain allowlist exists specifically for a
company that **does not exist yet** (an id allowlist cannot name a record HubSpot has not
created); `scripts/remediate_veto_companies.py::post_webhook_event`'s `domain` parameter
routes through `HubSpot Company Search` (domain EQ) *instead of* the bare-event
fetch-by-id lane specifically to populate `identity_keys.domain` for that not-yet-existing
case. Entain already exists with a known id — the domain-allowlist path was the wrong
tool for an existing record, not a defect in the plan's intent to arm and recompute.
Fixed inline by switching to the id-based allowlist and a bare (no-domain) event, which
routes `IF Company Bare Event` → `HubSpot Company Fetch By Id` — no domain match
required. No architectural change; both mechanisms are pre-existing, tested code paths in
the same script.

**Zero HubSpot writes occurred in this attempt.** The record's derived fields were
byte-identical before and after (confirmed by the `t1` read at the end of attempt 1,
below) — this was a read-only misroute, not a partial write.

---

## 5. Disarm (closing the failed attempt) — ungated, independently re-read

`.venv/bin/python scripts/june_run_arm.py --disarm`

```json
{
  "outcome": "disarmed",
  "observed": {
    "ALLOW_HUBSPOT_RECORD_WRITES": "false",
    "ALLOW_HUBSPOT_CREATE": "false",
    "TEST_RECORD_IDS": "",
    "TEST_RECORD_DOMAINS": ""
  }
}
```

Intermediate tier read (end of attempt 1, `06:39:08Z`): `lv_anti_icp_flag: "true"`,
`lv_anti_icp_reason: "Non-ANZ geography; No broadcast or streaming content"` (unchanged —
the flag/reason chain never ran), `lv_icp_tier: "D"` (unchanged), while
`lv_country_region_normalized: "ANZ"` and `lv_produces_content: "true"` (the direct PATCH
from step 4, which HAD landed) and `lv_icp_fit_score: "-20"` (HubSpot's `calculation_equation`
property recomputed immediately from the raw inputs — this property derives from the raw
fields, not from a separate component-score write, and its reaction here independently
confirms the revenue-band arithmetic predicted in `49-ENTAIN-EVIDENCE.json`:
`org_type 0 + geography 10 + produces_content 20 + revenue -50 = -20`). `lv_icp_tier`
stayed `D` because `lv_anti_icp_flag` had not yet cleared — tier grading (WF1) still saw a
live hard veto.

---

## 6. Arm attempt 2 — by ID (correct mechanism for an existing record)

`ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --ids 10024564084`

```json
{
  "outcome": "armed",
  "observed": {
    "ALLOW_HUBSPOT_RECORD_WRITES": "true",
    "TEST_RECORD_IDS": "10024564084",
    "TEST_RECORD_DOMAINS": ""
  },
  "record_ids": ["10024564084"],
  "record_domains": []
}
```

Allowlist asserted non-empty and exactly the single intended id (`10024564084`) before
trusting the armed state. No re-PATCH of the inputs was needed — they had already landed
and were independently confirmed in step 4.

**D-18 recompute POST — bare event, no domain key.**
`post_webhook_event('10024564084', True, cfg, recompute=True, domain=None)`

- Sent `06:42:00Z`, HTTP 200.
- **Execution `11873`** — 06:42:00.650Z → 06:42:03.661Z (3.0s), `status: success`,
  `finished: true`, `resultData.error` absent.

`resultData.runData` node list, **21 nodes**, verbatim and in order:

```
Webhook Trigger
IF List Input
Parse HubSpot Event
IF Object Type Supported
Credit Request
Route By Object Type
IF Lusha Credit Requested
IF Apollo Credit Requested
IF ZoomInfo Credit Requested
Build Company Identity
IF Company Bare Event
HubSpot Company Fetch By Id
Adapt Company Fetch By Id
Company Gate
IF Company Recompute
Decide Company Action
IF Company Create
IF Company Enrich
HubSpot Company Update
Build Response
Respond to Webhook
```

21 nodes disarmed-to-armed-write baseline is 20 → 21 (the extra is `HubSpot Company
Update` — CLAUDE.md's own healthy-signature note). This is a healthy run, not a short
dead chain (constraint #8): the presence of `HubSpot Company Update` in `runData`,
together with an actual property write confirmed below, is the positive signal — duration
alone is never trusted as the sole evidence.

**`Company Gate` — `existingRecord` (fetched by id, not by domain search):**

```json
{
  "identity_keys": { "domain": "entaingroup.com", "companyName": "Entain" },
  "existingRecord": {
    "hs_object_id": "10024564084",
    "domain": "www.entaingroup.com",
    "lv_country_region_normalized": "ANZ",
    "...": "..."
  }
}
```

`existingRecord.lv_country_region_normalized: "ANZ"` — the fetch-by-id lane picked up the
already-PATCHed input, confirming the causal chain (PATCH → fetch → Decide) rather than a
race.

**`Decide Company Action` output, verbatim (trimmed to the decision fields):**

```json
{
  "action": "enrich",
  "hs_object_id": "10024564084",
  "properties": { "lv_anti_icp_flag": "false", "lv_anti_icp_reason": "" }
}
```

`executionTime: 27ms`.

**`HubSpot Company Update` — the actual PATCH, verbatim (trimmed to load-bearing fields):**

```json
{
  "id": "10024564084",
  "properties": {
    "lv_anti_icp_flag": "false",
    "lv_anti_icp_reason": ""
  },
  "updatedAt": "2026-08-13T06:42:03.380Z"
}
```

`executionTime: 604ms`. **Exactly two properties in the PATCH body** — the derived veto
flag and reason only. No score or tier property appears anywhere in this node's payload,
consistent with D-07 and with the recompute lane's own no-`merge` design (nothing else
could have been written even in principle).

**Poll:** `lv_anti_icp_flag` settled to `"false"` in 5.7s (interval 5s, one extra poll
past the immediate value).

---

## 7. t1 — independent tier read, after settle

Read `2026-08-13T06:42:09Z`:

```json
{
  "lv_anti_icp_flag": "false",
  "lv_anti_icp_reason": "",
  "lv_country_region_normalized": "ANZ",
  "lv_icp_fit_score": "-20",
  "lv_icp_tier": "Unscored",
  "lv_org_type": "gambling_operator",
  "lv_produces_content": "true",
  "lv_revenue_band": "1.2B+"
}
```

**`t1 − t0` = 200.3 seconds** (06:38:49Z → 06:42:09Z). This interval spans the entire
window including the diagnosed and corrected domain-routing misroute — a true elapsed
interval, disclosed rather than reported as if the transition were direct and fast.
Unlike Phase 47.5's rehearsal (two reads ~5 seconds apart, unable to establish causality),
this transition has a full causal chain: input PATCH confirmed by independent read-back
→ `existingRecord` in the successful execution shows the new inputs were picked up →
`Decide Company Action` computed off them → `HubSpot Company Update` PATCHed the derived
fields with its own server timestamp → t1 read after settle shows the changed value. The
transition is proven as a transition, not inferred from proximity.

**Assertion:** `lv_icp_tier != "D"` — **TRUE** (`t1 tier = "Unscored"`).

No specific tier was asserted or expected as a hard-coded literal. `Unscored` is exactly
the outcome `49-ENTAIN-EVIDENCE.json`'s pre-flight arithmetic predicted from Entain's
`1.2B+` revenue band (`org_type 0 + geography 10 + produces_content 20 + revenue -50 =
-20`, which grades below the C floor of 15 and above no hard veto — `Unscored`, per
`src/icp_scoring.py`'s `tier_rules`). This satisfies D-15's transition proof even though
the landing tier is neither `B` nor `C`.

---

## 8. Disarm (final) — ungated, independently re-read twice

`.venv/bin/python scripts/june_run_arm.py --disarm`

```json
{
  "outcome": "disarmed",
  "observed": {
    "ALLOW_HUBSPOT_RECORD_WRITES": "false",
    "ALLOW_HUBSPOT_CREATE": "false",
    "TEST_RECORD_IDS": "",
    "TEST_RECORD_DOMAINS": ""
  }
}
```

That `observed` block is `n8n_arming.disarm`'s own independent re-read, not an echo of
what it wrote. A **second, separate** verification pass was then run:

`.venv/bin/python scripts/verify_live_write_safety.py --expectation disarmed --json` —
full scan, every declaring node, every deployed workflow (not scoped to this one
workflow):

```json
{ "ok": true, "reasons": [] }
```

**Both armed surfaces are provably closed**, confirmed by two independent read-backs
neither of which is the mutation call's own echo. Disarm ran unconditionally after both
the successful window and the earlier failed one — the failed attempt's own disarm (§5)
already demonstrates the disarm path runs regardless of the write leg's outcome.

---

## 9. Cost accounting

| Item | Declared (D-05/plan) | Actual |
|---|---|---|
| Records | 1 | 1 (Entain `10024564084`) |
| n8n executions | ~1–2 | **2** — `11872` (refused, 0 writes; domain-routing misroute) and `11873` (succeeded) |
| Provider credits (Lusha/Apollo/ZoomInfo) | 0 | **0** — confirmed: no provider node appears in either execution's `runData` beyond the three always-run `* Credit Requested` IF nodes, which fire on every dispatch regardless (`providers_requested: []` in both) |
| Anthropic calls (this task) | 0 (Task 1 spent the declared research call) | **0** — Task 3 makes no model calls |
| HubSpot direct PATCH calls | n/a | 1 (the two-input PATCH, step 4) + 2 n8n-internal `HubSpot Company Update` calls (attempt 1: none reached; attempt 2: 1, the veto-clear PATCH) |
| n8n budget (2,500/month) | — | 2 of 2,500 (0.08%) |

The extra execution (`11872`) is disclosed rather than absorbed, per the plan's own
instruction ("exceeding it in any way is a disclosure obligation in the run report"). It
stayed within the declared "roughly 1–2" range and consumed zero provider credits and
zero Anthropic calls — the cost of the misroute was entirely in a second n8n execution and
a few minutes of wall-clock time.

---

## 10. Census leg (D-16) — runs unconditionally, live re-derivation, dated 2026-08-13

**Jam TV `17317850381` — veto retained, plain read:**

```json
{
  "name": "Jam TV",
  "domain": "www.jamtv.it",
  "lv_org_type": "broadcaster",
  "lv_country_region_normalized": "Other",
  "lv_anti_icp_flag": "true",
  "lv_anti_icp_reason": "Non-ANZ geography",
  "lv_icp_tier": "D"
}
```

Its veto is **geographic** (region `Other`, reason `Non-ANZ geography`). Phase 48's
`lv_org_type = "broadcaster"` write could not and did not clear it — org type is not the
predicate this veto fires on. This is a correct, deliberately-preserved non-ANZ veto (Jam
TV is the Italian broadcaster jamtv.it — D-23), not a candidate for re-examination.

**Portal-wide non-ANZ veto census (`lv_anti_icp_flag = true` AND reason contains the
`config/icp_scoring.yaml`-sourced non-ANZ reason string, read live via search, not
transcribed):**

| Record | Reason | Count |
|---|---|---|
| Jam TV `17317850381` | `Non-ANZ geography` | 1 |

**Census = 1** (was 2 — Entain + Jam TV — before this task; Entain cleared its non-ANZ
veto in §6/§7, so the live count is now **1**, dated 2026-08-13). All 6 currently-vetoed
companies were read for context:

| id | name | reason | region |
|---|---|---|---|
| 15274105699 | Supertech Electronics | No broadcast or streaming content; Hardware/AV/LED vendor, not sports-media buyer | AU |
| 16047156820 | Queensland Racing Integrity Commission | No broadcast or streaming content | AU |
| 17317850381 | Jam TV | Non-ANZ geography | Other |
| 17791151956 | Big Screen Video | No broadcast or streaming content | AU |
| 17861423879 | Sportsbet | No broadcast or streaming content | AU |
| 18047161864 | Simtech LED | Hardware/AV/LED vendor, not sports-media buyer | AU |

Only Jam TV carries the non-ANZ reason; the other five carry genuine no-content or
hardware-vendor vetoes, unrelated to this task and untouched.

**VETO-03 bar — no company carries a non-ANZ veto together with a blank region**
(`lv_anti_icp_flag = true` AND `lv_country_region_normalized` `NOT_HAS_PROPERTY`, a live
HubSpot search, not a restatement of a prior phase's number):

**Count = 0.**

---

## 11. What this proves — and what it does not

**Proven.** The live D → non-D tier transition on a hard-vetoed record is captured *as a
transition*, closing the gap 47.5-A-LIVE-PROOF.md left open ("not proven: a live D →
non-D tier transition... it is a true assertion about the end state and it was not
weakened — but it is not evidence that the tier derivation reacts to a cleared flag").
Here: an independent pre-write tier read (`D`), a confirmed input PATCH, node-level proof
that the recompute lane's `existingRecord` picked up the new inputs, `Decide Company
Action` deriving and `HubSpot Company Update` PATCHing exactly the two veto fields, and
an independent post-settle tier read (`Unscored`, i.e. `≠ D`) — a full causal chain, not
two nearby reads.

**Also proven, incidentally.** `lv_icp_fit_score` (the `calculation_equation` property)
reacts directly to the raw canonical inputs (`lv_country_region_normalized`,
`lv_produces_content`, `lv_org_type`, `lv_revenue_band`), independent of the n8n
recompute lane — it changed from `-50` to `-20` the moment the direct HubSpot PATCH
landed in §4, before any n8n execution ran. The veto flag/reason and the tier grading
(WF1) are the parts that specifically require the recompute lane; the score itself does
not.

**Not proven, and not claimed.** This transition does not establish anything about
records whose landing tier is `B` or `C` rather than `Unscored` — Entain's revenue band
happens to place it below the graded floor. A future re-examination that clears a veto on
a lower-revenue record would still be the first live proof of a D → (B or C) transition.

**Zero collateral cost.** No provider, research, or judge node ran in either execution
(§9). No company other than Entain was writable at any point — the allowlist was asserted
non-empty and exactly one id/domain before each arm was trusted, and both windows closed
with independent, non-echoed read-backs.

**Item now fully discharged, not re-deferred.** This was the third consecutive phase this
item was assigned to (47.5, 48, 49) — it closes here.
