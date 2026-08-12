# Phase 48: Enrichment Coverage - Context

**Gathered:** 2026-08-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Every scored company either carries a real `lv_org_type`, or is individually recorded as
un-enrichable **with a stated reason distinguishable from "never attempted"** (COVER-01) — spent
through a write window whose cost is estimated ex-ante against the 2,500/month n8n allowance and
the current Lusha balance, reported after, and **refused outright rather than truncated** if the
estimate exceeds either budget (COVER-02).

Phase 47's strict enum gate refused to guess-map free-text research output into `lv_org_type`.
Phase 48 makes that mapping decision per record, choosing one of three outcomes: **map to an
existing enum option**, **add a new option then map** (rejected this phase — see D-02), or **mark
un-enrichable with a reason**.

**Not this phase:** provider-waterfall latency/throughput work, async webhook architecture,
tier-distribution reporting as a deliverable (Phase 49 / RESCORE-03), Entain's ANZ operating
presence, the un-proven live `D` → non-`D` tier *transition*.

</domain>

<population>
## The population — re-derived live 2026-08-12, NOT from COVER-01's stale "18"

`REQUIREMENTS.md` COVER-01's "18 scored companies" predates Phase 47, which resolved
`lv_org_type` for 13 of its 17 pinned records. Neither 18 nor 5 should be planned against without
re-deriving. The live read below is the anchor; **re-derive again at plan time and stamp the date.**

```
HubSpot companies search, 2026-08-12
  filter: lv_icp_fit_score HAS_PROPERTY  AND  lv_org_type NOT_HAS_PROPERTY
  scored population ......... 66
  blank lv_org_type ......... 5
```

| id | name | tier | score | region | veto | captured research in `47-RESEARCH-RESULTS.json` |
|---|---|---|---|---|---|---|
| `15008671672` | Racing NSW | B | 40 | AU | false | **NO** — never in the 17 pinned |
| `17317381378` | Editix | Unscored | 0 | **blank** | false | yes — `matched: false`, conf **5** |
| `17317850381` | Jam TV | D | 20 | Other | **true** | yes — conf 85 |
| `20538284384` | Waikato Racing Club Inc | C | 30 | NZ | false | yes — conf 85 |
| `20943964946` | The Rumble / Pacific Action Sports | B | 40 | AU | false | yes — conf 92 |

**4 of 5 need no new spend.** Their evidence was already paid for in Phase 47 and is on disk.

**The live `lv_org_type` enumeration — all 9 options, read 2026-08-12:**

```
governing_body_league · content_producer · broadcaster · individual_club_team
regulator · gambling_operator · hardware_vendor · other · unknown
```

</population>

<decisions>
## Implementation Decisions

### Enrichment path

- **D-01:** Resolve the 4 records with captured evidence by an **offline enum-mapping pass over
  `47-RESEARCH-RESULTS.json`** — zero API cost, zero provider credits. Issue **one** fresh
  enum-constrained web-research call for **Racing NSW `15008671672`** only, which has no captured
  research. **Total paid work: 1 record.** The ex-ante cost estimate is still written per
  COVER-02; it will read roughly one research call (~$0.07 order-of-magnitude, per
  `47-COST-ESTIMATE.md`'s measured $0.0686/record floor).
  — **Reversibility:** reversible — the mapping is a value write per record, undone by clearing
  the property; no schema or contract changes.

  **Rejected:** the ROADMAP's literal "full provider waterfall per record". Phase 47's D-08
  already bypassed the waterfall for standalone Python research, and providers do not return
  `lv_org_type` at all — they would spend Lusha/ZoomInfo credits for firmographics this phase
  does not need. **Also rejected:** re-researching all 5 with a corrected prompt (Phase 47 option
  (a)) — it discards already-paid evidence for uniformity Phase 48 does not need at n=5.

- **D-05:** **The Rumble `20943964946` → `content_producer`.** Its research says "Event organizer
  / Sports league operator" (conf 92) and names the Rumble Pro Tour + Amateur Series, but the same
  evidence names **Skate Australia** as the sport's body and The Rumble as a *partner*. It
  produces and broadcasts content (740k avg viewership); it does not govern the sport.
  `content_producer` (+20) is the honest reading over `governing_body_league` (+40).

**The per-record mapping table this phase implements:**

| id | name | outcome | basis |
|---|---|---|---|
| `17317850381` | Jam TV | `broadcaster` | research: "Media company / Web television broadcaster", conf 85 |
| `20538284384` | Waikato Racing Club | `individual_club_team` | research: "Racing Club / Sports Organization", conf 85 |
| `20943964946` | The Rumble | `content_producer` | D-05 |
| `17317381378` | Editix | `unknown` + reason (D-03) | research `matched: false`, conf 5 |
| `15008671672` | Racing NSW | fresh research, then map | no captured evidence |

### The `venue` enum option

- **D-02:** **Defer `venue`. No record in this population needs it.** *(Amendment written 2026-08-12 — the dated DEFERRAL block is live at the top of the decision file.)* The LOCKED decision
  `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md` says `venue` implements in
  Phase 48; its "no portal work is required" clause is **false** (already corrected in a dated
  block at the top of that file). Adding it is a HubSpot **enum-option PATCH** via
  `scripts/sync_hubspot_properties.py`, which is portal schema work requiring its own arming
  decision — and none of the five records' evidence maps to it. Waikato (racecourse / event
  centre) is the nearest miss and maps better to `individual_club_team`.
  **Amend the LOCKED decision with a dated block recording that the population was examined and
  the option was not spent** — do not silently drop it.
  — **Reversibility:** reversible — deferring costs nothing; a future phase adds the option when a
  record actually demands it.

