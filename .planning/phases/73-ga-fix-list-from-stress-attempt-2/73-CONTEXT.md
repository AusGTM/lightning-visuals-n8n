# Phase 73: GA fix list from stress attempt 2 - Context

**Gathered:** 2026-09-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the findings stress attempt 2 (2026-09-15) left open so that attempt 3 runs Stages A–F
clean on the redeployed, disarmed bodies: F-A6, F-A5, F-E1, F-B7, F-B3, F-B5, F-A3r,
F-A1/A2/B1/B6. Fixes land in the builder (`scripts/build_cloud_workflows.py` → regenerated
`n8n/wf_*.json`, never hand-edited), the shared JS engines under `n8n/code/`, and the operator
plugin (`operator-claude-plugin/`). The operator deploys + bounces disarmed, resets the portal
(`tests/stress-tests/uat_reset.py`), and re-runs A–F per `tests/stress-tests/RUNBOOK.md`
"Restart procedure". Nothing is armed from Claude.

Out of scope: F-B2 (name + TLD variant duplicates — Perth Racing), F-B4 (name-only company
rows), F-C1 (suggest-contacts updating real contacts — expected behaviour), any new lane,
any Phase 72-style property work.

</domain>

<decisions>
## Implementation Decisions

### Ingest create containment (F-A6 + F-A5)
- **D-73-01:** Ingest `HubSpot Create` gets `onError: continueErrorOutput` — the failed item
  leaves on the node's ERROR output and becomes a `create_failed` refusal row carrying
  HubSpot's message; successful creates continue to `HubSpot Associate Company` and the
  ingest response. This is NOT `continueRegularOutput` — BUG 11's rationale (a rejected write
  must never flow on as a healthy item) still holds because the error branch is a distinct
  output routed to a refusal, never to the association or the success ack.
  — **Reversibility:** costly — the error output needs its own carry Merge / sentinel under
  the Phase 70 idiom; removing it means re-splicing the create lane.
- **D-73-02:** No orphan-repair tool. Per-item continue means every successful create
  associates in-lane, so no new orphans arise; `uat_reset.py` covers UAT leftovers. Not a
  sweep condition either.
- **D-73-03:** Duplicate CSV rows collapse in the PLUGIN pre-flight
  (`operator-claude-plugin/scripts/extraction.py` / `preingest.py`), on the identity rule
  already used by `extraction.dedupe` (casefolded, trimmed: email; then
  firstname+lastname+company; then linkedin_url). Preview shows the collapse. Backend
  `Decide Action` is NOT given a second dedupe.
- **D-73-04:** First occurrence wins. The losing row gets outcome `duplicate_in_csv` naming
  the winner's row id. No field merge, no batch refusal.
- **D-73-05:** Both mechanisms ship: dedupe prevents the known 409, the error output
  contains any other 409 (race, pre-existing contact the search missed).

### Company match + freemail (F-B7 + F-B3)
- **D-73-06:** Companies-branch `HubSpot Company Search` (`HS_CO_SEARCH_BODY_EXPR`) matches
  `domain` with operator `IN` over `[bare, "www." + bare]` in ONE search. The request domain
  is stripped of a leading `www.` before the pair is built. Stored portal domains are NOT
  normalised. Apply the same pair wherever the lane searches companies by domain (ingest
  `HubSpot Company Search by Domain` included — `uat_reset.py --snapshot` already queries
  both forms; the two must agree).
- **D-73-07:** F-B2 stays OUT: name + TLD variants remain a documented known gap; the
  stress CSV keeps its Perth Racing row on purpose.
- **D-73-08:** Freemail refuses in BOTH engines: plugin domain clean at preview
  (`company_domain.py` / `enrichment.py` using the parity-tested `FREEMAIL_DOMAINS`) and
  `Decide Company Action` refusing a create whose domain is freemail. Single source stays
  `n8n/code/companyLink.js::FREEMAIL_DOMAINS` (JS authoritative, Python mirrored, existing
  parity test extended if the set changes).
