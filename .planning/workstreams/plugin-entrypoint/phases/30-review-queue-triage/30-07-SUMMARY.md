# 30-07 / RB-9 — the armed review canary

**Status: RUN 2026-08-03, agent-driven end to end at the operator's instruction. Steps 1-7 and 9-10
PASS. Step 8 (APPROVE) is BLOCKED by a product bug and is recorded as blocked, not passed.**

**At a glance:** armed read-back **PASS** (review armed, dispatch pair still disabled) · both plugin
gates proven to hold **alone, with zero requests built** · reject **verified** by independent re-read
and the record correctly stayed queued · approve **failed closed** on a HubSpot 400 · window closed,
**disarmed PASS** · **no other record touched**, on three independent lines of evidence.

**The headline finding:** the pipeline stages provider free-text into `industry`, which is a HubSpot
**enumeration**. Every approve of an `industry` candidate 400s, the preview cannot detect it, and the
client reports it with the same `unparseable_response` it uses for a fail-closed allowlist drop — so
the runbook's own diagnostic advice points the operator away from the real cause.

---

## Pre-flight — established read-only, 2026-08-03, before any arming

| Item | Value |
|---|---|
| Canary record | **`9604614548` — Melbourne Racing Club, a COMPANY** |
| How it was chosen | RB-7's armed enrichment produced it: the pipeline flagged it `needs_review` and held a real conflict, satisfying step 1 with no setup |
| The held conflict | `industry` — provider `arts, entertainment, and recreation` vs stored `SPORTS`; staged as a review candidate, current value untouched |
| Review workflow | `WBJwoZOo63wzeP69` — `LV Review Decision (Cloud)`, **currently inactive** |
| Review endpoints | `hubspot/review/queue`, `hubspot/review/decision` — both in that workflow, hence `http_404` until step 4 |
| Flag state BEFORE | **disarmed everywhere** — `verify_live_write_safety.py --expectation disarmed` → `VERDICT: disarmed PASS`, 5 workflows / 11 declaring nodes |
| Tenant | `https://alexherman.app.n8n.cloud` |

Because the record is a **company**, point 3's "contacts are allowlistable only by `TEST_RECORD_IDS`"
trap does not apply — but `TEST_RECORD_IDS=9604614548` is what to use regardless.

### The reload gap applies here — read this before step 3

`ENABLE_BAKED_FLAGS` overlays every workflow in the deploy set, and `ALLOW_HUBSPOT_REVIEW_WRITES` is
declared in four, **three of them ACTIVE**:

```
LV Scheduled Maintenance (Cloud)     ACTIVE    4 nodes  <-- hosts the 15-min approve backstop
LV Enrichment (Cloud template)       ACTIVE    2 nodes
LV Contact Ingest (Cloud template)   ACTIVE    2 nodes
LV Review Decision (Cloud)           inactive  2 nodes
```

`deploy_n8n_workflows.py` PUTs without activating, so those three keep serving disarmed bodies until
bounced. Predicted, before the fact:

1. **Step 3b will report `armed PASS` while three running instances are still disarmed** — it reads
   stored content. Same false confidence that burned RB-3.
2. **Step 8's APPROVE will probably do nothing**, because the documented approve flow goes through
   `reviewApply.js`'s 15-minute backstop, which lives in `LV Scheduled Maintenance` — active, cadence
   confirmed live (ticks 03:30, 03:45, 04:00Z). Its running body will still be disarmed.

**Mitigation: bounce all three active workflows immediately after step 3, and again after step 9.**
Step 4 handles `LV Review Decision` by activating it from cold.

**Step 9's order is reversed from the runbook's original:** deactivate `LV Review Decision` FIRST,
then redeploy disarmed, then bounce the three actives, then read back.

**Record whether prediction 2 held.** If the approve lands without a bounce, the model of the
backstop is wrong and that is the more valuable finding.

---

## The run

### Step 2 — before snapshot — **DONE 2026-08-03T04:16:52Z**

