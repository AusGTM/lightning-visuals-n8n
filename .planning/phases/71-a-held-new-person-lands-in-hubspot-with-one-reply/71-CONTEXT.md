# Phase 71: A held new person lands in HubSpot with one reply - Context

**Gathered:** 2026-09-11
**Status:** Ready for planning

<domain>
## Phase Boundary

A rich `no_match` reveal of a new person — usable email at a company HubSpot already holds
(the Jimmy Busteed shape, `jbusteed@australianturfclub.com.au`, ATC `9605284724`) — reads
`new_person` and lands in HubSpot with ONE count-restating reply, on both surfaces:
`enrich-before-ingest` step 6's ready answer and `review-triage`'s one table. The operator is
never asked a question. Settlement of a held entry survives the run boundary under a stable
identity. Proven live at the end of the phase on the second-round `contact-upload` CSVs.

Not in this phase: any new hold code; client-side company creation through the ingest lane; a
second company-resolution implementation anywhere (§13.0.1); arming outside the gate.

</domain>

<decisions>
## Implementation Decisions

### Carried forward — NOT reopened (operator instruction 2026-09-11: "do not relitigate")
- **F2 ruling (operator, 2026-09-11)** — `no_match` holds are faceted at READ time (new person /
  needs company / nothing found); `review-triage` reads both queues in ONE continuously-numbered
  table; `create` lands through the contact-ingest lane under a review-lane grant; the batch
  renders the ready answer and never asks. Criterion: most frictionless operator experience with
  relative safety, **review over approve**, both routes offered with equal weight. Rejected there
  and still rejected: export-to-`contact-upload`, an in-flow approve question (UAT F4).
- **D-69-03** — a client-side durable store ACCUMULATES across runs; each entry carries its own
  `run_id`. `held_queue.json` moves to this shape: settlement verbs (w6p) must outlive the run
  that wrote them, and `classify_read`'s `another_run` rejection cannot stand once the queue is
  multi-run.
- **D-69-04** — `row_id` is explicitly NOT a key (minted per batch, positional).
- **D-70-11** — `confidence.assess` is the ONLY per-row verdict; a facet is a read, never a
  verdict, never a hold code. `confidence.ALL_HOLD_CODES` stays closed.
- **CLAUDE.md §13.0.1** — the ingest lane resolves company by email domain then exact name, holds
  ONE implementation of the association rule; an absent company is downgraded to review
  server-side and never lands. The plugin never reproduces that downgrade client-side and never
  creates a company through the ingest lane; company creation stays in the enrichment lane's
  companies form (`enrich-records`).
- **Backload human gates (operator, 2026-09-09)** — the live proof is ONE end-of-phase UAT gate,
  not a mid-phase probe. Nothing armed before it. SAFE-01..05 unchanged.

### Who knows the company exists (the seed for `classify_facet`)
- **D-71-01: Stamp it on the held entry at persist time.** At `enrich-before-ingest` step 6 the
  batch already knows whether the row's cleaned email domain is among step 2's confirmed domains
  or this run's own company creates (`preingest` same-run dependency index). That fact is written
  onto the held entry when it is persisted; `classify_facet` reads it from the entry on BOTH
  surfaces. Zero lookups; `review-triage`'s cold start is solved by the entry itself.
  Supersedes w6p's executor choice "nothing writes a confirmed company back into the entry" —
  that was an executor design, not an operator ruling. — **Reversibility:** costly — the field
  becomes part of the on-disk entry schema every reader validates.
- **D-71-02: No backend read at facet time.** The plugin has no direct HubSpot access; a lookup
  would need a second company resolver, which is the drift Phase 61 refused (§13.0.1). Rejected.
- **D-71-03: `known_company_domains` stays an argument, sourced from the stamp.** The pure
  signature `classify_facet(entry, known_company_domains)` is kept; callers derive the set from
  the entry's stamp (and may still ADD a domain the operator confirms in-conversation, per
  `review-triage` 2c — that route is unchanged). The default empty set remains the safe direction.