### The un-enrichable marker (COVER-01's "distinguishable from never attempted")

- **D-03:** **`lv_org_type = "unknown"` + a reason in `lv_enrichment_review_reason`.** Both already
  exist live — `unknown` is one of the 9 options, `lv_enrichment_review_reason` is a live
  multi-line text property — so **zero portal work**. The semantics:

  ```
  lv_org_type blank      = never attempted
  lv_org_type "unknown"  = attempted, evidence insufficient; reason in lv_enrichment_review_reason
  ```

  Editix `17317381378` is the live case: `matched: false`, confidence **5**, every field null.
  Searches for `edetrix.com.au` returned EditiX (an XML editor), Editrix, and EditShare — no
  company matching the name+domain. Its identity is unresolvable, not merely unresearched.
  — **Reversibility:** costly — the blank-vs-`unknown` semantics become the query contract every
  future coverage sweep keys on; changing it later means re-interpreting every record written here.

  **Blank region is safe.** `src/icp_scoring.py:82` maps an empty region to `region_key =
  "unknown"`, **not** `non_anz`, so writing to Editix (whose region is blank) cannot fire a
  spurious geography veto. That bug is already dead. `unknown` scores 0 org-type points, so Editix
  stays `Unscored` — honest.

### Credit-swallow guard (folded todo)

- **D-04:** **Fix the lane properly, not just the driver.** Add a gate immediately after
  `Claude Web Research` in `scripts/build_cloud_workflows.py` that detects an `error`-shaped
  payload and routes to a failure branch rather than into merge/normalize. Treat "research
  returned an error object" as `unknown`, never as data — the same prefer-unknown-over-guessing
  rule `docs/WEB-RESEARCH-SPEC.md` already states for the model's own output.
  — **Reversibility:** costly — it changes the sealed enrichment lane's control flow; undoing
  needs another rebuild + operator deploy + bounce.

  **This obliges an operator deploy.** `scripts/deploy_n8n_workflows.py` needs `DRY_RUN=false`
  **and** `ALLOW_N8N_DEPLOY=true` in one invocation, plus a **bounce** (deactivate → reactivate)
  afterward — and the Phase 47.5 deploy waiver **EXPIRED with that phase**. Never hand-edit
  `n8n/wf_*.json`. Prove the running instance changed with a live execution's own node list, not
  a stored read-back.

### Windows and cost discipline

- **D-06:** **Declare up front: 1 operator deploy+bounce, 1 armed write window, record cap 5.**
  Phase 47 needed five arm/disarm cycles against a must_have of one; Phase 47.5's correction was
  declaring two before opening either and using exactly two. Phase 48 declares one of each.
  Exceeding the declaration is a disclosure obligation in the run report, not a silent event.

- **D-08:** **Touch-once.** The ROADMAP warns a record needing both a region fix and org-type
  enrichment should be touched once. Live check: **Editix `17317381378` is the only overlap**
  (blank region AND blank org type) — and its research resolved neither, so it takes exactly one
  write (`unknown` + reason). No record in this population needs a region PATCH.

### Re-derivation after the writes