**The runbook's flag name is wrong.** There is no `--company-id`; the interface is `--target-id`
plus `--target-object-type`. Command actually run:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/canary_record_snapshot.py', run_name='__main__')" \
  snapshot --label 30-07-review-canary --target-id 9604614548 --target-object-type companies
```

Artifact: `.planning/phases/22-armed-e2e-enrichment-canary/snapshots/30-07-review-canary-20260803T041652Z.json`
(the script writes into Phase 22's snapshots directory by construction — not a mistake, just not
where a Phase 30 reader will look for it).

Also printed: `research_gate_will_fire: true` — `lv_produces_content` is blank.

**Before-state of the review-relevant properties:**

```
lv_enrichment_needs_review           'true'
lv_enrichment_status                 'needs_review'
lv_enrichment_review_reason          'industry: Refresh candidate requires review in MVP.'
lv_enrichment_review_candidate_json  [{"chosen_value":"arts, entertainment, and recreation",
                                       "confidence":85,"current_value":"SPORTS","decision":"ne…}]
lv_enrichment_provenance             {"industry":{"confidence":85,"source":"waterfall",
                                       "validation_status":"human_review_required",
                                       "value":"arts, e…}}
lv_enrichment_review_approved        None
lv_enrichment_reviewed_at            None
lv_enrichment_reviewed_by            None

lv_org_type                          'individual_club_team'   (verified_at 03:39:12.266Z)
lv_content_type                      'live_broadcast'
lv_country_region_normalized         'AU'
lv_employee_band                     '201-500'
lv_sponsorship_reliant               'true'
lv_icp_fit_score                     '2'
lv_icp_tier                          None
lv_icp_score_breakdown               None
lv_icp_needs_review                  None
```

**This makes step 8's provenance check exact.** After the approve, `industry`'s provenance entry must
name a **human** source with `human_approved`, a timestamp and the reason — **and `"source":"waterfall"`
with `confidence: 85` must still be readable inside that entry.** The three `reviewed_*` fields being
`None` now means any value they hold afterwards came from this canary and nothing else.

**⚠ Neighbour coverage is thin — step 10 will be weak as it stands.** The snapshot captured exactly
**one** neighbour, `contacts/201`, whose `name` is `None`. "No other record was touched" rests on
that one comparison plus the allowlist. **Before step 10, re-run the snapshot with several
`--neighbor-company-id` values** (the other HubSpot test companies) so the neighbour verdict has
something to say. As captured, a write to any real company other than the target would go unnoticed
by `compare`.

### Step 3 — armed deploy, review writes only — **DONE 2026-08-03T~04:2xZ**

**Run by the agent at the operator's explicit second instruction.** The agent flagged that HANDOFF §5
records arming as the one line kept agent-blocked; the operator reaffirmed. See the HANDOFF §5
amendment — the invariant was changed deliberately, not eroded.

```
ENABLE_BAKED_FLAGS: ALLOW_HUBSPOT_REVIEW_WRITES -> "true" rewritten 10x in
  ['LV Contact Ingest', 'LV Enrichment', 'LV Review Decision', 'LV Scheduled Maintenance']
ENABLE_BAKED_FLAGS: TEST_RECORD_IDS -> "9604614548" rewritten 10x in (the same four)
updated ... (200) x5
```

**Rewrite count 10×, non-zero.** Four declaring workflows — exactly the blast radius predicted
above, no surprises.

- **Bounce of the three active workflows: DONE.** `deactivate=200 activate=200` for Scheduled
  Maintenance, Enrichment and Contact Ingest; all three restored active.

> **Note on the prediction.** Prediction 2 (the approve would no-op without a bounce) can no longer
> be cleanly falsified, because the mitigation was applied rather than withheld. Safety was chosen
> over the experiment, deliberately. If the approve now lands, that is *consistent with* the
> prediction but does not prove it; proving it would have required knowingly running an armed window
> in a state believed broken.

### Step 3b — armed read-back — **VERDICT: armed PASS**

```
expectation: armed
expected allowlist: '9604614548'
expected armed: ALLOW_HUBSPOT_REVIEW_WRITES
every other write-enabling boolean is asserted disabled wherever it is declared
coverage: 5 workflow(s) fetched, 11 declaring node(s) found
  ... ALLOW_HUBSPOT_REVIEW_WRITES='true'  TEST_RECORD_IDS='9604614548'
  ... ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false'   (everywhere)
VERDICT: armed PASS
```

**The symmetric assertion is the point:** review authority armed, the dispatch pair still disabled
everywhere it is declared. The window is scoped, not widened.

### Step 4 — activate the review-decision workflow — **DONE**

- `POST /activate` → `200`; read-back confirms `active: true`.
- Queue endpoint reachable afterwards: **yes** — `available: True`, `reason: None`,
  `object_type: companies`, `total: 1`, `returned: 1`, the single row being **Melbourne Racing Club**.
  The prior `http_404` was the workflow being off, as predicted.

**Queue row shape, for whoever drives the decision:** the record id arrives as **`hs_object_id`**
(`"9604614548"`), not `record_id` or `id`. The row also carries `domain` (`mrc.racing.com`),
`lv_enrichment_review_candidate_json`, `lv_enrichment_review_reason` and the full
`lv_enrichment_provenance` blob. The provenance shows the enrichment used **`claude_web`** with
evidence URLs for `lv_content_type` and `lv_country_region_normalized`, and `waterfall` for
`industry` and `lv_employee_band` — so RB-7 exercised the research lane too, which its own log did
not record.

**⚠ The armed window is now OPEN and stays open until step 9** — unlike RB-7's 54 s self-closing
cycle. Blast radius is one record. `LV Scheduled Maintenance` is armed, active, and on a 15-minute
cadence carrying `Review Apply Update Write Gate`, so **once `lv_enrichment_review_approved` is set,
the backstop can apply it automatically within 15 minutes.** That is the documented approve path,
not a fault — but it means the approve is not necessarily instantaneous or operator-triggered.


### Step 5 — the queue read — **PASS, with one defect found**

Queue rendered `1 flagged, all shown below`, the record named, and the conflict in plain language:

```
## Melbourne Racing Club
Flagged because: industry: Refresh candidate requires review in MVP.
- **industry**
  - HubSpot holds now: SPORTS
  - The pipeline wants to set: arts, entertainment, and recreation
  - Proposed by: waterfall, confidence 85
  - Held back because: Refresh candidate requires review in MVP.
```

`held_decisions()` returned the single stored candidate intact.

**DEFECT — the HubSpot link renders broken.** `render_record` extracts `row.get("hs_object_id")` at
its line 246 and then calls `link_lookup(row)` at line 247 — passing the **whole row**, not the id.
`record_link(object_type, record_id, portal_id)` takes an **id**. The two do not compose, and the
natural composition produces:

```
Open in HubSpot: https://app.hubspot.com/contacts/22617666/record/0-2/{'createdate': '2022-09-16…<entire row dict>
```

`record_link`'s own docstring says "A broken link is worse than no link" — and this is exactly that.
`tests/test_review_queue.py:96` encodes the correct lambda
(`lambda row: record_link(object_type, row.get("hs_object_id"), portal_id)`), but
`skills/review-triage/SKILL.md:61` shows only `render_queue(rows, total, policy_lookup, link_lookup)`
and **never defines what those lambdas must be**. So the tested side is right and the shipped
instructions are silent — **the fifth instance of this milestone's recurring "a contract held in two
places, tested on only one" defect** (HANDOFF §2 counted four).

**Fix:** put the two lambda definitions verbatim into `review-triage/SKILL.md`. Not applied here — it
would have changed the surface mid-canary.

### Step 6 — preview with writeback NOT armed — **PASS**

Ran with `ALLOW_REVIEW_SUBMIT` unset, confirming previews are ungated by design (D-03/D-05).

| decision | outcome | would_write |
|---|---|---|
| reject | `rejected` | **1 key** — `lv_enrichment_review_reason` |
| approve | `applied` | **8 keys** — `industry`, `lv_enrichment_needs_review`, `lv_enrichment_provenance`, `lv_enrichment_review_approved`, `lv_enrichment_review_candidate_json`, `lv_enrichment_review_reason`, `lv_enrichment_reviewed_at`, `lv_enrichment_reviewed_by` |

Matches D-30 exactly. Nothing was sent.

Worth noting: an **approve** sets `lv_enrichment_review_approved` to `False`. Presumably "no longer
awaiting apply", but the naming reads backwards and an operator seeing the patch would reasonably
misread it.

### Step 6b — each gate proven ALONE — **PASS, stronger than asked**

The runbook says to prove gate 1 with a **rejection**. That is wrong and contradicts its own gate
table: `UNDOING_DECISIONS = ("reject",)` deliberately exempts reject from `ALLOW_REVIEW_SUBMIT`, so a
rejection can never demonstrate that gate. **Gate 1 was proven with an approve instead.**

A spy transport that raises if a request is even constructed was injected for both probes:

| probe | env | session arm | decision | result | transport calls |
|---|---|---|---|---|---|
| 6b-i | `ALLOW_REVIEW_SUBMIT` **unset** | armed | approve | `submit_not_enabled`, message names `ALLOW_REVIEW_SUBMIT` | **0** |
| 6b-ii | `ALLOW_REVIEW_SUBMIT=true` | **not armed** | approve | `not_armed` | **0** |

**Zero calls in both cases** — not merely refused, but no request built at all.

### Step 7 — REJECT — **PASS, and it proved the exemption live**

Run deliberately with `ALLOW_REVIEW_SUBMIT` **unset**, to test the documented exemption rather than
assume it.

```
outcome: rejected
verified_properties: {'lv_enrichment_review_reason': 'RB-9 canary: rejecting the industry candidate; …'}
VERDICT status: verified | mismatched: []
"Confirmed: the record was re-read after the write and all 1 field(s) hold the approved values."
```

Record **still queued** afterwards: `total: 1`, `lv_enrichment_needs_review='true'`, candidate still
stored. Exactly the required behaviour.

**Finding — a rejection leaves no audit trail of who or when.** `lv_enrichment_reviewed_by` and
`lv_enrichment_reviewed_at` remain `None` after a rejection, because D-30 restricts it to one key.
The reason text is the only evidence a human acted. For a surface whose purpose is auditable human
adjudication, that is a gap worth a decision.

### Step 8 — APPROVE — **BLOCKED BY A PRODUCT BUG. Not a pass.**

```
available: False | reason: unparseable_response | outcome: None
VERDICT status: failed
```

**Nothing landed** — the record was unchanged, `hs_lastmodifieddate` still the reject's 04:42:07.934Z.
Fail-closed behaved correctly.

**Root cause, established rather than guessed:**

1. n8n execution **1173 = `error`** (not a silent gate drop). `execution_errors.py` named it:
   node `Review Decision Update`, cause `malformed_record`, raw **`Bad request - please check your
   parameters`** — a HubSpot 400.
2. HubSpot's `industry` on companies is an **`enumeration` / `select` with 148 fixed options.**
   `SPORTS` (the stored value) is a valid option. The staged candidate
   **`arts, entertainment, and recreation` is not an option at all** — it is a provider display
   label.
3. All seven other keys in the approve patch validate clean against the live property schema
   (`bool`, `string`, `datetime` as appropriate). **`industry` is the sole cause.**

**So the enrichment pipeline stages provider free-text into a HubSpot enumeration property without
mapping it to a valid option, and every approve of an `industry` candidate 400s.** The record was
only ever safe because the non-clobber policy held it at `needs_review` — the approve path for this
field cannot succeed as built.

**The preview cannot catch it.** `preview_decision` returned `outcome: applied` with the invalid
value, because the dry run computes the patch without validating against HubSpot's property schema.
The operator is shown, and asked to approve, a write that is guaranteed to fail.

**⚠ The runbook's diagnostic advice is actively misleading for this failure.** It says an
`unparseable_response` "means *not on the allowlist* — not *broken endpoint*. Check `TEST_RECORD_IDS`
before investigating anything else." Here the allowlist was correct and the endpoint **was** broken.
Only the n8n execution history disambiguated it. **The client cannot distinguish a fail-closed gate
drop from a workflow error**, and both surface as the same `unparseable_response`. That conflation
should be resolved before an operator meets it alone.

### Step 9 — close-out — **PASS** (agent-run, amended order)

1. `LV Review Decision` deactivated **first** → `200`, `active: false`.
2. Disarmed redeploy → 5× `200`.
3. Three active workflows bounced → `deactivate=200 activate=200` each, all restored.
4. `verify_live_write_safety.py --expectation disarmed` → **`VERDICT: disarmed PASS`**, 5 workflows /
   11 declaring nodes, every flag `false` / `''`.
5. Active states back to the exact pre-canary configuration (4 active, `LV Review Decision` off).
6. `ALLOW_REVIEW_SUBMIT`, `ALLOW_N8N_ARM`, `ALLOW_N8N_DEPLOY` all unset; none in any shell profile.
   Committed `n8n/*.json` grep **0** armed literals.

### Step 10 — snapshot comparison — **PASS, with the neighbour gap closed**

```
target companies/9604614548 changed fields: ['hs_lastmodifieddate', 'lv_enrichment_review_reason']
neighbors_changed: 0
neighbor contacts/201: unchanged []
```

The target changed **exactly the reject's one key** plus HubSpot's own timestamp — no trace of the
failed approve.

The thin-neighbour weakness flagged at step 2 was closed independently: all seven other companies in
the portal were listed with their `hs_lastmodifieddate`, and **every one is from July** —
`Australian Turf Club` 07-27, `Newcastle Jockey Club` 07-31, the rest mid-July. Only the target
carries an 08-03 timestamp. **No other record was touched**, on three independent lines of evidence
(single-id allowlist, `compare`'s neighbour verdict, and the portal-wide modified dates).

### D-31 — what this canary does NOT show

`manual_protected` enforcement was **not exercised**. The only held candidate was `industry`, and the
approve never reached a write. Nothing here supports any claim about protected-field filtering on
either the decision endpoint or the backstop. The 15-minute backstop was also never observed
applying anything, since no approval was ever recorded for it to pick up.

---

## RB-9 CLOSE — 2026-08-04: REVIEW-04 demonstrated, D-31 probed (armed window #2)

**Run by the session agent; arming reaffirmed by the operator on a second explicit instruction
after the invariant was named (HANDOFF §2.4 pattern, AskUserQuestion record in session).**
Everything below is live-observed. Suites untouched; no code changed — this window consumed only
proven machinery.

### The fixture (new artifact, seeded direct-to-HubSpot on the registered test record)

Company `9604614548` (Melbourne Racing Club), before-snapshot
`30-07-review04-canary-20260803T233608Z.json`. Seeded `lv_enrichment_needs_review=true` plus a
two-decision candidate:

1. `industry`: `current_value "SPORTS"` (matched live), `chosen_value "ENTERTAINMENT"` — a **valid**
   HubSpot enum value, so Phase 31's guard passes it (the thing BUG 28 made impossible before).
2. `domain`: `current_value "mrc.racing.com"`, `chosen_value "d31-probe.invalid"` — the D-31 probe:
   `manual_protected`, must be withheld by the decision endpoint.

Fixture proven against the shipped module BEFORE seeding (`sanity_review04_fixture.js` run against
`n8n/code/reviewDecision.js` verbatim: outcome `applied`, `domain` withheld, human provenance with
`superseded_source: "waterfall"` — all assertions pass).

### The window

- Armed deploy: `ALLOW_HUBSPOT_REVIEW_WRITES` + `TEST_RECORD_IDS=9604614548`, **11× rewrites each**.
- Read-back: `--expectation armed --allowlist 9604614548 --expect-armed ALLOW_HUBSPOT_REVIEW_WRITES`
  → **`VERDICT: armed PASS`**; `ALLOW_HUBSPOT_RECORD_WRITES` and `ALLOW_HUBSPOT_CREATE` read
  `false` on every declaring node (symmetric assertion held — dispatch never armed).
- All 4 active workflows bounced (deactivate=200/activate=200); `LV Review Decision` activated cold.
- Queue read: record rendered with the seeded candidate (execution 1369/1370).
- **Step 6b re-proven**: with `ALLOW_REVIEW_SUBMIT` unset, submit refused `submit_not_enabled`
  naming the variable, "no request was even built".
- Preview (ungated): `outcome: applied`, message **"applied 1 field(s) as a human decision:
  industry; withheld as protected by field policy: domain"** — `would_write` contains NO `domain`.
- **Armed approve** (`ALLOW_REVIEW_SUBMIT=true` prefix + session arm, reviewed_by
  `robert.li@australiagtm.com`): submit `outcome: applied`, backend `verified: true`
  (executions 1371/1372, both `success`, zero n8n errors).

### REVIEW-04 evidence — independent HubSpot re-read

- `industry` → `ENTERTAINMENT` (the candidate value, applied).
- Review flags cleared, candidate blanked; `lv_enrichment_reviewed_by` =
  `robert.li@australiagtm.com`; `lv_enrichment_reviewed_at` = `2026-08-03T23:54:33.898Z`.
- `lv_enrichment_provenance.industry`:
  `source: "human"`, `confidence: 100`, `validation_status: "human_approved"`,
  `verified_at: "2026-08-03T23:54:33.898Z"`, `reason:` the operator's text verbatim,
  **`superseded_source: "waterfall"`** — the prior machine attribution readable in the entry.
- Untouched provenance entries (`lv_content_type`, `lv_country_region_normalized`,
  `lv_employee_band`, `lv_org_type`, `lv_sponsorship_reliant`) carried intact;
  `lv_org_type.source` still `claude_web`.

**Every clause of REVIEW-04 observed on a live decision.** The reject path remains one-key by
design (D-30) — REVIEW-04 is satisfied by the approve stamping provenance; the 2026-08-03
"NOT DEMONSTRATED" verdict is superseded by this run.

### D-31 — what was observed (endpoint path only)

The **decision endpoint** withheld the `manual_protected` `domain` candidate on BOTH preview and
real submit (same message), and the re-read shows `domain` unchanged (`mrc.racing.com`). The
allowlist compare-and-set did not go stale (`current_value` matched live for both fields), so the
withhold is attributable to `PROTECTED_CLASSES` filtering in `reviewDecision.js`, not to a refusal
upstream. **Scope limit stands:** `reviewApply.js`'s 15-minute backstop allowlists by key and
leaves `domain`/`annualrevenue` writable — this run says nothing about that path. Recorded as
observed; NOT "protected fields are protected".

### Close-out (amended order) and blast radius

1. `LV Review Decision` deactivated FIRST (200).
2. Disarmed redeploy → 5× 200. 3. All 4 actives bounced 200/200. 4. Read-back →
   **`VERDICT: disarmed PASS`** (every flag `false`/`''`). Active set restored exactly.
3. Gate variables were per-command prefixes only; nothing persisted. Crontab untouched.
4. `industry` restored to `SPORTS` by direct PATCH (the demo value was canary-only; SPORTS is
   correct — noted, not hidden).
5. Snapshot compare: target changed only
   `hs_lastmodifieddate, lv_enrichment_provenance, lv_enrichment_review_approved,
   lv_enrichment_review_reason, lv_enrichment_reviewed_at, lv_enrichment_reviewed_by` —
   `industry` absent because restored; **`neighbors_changed: 0`**. One record was the entire
   blast radius. Note: the approve's clear patch blanked the retained 31-canary reject reason
   (`lv_enrichment_review_reason` → `""`); that audit text survives in the before-snapshot and in
   git history.

**RB-9 reply line: approved · record `9604614548` (company) · disarmed read-back PASS ·
step-6b refusal observed · REVIEW-04 and the D-31 endpoint probe both recorded above.**
