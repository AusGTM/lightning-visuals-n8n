# Phase 69: Held rows survive the round - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning

<domain>
## Phase Boundary

A person a suggestion round correctly declined to send is durable: recorded in a client-side
store that survives the run, surfaced to the operator as one end-of-run batch, and drained by
the operator in a single sitting. After the live Roma Turf Club round the only record of two
correctly-held committee members was a chat message; this phase closes that.

**In scope:** the decline store (its shape, keying, lifecycle), the end-of-run batch report
over it, the drain actions, and `SKILL.md` step 8's routing into it instead of into
`held_queue.save`.

**Out of scope:** `confidence.ALL_HOLD_CODES` (not widened — see D-69-02), the match-gate
held-row path `enrich-before-ingest` uses (unchanged), why a person was declined (the email
and matcher causes are quick tasks 260905-ad2 / 260905-rf1, already landed), and the
round-empty cause classifier (Phase 65).

</domain>

<decisions>
## The store

- **D-69-01: A new client-side durable store, not a widened `held_queue`.** Operator ruling:
  "client-side durable store". It follows every convention `held_queue.py` and
  `run_manifest.py` already established — resolved under
  `durable_paths.resolve_state_path().parent`, written with
  `durable_paths._atomic_write_0600`, whole-document overwrite, validate-every-entry before
  anything is written, the secret/grant-name refusal (`_looks_forbidden`), and a
  `classify_read`-style reader. It is a sibling of `held_queue.json`, not a section inside it.
  — **Reversibility:** costly — a second store is a second file on operator machines; merging
  it back into `held_queue` later means a migration of live operator state.

- **D-69-02: `confidence.ALL_HOLD_CODES` is NOT widened.** The brief's central warning, kept:
  `ALL_HOLD_CODES` is the match-gate vocabulary ("could not identify"); a suggestion-round
  partition code means "identified fine, declined to send". Letting a decline into
  `held_queue` would put a decline into the review queue wearing a match verdict's clothes.
  `held_queue.save`'s `HeldQueueError` on `no_email` / `email_domain_mismatch` is **correct
  behaviour and stays** — the skill is what changes.

- **D-69-03: The store ACCUMULATES across runs; each entry carries its own `run_id`.**
  Deliberately diverges from `held_queue`'s single-`run_id` document, where a new run
  overwrites and `classify_read` reports `another_run` as a rejection. A deferred entry has to
  survive a run boundary, so run scope moves from the document to the entry. A new run merges
  into the document; it never overwrites it.
  — **Reversibility:** one-way — once operator machines hold a multi-run document, reverting
  to a single-run document discards every deferred entry that has not been drained.

- **D-69-04: An entry is keyed `company_id` + normalised name key.** The name key is
  `suggest_contacts._name_key` — the same case-folded, whitespace-collapsed first+last key
  dedupe already trusts (D-62-18). Stable across runs, so a person re-found in a later round
  updates their existing entry rather than appearing twice. `row_id` is explicitly NOT the key:
  `build_rows_spec` mints it per batch, so it changes every run.

## The drain

- **D-69-05: The operator sees one end-of-run batch and drains it in a sitting.** Not a
  per-company halt. The report covers this run's declines AND the deferred backlog from
  earlier runs in the same view.

- **D-69-06: Four actions.** `send`, `defer`, `delete`, `export`.
  - **send** — dispatch to HubSpot after the operator supplies what was missing. This is a
    WRITE path and gets no exemption: the open grant, the per-run ceilings,
    `extraction.validate()` and every gate a normal send clears all apply unchanged. A
    drained entry is not a back door.
  - **defer** — entry stays, untouched, and reappears in the next end-of-run batch. No spend,
    no write.
  - **delete** — removed from the store permanently.
  - **export** — written out as a spreadsheet row the operator fixes by hand and feeds back
    through `contact-upload`. No write path, no grant, reuses an ingest lane that exists.

- **D-69-07: Delete is removal only — no tombstone, no suppression.** A later run that
  rediscovers the same person re-queues them. Rejected: recording a suppression key. The
  operator chose to re-decide rather than carry a permanent do-not-suggest list.

- **D-69-08: Two drain surfaces.** Inline at the end of a round (this run's declines plus the
  backlog), AND a standalone skill the operator can invoke any time. The standalone route is
  the durable one: a backlog deferred across several runs must be reachable without running a
  round to get at it.
  — **Reversibility:** reversible — the standalone skill is additive.

### Claude's Discretion

- The store's filename and module name (`suggestion_declines.json` / `suggestion_queue.py` are
  placeholders, not decisions).
- How much of `held_queue.py`'s validation is shared via a common helper versus duplicated.
  Sharing is preferred; a shared helper must not drag `ALL_HOLD_CODES` along with it (D-69-02).
- The standalone drain skill's name, and whether it is a new skill or a mode of an existing one
  (`review-triage` is the nearest neighbour).
- The exact batch-report layout.

### Folded Todos

- **`2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md`** — this phase in
  full. Its explicit "do not fix it that way" (widening the frozenset) is honoured by D-69-02,
  and its "the real question is durability" is answered by D-69-01/-03 rather than by the
  report-only alternative it also offered.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief
- `.planning/todos/pending/2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md`
- `.planning/ROADMAP.md` § "Phase 69" and § "Binding on all six" (SAFE-01..05).
- `.planning/milestones/v1.2-REQUIREMENTS.md`

### The precedent to copy
- `operator-claude-plugin/scripts/held_queue.py` — `queue_path`, `build_entry`, `save`,
  `load`, `classify_read`, `_looks_forbidden`, `ROW_FIELD_ALLOWLIST`. Copy the conventions;
  do NOT extend `ALL_HOLD_CODES` (D-69-02) and do NOT copy the single-`run_id` document
  scoping (D-69-03).
- `operator-claude-plugin/scripts/run_manifest.py` — `manifest_path`, `save`, `load_scoped`,
  `rows_to_resume(rows, manifest, held_entries=..., current_outcomes=...)`. `rows_to_resume`
  already reads `held_entries`; it is the nearest existing hook for a drain pass.
- `operator-claude-plugin/scripts/durable_paths.py` — `resolve_state_path`,
  `_atomic_write_0600`. The one resolution rule; never a second.

### The code this phase changes
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` step 8 — routes partition holds
  through `held_queue.build_entry` / `held_queue.save` today. That routing is the defect.
- `operator-claude-plugin/scripts/suggest_contacts.py` — `partition_for_dispatch`,
  `_name_key` (supplies D-69-04's key half), `round_artifact`.
- `operator-claude-plugin/scripts/confidence.py` — `assess`, `ALL_HOLD_CODES`. Read to
  understand the vocabulary boundary; not modified.

### The write path a `send` must clear unchanged
- `operator-claude-plugin/scripts/write_grant.py` — the grant and its envelope figures.
- `operator-claude-plugin/scripts/dispatch.py` — the dispatch call and `source_by_field`.
- `operator-claude-plugin/scripts/extraction.py` — `validate`, `strip_row_id`.
- Phase 57's per-run ceilings and refusal-before-start. A drained `send` is a normal send.

### Cross-phase
- `.planning/phases/64-.../64-CONTEXT.md` — D-64-08's `ended` reason.
- Phase 65's cause classifier: a dead-ended company's cause is a FIELD on a stored entry.
  65 names the cause; 69 is what makes it survive. Neither phase owns both halves.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `durable_paths.resolve_state_path()` / `_atomic_write_0600` — the client-side durable
  directory and its 0600 atomic write, already the single resolution rule for
  `held_queue.json`, `run_manifest` and `artifact_store`.
- `held_queue._looks_forbidden` / `_first_forbidden` — the grant/secret name refusal, needed
  verbatim by any new store that persists operator-visible rows.
- `held_queue.ROW_FIELD_ALLOWLIST` (`("row_id",) + enrichment.MATCH_LOOKUP_KEYS`) — the
  precedent for persisting only allowlisted row fields.
- `suggest_contacts._name_key` — half of D-69-04's key; already the conservative identity
  notion the round trusts.
- `run_manifest.rows_to_resume(..., held_entries=...)` — already reads held entries; the
  nearest existing hook for a drain pass.

### Established Patterns
- **Validate before write.** `held_queue.save` validates every entry first, so a raising save
  leaves the previous file untouched. The new store must do the same.
- **Whole-document overwrite, caller assembles the map.** `save(run_id, entries)` takes the
  full map — typically `load()`'s return with this run's entries merged in. D-69-03 keeps the
  overwrite mechanic and moves the run scoping into the entries.
- **A refusal is behaviour, not a bug.** `held_queue.save`'s `HeldQueueError` stays.
- **Plugin scripts are pure** — no HTTP client, no model call. The store does filesystem I/O
  the way `held_queue` already does; the drain's decisions stay pure.
- **No `while` loop in any plugin script** (`tests/test_report_sufficiency.py::_has_while_loop`).

### Integration Points
- `SKILL.md` step 8's held half is the caller that changes.
- The end-of-run batch report is new operator-facing surface; Phase 68's disclosure audit
  covers what halts and what does not, so keep the report a report.
- A drained `send` re-enters `extraction.validate()` → `dispatch.dispatch(...)` — the existing
  path, no parallel one.

</code_context>

<specifics>
## Specific Ideas

- The defining live case: Roma Turf Club, two correctly-held committee members, one with no
  email and one whose waterfall email was a different Craig Smith at `thehartford.com`. Both
  holds were right. Losing them was not.
- Operator's framing of the drain: "review and drain" — a queue with a lifecycle, where defer
  and delete are first-class alongside send.
- The store is client-side. Nothing about this phase writes state to HubSpot.

</specifics>

<deferred>
## Deferred Ideas

- **Suppression / do-not-suggest list** — explicitly rejected in D-69-07. If the operator later
  tires of re-deciding the same person, it is a phase of its own.
- **Draining the enrich-before-ingest match-gate held queue through the same surface** — out of
  scope; that queue has its own vocabulary and its own review lane.
- **Retention / pruning of a long-lived accumulating store** — not decided. Worth a look once
  real backlog sizes are observed.

### Reviewed Todos (not folded)
- `2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md` — Phases 64 and 65.
- `2026-09-04-state-the-price-and-keep-moving.md` — Phase 68; the batch report must not become
  a halt, which is 68's rule, applied here.

</deferred>

---

*Phase: 69-held-rows-survive-the-round*
*Context gathered: 2026-09-05*