- **D-09:** **Fire a recompute POST per written record and report before/after.** Writing
  `lv_org_type` *completes* each record, so `Company Gate` will return `skip` on every future
  trigger and `Decide Company Action` — the sole writer of `lv_anti_icp_flag` /
  `lv_anti_icp_reason` — would never run again. The Phase 47.5 recompute lane is the only way to
  settle the derived chain, and it is **free**: 0 provider credits, 0 Anthropic calls, 1 n8n
  execution per POST (measured, executions 11858–11861).

  ```
  POST {N8N_URL}/webhook/hubspot/enrichment/event    header: X-Enrichment-Secret
  body: the usual D-18 event + "recompute": true
  helper: scripts/remediate_veto_companies.py::post_webhook_event(..., recompute=True)
  ```

  The before/after is recorded as this phase's own evidence. **Plain-language tier-distribution
  reporting remains Phase 49's deliverable (RESCORE-03)** — Phase 48 records, Phase 49 narrates.

### Claude's Discretion

- Chunking, task ordering, and whether the offline mapping pass is a script or a plan-time table.
- Whether the Racing NSW research call reuses `src/web_research.py::claude_web_research` with a
  corrected enum-constrained `RESEARCH_SYSTEM`, or a narrower one-off prompt. Either is fine as
  long as the output is constrained to the 9 live options.
- Where the gate node's failure branch terminates (`Build Response` with a stated reason is the
  established idiom).

### Folded Todos

- **`.planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-failure.md`** (score 0.9,
  severity major). A `400 invalid_request_error` from `Claude Web Research` — e.g. Anthropic
  credit exhausted — does **not** fail the execution. Live on exec `11833`: `status: success`,
  `finished: true`, **zero** node-level errors, and the 400 carried as data on the node's main
  output. Downstream it was consumed where a `ProviderResult` belongs, producing
  `lv_revenue_band: "1-5M"` / `lv_employee_band: "10-50"` for a regional racing club from a
  research call that never succeeded. Phase 48 is a research-touching, armed run — this is the
  failure mode most likely to poison it. Folded and fixed at the lane per **D-04**.

</decisions>

<constraints>
## Hard rules that bind this phase — downstream agents MUST honour these

