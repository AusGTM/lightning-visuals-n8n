# Phase 47 — handover (2026-08-12)

Written because the prior session ran out of context immediately before the armed write window.
**Nothing is armed. Zero HubSpot writes have occurred at any point in this phase.**

---

## Where things stand

| Plan | Wave | State |
| --- | --- | --- |
| 47-01 | 1 | ✅ complete — `scripts/remediate_veto_companies.py` + 28 offline tests |
| 47-02 | 1 | ✅ complete — D-02 traceability, `47-COST-ESTIMATE.md`, `COVERAGE.md` |
| 47-03 | 2 | ✅ complete — before-snapshot, property guard, live research pass, disarmed dry-run |
| 47-04 | 3 | ⬜ **not started** — the armed window. `autonomous: true` per D-22 |

Full suite green (2579 passed, 128 skipped). Working tree clean. `scripts/run_scoring_parity.py`'s
population sweep is **red by design** until Phase 49 — not a defect, do not fix it here.

---

## Do this first

### 1. Re-verify Anthropic credit

It ran out mid-phase and was topped up. Confirm before spending:

```bash
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from anthropic import Anthropic
print(Anthropic().messages.create(model='claude-haiku-4-5-20251001',max_tokens=4,
      messages=[{'role':'user','content':'ok'}]).usage)"
```

Background in `47-BLOCKED.md`. Note the key in `.env` is the only working credential — the SDK's
auto-discovered profile is malformed (`~/.config/anthropic/credentials/default.json`, missing
`refresh_token`).

### 2. Re-run the abort checks on the dry-run

`47-PRE-ARM-REVIEW.md` confirmed these clean, but re-confirm after any change:

```bash
D=.planning/phases/47-veto-remediation/47-DRYRUN.md
grep -nE '"(lv_anti_icp_flag|lv_anti_icp_reason|lv_icp_fit_score|lv_icp_tier)"\s*:' $D   # must be empty
grep -nE '"lv_produces_content"\s*:\s*(false|"false")' $D                                 # must be empty
grep -cE "10024564084|15860277364|17317184159" $D                                         # must be 0
grep -oE '\b[0-9]{10,11}\b' $D | sort -u | wc -l                                          # must be 17
```

Abort before arming if any fails.

---

## The one thing that changed late — read before arming

**Jam TV (`17317850381`) is a TRUE veto and must NOT clear.** See D-23 in `47-CONTEXT.md`.

The portal holds two separate records: this one is the **Italian** broadcaster (`jamtv.it`,
`country: Italy`, `industry: BROADCAST_MEDIA`), and there is a *different* record for the
Australian sports-and-entertainment company. Operator confirmed its current scoring card is
correct — score 0, anti-ICP flag Yes, Tier D, reason "Non-ANZ geography".
Record: https://app-ap1.hubspot.com/contacts/22617666/record/0-2/17317850381

Phase 46 flagged it `false_veto` only because `lv_country_region_normalized` was blank — the
blank-region bug making a genuine veto look manufactured.

**It stays in the window, written once:** `lv_country_region_normalized = "Other"`. The veto then
correctly persists.

**Why it is not simply dropped.** VETO-03's bar is a HubSpot search for *a non-ANZ veto reason AND
a blank `lv_country_region_normalized`* returning zero. Jam TV currently matches **both** halves.
Dropping it leaves VETO-03 failing on the one record everyone agrees is correct. Writing `Other`
populates the field and moves it outside the search.

**Expected window outcome: 16 clear, Jam TV correctly stays Tier D.**

`47-04-PLAN.md`'s `must_haves` were amended for this (commit below). A prior session's
`47-PRE-ARM-REVIEW.md` calls Jam TV a "wrong-entity match" — **that conclusion is superseded by
D-23**; the research was correct, the review was not. The rest of that review still stands.

---

## Also expected, not failures

- **Simtech LED (`18047161864`) classifies `hardware_vendor`** — a *genuine* hard veto, correct
  under D-16. It will not reach a real tier and that is right.
- **Editix (`17317381378`) is unresolved** — `matched: false`, `confidence: 5`. Searches on the CRM
  domain `edetrix.com.au` found nothing. Correct D-14 behaviour; recorded as un-enrichable with a
  stated reason, satisfying COVER-01's "distinguishable from never attempted" bar. Its CRM domain
  may itself be a data-entry error (name "Editix" vs domain `edetrix.com.au`) — out of scope.
