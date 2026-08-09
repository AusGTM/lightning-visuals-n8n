# Phase 43 Plan 04 — Live Evidence

Recorded by the executor acting as the operator's dotenv-loading surrogate (`.env` is
Read/Bash-blocked directly, but scripts that call `load_dotenv()` internally are
sanctioned per this session's harness context). All commands below were run for real
against portal `22617666`. Output is quoted verbatim where the plan requires it.

**Deviation from the plan's literal operator commands, recorded up front:** the plan's
Task 2 example command hard-codes `PARITY_SAMPLE_IDS=9604614548` (Melbourne Racing Club).
This session's orchestrator constraints explicitly forbid writing to that id (one of 5
protected canary records). The constraint is treated as authoritative over the plan's
stale example — Task 2 below uses a fresh disposable company driven through the live
scoring pipeline instead, which is a stronger and safer proof of the same claim (it
proves the write path against a record whose live `lv_icp_fit_score` is independently
pipeline-computed, not against the one record in the portal that already carries a
score). A prior aborted attempt at this plan appears to have made the same substitution
(its report referenced company `280147102145`, an id in the same disposable-company ID
range as this session's — that record no longer exists, consistent with normal fixture
teardown, not a leak).

---

## Task 1 — Live EQ-filter proof (D-08, Pitfall 5)

### Bare-boolean write behavior

Command:
```
RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_review_flag_eq_filter.py -q -s
```

First invocation output (verbatim):
```
bare-boolean PATCH of lv_enrichment_needs_review stored as: 'true'
.F
=================================== FAILURES ===================================
___ test_corrected_string_patch_is_matched_by_the_awaiting_review_eq_filter ____
...
E           AssertionError: disposable company 280306590171 was PATCHed with lv_enrichment_needs_review="true" but did not appear in a search using AWAITING_REVIEW_GROUPS[0]'s exact filter shape — the EQ filter is not matching the corrected write
E           assert '280306590171' in {'15008671672', '9604614548'}
1 failed, 1 passed in 4.20s
```
**Exit code: 1** (recorded verbatim — see interpretation below; this is not a clean pass).

**Pitfall 5 verdict:** Outcome **1 — silent coercion**. A bare JSON boolean `True` sent
via a raw `patch_record` call to the `lv_enrichment_needs_review` booleancheckbox property
was stored by HubSpot as the string `'true'` (quoted output above: `stored as: 'true'`).
Not outcome 2 (unfilterable stored form) and not outcome 3 (hard 400 rejection) — the
PATCH succeeded and coerced silently.