| Rule | Detail |
|---|---|
| **Project-level D-07** | **Never PATCH `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_icp_fit_score`, `lv_icp_tier`.** Write inputs, let the derived chain settle, read it back. Held absolutely through both Phase 47.5 windows. (This phase's own decisions are numbered D-01..D-09 in the section above; no `D-07` is reused there) |
| **No new HubSpot properties** | Standing v0.9 constraint. Adding an *option* to an existing enumeration is not a new property — but it is still portal schema work with its own arming (this is why D-02 defers `venue`) |
| **Out-of-vocabulary `lv_org_type` 400s, and in a batch fails the batch** | The strict allowlist in `scripts/remediate_veto_companies.py:142` is correct. `lv_org_type` IS an `enumeration` / `select` (verified live 2026-08-12). All three D-V4 normalization layers still required: the CRM guard stops a bad value reaching the *record*, not the *write*, and `.get(org_type, 0)` scores an unrecognised key **0, silently** |
| **Arming is operator-only** | `D-47.5-01` and its amendment delegated arming to Claude **for Phase 47.5 only**. EXPIRED. Do not carry forward, do not cite |
| **Deploys are operator-only** | Same expiry. `DRY_RUN=false` **and** `ALLOW_N8N_DEPLOY=true` in one invocation, plus a bounce |
| **Never hand-edit `n8n/wf_*.json`** | Edit `scripts/build_cloud_workflows.py` / `n8n/code/*.js`, rebuild, deploy, bounce |
| **Parity rule (Phase 46)** | Any *scoring-predicate* change lands in every engine holding it, in one commit. D-04's gate node is control flow, not a predicate — but if planning touches a predicate, the rule binds |
| **`Decide Company Action` is the single veto writer** | Do not add a second |
| **Re-derive the population live, stamp the date** | A committed snapshot is evidence, not a guarantee. Re-list the live property before writing to it |
| **`.env` is Read/Bash permission-blocked** | Drive live work through the dotenv form with an **absolute** path: `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('/abs/path/.env'); …"`. Bare `load_dotenv()` resolves relative to the calling file; with no `conftest.py`, live pytest needs a wrapper passing an absolute path or every HubSpot read 401s |
| **Tests** | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` — **glob form**; the directory form is broken on node 24 |
| **`run_scoring_parity.py`'s population sweep is RED BY DESIGN** until Phase 49 | Do not "fix" it |

### Traps that already cost real time — do not re-pay them

1. **n8n `status: "success"` lies.** A node can receive a 400 and pass the error object downstream
   **as data**, `executionStatus: "success"`, zero node-level errors. Judge a run by node-level
   `runData`. (This is exactly the folded todo.)
2. **A client POST timeout is not a failure.** n8n completes server-side. `post_webhook_event`
   defaults to a 300s read timeout. Never retry on timeout without reading the execution back —
   that is how a record gets touched twice.
3. **Stored ≠ running.** A bare `PUT /api/v1/workflows/{id}` does not reload a running workflow.
   Bounce, then prove it with an **independent** GET or a live execution's own node list.
4. **An EMPTY allowlist denies every write and still reports `armed`.** Assert the allowlist is
   non-empty **and** exactly the intended id set, in the driver, at arm time.
5. **`isReturnOnly()` treats any non-`"write"` mode as return-only.** Anything carried as a `mode`
   value on a write path reports success and writes nothing. Request-level row properties, not modes.
6. **Duration is a cheap tell.** A healthy company recompute is 20 nodes disarmed, 21 armed (the
   extra is `HubSpot Company Update`). 2.4s against a normal 10–37s means the chain died early.
7. **`ENRICH_CO_GATE` is shared by three workflows**, only one of which has a `Parse HubSpot Event`
   node. Any `$()` read of a request-level property must use the repo's `nodeAll` try/catch idiom
   and **fail closed**, or the SJ-2 daily sweep throws on every row.

</constraints>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase entry point
- `.planning/phases/48-enrichment-coverage/48-HANDOVER.md` — written 2026-08-12 after 47/47.5
  closed; assumes no memory of that day. Read first.

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — COVER-01 / COVER-02 text and the **D-02 split**: Phase 47 covers
  17 records, Phase 48 covers the rest; **neither phase may claim full COVER-01/02 closure alone**
- `.planning/ROADMAP.md` § "Phase 48: Enrichment Coverage" — four success criteria
- `.planning/STATE.md` — current position, decisions log

### Already-paid evidence and the cost pattern
- `.planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json` — **the input to D-01's free
  pass.** Keyed by company id; 17 entries; the 4 this phase maps are `17317381378`,
  `17317850381`, `20538284384`, `20943964946`
- `.planning/phases/47-veto-remediation/47-COST-ESTIMATE.md` — the ex-ante estimate pattern
  COVER-02 wants, and the measured $0.0686/record floor
- `scripts/remediate_veto_companies.py` — `estimate_cost()` (the estimate must be produced by this
  function, not hand-derived), `post_webhook_event(..., recompute=True)`, `PINNED_COMPANY_ID_ORDER`,
  the strict enum allowlist at `:142`
- `.planning/phases/47-veto-remediation/47-04-SUMMARY.md` § "Not closed here" — the four records
- `.planning/phases/47-veto-remediation/47-RUN-REPORT.md` § "Window accounting" — the five-window
  disclosure that motivated D-06

### The enumeration and its normalization
- `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md` — D-V1..D-V6 **plus the
  dated correction block** at the top. **D-02 amends this file again.**
- `docs/ORG-TYPE-ENUM-MIGRATION.md` — the migration runbook; the cheap rollback window is CLOSED
- `config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json` — committed live
  schema snapshot (2026-08-08): `type: enumeration`, `fieldType: select`, 9 options
- `config/hubspot_properties.yaml` — mirrors the same; the source `sync_hubspot_properties.py` uses
- `scripts/inventory_org_type_values.py` — existing value inventory tooling

### The lane, the recompute path, and the veto
- `CLAUDE.md` §13.0 — the recompute lane as-built (`IF Company Recompute` / `IF Company Skip`),
  and the three things it does **not** change
- `CLAUDE.md` §10.3.1 — the hardware veto's OR predicate; **any record classified
  `hardware_vendor` acquires a hard veto and lands Tier D.** None of these 5 do, but the rule binds
- `CLAUDE.md` §4.0 — the `lv_`-prefix delta; no bare `enrichment_*` property exists in the portal
- `CLAUDE.md` §19.0, §19.1 — as-built cadences; **the poller is NOT a veto-refresh path**
- `docs/OPERATOR-VETO-REFRESH.md` — amended 2026-08-12
- `docs/WEB-RESEARCH-SPEC.md` — the research contract; prefer-unknown-over-guessing, the rule D-04
  extends to error-shaped payloads
- `scripts/build_cloud_workflows.py` — where D-04's gate node is built. **The only editable source
  for the lane.**
- `src/icp_scoring.py` — the Python engine; `:82` blank-region handling, `:125` the OR predicate

### Phase 47.5 precedent (window discipline and proof standards)
- `.planning/phases/47.5-veto-recompute-path/47.5-RUN-REPORT.md` — pre-arm guard, per-record
  outcomes, cost actuals. The shape D-06's run report should take
- `.planning/phases/47.5-veto-recompute-path/47.5-C-DECISION.md` — the OR decision + deploy record
- `.planning/phases/47.5-veto-recompute-path/47.5-CONTEXT.md` — `D-47.5-01` and both waivers
  (**EXPIRED** — cited here only so nobody re-cites them as live)

### Known-stale, deliberately not cited as truth
- `docs/SYSTEM-CONTRACT.md` § "Boundary of responsibility" — still says computing scores/tiers/vetoes
  is out of scope; false since Phase 40-05. Needs an operator decision, not a sweep edit
- `.planning/workstreams/milestone/STATE.md` — v0.5-era, superseded by root `STATE.md`. Do not cite
- `CLAUDE.md` §12.7 `compute_icp_score` — the local-MVP prototype, not the live rule

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/remediate_veto_companies.py` (49.7K) — the Phase 47/47.5 driver. Already carries
  `estimate_cost()`, `post_webhook_event(..., recompute=True)` with a 300s default read timeout,
  the strict enum allowlist, and the pinned-id ordering. **Phase 48's driver should extend this
  rather than start fresh.**
- `scripts/june_run_arm.py --domains` — record-scoped arming helper landed in 47.5-01
- `scripts/check_provider_credits.py` — provider credit checks (Lusha `credits.remaining` works;
  ZoomInfo GTM needs `Accept: vnd.api+json` or 406s; Apollo key is not master → 403 → degrade null)
- `scripts/sync_hubspot_properties.py` + `config/hubspot_properties.yaml` — the enum-option PATCH
  path, **not** exercised this phase (D-02)
- `src/web_research.py::claude_web_research` — the standalone Python research path D-08 chose in
  Phase 47; `RESEARCH_SYSTEM` is the prompt that must be enum-constrained for Racing NSW
- `scripts/deploy_n8n_workflows.py` — D-04's deploy, operator-armed

### Established Patterns
- **Two engines, one commit** — `src/icp_scoring.py` and the `Decide Company Action` node built by
  `scripts/build_cloud_workflows.py` carry the same predicates and must stay byte-identical
- **Estimate produced by code, not prose** — `47-COST-ESTIMATE.md`'s figures were read from a live
  `estimate_cost()` call so the doc and the function cannot silently drift
- **Dated amendment blocks** — the house style for correcting a stale doc or a LOCKED decision
  (see the correction block already at the top of the venue decision file)
- **`nodeAll` try/catch, fail closed** — the idiom for any `$()` read of a request-level property
  in a shared code node

### Integration Points
- D-04's gate node sits immediately after `Claude Web Research` in `wf_enrichment_cloud.json`,
  built from `scripts/build_cloud_workflows.py`, terminating at `Build Response` with a reason
- The recompute POST (D-09) enters at the D-18 webhook and routes `Company Gate` →
  `IF Company Recompute` → `Decide Company Action`, bypassing providers/research/judge/merge
- `lv_enrichment_review_reason` (live, multi-line text) is the un-enrichable reason's home (D-03)

</code_context>

<specifics>
## Specific Ideas

- **Editix is the archetype the marker exists for.** Its research is not low-confidence — it is
  `matched: false`, confidence 5, every field null, with an evidence summary explaining that
  `edetrix.com.au` matched nothing and the near-hits were an XML editor, an AI book-editing tool,
  and a media software vendor. "Attempted, identity unresolvable" is a genuinely different state
  from "not yet looked at", and D-03 is what makes that visible in the CRM.
- **Jam TV must stay vetoed (D-23).** Writing `broadcaster` adds +20 base and **cannot** clear its
  veto — verified live: `lv_anti_icp_reason = "Non-ANZ geography"`, region `Other`. The veto is
  geographic, the write is org-type. Confirm in the read-back regardless.
- **Waikato's research flags `lv_is_gambling_operator: true`** (NZ Racing Board distributions, TAB
  betting). Gambling is a graduated deduction and `graduated_deductions` is `{}` since Phase 46
  D-03, so it changes nothing — but do not let it be mistaken for a veto trigger.