- **16 of 17 land with no `lv_org_type`.** Research returned free text ("Sporting club / Racecourse
  operator", …) and the enum gate correctly refused to guess-map it. **VETO-01 still lands** — the
  veto clears on *region*, not org type. COVER-01 is only partly served, which D-02 explicitly
  permits (it maps to both Phase 47 and 48). Structural fix is locked for Phase 48 — see below.
- **Coffs Harbour (`14752488879`)** — raw research returned `produces_content: false` and
  `is_gambling_operator: true`, both wrong, both correctly gated out of the payload. The **cache
  retains them**, so anything re-reading `47-RESEARCH-RESULTS.json` raw must re-apply the gates.

---

## Running the window

`47-04-PLAN.md` owns the ceremony; follow its four tasks. Key constraints:

- **D-22 — arming is delegated to Claude for this run only** (operator said `run autonomous:true`,
  2026-08-12). Set `ALLOW_VETO_REMEDIATION`, `DRY_RUN=false`, `ALLOW_N8N_ARM`,
  `ALLOW_HUBSPOT_RECORD_WRITES` **per-shell only** — never a profile, never `.env`. This waiver is
  scoped to Phase 47 and expires with it.
- **D-19 — arm BOTH surfaces:** the script's own env gate AND the n8n workflow via
  `n8n_arming.arm_for_dispatch()` with `TEST_RECORD_IDS` = the pinned ids. **Disarm is ungated** and
  must run even if the write leg fails. Disarm both, then **independently read back** both and quote
  them verbatim in `47-RUN-REPORT.md`.
- **D-07 — never PATCH** `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_icp_fit_score`,
  `lv_icp_tier`. Change inputs; let the derived chain settle.
- **D-21 — write only** `lv_org_type_verified_at` and `lv_produces_content_verified_at` to HubSpot;
  19 of 21 D-09 metadata properties do not exist live. The rest of the evidence trail lives in
  `47-RESEARCH-RESULTS.json` / `47-RUN-REPORT.md`.
- **Two settle loops, never one:** `settle_tier` (~120s, calculated property + WF1) and
  `settle_veto` (~900s, n8n-dependent). Separate timeouts.
- **Do NOT trust n8n `status: success`.** Discovered live this phase (`47-BLOCKED.md`): the
  `Claude Web Research` node reports `executionStatus: "success"` with zero node errors while
  400-ing, passing its error downstream **as data**. The only trustworthy evidence is the read-back
  of `lv_anti_icp_flag` — which `settle_veto` already does.
- **One window.** Do not reopen to retry.

---

## Decisions locked this session (do not re-litigate)

In `47-CONTEXT.md`:

- **D-18** trigger is a direct webhook POST per record · **D-19** two armed surfaces, not one ·
  **D-20** the ~4 redundant second-pass research calls are accepted and budgeted ·
  **D-21** D-09 narrowed to the 2 stamps that exist live · **D-22** arming delegated for this run ·
  **D-23** Jam TV is a true veto.

In `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md` — **Phase 48/49 work, not
Phase 47**:

- **D-V1** new `venue` org type, weight **5**, no hard veto, motion `work_via_league`
- **D-V2** on entity collision, `individual_club_team` wins (the club is the buyer; the venue is
  its asset)
- **D-V3** implement Phase 48, score in Phase 49's full-population re-score
- **D-V4/D-V5** three-layer determinism — generation-time enum schema, deterministic reviewed alias
  table, `unknown`-answering classifier fallback — applied to `lv_org_type`,
  `lv_country_region_normalized`, and **every** property read by exact value. Booleans are
  tri-state; layer 1 must offer `unknown` explicitly.

---

## Loose ends for after the window

1. **`46-SIMULATION-REPORT.md` still flags Jam TV `false_veto`** — correct it so a later phase does
   not re-target the row.
2. **`.planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-failure.md`** — the silent
   n8n failure. Real defect, separate from the billing state.
3. **`scripts/remediate_veto_companies.py:142`** claims free text "400s the batch because the
   property is an ENUMERATION". It is **not** an enumeration in HubSpot
   (`docs/WEB-RESEARCH-SPEC.md:208`); writes are accepted and then silently score 0 via
   `.get(org_type, 0)`. Right discipline, wrong stated reason — fix the comment before someone
   removes the gate.
4. **Phase 47 requirement ticks** (VETO-01/02/03) belong to 47-04, not earlier plans.

---

## Key artefacts

```
.planning/phases/47-veto-remediation/
  47-CONTEXT.md            D-01..D-23 (three amendment blocks near the end)
  47-PRE-ARM-REVIEW.md     abort checks; its Jam TV conclusion is superseded by D-23
  47-BLOCKED.md            the billing outage + the n8n silent-failure evidence
  47-DRYRUN.md             exact PATCH payloads and webhook bodies
  47-RUN-REPORT.md         predicted outcomes; actuals to be filled by 47-04
  47-RESEARCH-RESULTS.json the cache 47-04 consumes via --from-cache
  47-BEFORE.json           live before-snapshot of all 17
  47-COST-ESTIMATE.md      ex-ante budget; fill actuals after the run
.planning/decisions/2026-08-12-org-type-venue-and-normalization.md
```

Resume with `/gsd-execute-phase 47` (it will pick up 47-04 as the only incomplete plan).