### Stable held-entry identity
- **D-71-04: The key is the row's satisfied identity group, normalised.** Derived from
  `required_identity.any_of` in `config/column_mapping.yaml` — `email` when present (cleaned,
  case-folded), else `firstname+lastname+company` through the same case-folded, whitespace-
  collapsed name key D-69-04 trusts (`suggest_contacts._name_key`), else `linkedin_url`. This
  resolves the conflict with D-69-04, which keys on `company_id` — a `needs_company` row has none
  by definition. `row_id` is carried on the entry as source position only. Settlement
  (`record_verb`), `is_settled`, `open_entries` and `run_manifest.rows_to_resume`'s
  `confidence_held` branch all key on the stable key. — **Reversibility:** one-way — a published
  on-disk schema on operator machines; changing it again means another migration.

### The on-disk queue
- **D-71-05: Wipe once, no migration code.** The live `held_queue.json` (run `a254d1e`, 4 UAT
  entries: Barry Milton twice, Jimmy Busteed with `email: ""` from before F2-1) is deleted in the
  gate's clean-up step; the second-round CSVs repopulate it under the new key. No lazy rekey on
  `load()`. A legacy document (positional keys, no stamp) is refused by `load()` as `anomalous`
  with a one-line reason naming the wipe — never silently read as empty.

### Folded Todos
- **`.planning/todos/pending/2026-09-11-known-company-domains-never-seeded-so-no-held-row-reads-new-person.md`**
  (design) — the seed question. Closed by D-71-01..03.
- **`.planning/todos/pending/2026-09-11-held-queue-row-id-is-positional-not-a-stable-identity.md`**
  (design) — the identity question. Closed by D-71-04..05.
- **`.planning/todos/pending/2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md`**
  (minor) — folded under §31 rule 3: adjacent residual in `held_queue.py`'s persist path, the
  same function this phase edits, and it dropped Grant Dewsbury from the UAT CSV. Fix once so a
  person named Grant or a company named Token persists; the marker must still refuse an actual
  grant token / secret value. Every store the todo lists (`held_queue`, `suggestion_declines`,
  `run_manifest`, `run_state`, `run_report`) takes the same fix through the shared matcher.

### Live gate
- **D-71-06: One end-of-phase UAT gate on the second-round CSVs** (`docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`
  §1d). It must produce at least one `new_person` row live — a person NOT in HubSpot whose
  company IS (the Jimmy Busteed shape) — and land them with one `create all N` reply on the
  batch surface, then exercise `review-triage`'s cold-start create on a second such row in a
  fresh sitting. Hand-delete the UAT contacts afterwards (§1d clean-up). Arming is per-send and
  disarmed after, as every prior gate.

### Claude's Discretion
- Field name and shape of the persist-time stamp; whether it records the source
  (`step2_confirmed` / `same_run_create`) beside the boolean.