</specifics>

<deferred>
## Deferred Ideas

- **`venue` as a 10th enum option** — deferred by D-02; revisit when a record's evidence actually
  demands it. Requires a portal enum-option PATCH with its own arming.
- **Entain `10024564084`'s ANZ operating presence** — never examined; it was excluded from 47.5's
  window on arithmetic (a second veto from `lv_produces_content = false`), not on a geography
  finding. Phase 49.
- **A live `D` → non-`D` tier *transition*, proven as a transition** — end states are right; the
  reads are 1–2s apart. Phase 49.
- **Plain-language before/after tier distribution as a deliverable** — Phase 49 / RESCORE-03.
  Phase 48 records the numbers (D-09); Phase 49 narrates them.

### Reviewed Todos (not folded)

- **`2026-08-04-enrichment-throughput-ceiling.md`** (score 0.9) — 82% of a full run is two
  sequential Anthropic calls (Judge 16.1s, Research 12.1s of a 34.2s wall). Real and measured, but
  it bites at 1000 records; Phase 48's population is **5**. Its remedies (tighten the judge gate,
  cheaper judge model, concurrency, async webhook) are architecture decisions touching the sealed
  lane — their own phase, not a Phase 48 patch.
- **`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`** (score 0.6) — unattended sweep
  breaks on plugin update. Unrelated to enrichment coverage.
