# Phase 36: Enrichment Propose Mode & Match Lane — Context & Handover

**Written:** 2026-08-05 for a context clear. **Read this first; it is self-contained.**
**Workstream:** `plugin-entrypoint` · **Backend only.** No plugin file changes. No plugin release.
**Paired with Phase 37**, which is the client half and depends on this landing first.

---

## 1. Where things stand

- **Phase 34 SEALED** (plugin `0.9.0`), **Phase 35 COMPLETE** (plugin `0.10.0`, on master, clone
  refreshed). UAT session 2 is **7/7 PASS**.
- Baselines to beat: plugin **1052 passed / 5 skipped** · full python **1933 / 6** · node **553** ·
  disarmed-artifact gate **0**.
- Tenant disarmed; 4 workflows active (`LV Backend Status`, `LV Contact Ingest`, `LV Enrichment`,
  `LV Scheduled Maintenance`), `LV Review Decision` inactive at rest and must STAY inactive.
- Branch `feat/v0.6-plugin-entrypoint`, in sync with `origin/master`.

---

## 2. The problem, measured live

A contact row with **firstname + lastname + company but no email dead-ends completely and silently.**

Live case: 9 Gold Coast Turf Club directors extracted from their board page (Phase 35's acceptance
walk) — names, roles, company, **no emails**. All 9 evaporate on upload.

Traced and verified in the deployed artifacts:

- `wf_contact_ingest_cloud.json`'s ONLY HubSpot query is `HubSpot Search by Email` (`email EQ`).
  `resolveIdentity.js` implements `phone_lastname` / `name_company` / `linkedin_url` branches, but
  those search keys are never populated in this lane, so they are dead code here.
- For a no-email row: `{outcome:"ambiguous", contact_id:null, reason:"no email, insufficient identity"}`.
- `Decide Action` routes `ambiguous → review` → `Set Review`, a bare `Set` node whose entire output is
  `{"queue":"needs_review"}` — every other field dropped.
- **No HubSpot write. No object id. No footprint.** The only durable trace is the n8n execution record.

**Consequence:** "upload now, enrich later" is not a slower path for these rows — **it is not a path at
all.** Both enrichment entry points require an existing HubSpot object id. Enrichment is what would
supply the email; the email is what ingestion needs to produce a record.

---

## 3. What ALREADY works — verified, do not redesign

`wf_enrichment_cloud.json` **already accepts a raw row**:

- `Parse HubSpot Event` spreads `...event` onto the row (a documented "minimum-scope shim").
- `Build Identity` builds `identity_keys` from **that payload**, not from a fetched record. Its own
  comment: *"Name+company let the providers match when no email is in hand (the common pre-enrichment
  case). ZoomInfo/Apollo accept firstName+lastName+companyName."*
- `objectId` is NOT mandatory. The only hard gate is `objectType`.
- `Adapt Search` on zero hits → `existingRecord:{}` → `Enrichment Gate` → `action:"create"`.
- Apollo (`first_name/last_name/organization_name`) and ZoomInfo (`hasZoomKey`:
  `emailAddress || (firstName && lastName && companyName)`) both accept name+company **today**.
- `Build Response` already returns the merged `properties`.

So the backend work is a **declared mode plus one extra search lane**, not new machinery.

---

## 4. The decision (operator, 2026-08-05)

Enrich-first becomes the **default**; ingest-first stays available for dense datasets. Governing rule,
the operator's words: *"a contact and company should be as enriched as possible BEFORE ingest. We do
NOT want incomplete contacts and companies in HubSpot."*

**This phase's four locked decisions:**

1. **Explicit `mode:"propose"`** — runs the waterfall, returns merged `properties`, **never enters the
   write path**. Explicitly NOT reading properties off a `write_blocked` response: that would make a
   feature depend on `ALLOW_HUBSPOT_CREATE` staying false, and this repo arms/disarms that constant for
   other reasons. The safety gate must keep doing only its own job.
2. **Match tiers.** `email EQ` → HIGH, auto-matched. Else `lastname EQ` + `company CONTAINS_TOKEN` →
   MEDIUM, returned as a **proposal** with enough of the candidate to judge it. No hit → enrich.