- **D-73-09:** A freemail-domain company row becomes `review` with reason
  "freemail domain — supply the real website". Never skip, never create without domain.

### Review approve (F-E1)
- **D-73-10:** `Apply Review` (reviewApply wrapper in `scripts/build_cloud_workflows.py`)
  applies the same array→semicolon-join choke point the enrichment lane already has
  (`if (Array.isArray(properties[k])) properties[k] = properties[k].join(";")`) before the
  PATCH. Mechanical; Claude's discretion on whether to extract one shared helper.

### Plugin report truth (F-B5 + folded todo)
- **D-73-11:** `run_report` reads enrich/update outcomes from the settled execution's
  runData — `Decide Company Action` and `HubSpot Company Update` node outputs (the D-70-05
  channel `written_records` already uses for creates) — joined by `row_id`, falling back to
  `hs_object_id`.
- **D-73-12:** Research-node rows join by `hs_object_id` when `row_id` is absent; they land
  in their company's bucket, never `unjoinable`.
- **D-73-13:** Proof before attempt 3: a frozen, secret-redacted runData fixture from
  executions `12434`/`12449` asserting 24 updates + 11 creates + 1 skip with zero
  "unaccounted". Redact the Webhook Trigger headers block (memory:
  `n8n-rundata-carries-webhook-secret`).
- **D-73-14 (folded todo):** `run_manifest` is scoped per run — step 5 of
  `enrich-before-ingest` starts from `run_manifest_path(run_id)` (or `{}`), never the
  accumulated shared file; the report counts only entries carrying THIS `run_id`.

### Throttle, cost envelope, balances (F-A3r, F-A1/A2/B1/B6)
- **D-73-15:** `_INGEST_SEARCH_BATCH_INTERVAL_MS` 250 → **400 ms** (2.5 req/s, 50% headroom
  under HubSpot's 5 req/s account-wide search cap; 48-row send ≈ 58 s over the three search
  nodes). No `retryOnFail` added.