- **`2026-08-04-uat-22-names-aliases-the-mapping-lacks.md`** (score 0.6) — CSV header aliases in
  contact upload. Unrelated to enrichment coverage.

</deferred>

---

## D-48-01 — deploy AND arming delegated to Claude for this phase only (operator, 2026-08-13)

Phase 48 halted at plan 48-04's `human-action` checkpoint. The operator was asked, with the
alternatives on the table (run the commands themselves, or pause the phase at 4/7), and chose to
**delegate both the deploy+bounce and both arming surfaces to Claude for Phase 48 only.**

This is a **scoped waiver** of the operator-only rule recorded in this file's `<constraints>`
table, which says of `D-47.5-01`: *"EXPIRED. Do not carry forward, do not cite."* That remains
true — **`D-47.5-01` is not being revived.** This is a NEW, separately-granted waiver with its
own expiry, and it is written down for the same reason its predecessor was: so that a later
phase cannot mistake it for standing authority.

Terms, all binding:

- **Expires with Phase 48.** Does not carry to Phase 49 or any later work. The
  `<constraints>` table's "Arming is operator-only" / "Deploys are operator-only" rows resume
  full force the moment this phase seals.
- **Arming vars are set per-shell only** — never `.env`, never a profile, never exported into a
  shell that outlives the window.
- **Disarm is ungated** and runs even when the write leg fails or raises. Closing the window
  always wins.
- After disarming, **independently re-read both surfaces** and quote the read-back verbatim.
  Closure is evidenced, never asserted. A re-read of the stored PUT body is not evidence
  (Trap 3).
- **D-06's declaration is unchanged and still binds:** exactly **1** deploy+bounce, **1** armed
  write window, record cap **5**. Delegation changes who types the command, not how many times
  it may be typed. Exceeding the declaration is a disclosure obligation in the run report.
- **Both arming surfaces must be armed together** — the driver's own env-flag gate (direct
  HubSpot PATCH leg) and `scripts/june_run_arm.py`'s n8n-side allowlist (the
  `Decide Company Action` → `HubSpot Company Update` leg). Arming one and not the other means
  the writes silently do not land.
- **Trap 4 still applies:** an EMPTY allowlist denies every write and still reports `armed`.
  Assert the allowlist is non-empty **and** exactly the intended id set, in the driver, at arm
  time.
- **Project-level D-07 is unaffected:** `lv_anti_icp_flag`, `lv_anti_icp_reason`,
  `lv_icp_fit_score` and `lv_icp_tier` are never PATCHed. Inputs change; the derived chain
  settles; it is read back.

Recorded rather than assumed: the operator's own `48-DEPLOY-PROOF.md` baseline (109 live nodes
vs 111 in the committed artifact) was captured before this waiver was granted, so what is being
delegated is an already-specified, already-reviewed action — the extension changes who runs it,
not what runs.

---

*Phase: 48-enrichment-coverage*
*Context gathered: 2026-08-12*
*D-48-01 waiver appended: 2026-08-13*