3. **Widen `Lusha Enrich` on cloud** to the name+company+domain identity set. `lushaContactBody()` in
   `n8n/code/lushaRequest.js` already supports it and is tested; the cloud node's inline expression is
   the narrow part, and that split is **currently deliberate and documented**. This is a recorded
   decision reversal, not a bug fix — rewrite the comment in place with the date and reason.
4. **Chunking stays client-side** (Phase 37). This phase's half is the refusal: an oversize `events`
   array is **refused whole, never truncated** (the D-15 principle the list lane already honours).

---

## 5. Two findings that change scope — both verified in the artifacts

### A. Mixed-lane duplication — a latent live bug this feature would activate

`Adapt Search` and `Adapt Fetch By Id` **both** open with `const rows = $('Build Identity').all();`
and index-align to their own HTTP node. Confirmed by reading the deployed JSON.

Safe today only because every batch is homogeneous. A CSV where row 0 has an email and row 1 does not
activates two lanes, and **both adapters emit both rows** into `Enrichment Gate` → duplicated provider
calls, double credit burn, duplicate response items. Adding a third lane makes mixed batches ordinary,
so this latent bug becomes a live one.

**Fix:** `Build Identity` computes `lane` once (`laneOf()`); each adapter filters to its own lane before
index-aligning. **Ships alone, is a bug fix on its own, and must land BEFORE the new lane.**

**Paired client-side rule** (two-sided, not backend-enforceable): a chunk carries rows of one lane.
That keeps exactly one lane active per execution and sidesteps n8n's `$(node).all()` run-index pairing,
which this repo's own comments flag as "not provable offline". Pin in
`tests/test_phase31_two_sided_contracts.py` — the existing precedent for exactly this shape.

### B. The ingest lane manufactures its own batch-wide failure

`HubSpot Search by Email`'s filter value is `($json.email_normalized || $json.email)`. For an emailless
row that is `undefined`, `JSON.stringify` drops the key, HubSpot rejects the filter, `onError:
continueRegularOutput` swallows it — and `Adapt Search Results` declares `let lookup_failed = false;`
**outside the row loop**, stamping it on every row.

So **one emailless row marks the whole upload lookup-failed**, and `Decide Action` demotes
`create → review` on that flag. That is this feature's own re-upload path breaking: the operator
confirms proposals, uploads the enriched CSV alongside rows enrichment could not fix, and the creates
silently do not happen.

**Fix (one expression, one node):**
```
value: ($json.email_normalized || $json.email || "no-email@invalid.invalid")
```
RFC 2606 `.invalid` can never be a real address. The search returns 200 with zero hits, `lookup_failed`
stays false. Does not touch the `search[i]` prohibition that `tests/test_ingest_search_contract.py` pins.

**Out of scope:** rewriting the batch-wide `lookup_failed` scope itself. Once it can no longer be
manufactured, a batch-wide flag can only be set by a genuine HubSpot failure, where fail-closed is
correct. Amend the comment to say the scope is now deliberate; do not rewrite it.

---

## 6. Wire contract

### Request

```json
{
  "mode": "propose",
  "providers": ["lusha","apollo","zoominfo"],
  "events": [
    {"row_id":"r1","objectType":"contact","firstname":"Jane","lastname":"Doe","company":"GCTC"}
  ]
}
```

| Field | Rule |
|---|---|
| `mode` absent | today's behaviour, **byte-identical** — no existing caller changes |
| `mode:"write"` | explicit today's behaviour |
| `mode` any other value | return-only — **fail-safe: a typo returns proposals, never writes** |
| `row_id` | client-generated, echoed verbatim, never interpreted. **The join key** — `event_id` is `sub:undefined:<now>` for an id-less row and is useless here |
| `events.length > ENRICH_MAX_LIST_RECORDS` | whole request **refused**, nothing enriched |

The predicate is deliberately NOT an allow-list of modes — two states, no third:
```js
const return_only = mode != null && String(mode).toLowerCase() !== "write";
```

### Response — 200, one item per row

```
{ row_id, mode, action:"proposed", object_type, hs_object_id,
  match: { tier, auto, reason, candidates:[{hs_object_id, firstname, lastname, email, jobtitle, company}] },
  properties: { ...only what the waterfall discovered... },
  gap_flag, remaining_credits }
```

