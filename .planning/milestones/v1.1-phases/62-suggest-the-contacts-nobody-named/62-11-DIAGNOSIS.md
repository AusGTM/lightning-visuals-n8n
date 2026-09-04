# G-62-6 Diagnosis — where the two lost rows went

Read-only against the n8n executions API (`GET` only — no dispatch, no arming, no
HubSpot write) and the committed `n8n/wf_enrichment_cloud.json`. Rows are named by
`row_id`; no email address or phone number from a real person is pasted below (the two
rows that got no verdict — `row-2`, `row-5` — are the entire point; the two that got a
verdict wrongly, `row-1`/`row-6`, are already named in `62-UAT.md`).

## Leg A — static, no network

### Multi-inbound-at-index-0 nodes on the contacts propose path

n8n runs a node once per inbound connection that DELIVERS data. A node fed by more than
one edge into its `main[0]` input can therefore run once per edge in a single execution
— and if different rows in the same batch take different upstream branches, that node
gets one run per branch, each carrying a subset of the batch.

Reachable on the contacts-propose lane, walking `n8n/wf_enrichment_cloud.json`'s
`connections`:

| Node | Inbound edges (source, output index) | Per-row data-dependent? |
|---|---|---|
| `Parse HubSpot Event` | `Execute Workflow Trigger`(0), `IF List Input`(1), `IF List Expanded`(0) | No — these are alternate ENTRY points (only one fires per invocation kind), not a reconverge of one batch's rows |
| `Enrichment Gate` | `Adapt Fetch By Id`(0), `Adapt Linkedin Search`(0), `IF Name Searchable`(1), `Adapt Name Search`(0), `Adapt Search`(0) | **Yes** — different rows can resolve identity by a different lane (id / linkedin / name-search / search) depending on what data each row carries |
| `IF Apollo Enabled`, `IF ZoomInfo Enabled`, `Normalize + Score`, `ZoomInfo Enrich` | provider-waterfall skip/cache-token chains | No, in the observed data — every item in a batch shares one config-driven branch; confirmed single-run in all three fetched executions |
| **`Merge Winners`** | `IF Contact Research Needed`(1, false-branch), `IF Contact Needs Judge`(1, false-branch), `Apply Contact Judge Verdict`(0) | **Yes — this is the node Leg B evidences firing** |
| `Merge Company` (company lane, sibling) | `IF Research Needed`(1), `IF Needs Judge`(1), `Apply Judge Verdict`(0) | Same shape as `Merge Winners`, on the COMPANY lane — no company rows in this batch, not evidenced live here |

Everything downstream of `Merge Winners` on the contacts lane is single-inbound
(`Merge Winners -> Set Data Quality + Gap Flag -> Decide Action -> IF Create -> {HubSpot
Create, IF Enrich -> {HubSpot Update, (skip)}} -> Build Response -> Respond to
Webhook`), so a multi-run split at `Merge Winners` propagates forward unchanged all the
way to `Build Response` and `Respond to Webhook` — confirmed by Leg B below.

### Run-0-only call sites, classified against Decision 2's table

| Call site | Reads | Verdict-row or metadata | In scope for this plan |
|---|---|---|---|
| `watch._build_response_rows` (via `report_enrichment._first_node_items` on `Build Response`) | the async round's verdicts | verdict-row | **yes — this is the confirmed defect (Q2)** |
| `report_enrichment.enrichment_row_ledger` (`Decide Action` / `Decide Company Action`, inline `runs[0] if isinstance(runs, list) and runs else None`) | verdict rows | verdict-row | **yes — Leg B shows `Decide Action` itself runs twice (`[1, 1]`) in `12096`/`12098`; a caller reading it directly (not through `recover_async_dispatch`) hits the identical defect** |
| `report.contact_row_ledger` (`Decide Action`, on `LV Contact Ingest (Cloud template)`) | verdict rows | verdict-row | no evidence — a DIFFERENT workflow, not exercised by `12096`/`12097`/`12098` (those are `LV Enrichment (Cloud template)` executions) — named, untouched |
| `report._write_node_items` (`HubSpot Update`/`HubSpot Create`, contact-ingest workflow) | "this landed" rows | verdict-row | same as above — different workflow, no evidence, named, untouched |
| `report_enrichment.remaining_credits_from_response` (`Build Response`, `Parse HubSpot Event`) | provider balances | metadata | no — explicitly excluded (Decision 2) |
| `watch.token_usage_from_execution` (`Build Response`) | token usage | metadata | no — explicitly excluded (Decision 2) |
| `watch._execution_carries_run_id` (`Parse HubSpot Event`, via `_first_node_items`) | correlation id | metadata-like, and `Parse HubSpot Event` is confirmed single-run in all three fetched executions | no |
| `scheduled_arm._sj3_ids` | — | already loops every run | no — precedent that runs can be plural |

