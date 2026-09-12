# Phase 72: Enrichment extras land in HubSpot - Context

**Gathered:** 2026-09-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Every field the waterfall finds and the operator paid for reaches the HubSpot record it was found
for. Contacts: mobile, LinkedIn, seniority, persona, city/state/country (+ ISO codes) land on a
CREATED contact instead of being dropped at the ingest dispatch boundary
(`preingest.strip_enrichment_extras` / `extraction.canonical_props()`'s 8-header set). Companies:
the same geo shape and a phone slot. Conflicts resolve with a recency bias inside the existing
policy classes. Multiple email / phone values are held in fixed slots. The LinkedIn naming defect
is fixed. Proven live at the end of the phase by re-reading one created contact.

Not in this phase: any change to `confidence.assess` / hold codes (D-70-11), the held-entry
schema (D-71-04/05), company creation routes (§13.0.1), the ICP inputs (`lv_country_region_normalized`
stays judge-gated and never fed by contact geo), company email (HubSpot companies have no email
property — stated non-goal), a `_3` overflow slot, per-field `_source`/`_verified_at` properties.

</domain>

<decisions>
## Implementation Decisions

### Carried forward — NOT reopened
- **Operator rulings 2026-09-12 (D-71-06 gate, `71-UAT.md` F71-5):** (1) fix the LinkedIn naming
  defect; (2) do NOT drop enrichment extras — map them; (3) recency bias for conflicts; (4)
  multiple email/phone/mobilephone acceptable. These are the phase's charter.
- **CLAUDE.md §13.0.1** — ONE association implementation, server-side; company creation stays in
  the enrichment lane's companies form. Nothing here adds a company-resolution path.
- **SAFE-01..05** — no `min_confidence` lowered, no `fill_blank_only` weakened (D-72-05 is scoped
  so it does not), no drop path softened, ceilings stay refusals.
- **Phase 66 RICH-01..06** — the 12-key `promotable_contact_props()` set from `config/field_policy.yaml`
  is the widened set; RICH-04's strip is what this phase retires. **58-05** — company `country`/`city`
  fill_blank_only from the Apollo org record. **58-06** — material-conflict judge gate unchanged.
- **Phase 46 parity rule** — any merge-policy predicate change lands in both engines
  (`n8n/code/mergeContacts.js` + `mergeCompanies.js` and `src/merge_policy.py`) in one commit.
- **Carried forward, D-70-11 and D-71-01..05** — verdicts, facets, held-entry keys and stamp untouched.

### Where the mapping lives
- **D-72-01: Widen the ingest lane; the plugin stops stripping.** `config/column_mapping.yaml` and
  `n8n/code/columnMap.js` (YAML/JS parity test) accept the 12 promotable contact keys; the ingest
  lane's candidate assembly (`scripts/build_cloud_workflows.py`, the `email/firstname/lastname/
  jobtitle/company` + linkedin block near line 417) admits them; `preingest.strip_enrichment_extras`
  becomes a no-op by construction. Rejected: create-thin-then-enrich-by-id (second provider spend
  per created contact) and plugin-side-only rename. — **Reversibility:** costly — the ingest lane
  JSON is regenerated and deployed; rollback is the pre-72 bundle.
- **D-72-02: ONE source of truth for "which keys reach HubSpot on create" = `config/field_policy.yaml`.**
  `promotable_contact_props()` already derives the 12 keys from it; the column map and the lane
  assembly read the same list, pinned by a parity test. No second list.
- **D-72-03: `mobile` aliases to `mobilephone`, not `phone`.** `phone` is the landline/office slot.
- **D-72-04: LinkedIn lands in BOTH `lv_linkedin_url` (canonical, PN-1 unchanged) and native
  `hs_linkedin_url`.** The defect was plugin-side: the lane already maps the `linkedin_url` header to
  `lv_linkedin_url` (`build_cloud_workflows.py:398-421`); `strip_enrichment_extras` dropped the key
  before the CSV. No `linkedin_url` contact property exists on the portal.

### Recency rule, scoped
- **D-72-05: On CREATE, provider wins; the CSV value is recorded as a conflict** (merge report +
  `source_values` on the held row), never silently lost. Identity fields (`email`, `firstname`,
  `lastname`, `company`) are not subject to this — they are the row's identity and stay as supplied.
- **D-72-06: On UPDATE, recency overwrites a non-blank HubSpot value ONLY for `stale_refreshable`
  fields older than their `stale_after_days`** (jobtitle 180d; industry 365d; numberofemployees is
  fill_blank_only per 58-05 and stays so), and only when the provider observation is newer than the
  existing value. `fill_blank_only` still fills blanks only; `manual_protected` never. This is the
  SAFE-01 line.
- **D-72-07: Observation times.** Provider value = the run's dispatch time; HubSpot existing value =
  the property's own history timestamp (`propertiesWithHistory` `versions[].timestamp`), not the
  record's `lastmodifieddate`; a CSV value carries no time and ranks oldest.
- **D-72-08: A value the pipeline itself wrote (provenance source apollo/lusha/zoominfo/claude_web)
  is replaceable by a newer provider value at or above the field's `min_confidence`** — the
  §17.2.1 "previously written by the enrichment system" clause extended to provider sources, with
  the same four conjuncts (provenance entry must still match the current value; no material
  conflict). — **Reversibility:** reversible (policy keys).
- **D-72-09: Recency lives in the shared policy layer, both objects, both engines** — expressed as
  `field_policy.yaml` classes/TTLs and implemented in `mergeContacts.js`, `mergeCompanies.js`, and
  `src/merge_policy.py` under the Phase 46 parity rule. Companies inherit it in this phase with their
  existing TTLs.

### Multi-value email / phone
- **D-72-10: A second email goes to `hs_additional_emails` (native, writable, `;`-separated); the
  primary `email` is never rewritten on an existing record.** On create the CSV email is primary and
  the provider's becomes additional.
- **D-72-11: Fixed-cap overflow, exactly one `_2` slot per kind** — `lv_phone_2`, `lv_mobilephone_2`
  on contacts, `lv_phone_2` on companies — created ONCE at setup by a property script (schema-level,
  per object type; never per record, never during a run). A third value goes to
  `lv_enrichment_provenance` only. No `_3`, ever. — **Reversibility:** costly — custom properties on
  the operator's portal.
- **D-72-12: When providers disagree on the same slot, the `source_registry` trust-rank winner takes
  the slot and the loser takes the `_2` slot** — both provenanced. No judge call for phone/email
  disagreements (RO-2 stays: only material fields reach the judge).
- **D-72-13: Verification stamps = provenance JSON only.** `lv_enrichment_provenance` records
  source/confidence/timestamp per landed slot; no new per-field `_source`/`_verified_at`
  properties. `lv_mobilephone_verified_at` keeps its one existing use.
- **D-72-14: Companies gain phone and domain slots** — `phone` (fill_blank_only) + `lv_phone_2` in scope; `hs_additional_domains`
  in scope for extra provider domains; company email is a stated non-goal (no such property).

### Geo + live gate
- **D-72-15: Geo lands as names into `city`/`state`/`country` and as ISO codes into
  `hs_state_code`/`hs_country_region_code` only when the provider supplies a code** — nothing
  derived by guessing. Same shape on contacts and companies (companies gain `state` + the two code
  fields beside the shipped `country`/`city`, same fill_blank_only class).
- **D-72-16: Contact geo never feeds the company's `lv_country_region_normalized`.** Region stays a
  company-waterfall + judge-gated ICP input (58-06); a person's location is not evidence of the
  org's region.
- **D-72-17: One end-of-phase live gate (backloaded, operator ruling 2026-09-09)** — re-run one absent
  person at a company HubSpot holds through `enrich-before-ingest`, `create all 1`, then read the
  contact back and assert `mobilephone`, `hs_linkedin_url` + `lv_linkedin_url`, and geo landed; plus
  one UPDATE row proving a non-blank `fill_blank_only` field was NOT overwritten. Hand-delete after.
  Nothing armed before it.
- **D-72-18: Deploy scope = the ingest lane only.** Regenerate every JSON from the one builder, but
  deploy + bounce only `wf_contact_ingest_cloud` at the gate; the others must diff clean.

### Plan-time rulings (operator, 2026-09-12, at /gsd-plan-phase 72 after research)
- **D-72-19: LinkedIn naming closes INSIDE `merge_enriched` (research Fork 1, Option B).**
  `preingest.merge_enriched` aliases the provider response's `lv_linkedin_url` onto the row's
  existing `linkedin_url` key (one-entry alias table checked before the `allowed_keys` filter).
  No `column_mapping.yaml` change for this field, `required_identity.any_of` untouched, the
  ingest lane keeps reading `row.linkedin_url` and mapping it to `lv_linkedin_url` (PN-1);
  `hs_linkedin_url` is added as a second write target in the lane per D-72-04. Rejected: a
  second canonical column `lv_linkedin_url` (cascades into identity rules and the wrapper).
- **D-72-20: `source_values` for a CREATE conflict lives in the merge REPORT only (research
  Fork 2, option b).** The CSV loser is recorded in `MergeResult.conflicts` and the end-of-run
  report; the persisted held-entry schema (D-71-04/05: `hold_code`, `reason`,
  `observed_signals`, `resume_fingerprint`, `row`, optional `company_known`) stays literally
  untouched. D-72-05's "on the held row" wording is superseded by this ruling.

- **D-72-21: Deploy scope widens to EVERY regenerated workflow whose JSON changed (supersedes
  D-72-18's "ingest only / others diff clean").** `mergeContacts.js` and `mergeCompanies.js` are
  inlined by `scripts/build_cloud_workflows.py` into `wf_enrichment_cloud`, `wf_review_decision_cloud`
  and `wf_scheduled_maintenance_cloud` as well as `wf_contact_ingest_cloud`, so D-72-09's recency
  change cannot leave those diff clean. At the gate: regenerate all, deploy + bounce DISARMED every
  cloud workflow with a changed body (`scripts/deploy_n8n_workflows.py`, `scripts/bounce_n8n_workflows.py`),
  read node counts and `settings.executionOrder: "v1"` back, keep "committed and live are level".
  A workflow whose regenerated JSON is byte-identical is not redeployed. Rollback bundle = the last
  pre-72 commit. Nothing armed before the gate; the D-72-17 armed send stays one record.

- **D-72-22: Provider-sourced ingest fields carry provider-grade confidence (execution-time
  ruling, 2026-09-12, raised by plan 01's tracer as a blocking-human decision).** The ingest lane
  calls `mergeContacts(..., { source: "csv", confidence: 80 })` flat, while `mobilephone` and
  `lv_linkedin_url` are `fill_blank_only` at `min_confidence: 85` — so a CSV-carried mobile ALWAYS
  answered `needs_review`, even into a blank field on a `net_new` row, and never reached the
  `HubSpot Create` body (verified live in-session). Ruling: `MERGE_CONTACTS`
  (`scripts/build_cloud_workflows.py`) derives `confidenceByField[f] = 85` (the waterfall's own
  grade) for every field whose `row.source_by_field[f]` names a provider; a field resolving to
  `csv`, or absent from the map, keeps the flat 80. No `min_confidence` moves (SAFE-01 intact);
  an operator-typed guess stays as untrusted as before. Plan 03's truthful `source_by_field`
  population makes this reachable on the enrich-before-ingest path; plan 04's recency gate keys
  off the same map. Rejected: flat 80→85 (erases the csv<waterfall trust gap), a
  `mobilephone`-only override (no principle; LinkedIn hits the same wall in plan 02),
  retargeting the tracer to the merge decision (plan's must-have goes unmet).

### Claude's Discretion
- Exact parity-test shape for the YAML/JS/policy three-way list (extend
  `tests/n8n/columnMapIdentityParity.test.mjs`'s idiom or a new test).
- Property-creation script shape (one script, `--plan/--execute/--verify`, like
  `scripts/set_named_account_score_floor.py`).
- How `hs_additional_emails` is serialised on write (single `;`-joined string vs array) — verify
  live, record in the SUMMARY.
- Which provider fields map to which geo slot per provider (`normalizeProviders.js` branches).

### Folded Todos
- **`.planning/todos/pending/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md`**
  (design, F71-5) — the charter; its mapping table is superseded by D-72-01..16 above (differences:
  `_2` slots capped at one, stamps provenance-only, companies included). Move to `completed/` with
  the resolution when the phase closes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The rulings and the live evidence
- `.planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-UAT.md` — F71-5 (what was dropped, on which record), the four operator rulings verbatim.
- `.planning/todos/pending/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md` — the mapping table as first proposed.
- `.planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-REVIEW-FIX.md` — WR-02: `held_queue.identity_keys` now reads `extraction.identity_groups()`; the YAML-as-source pattern to reuse.

### The lane and the policy
- `config/field_policy.yaml` (`contacts:` twelve promotable keys; `companies:` classes/TTLs) — D-72-02's single source.
- `config/column_mapping.yaml` + `n8n/code/columnMap.js` + `tests/n8n/columnMapIdentityParity.test.mjs` — the YAML/JS parity idiom.
- `operator-claude-plugin/scripts/preingest.py` (`strip_enrichment_extras`, `promotable_contact_props`, `merge_enriched` fill-not-overwrite rule) and `operator-claude-plugin/scripts/extraction.py` (`canonical_props`, `write_dispatch_csv` STRUCT-01 guard).
- `scripts/build_cloud_workflows.py` — ingest candidate assembly (~L398-421, PN-1 linkedin mapping), enrichment POLICY block (~L1852-1882, the 12 keys). Never hand-edit `n8n/wf_*.json`.
- `n8n/code/mergeContacts.js`, `n8n/code/mergeCompanies.js`, `src/merge_policy.py` — the two engines + Python oracle (Phase 46 parity).
- `n8n/code/normalizeProviders.js` — company `country`/`city` push (58-05, ~L482-490); ZoomInfo company enrich carries no city.
- `CLAUDE.md` §6.1 (metadata pattern), §9 (ownership classes), §13.0.1, §17.2.1 (system-correctable sources), §29.1 (`numberofemployees` scoped exception), §31 (todo triage).

### Portal facts (verified live 2026-09-12)
- Contact props present: `mobilephone`, `hs_additional_emails` (enumeration, writable), `work_email`, `hs_whatsapp_phone_number`, `hs_linkedin_url`, `lv_linkedin_url`, `seniority`, `hs_seniority` (enum), `lv_persona_group`, `city`/`state`/`country`, `hs_state_code`, `hs_country_region_code`, `lv_mobilephone_verified_at`. **No `linkedin_url`.**
- Company props present: `phone`, `city`, `state`, `country`, `hs_state_code`, `hs_additional_domains`, `address`, `zip`. **No email.**
- Memory note `hubspot-property-api-gotchas`: property names lowercase; booleans need options; both fail live-only.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `preingest.promotable_contact_props()` — already the 12-key list from `field_policy.yaml`.
- `extraction.identity_groups()` — YAML loader pattern (WR-02 reused it).
- `scripts/set_named_account_score_floor.py` — `--plan/--execute/--verify` operator-tool shape for property creation.
- `scripts/deploy_n8n_workflows.py`, `scripts/bounce_n8n_workflows.py`, `scripts/build_cloud_workflows.py` — regenerate/deploy/bounce.
- `tests/n8n/columnMapIdentityParity.test.mjs` — parity-test idiom.

### Established Patterns
- Fill-not-overwrite per field with `conflicts` recorded (`merge_enriched`); `source_registry.yaml` trust ranks; provenance stamped in `lv_enrichment_provenance` (§17.2.1).
- Disarmed deploy + bounce, one live gate at phase end, per-send arming.

### Integration Points
- `enrich-before-ingest/SKILL.md` step 7 (the strip call) and `review-triage/SKILL.md` 4a (same strip on the create route).
- Ingest lane: `columnMap.js` → candidate assembly → `Merge Contacts` → `HubSpot Create`/`Update`.
- Property creation must precede the first armed send.

</code_context>

<specifics>
## Specific Ideas

- Busteed `352422766048` is the reference: his held row carried `mobilephone +61 419 212 580` and `lv_linkedin_url http://www.linkedin.com/in/jimmybusteed`; after this phase an equivalent create must show both on the record.

</specifics>

<deferred>
## Deferred Ideas

- A `_3` overflow slot or a multi-value text property — only if provenance-JSON overflow proves insufficient live.
- Per-field `_source`/`_verified_at` properties for the new slots (§6.1) — if HubSpot-view visibility is asked for.
- Company email (`lv_company_email`) — no property, no source today.

### Reviewed Todos (not folded)
- `2026-08-04-enrichment-throughput-ceiling.md`, `2026-09-04-company-domain-has-no-candidate-source.md`, `2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md`, `2026-09-12-rows-to-resume-current-outcomes-never-wired-fingerprint-branch-dead.md`, `2026-09-12-shared-run-manifest-accumulates-positional-verdicts-across-runs.md` — matched by keyword only; unrelated to the mapping/recency scope.

</deferred>

---

*Phase: 72-enrichment-extras-land-in-hubspot*
*Context gathered: 2026-09-12*