| tier | when | `auto` | `hs_object_id` |
|---|---|---|---|
| `high` | `email EQ` hit, or caller-supplied `objectId` | true | set |
| `medium` | `lastname EQ` + `company CONTAINS_TOKEN` hit | **false — proposal** | null (candidates carry ids) |
| `none` | searched, no hit → enrich | false | null |
| `unknown` | the match search itself failed | false | null |

`unknown` is not `none`. "We did not find one" and "we could not look" are different answers and this
codebase collapses neither.

`properties` carries only what the waterfall **discovered** — `firstname/lastname/company` are absent
because the client already holds them and joins on `row_id`. That also sidesteps the BUG 19 create-seed
question: nothing here is a create payload.

---

## 7. Build plan (all changes are to `scripts/build_cloud_workflows.py`)

**The workflow JSON is GENERATED. Never hand-edit `n8n/*.json`.**

1. **`n8n/code/matchProposal.js`** (new, pure): `laneOf()`, `mediumCandidates()`, `summarizeMatch()`.
   `mediumCandidates` **re-verifies by value** — a candidate counts only if its `lastname` equals the
   row's case-insensitively AND its `company` shares a token. `CONTAINS_TOKEN` is fuzzy by design; the
   re-verification is the difference between a proposal and a guess (the BUG 22b lesson applied
   prophylactically — never trust that the search filtered).
2. **`lane` stamp** in `ENRICH_BUILD_IDENTITY` + lane filters in `ENRICH_ADAPT_SEARCH` and
   `ENRICH_ADAPT_FETCH_BY_ID_CONTACT`. Finding A. **Ships alone.**
3. **Match lane** — new nodes `IF Has Email`, `IF Name Searchable`, `HubSpot Name Search`,
   `Adapt Name Search`. Only `IF Bare Event`'s **false edge** re-points (to `IF Has Email`).
   Use the existing `_hs_http_search_node` helper. **`CONTAINS_TOKEN`, not `CONTAINS`** — HubSpot CRM
   v3 has no `CONTAINS` operator and a bare one is a guaranteed 400. Register `HubSpot Name Search` in
   `scripts/deploy_n8n_workflows.py`'s `NODE_CREDENTIAL_MAP`: an unmapped HubSpot node deploys
   **unbound** and 401s only at runtime — this repo has been bitten four times.
4. **Propose mode** — `ENRICH_PARSE_EVENT_CLOUD` reads `mode`; `ENRICH_DECIDE_CLOUD` sets
   `action:"proposed"` **before** `_writeSafetyAllows` and echoes `row_id`/`mode`/`match`;
   `ENRICH_DECIDE_CO_CLOUD` gets the same guard (a propose envelope with `objectType:"company"` must
   not write either). `"proposed"` matches neither `IF Create` (`=="create"`) nor `IF Enrich`
   (`=="enrich"`), so the row exits via `IF Enrich`'s false lane to `Build Response`. **No `ALLOW_*`
   constant is read on this path** — the arming grep stays 0 and the feature cannot be re-armed by
   flipping a flag.
5. **`Skip (NoOp)` and `Unsupported Object Type` become Code nodes** that spread the row. A `Set v3.4`
   emits only its assigned key, so a HIGH-matched fresh row would return an **uncorrelatable** reply
   with no `row_id`. Node names unchanged so connections and the credential map hold. Retire their
   exemptions in `tests/test_row_carry.py`.
6. **Batch-size refusal** on the `events` array. Pre-flight before shipping: confirm
   `SJ-3 Dispatch To Enrichment` in `wf_scheduled_maintenance_cloud.json` uses `mode:"each"`, and that
   no HubSpot webhook subscription posts to this URL (HubSpot natively batches ≤100 events per POST).
7. **Lusha widening** + rewrite the "deliberately narrow" comment in place to record the reversal:
   the narrow set was inherited from the retired v2 endpoint where name/company 400'd;
   `docs/LUSHA-V3-CONTRACT.md` §3 confirms v3 accepts them; the LOCAL-LIVE builder already sends the
   broad set; v3 bills ~1 credit flat per contact so the wider identity costs nothing extra.
   `tests/n8n/lushaRequestContract.test.mjs` already asserts expression-vs-module equality — extend its
   input matrix, which strengthens the anti-drift guard.