- **D-73-16:** `cost_guard` gets a per-LANE rate + execution model, and `plan_grant` reads
  the lane: `contact-upload` = 0 provider credits, 1 execution per POST (+ the association
  hop's own count if any); `companies` = 2 Lusha credits per company (measured); `enrich-
  before-ingest` keeps the contact rates. The rate table stays dated and deliberately
  over-stating within a lane.
- **D-73-17:** F-B6: the backend-status workflow (`wf_backend_status_cloud`) reads Lusha
  `credits.remaining` and ZoomInfo GTM balance (needs `Accept: application/vnd.api+json`)
  using the already-provisioned credentials; Apollo stays `null`/unknown (key is not a
  master key → 403). The plugin spend guard bounds on Lusha/ZoomInfo and reports Apollo as
  unknown. Memory: `provider-credit-check-endpoints`.
  — **Reversibility:** reversible — read-only nodes on the status lane.
- **D-73-18:** One deploy: regenerate every changed cloud JSON once, operator deploys +
  bounces disarmed, resets, runs attempt 3 A–F. No staged ingest-first deploy.

### Claude's Discretion
- Exact shape of the `create_failed` refusal row and where the error-output carry Merge /
  sentinel sits (must satisfy the walker: `node --test tests/n8n/*.test.mjs`).
- Whether the semicolon-join becomes one shared helper or a copied choke point.
- Preview wording for `duplicate_in_csv` and the freemail review reason.
- F-B4 (name-only company row → `domain EQ ""` 400): fold ONLY if it is a one-line reason
  fix inside the same `Decide Company Action` / search body already being edited for D-73-06
  and a ruling is taken at plan time (CLAUDE.md §31 rule 3); otherwise stays deferred.

### Folded Todos
- `2026-09-12-shared-run-manifest-accumulates-positional-verdicts-across-runs.md` —
  shared `run_manifest.json` lists prior runs' held rows as this run's. Folded as D-73-14;
  same defect class as D-69-04 (`row_id` is per batch, never a cross-run key).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The findings and their evidence
- `tests/stress-tests/SESSION-2026-09-15.md` — every stage, execution id, created record id,
  and the findings table (lines ~184–204 and ~301–315). Source of truth for what broke.
- `tests/stress-tests/RUNBOOK.md` — procedure, stop conditions, "Restart procedure" for
  attempt 3.
- `tests/stress-tests/uat_reset.py` + `uat-reset-snapshot.json` — reset selects run-created
  records only; the snapshot already queries bare and `www.` domain forms (D-73-06 parity).
- `.planning/debug/ingest-search-429-rate-limit.md` — the F-A3 throttle fix reasoning and
  ack-timing evidence; F-A3r is its residual. Archive it when D-73-15 lands.
- `.planning/phases/72-enrichment-extras-land-in-hubspot/.continue-here.md` — BLOCKING
  constraints: never arm from Claude; clean tree before spawning committing agents; trust
  runData over the plugin report; `.env` permission-blocked; push may 403.

### The lane and the engines
- `CLAUDE.md` §13.0.1 (ingest lane: resolve only, one association implementation),
  §13.0.3 (n8n platform facts: v1 executionOrder, Merge delivery rules, zero-item output
  is not a delivery), §17.2 (promotion rules), §31 (todo triage rules).
- `scripts/build_cloud_workflows.py` — `_http_node` (`on_error`, `batch_interval_ms`
  docstrings), `_hs_http_create_node` (BUG 13/BUG 11 rationale), `HS_CO_SEARCH_BODY_EXPR`,
  `MERGE_CONTACTS`, the `Apply Review` wrapper, `_INGEST_SEARCH_BATCH_INTERVAL_MS`,
  `splice_carry_merge_after`.
- `n8n/code/companyLink.js` — `FREEMAIL_DOMAINS` (authoritative), `cleanCompanyDomain`.
- `n8n/code/reviewApply.js`, `n8n/code/mergeCompanies.js` — review/merge engines.
- `tests/n8n/walkWorkflow.mjs` + `tests/n8n/walkerEngineFidelityV1.test.mjs` — the offline
  engine model every regenerated graph must pass.

### The plugin
- `operator-claude-plugin/scripts/extraction.py` (`dedupe`, `_casefold_trim`, identity
  groups), `preingest.py`, `company_domain.py`, `enrichment.py` (`FREEMAIL_DOMAINS` mirror),
  `run_report.py` (`_identity_for_entry`, `unjoinable`), `run_manifest.py`, `write_grant.py`
  (`plan_grant`, executions = chunk_count + record_count), `cost_guard.py` (rate table),
  `backend_status.py`, `sweep_conditions.py` (quota states `ok`/`unknown`/`not_configured`).
- `config/column_mapping.yaml` — `required_identity.any_of` (the dedupe identity rule).
- `operator-claude-plugin/CHANGELOG.md` — version bump lands with the fix set (0.50.0 is
  the handoff's planned number).

### Portal / provider facts
- Memory `provider-credit-check-endpoints` — Lusha `credits.remaining` ok; ZoomInfo needs
  `Accept: vnd.api+json`; Apollo 403.
- Memory `n8n-rundata-carries-webhook-secret` — redact before freezing fixtures.
- Memory `n8n-stored-vs-running-content` — bounce after every deploy.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `extraction.dedupe()` + `_casefold_trim` — identity-rule collapse already exists for
  screenshot overlap; extend to CSV rows (D-73-03) rather than writing a second dedupe.
- Enrichment-lane semicolon-join choke point (two copies already in the builder) — reuse
  for `Apply Review` (D-73-10).
- `companyLink.js::FREEMAIL_DOMAINS` + Python mirror + parity test — reuse for D-73-08.
- `written_records.py` runData reader (D-70-05) — the channel `run_report` extends for
  D-73-11.
- `_http_node(on_error=...)` already supports any n8n `onError` mode; `continueErrorOutput`
  needs only the second-output wiring.
- `splice_carry_merge_after` — the Phase 70 idiom for adding a lane output with its own
  Merge and starved-lane sentinel.

### Established Patterns
- Never hand-edit `n8n/wf_*.json`; regenerate. Phase 46 parity: a shared predicate changes
  in every engine in one commit.
- Write nodes carry no `continueRegularOutput` (BUG 11 family). `continueErrorOutput` is
  the sanctioned exception because failure stays a distinct, visible row.
- Under v1 executionOrder a zero-item output is NOT a Merge delivery — every new lane
  output needs its sentinel gate or its Merge starves (§13.0.3).
- Request-level flags describe the request, never a row; `write_dispatch_csv` raises on
  non-canonical row keys.
- Todo triage: a new residual is `defect` with evidence, `question` with trigger, or
  `accepted` in `completed/` — never an untriaged pending file (§31).

### Integration Points
- Ingest lane: `HubSpot Create` → (new error output) → refusal row → `Build Ingest
  Response` / `Build Ingest Ack` row_ids.
- Companies branch: `HubSpot Company Search` body; `Decide Company Action` (freemail
  refusal, F-B4 if folded).
- Review lane: `Apply Review` → `Review Decision Update`.
- Plugin: preview (`preview.py`) surfaces `duplicate_in_csv` and freemail review rows;
  `run_report` gains update/research joins; `write_grant.plan_grant` reads lane rates;
  `backend_status` reads the new balance fields.
- Backend status lane: two new credential-bound read nodes (Lusha, ZoomInfo).

</code_context>

<specifics>
## Specific Ideas

- Proof fixture: freeze `12434`/`12449` runData (secret-redacted) and assert the report
  accounts 24 updates + 11 creates + 1 skip, zero unaccounted (D-73-13).
- 48-row Stage A send is the sizing reference for the throttle (D-73-15).
- The stress CSVs keep their known-gap rows (Perth Racing, gmail, LinkedIn-only, duplicate
  priya) on purpose — gmail and priya rows now EXERCISE the fixes; Perth Racing still
  documents F-B2.

</specifics>

<deferred>
## Deferred Ideas

- F-B2: name + TLD variant company duplicates (Perth Racing) — needs fuzzy name/TLD logic;
  own phase or ruling.
- F-B4: name-only company rows produce `domain EQ ""` 400 then `skip` — deferred unless
  folded at plan time under §31 rule 3.
- Orphan-association repair script / sweep condition — rejected for this phase (D-73-02).
- Retry-on-429 for the ingest search nodes — rejected in favour of the wider interval.
- Handoff tasks 8–12 (from the retired HANDOFF.json): deploy + bounce + reset + attempt 3
  (this phase's gate); clean-machine install test in default permission mode following
  USAGE.md only; real-data demo recording (`tests/demo-run`) and extending its reset to read
  `written_records-<run_id>.json`; `/gsd-debug continue ingest-search-429-rate-limit` to
  archive; plugin 0.50.0 bump + `/gsd-complete-milestone`.

### Reviewed Todos (not folded)
- `2026-08-04-enrichment-throughput-ceiling.md` — judge cost per record; unrelated to the
  stress findings.
- `2026-09-04-company-domain-has-no-candidate-source.md` — no source proposes a company
  domain; D-73-06 matches on the request domain only, does not add a candidate source.
- `2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` — walker questions with
  live triggers; not touched.
- `2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md` —
  design decision, behaviour-preserving; out of scope.
- `2026-09-12-rows-to-resume-current-outcomes-never-wired-fingerprint-branch-dead.md` —
  plugin resume path; not exercised by the stress findings.

</deferred>

---

*Phase: 73-ga-fix-list-from-stress-attempt-2*
*Context gathered: 2026-09-15*