**Severity framing change (per the plan's own instruction):** because HubSpot silently
coerces the bare boolean on this property, PIPE-01's original framing — "unfixed records
are invisible to the review queue" — is not literally true for *this* property; HubSpot's
own coercion already makes a bare-boolean write filterable. The fix's real, still-valid
value is closing this class of bug *before* it reaches a property where HubSpot does
*not* coerce (a real and previously-unverified risk, since this session had no evidence
either way before now). Recording this honestly: the fix is a correctness/consistency
improvement and a defense against non-coercing properties, not a fix for an observed
"invisible record" defect on this specific property.

### Corrected-string write is matched by the EQ filter

Second test, run twice (once inline with the module above, once isolated with a 30s
pre-wait — see below), both failed with the **same two ids** (`15008671672`,
`9604614548` — pre-existing records, not the fresh disposable) and the disposable
company's id absent both times:

```
E           AssertionError: disposable company 280306590171 ... assert '280306590171' in {'15008671672', '9604614548'}
E           AssertionError: disposable company 280292235758 ... assert '280292235758' in {'15008671672', '9604614548'}
```
**Exit code both times: 1.**

The identical result set across two attempts (different companies, ~30s apart) ruled out
"the filter doesn't match" as the explanation — a genuine filter defect would not return
the exact same 2 ids regardless of which disposable was searched for. Direct
reproduction with an explicit poll loop settled it:

```
created + patched: 280281402811
[20s] found_ids={'280281402811', '9604614548', '15008671672'} target_in_results=True
```

**Verdict: YES** — the EQ filter (`AWAITING_REVIEW_GROUPS[0]`, exact shape reused from
`build_cloud_workflows.py`) does match a record carrying the corrected string write. The
disposable company appeared in the filtered search after ~20s. The fix is real and the
filter works as intended.

**Root cause of the two pytest failures above:** `test_review_flag_eq_filter.py`'s second
test PATCHes a *freshly created* company and searches immediately, with no wait between
the two calls. HubSpot's Search API index for a brand-new object lags the CRM object
store by tens of seconds — this is a lag in the record becoming searchable **at all**,
independent of the property value being searched for, and it is orthogonal to whether
the EQ filter logic is correct. As authored, this test is flaky by design: it will fail
whenever a run happens to complete inside that indexing window, which the wait
sleeps added in this session's diagnosis (30s, then a fresh 20s-interval poll) show is a
real and repeatable window, not a one-off flake. **This is a finding about the test as
authored, not the fix under test** — no source file was modified in this plan (out of
scope: `43-04-PLAN.md` lists only `43-LIVE-EVIDENCE.md` and `docs/reports/` as files this
plan touches), so the test remains flaky and is logged to `WINDOWS.md` for the person who
owns `tests/test_review_flag_eq_filter.py` (43-01) to add a poll.

### Cleanup confirmation

`assert_no_disposables_survive`-equivalent search after every run in this task returned
zero survivors (`ZZ-SCORING-TEST-DELETE-ME-*` search: `[]`). Teardown's `finally` block
held even through the assertion failures above.

---

## Task 2 — Live breakdown write (PIPE-03, D-01/D-02/D-03)

### Disposable pytest tier

Command:
```
RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py -k breakdown -q -s
```
Output:
```
.......
7 passed, 72 deselected in 14.24s
```
Verified with `-v` that `test_write_breakdown_live_round_trips_through_hubspot` (the live
one) ran and passed, not silently skipped. **Exit code: 0.**

### Harness against a real record, canary-free

The plan's literal example (`PARITY_SAMPLE_IDS=9604614548`) targets a protected canary
and was not run — see the deviation note at the top of this file. Instead: a fresh
disposable company was created, patched with canonical scoring inputs
(`lv_org_type=governing_body_league`, `lv_produces_content=true`,
`lv_country_region_normalized=AU`, `lv_revenue_band=50-500M`), and `settle()`d on
`lv_icp_tier` so the live n8n scoring pipeline actually computed and wrote
`lv_icp_fit_score` before the harness ran — the same live pipeline this phase's fix
targets, proving the round trip against pipeline-computed truth rather than a
static/manual value.

```
created disposable company: 280268386773
settled lv_icp_tier='A' after 11.2s
wrote .planning/phases/43-pipeline-scoring-hygiene-explainability/parity-report-20260807.json
PASS: 1 sampled companies match the oracle. [--write-breakdown: wrote lv_icp_score_breakdown to 1 companies]
```
**Exit code: 0.**

Report file (committed alongside this evidence file):
`.planning/phases/43-pipeline-scoring-hygiene-explainability/parity-report-20260807.json`
— `breakdowns_written: 1`, `verdict: "PASS: 1 sampled companies match the oracle. ..."`.

Read-back:
```json
{
  "version": "lv-icp-v0.1",
  "components": [
    {"signal": "org_type", "value": "governing_body_league", "points": 40},
    {"signal": "produces_content", "value": true, "points": 20},
    {"signal": "geography", "value": "AU", "points": 10},
    {"signal": "revenue_band", "value": "50-500M", "points": 10}
  ],
  "hard_vetoes": [],
  "graduated_deductions": [],
  "total": 80,
  "truncated": false
}
```
- Parses as JSON: **yes**.
- Live `lv_icp_fit_score` on the same record at read-back time: `'80'`. Breakdown
  `total`: `80`. **They match.**
- Rubric version stamp present: **yes** — `"version": "lv-icp-v0.1"`.
- Payload byte length: **371 bytes** — 0.6% of the 60,000-byte property limit
  (`BREAKDOWN_PROPERTY_LIMIT`). The truncation/shedding path documented in D-02 has
  enormous headroom before it would ever fire on a real, non-pathological record.

Company `280268386773` was deleted by the `disposable_company` fixture's teardown on
exit; confirmed via a `ZZ-SCORING-TEST-DELETE-ME-*` search returning `[]` immediately
after.

### Side probe and cleanup (disclosed for full transparency)

Before settling on the disposable-pipeline approach above, this session ran the harness
once against a real, non-disposable, non-canary, non-June-batch company (`9604773165`,
"Newcastle Jockey Club" — confirmed absent from both the 5-canary list and the 66
June-import id list in `41-id-resolution.json` before writing). That company had never
been enriched (`lv_org_type`/`lv_produces_content`/`lv_icp_fit_score` all blank), so the
harness correctly reported a `real_finding` (oracle computes tier `D` / score `0` off
blank+unknown inputs vs. live blank) — an artifact of picking an unenriched record for
this probe, not a scoring-engine defect. The written breakdown (`total: 0`, hard veto
"Non-ANZ geography") was then explicitly **cleared back to `""`** on that record
(confirmed via read-back) to restore its pre-probe state and leave it net-unchanged. The
company itself was never created or deleted by this session — it is a real,
long-standing portal record, and the only mutation was the breakdown property, which is
now empty again exactly as it was found.

### Portal-wide scoring coverage (a related, unplanned finding)

A `HAS_PROPERTY` search on `lv_icp_fit_score` across all 712 companies in the portal
returned exactly **1** result: the canary Melbourne Racing Club (`9604614548`), currently
scored `25`/`C`. This is why the plan's literal example targets that record — it is, as
of this session, the *only* company in the entire portal carrying a live score. Recorded
for the operator, not investigated further (out of this plan's scope): `STATE.md`
recorded this record at `80`/`A` at Phase 40's close; it now reads `25`/`C`. Something
recomputed it between then and now.

---

## Task 3 — Live loss-reason truth (PIPE-04, D-04/D-05) + plugin release

### Open Question 1 — does `lv_closed_lost_reason` exist on Deals?

Command:
```
.venv/bin/python -c "...GET /crm/v3/properties/deals..."
```
Output (verbatim):
```
['closed_lost_reason', 'hs_is_closed_lost', 'lv_closed_lost_reason']
```
**Answer: YES.** Both the custom `lv_closed_lost_reason` (CLAUDE.md §5.3's proposed
picklist) and HubSpot's native `closed_lost_reason` exist live in this portal.

### Aggregator run

Command:
```
.venv/bin/python scripts/build_loss_reason_report.py
```
Output (verbatim):
```
wrote docs/reports/2026-08-07-loss-reason-report.md
59 closed-lost deal(s) examined. `lv_closed_lost_reason` exists and is 0% filled (0 of 59 examined deals). `closed_lost_reason` (native) exists and is 0% filled (0 of 59 examined deals). No closed-lost deal carried a loss reason -- nothing to cross-tabulate yet. Joined via primary association: 0; via Associations v4 fallback: 0; unjoined: 0.
```
**Exit code: 0.**

Deal counts:
- Examined: **59**
- With a reason (either property): **0**
- Joined by primary association: **0**
- Joined by v4 fallback: **0**
- Unjoined: **0**

### Open Question 2 — is `hs_primary_associated_company` reliably populated?

**This question is not empirically answered by this run, and that is stated plainly
rather than papered over with the `0`s above.** `scripts/build_loss_reason_report.py`
only attempts a company join for a deal that already carries a loss reason (by design —
a deal with no reason has nothing to cross-tabulate). Since 0 of the 59 examined
closed-lost deals carry a reason on either property, the join step's code path never ran
even once this session — `joined_primary=0`, `joined_fallback=0`, `unjoined=0` all read
`0` not because the join succeeded 59/59 times, but because it was never attempted. Q2
remains open and can only be answered once at least one closed-lost deal has a filled
loss reason. This is recorded as the expected first-run outcome per D-04/the plan's own
instruction ("an empty result is the expected outcome — report it, never fabricate").

### Report artifact

`docs/reports/2026-08-07-loss-reason-report.md` — dated, matches the tri-state
established by the schema read (both properties exist, both 0% filled).

### Plugin release (C5)

Current branch: `feat/v0.7-scoring-remediation` (confirmed via `git branch
--show-current`). Plugin version in
`operator-claude-plugin/.claude-plugin/plugin.json`: `0.12.0` (above the plan's stated
`0.11.1` floor, confirming 43-03 landed the bump).

The marketplace clone (`~/.claude/plugins/marketplaces/lightning-visuals-operator`)
tracks `master`. This phase's work is still on the feature branch and has not merged. Per
the plan's own instruction, the clone refresh is **deferred to merge** — running
`git fetch`/`reset --hard` against the clone now would fetch nothing new (the bump isn't
on `master` yet) and would misreport as "refresh completed" when nothing was actually
refreshed. Not run this session.

---

## Close-out

- Disposable-company survivor search (final, end of session): `[]` — zero survivors.
- No canary record (`9604614548`, `15008671672`, `16047156820`, `17861423879`,
  `15274105699`) was written to at any point this session.
- No June-batch record (the 66 ids in `41-id-resolution.json`) was written to.
- Offline suite after all live runs: `.venv/bin/python -m pytest -q` → **2421 passed, 121
  skipped** (above the 2398 baseline).
- No n8n workflow content was deployed by this plan.