8. **`ENRICH_GATE`** — beside the existing `lookup_failed` override: no email, no linkedin, no
   lastName+companyName → `action = "skip"`. Never burn three provider calls on an unmatchable row.
9. **Ingest sentinel** — finding B. **Independent; can ship first.**

---

## 8. Definition of done

1. A `mode:"propose"` request returns merged `properties` and `match` per row, with `row_id` echoed,
   and **writes nothing** — proven regardless of `WRITE_SAFETY_DEFAULTS`.
2. `mode` absent behaves **byte-identically** to today. No existing caller changes.
3. A mixed-lane batch (one row with an email, one without) emits each row **exactly once**.
4. A `CONTAINS_TOKEN` hit on the wrong surname yields **zero** candidates.
5. An oversize `events` array is refused whole with a reason; nothing is enriched.
6. An emailless row in the INGEST lane no longer sets `lookup_failed`, so sibling rows in the same
   upload keep their `create` action.
7. `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0**. No arming anywhere in this phase.
8. Suites green against §1's baselines (expect ~+30 node, ~+15 pytest).
9. Rebuilt, deployed **disarmed**, every active workflow **bounced**, read back `--expectation disarmed`.

---

## 9. Non-negotiables

1. **The JSON is generated** — change `scripts/build_cloud_workflows.py`, never `n8n/*.json` by hand.
2. **Never fix a test by making its premise false.**
3. **Red-check every new test** — revert, confirm the specific assertion fails, restore.
4. **Commit explicit paths only.** Never `git commit -a`.
5. **Never touch `~/.claude/plugins/`.**
6. **No arming.** No `ENABLE_BAKED_FLAGS`, no `ALLOW_HUBSPOT_*` set to true.
7. **Deploy is disarmed + BOUNCE.** A bare PUT never reloads a running workflow; only a
   deactivate→activate cycle does, and a read-back proves stored content only.
   **The classifier denies `scripts/deploy_n8n_workflows.py` to agents in every form** — hand the
   operator the one-liner from `35-CONTEXT.md` §6 and let them run it via `!`. The bounce
   (`n8n_control.set_active`) and the read-back DO pass and can be run by the agent.

---

## 10. One pinned test changes deliberately

`test_gate_exists_and_true_false_lanes_target_fetch_and_search_respectively` in
`tests/test_fetch_by_id_topology.py` asserts `IF Bare Event`'s false lane targets `HubSpot Search`.
It now targets `IF Has Email`. Amend with the reason inline, per this repo's convention.

---

## 11. Test commands (exact forms — alternatives are broken here)

```bash
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q   # 1052 passed, 5 skipped
.venv/bin/python -m pytest -q                                  # 1933 passed, 6 skipped
node --test tests/n8n/*.test.mjs                                # 553 pass (FILE glob only)
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json             # must be 0
```

System python lacks the deps. The node directory form is broken on node 24.

---

## 12. Risks (highest first)

1. **`Build Response` first-arrival truncation.** It has multiple inbound branches and fires on
   whichever arrives first — documented in the builder as "NOT hard determinism". The skip branch is
   1 hop; the waterfall is ~15 plus HTTP. A chunk mixing a skip row and an enriched row could answer
   with the skip row only. Mitigations: propose rows rarely skip; the chunk ceiling of 2 caps exposure
   at one row; `row_id` lets the client detect a row it got no verdict for. **Upgrade path if measured:**
   route propose-mode skip rows through the waterfall with all providers disabled — zero credits, one
   terminal. Do not build it until it bites.
2. **`company` is often blank on HubSpot contact records** (the association lives on the company
   object), so MEDIUM will miss real matches. Benign: a miss becomes "unmatched → enrich", never a
   wrong match.
3. **`CONTAINS_TOKEN` is token-based, not substring** — "GCTC" will not match "Gold Coast Titans Club".
   Value re-verification protects against false positives, not false negatives. A miss costs one
   enrichment; a wrong auto-match corrupts a record.
4. **Lusha name+company on cloud is documented but unproven on this endpoint.** The first propose run
   is the live proof; per-provider errors already surface in the response.

---

## 13. Sequencing

Steps 2 (lane stamp) and 9 (ingest sentinel) are independently valuable, independently revertable, and
fix live bugs. They can ship first. **Nothing before step 4 changes any existing caller's behaviour.**