## Leg B — live, read-only, over executions `12096`, `12097`, `12098`

All three: `status: success`. Per-node run/item table (only the nodes on the direct
contacts-propose path from `Parse HubSpot Event` to `Respond to Webhook`; the full
53-node dump for all three executions was produced and matches this pattern for every
remaining node — no node anywhere in any of the three executions shows a
summed-across-runs total below its input):

```
                                  12096            12097 (control)   12098
Parse HubSpot Event   runs/items  1 [2]     =2     1 [2]     =2     1 [2]     =2
Enrichment Gate       runs/items  1 [2]     =2     1 [2]     =2     1 [2]     =2
Lusha Enrich          runs/items  1 [2]     =2     1 [2]     =2     1 [2]     =2
Contact Web Research  runs/items  1 [1]     =1     1 [2]     =2     1 [1]     =1
Contact Judge Gate    runs/items  1 [1]     =1     1 [2]     =2     1 [1]     =1
Merge Winners         runs/items  2 [1,1]   =2     1 [2]     =2     2 [1,1]   =2
Set Data Quality+Gap  runs/items  2 [1,1]   =2     1 [2]     =2     2 [1,1]   =2
Decide Action         runs/items  2 [1,1]   =2     1 [2]     =2     2 [1,1]   =2
IF Create             runs/items  2 [0,0]   =0     1 [0]     =0     2 [0,0]   =0
IF Enrich             runs/items  2 [0,0]   =0     1 [0]     =0     2 [0,0]   =0
Build Response        runs/items  2 [1,1]   =2     1 [2]     =2     2 [1,1]   =2
Respond to Webhook     runs/items  3 [1,1,1] =3     2 [1,2]   =3     3 [1,1,1] =3
```

(`IF Create`/`IF Enrich` sum to 0 because every row in this batch took the `update`
path — `HubSpot Create` is entirely absent, `HubSpot Update` never ran either, meaning
every row's action was `write_blocked`/held before the write node, consistent with an
unarmed batch.)

`12096` and `12098` split into **two runs of one item each** starting at `Merge
Winners` and staying split all the way to `Build Response`. `12097` — the control,
where NEITHER row got a verdict lost — never splits: one run of two items,
start to finish. The split correlates exactly with what UAT already noted: in `12096`
and `12098` exactly one row had a Lusha match (an email came back) and one did not; in
`12097` neither row did, so both took the identical branch at `IF Contact Research
Needed` and never diverged.

Confirmed by `Contact Web Research`/`Contact Judge Gate`'s own item counts: `12096`/
`12098` each show only **one** item at these nodes (only the NOT_FOUND row needed
research+judge); `12097` shows **two** (both rows needed it, so both went down the
same branch together).

`Respond to Webhook` ran **three** times in `12096`/`12098` (once for `Build Async
Ack`'s early ack — this round used `async_ack: true` — and once per `Merge Winners`
branch reaching `Build Response`). Per `scripts/build_cloud_workflows.py`'s own
comment on this node (search `ENRICH_BUILD_ASYNC_ACK`/`Respond to Webhook`): "n8n's
webhook responder answers once and treats a later arrival as already-answered" — only
the FIRST arrival actually sends an HTTP response; the rest are no-ops on the wire.
This is the exact mechanism Q4 below extends to the synchronous path.

## Q1 — Is there a node whose SUMMED-across-all-runs output is short of what reached it?

**No.** Across all three executions and every node present in `runData` (53 distinct
node names checked per execution, not just the ones tabulated above), the
summed-across-all-runs item count never drops below its predecessor's. `Merge Winners`,
`Set Data Quality + Gap Flag`, `Decide Action` and `Build Response` all sum to exactly
`2` in `12096` and `12098`, matching `Parse HubSpot Event`'s own `2`. The rows are
split across runs, never dropped by a node.

## Q2 — Which run index does the client actually read, and what does it therefore see?