- Exact normalisation of the stable key and its serialisation in the JSON map.
- How `classify_read` reports a legacy document.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The ruling and its record
- `.planning/todos/completed/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md` — the F2 ruling verbatim, criterion, rejected shapes, and what w6n shipped against it.
- `.planning/UAT-autonomous-batch-2026-09-09.md` — the recorded run `a254d1e`, findings F2/F4, the held rows this phase is built against.
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` §1d — the second-round CSV shape and the gate's clean-up.

### What quick batch 260911-w6n shipped (read the SUMMARYs, not the plans)
- `.planning/quick/260911-w6o-f2-1-prerequisite-the-held-queue-entry-stores-the-source-row/260911-w6o-SUMMARY.md` — merged row persisted; allowlist; forbidden-name scan on keys.
- `.planning/quick/260911-w6p-f2-2-add-a-read-time-facet-classifier-to-operator-claude-plu/260911-w6p-SUMMARY.md` — `classify_facet`, verbs, settled-row resume guard; its "nothing writes back" choice is superseded by D-71-01.
- `.planning/quick/260911-w6q-f2-3-operator-claude-plugin-skills-review-triage-skill-md-to/260911-w6q-SUMMARY.md` — the one table, the create route by heading, the API reconciliation.
- `.planning/quick/260911-w6r-f2-4-operator-claude-plugin-skills-enrich-before-ingest-skil/260911-w6r-SUMMARY.md` — step 6 render, ready answer, 0.47.0.

### Prior decisions carried
- `.planning/phases/69-held-rows-survive-the-round/69-CONTEXT.md` — D-69-03 (accumulate, per-entry run_id), D-69-04 (row_id never a key), D-69-06 (a drained send clears every gate).
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md` — D-70-05 (runData by client-minted run_id), D-70-11 (one per-row verdict).
- `CLAUDE.md` §13.0.1 (server-side company resolution, ONE association implementation, absent company → review), §17.2.1, §31 (todo triage).
- `config/column_mapping.yaml` `required_identity.any_of` and `n8n/code/columnMap.js::requiredIdentity` — the identity groups D-71-04 keys on (YAML/JS parity test `tests/n8n/columnMapIdentityParity.test.mjs`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `operator-claude-plugin/scripts/held_queue.py` — `build_entry`, `save` (caller merges `load()` + new, atomic overwrite), `classify_read`, `classify_facet`, `record_verb`/`entry_verb`/`is_settled`/`open_entries`, `ROW_FIELD_ALLOWLIST`, `_first_forbidden`/`_first_forbidden_key`.
- `operator-claude-plugin/scripts/enrichment.py` — `_clean_domain`, `FREEMAIL_DOMAINS` (the one domain guard; mirrored in `n8n/code/companyLink.js`).
- `operator-claude-plugin/scripts/suggest_contacts.py::_name_key` — the name key D-69-04 trusts.
- `operator-claude-plugin/scripts/preingest.py` — same-run company dependency index (`company_dependency_id -> company_id`), `assign_same_run_company_ids`.
- `operator-claude-plugin/scripts/run_manifest.py::rows_to_resume` — the `confidence_held` branch that keys on the entry.
- `operator-claude-plugin/scripts/suggestion_declines.py` — the D-69 store: the accumulate-across-runs, per-entry `run_id`, stable-key precedent to copy.

### Established Patterns
- Durable stores: `durable_paths.resolve_state_path().parent`, `_atomic_write_0600`, validate-every-entry before write, `classify_read`-style reader, forbidden-name refusal.
- Skills delegate by heading, never duplicate a dispatch (`review-triage` → `contact-upload` steps 6-10).
- Tests pin recorded run shapes (`a254d1e` entries inline) and skill fences (`test_skill_sequence_coverage.py` COVERED registry; `test_enrich_before_ingest_skill_contract.py`; `test_review_triage_facets.py`).

### Integration Points
- `enrich-before-ingest/SKILL.md` step 6 persist fence (stamp written here) and facet render; step 9 restatement.
- `review-triage/SKILL.md` step 2b/2c (read + facet), 4a-4c (create route + re-facet), mark verb.
- `run_manifest.rows_to_resume` (settlement keyed on the new identity).
- Plugin version bump + CHANGELOG cut at phase end (0.48.0), marketplace clone refresh, Claude Code restart before the gate.

</code_context>

<specifics>
## Specific Ideas

- The headline truth to verify goal-backward: "Jimmy Busteed reads `new_person` on both surfaces and lands with one `create all 1` reply" — the exact case quick batch w6n left false.
- Grant Dewsbury is the UAT person the forbidden-name fold should let through.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-09-04-company-domain-has-no-candidate-source.md` — n8n enrichment lane; §17.2.1 correction inert. Adjacent by keyword only; not this phase.
- `2026-08-04-enrichment-throughput-ceiling.md`, `2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` — n8n runtime; unrelated.

</deferred>

---

*Phase: 71-a-held-new-person-lands-in-hubspot-with-one-reply*
*Context gathered: 2026-09-11*