Run 0, always — demonstrated by calling the shipped `watch._build_response_rows(ex)`
directly on the fetched payloads, next to the summed `Build Response` total computed
the same way Leg B's table above was:

```
12096  watch._build_response_rows -> 1 row  ['row-1']          | Build Response summed total: 2
12097  watch._build_response_rows -> 2 rows ['row-3', 'row-4'] | Build Response summed total: 2
12098  watch._build_response_rows -> 1 row  ['row-6']          | Build Response summed total: 2
```

A returned `1` against a summed `2` in `12096` and `12098` — and a returned `2`
matching a summed `2` in the control, `12097` — IS the observed defect, reproduced
directly off the shipped reader with no code change.

## Q3 — Did a row that returned no verdict still consume provider credit?

**No — not according to `Lusha Enrich`'s own per-item `billing` block**, which
contradicts the `62-UAT.md` root-cause note's "almost certainly yes" inference from the
7-credits/6-rows arithmetic. Matched to `row_id` via `Build Identity`'s output (same
item order, confirmed by name):

```
12096  item 0 = row-1 (Mark Oaten)   billing: {creditsCharged: 2, resultsReturned: 1}  -- SURVIVED
       item 1 = row-2 (Tim Curry)    billing: {creditsCharged: 0, resultsReturned: 0}  -- LOST, Lusha itself: NOT_FOUND
12097  item 0 = row-3                billing: {creditsCharged: 0, resultsReturned: 0}  -- survived (no email either way)
       item 1 = row-4                billing: {creditsCharged: 0, resultsReturned: 0}  -- survived
12098  item 0 = row-5 (Brett Ashney) billing: {creditsCharged: 0, resultsReturned: 0}  -- LOST, Lusha itself: NOT_FOUND
       item 1 = row-6 (Craig Smith)  billing: {creditsCharged: 1, resultsReturned: 1}  -- SURVIVED (the false match, G-62-7)
```

Both lost rows (`row-2`, `row-5`) came back from Lusha's own `NOT_FOUND` error with
`creditsCharged: 0`. Lusha itself found nothing for them and charged nothing — a row
that returns no verdict from THIS system did not, in these two cases, cost a Lusha
credit. That is a materially different (and better) finding than the UAT's inference,
and it is worth stating precisely because it is the opposite of what the balance-delta
arithmetic suggested.

**A second finding, not asked for but visible in the same data and worth flagging
plainly:** summing every `Lusha Enrich` item's own `billing.creditsCharged` across all
three executions gives `2 + 0 + 0 + 0 + 0 + 1 = 3` credits for the six rows — not the
`7` the UAT's before/after balance read (`3886 -> 3879`) reported for this round. No
other provider in these three executions charged anything (`ZoomInfo Enrich` 401'd on
every item; `Apollo Match` returned an empty object with no billing field on every
item). This diagnosis does not have evidence for where the other 4 credits went — only
that these three executions' own item-level billing accounts for 3, not 7 — and does
not extend Decision 3's scope by guessing further. It is named here because
`62-UAT.md` already flagged once that a bare balance delta can misstate spend (the
Round-1 "3886 -> 3885 -> 3886" phantom credit); this is the same caution applying a
second time, in the other direction.

## Q4 — Is the SYNCHRONOUS path exposed to the same split?

**Yes.** `Respond to Webhook`'s own three-run trace in `12096`/`12098` (above) already
demonstrates the mechanism live: it fires once per arrival, and only the FIRST arrival
actually sends the HTTP response — the builder's own comment names this explicitly
("n8n's webhook responder answers once and treats a later arrival as already-answered").
In this round `async_ack: true` meant the first arrival was the cheap ack from `Build
Async Ack`, so neither of `Build Response`'s two runs was racing to be the
HTTP-visible one — the real rows were recovered later, off the settled execution, by
`recover_async_dispatch`, and lost there instead (Q1-Q2).

A SYNCHRONOUS caller (`async_ack` omitted or `False`) has no such cushion: `Build
Response`'s two runs (one per `Merge Winners` branch) race each other directly for
`Respond to Webhook`, and the loser's row is never on the wire at all — not staged
for later recovery, not reachable by any executions-API read a synchronous caller
would think to make, because it has no `run_id` to correlate by (that mechanism is
`async_ack`-only, per `watch.py`'s own module docstring on `_execution_carries_run_id`).

**Caller reached:** `operator-claude-plugin/scripts/preingest.py::rerequest_unanswered`
(the one-shot re-request pass over `merge_report.unanswered` — the exact mechanism this
gap's own retry path would use) calls `chunking.dispatch_plan(...)` at line 738 with
`async_ack` omitted, i.e. `False` by default. If a re-request chunk itself splits at
`Merge Winners` the same way `12096`/`12098` did, the loser's row would be silently
absent from `outcome.responses` with no correlate-and-recover option — the exact defect
this plan closes for the async path, unclosed on the synchronous one. `enrich-records`
and `contact-upload`'s enrich pass reach the same `dispatch_plan` default and carry the
identical exposure for any multi-row chunk.

**Proposed backend fix (not implemented here, per Decision 4):** collapse the multi-run
fan-in before `Build Response` — either merge `Merge Winners`' three inbound branches
into a single item stream before proceeding (an n8n Merge node, not a bare
reconvergence of `main[0]`), or have `Build Response` itself iterate every run of every
inbound node with `$(...).all()` instead of trusting a single item context. Either
requires a `scripts/build_cloud_workflows.py` regeneration, a `tests/n8n/*.test.mjs`
static guard, and an operator deploy — recorded as a standing UAT item, not attempted
here.

**Verdict:** reader_reads_run_0

## Remaining exposure

Same-class readers this plan does NOT touch, named for the record:

- `report.contact_row_ledger` / `report._write_node_items` (`Decide Action`,
  `HubSpot Update`, `HubSpot Create` on `LV Contact Ingest (Cloud template)`) — reads
  `runs[0]` only, same idiom, same risk shape (`Decide Action` there is fed by a
  single inbound edge in that workflow's own topology per a first read of its
  connections, but this diagnosis did not walk that workflow's graph with the same
  rigor Leg A gave the enrichment workflow, and no live execution of it was examined).
- `Merge Company` (`n8n/wf_enrichment_cloud.json`, company lane) — the structural
  mirror of `Merge Winners` (3 inbound edges: `IF Research Needed`, `IF Needs Judge`,
  `Apply Judge Verdict`), feeding `Decide Company Action` the same way. **Now an
  OBSERVED split, not merely a structural mirror**: execution 12103 (2026-09-04)
  showed `Merge Company` running more than once with run 0 carrying a strict subset
  of its items. `report_enrichment.enrichment_row_ledger`'s fix (Task 2) already
  covers it — the fix reads by node name across every run, not by lane — so no
  further change is needed, but the "no live evidence" caveat above no longer holds.
- **The run-0 reader trap, second live occurrence (quick task 260904-5a8, execution
  12103, 2026-09-04, three executions after 12096/12098).** The shape: a hand-rolled
  `runData[node][0]["data"]["main"][0]` read — indexing run 0 directly instead of
  concatenating every run, the same idiom this diagnosis's Verdict names above. The
  fix: `operator-claude-plugin/scripts/report.py::all_node_items(run_data,
  node_name)`, which concatenates every run in order and tolerates an absent node, a
  non-list run collection, and a malformed run entry as `[]`. The occurrence: an
  ad-hoc probe on execution 12103 read `Merge Company` run 0, saw 1 of 2 items, and
  the resulting report claimed `Merge Company` was collapsing two null-id company
  rows and silently dropping a record. It is not — `Merge Company` is a single
  `$input.all().map(...)` with no filter, group, Set, Map, or slice, so it
  structurally cannot emit fewer items than it receives. An investigation was spent
  on a node that had done nothing wrong. The reader defect is the whole cost of the
  trap.
- `Enrichment Gate` (5 inbound edges: id-fetch / linkedin-search / name-search /
  search lanes) — genuinely per-row data-dependent, upstream of `Merge Winners`, and
  therefore capable of its own independent multi-run split before a batch ever reaches
  the confirmed defect. Not evidenced live in these three executions (all three showed
  `Enrichment Gate: runs=1`), and no reader in this codebase currently takes only
  `runs[0]` of this specific node, so there is nothing to fix — named because the SAME
  shape exists and a future reader of `Enrichment Gate`'s own output should not assume
  single-run.
- The synchronous-path exposure named in Q4 (`Respond to Webhook`, reached by
  `preingest.rerequest_unanswered`, `enrich-records`, and `contact-upload`'s enrich
  pass) — quantified, not fixed, per Decision 4.
