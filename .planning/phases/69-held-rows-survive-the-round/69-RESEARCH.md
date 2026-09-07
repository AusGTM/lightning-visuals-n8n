# Phase 69: Held rows survive the round - Research

**Researched:** 2026-09-07
**Domain:** plugin-local durable storage + skill-authoring convention (Python stdlib only; no new dependencies)
**Confidence:** HIGH

## Summary

This phase adds a fourth-ish persisted artifact to `operator-claude-plugin/scripts/` — a
sibling of `held_queue.json`, not a widening of it — that gives a suggestion round's
partition-declined people (Roma Turf Club's "no email" / "email domain doesn't match"
holds) somewhere durable to live, plus a drain surface (inline + standalone) to work them.
Every piece of machinery this phase needs already exists in the codebase as a precedent to
copy: `held_queue.py` is the template for the store's shape (path resolution, atomic
write, validate-before-write, forbidden-name refusal, `classify_read`), `durable_paths.py`
is the one path-resolution authority, and `enrich-before-ingest/SKILL.md` steps 5 and 7
are the exact, already-tested call sequences the drain's `send` action must re-enter
unchanged (grant, per-run ceiling, `extraction.validate()`, `dispatch.dispatch()`).

The central design fact this research surfaces: **the codebase's own established
convention for a sibling durable store is to REIMPLEMENT the forbidden-name refusal
(`_looks_forbidden`/`_FORBIDDEN_NAME_MARKERS`), never import it** — `held_queue.py`'s own
module docstring says this explicitly about `run_manifest.py`'s copy of the same code
(held_queue.py:68-70). This sits in mild tension with CONTEXT.md's "Claude's Discretion"
note that sharing is preferred; the research recommends following the established
precedent (duplicate the refusal, import only `durable_paths` and
`enrichment.MATCH_LOOKUP_KEYS`) because that is what every existing sibling store in this
codebase actually does, and it is exactly the discipline D-69-02 asks for at the schema
level (no accidental coupling to `confidence.ALL_HOLD_CODES`).

Two further findings shape the plan directly. First, the held row's `row` dict
(`suggest_contacts.synthesise_rows`) carries the company's **name**, never its HubSpot id
— so satisfying D-69-04's `company_id + name_key` composite key requires the SKILL.md
step-8 caller to look the id up from the round's own `rounds[]` structure (the
`{start, count}` range already used for the terminal `round_outcome` classify at
`suggest_contacts.py`'s call site, SKILL.md:628-634) and hand it to the new store's
`build_entry` explicitly; nothing downstream can derive it from the row alone. Second,
`extraction.write_dispatch_csv` is not reusable for the `export` action (D-69-06) because
it hard-refuses any row with no usable email (`extraction.py:924-930`) — exactly the
condition most held rows are in — so export needs its own small `csv` writer, not a call
into the existing dispatch-CSV path.

**Primary recommendation:** build a new module (`suggestion_declines.py`, placeholder
name, D-69's own discretion) that copies `held_queue.py`'s shape verbatim (path
resolution via `durable_paths`, atomic write, validate-before-write, `classify_read`) but
keyed by `(company_id, name_key)` with a per-entry `run_id` (D-69-03), validated against a
NEW closed vocabulary of the five partition `reason_code`s (which does not exist as a
named constant anywhere today and must be added, e.g. to `suggest_contacts.py`, mirroring
`confidence.ALL_HOLD_CODES`'s role for the OTHER vocabulary). Rewrite SKILL.md step 8's
held-half prose (and, if the plan chooses to make it executable, its code) to call this
store instead of `held_queue.build_entry`/`held_queue.save`. Build a new standalone skill
for the drain (review-triage's *shape* — fetch, let the operator pick, decide, confirm,
report — is a good pattern to imitate; its *mechanism*, a HubSpot-backend queue read via
`review_queue.fetch_queue`, is not, since our queue is a local JSON file). Route `send`
through `enrich-before-ingest/SKILL.md` steps 5+7's exact call sequence unchanged.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Decline persistence (the new store) | Plugin scripts (client-side filesystem) | — | Pure Python, no HTTP, no model call — `held_queue.py`'s own established tier (module docstring, held_queue.py:1-80) |
| End-of-run batch report | Plugin scripts → SKILL.md prose | — | Report-building is pure (`run_report.py` precedent); rendering is the skill's job, not a script's |
| Drain decisions (`send`/`defer`/`delete`/`export`) | SKILL.md (operator-interactive) → plugin scripts | Backend (HubSpot) for `send` only | `defer`/`delete`/`export` never leave the plugin's local filesystem; only `send` crosses into the write path |
| The `send` action's actual write | Backend / n8n Cloud via `dispatch.dispatch` | Plugin scripts (grant, ceiling, CSV build) | Unchanged existing write tier — D-69-06 explicitly forbids a parallel path |
| `confidence.ALL_HOLD_CODES` vocabulary | Plugin scripts (`confidence.py`) | — | Untouched, per D-69-02 — a different question's vocabulary, not this phase's to touch |

## User Constraints

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
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

### Deferred Ideas (OUT OF SCOPE)
- **Suppression / do-not-suggest list** — explicitly rejected in D-69-07. If the operator later
  tires of re-deciding the same person, it is a phase of its own.
- **Draining the enrich-before-ingest match-gate held queue through the same surface** — out of
  scope; that queue has its own vocabulary and its own review lane.
- **Retention / pruning of a long-lived accumulating store** — not decided. Worth a look once
  real backlog sizes are observed.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HELD-01 | The skill and the code agree on where partition holds go (step 8 currently routes them to `held_queue`, which raises `HeldQueueError`). | New store's `build_entry`/`save` are the target of the rewritten step-8 prose/code; §"Code Examples" and §"Q1/Q5" below give the exact old-vs-new call sites. |
| HELD-02 | `confidence.ALL_HOLD_CODES` is NOT widened, and a test pins the disjointness as deliberate. | §"Q8" confirms no such test exists today and that the two vocabularies (`ALL_HOLD_CODES` vs the 5 partition `reason_code`s) are already disjoint strings — the new test is a same-day addition, not a fix. |
| HELD-03 | Correctly-held people persist somewhere durable (chosen over "report-only"). | D-69-01/03/04 already choose the durable-store path over report-only; §"Standard Stack" and §"Architecture Patterns" give the store's shape. |

</phase_requirements>

## Standard Stack

### Core

No new dependency of any kind. Every piece is Python stdlib (`json`, `hashlib`, `csv`,
`datetime`, `pathlib`) plus the plugin's own existing internal modules
(`durable_paths`, `enrichment`, `suggest_contacts`, `extraction`, `write_grant`,
`dispatch`, `preingest`, `chunking`, `n8n_arming`, `run_report`, `config_gate`). This
mirrors every prior durable-artifact phase in this plugin (`artifact_store.py`,
`run_manifest.py`, `held_queue.py`, `remainder_queue.py`, `written_records.py`) — none of
them added a dependency, and this phase's problem shape (a fourth JSON file, same
directory, same write discipline) is identical in kind.

### Supporting

Not applicable — no supporting library. `csv` (stdlib) covers the `export` action's
output format.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plain-dict JSON store (the codebase's own idiom) | `sqlite3` (stdlib) | Rejected: every sibling store in this plugin is a single JSON document under `durable_paths`; a second persistence technology for one store is exactly the "second-source-of-truth pattern this milestone avoids everywhere else" `durable_paths.py`'s own docstring names (durable_paths.py:6). |
| Reimplemented forbidden-name refusal (precedent) | Import `held_queue._looks_forbidden` | `held_queue.py`'s own docstring states the reimplementation choice explicitly for `run_manifest.py`'s copy — "reimplemented, not imported ... so a future change to one cannot silently weaken another" (held_queue.py:68-70). Importing would be the first place in this codebase that breaks that discipline. |

**Installation:** none.

**Version verification:** N/A — no packages installed. `python3` invocation convention
(SKILL.md's own "run from the plugin root" banner) is unchanged.

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages (npm, PyPI, or otherwise).
Every module touched is either Python stdlib or an existing file already in
`operator-claude-plugin/scripts/`. No `npm view` / `pip index versions` check is
required, and no `## Package Legitimacy Audit` table is produced.

## Architecture Patterns

### System Architecture Diagram

```
 Suggestion round (SKILL.md step 8, unchanged sendable half)
   |
   +-- partition_for_dispatch(rows, company_domains) --> (sendable, held)
   |         held: [{"index","row","reason","reason_code"}, ...]
   +-- search_fallback.hold_weak_sources(records, sendable, held) --> (sendable, held')
   |
   v
 [THIS PHASE'S NEW CODE — step 8's held half, rewritten]
   for each held entry:
     company_id = lookup via rounds[].{start,count} range containing entry["index"]
     name_key   = suggest_contacts._name_key(entry["row"])
     if company_id and name_key:
         entry = suggestion_declines.build_entry(row, reason_code, reason, run_id)
         entries[(company_id, name_key)] = entry     # merge, never overwrite whole doc
         suggestion_declines.save(entries)             # validate-then-atomic-write
     else:
         # cannot key it -- surfaced in the report as unkeyable, never silently dropped
   |
   v
 suggestion_declines.json (durable, ACCUMULATES across runs -- D-69-03)
   |
   +-------------------------------------------------------------+
   |                                                               |
   v (inline, D-69-08 surface 1)                                  v (standalone, D-69-08 surface 2)
 SKILL.md step 9's end-of-run report                    NEW standalone drain skill
   this run's new declines + the whole backlog             loads suggestion_declines.json
   |                                                          any time, no round required
   v
 Operator picks an action per entry: send / defer / delete / export
   |
   +-- defer --> entry left untouched in the store, reappears next batch (no I/O beyond a no-op)
   +-- delete --> entry removed from the store, saved (no tombstone -- D-69-07)
   +-- export --> csv writer (stdlib), NOT extraction.write_dispatch_csv (that raises on
   |              no-email rows -- exactly what most held rows are)
   +-- send   --> re-enters the EXISTING write path, unchanged:
                    preingest.build_rows_spec([row])   # fresh row_id -- D-69-04's own point
                    extraction.validate(...)
                    preingest.strip_enrichment_extras(...) -> extraction.strip_row_id(...)
                    extraction.write_dispatch_csv(...)
                    write_grant.authorize_send / authorize_ungranted_send
                    n8n_arming.armed_window(...) -> dispatch.dispatch(...)
                    write_grant.record_dispatch_outcome(...)
                    # == enrich-before-ingest/SKILL.md steps 5+7's own sequence, verbatim ==
                  on success: entry removed from suggestion_declines.json
```

### Recommended Project Structure

No new directories. One new file at `operator-claude-plugin/scripts/suggestion_declines.py`
(placeholder name per D-69's own discretion), one new skill directory at
`operator-claude-plugin/skills/<drain-skill-name>/SKILL.md` (placeholder name), and edits
to `operator-claude-plugin/skills/suggest-contacts/SKILL.md` step 8/9.

### Pattern 1: Sibling durable store, copied from `held_queue.py`

**What:** A module-level `QUEUE_FILENAME`, `queue_path()` resolved fresh every call via
`durable_paths.resolve_state_path().parent / FILENAME` (never a second resolution rule —
`held_queue.py:147-151` is the exact precedent), a `build_entry(...)` pure constructor, a
`save(entries, path=None)` that validates every entry before writing anything
(`held_queue.py:186-224`), a `load(path=None)` that degrades whole to `{}` on any
malformed input (`held_queue.py:245-257`), and a `classify_read(path=None)` returning one
of `ABSENT`/`PARSEABLE`/`ANOMALOUS` for the review pass to narrate honestly
(`held_queue.py:260-279`; `ANOTHER_RUN` does not apply here since D-69-03 makes the whole
document multi-run by design — there is no "wrong run" to detect at the document level,
though an individual entry's own `run_id` is still informative in the report).

**When to use:** Any time the plugin needs a new persisted, operator-visible artifact
that must survive a plugin update (`durable_paths` migration) and must never carry a
secret or grant.

**Example (adapted skeleton, not existing code — composed from the cited precedent):**
```python
# Source: operator-claude-plugin/scripts/held_queue.py:147-224 (the pattern being copied)
import durable_paths

QUEUE_FILENAME = "suggestion_declines.json"   # placeholder, D-69's own discretion

def queue_path() -> Path:
    return durable_paths.resolve_state_path().parent / QUEUE_FILENAME

def save(entries, path=None) -> None:
    for key, entry in entries.items():
        # validate BEFORE writing anything -- held_queue.py:191-216's own discipline
        ...
    target = Path(path) if path is not None else queue_path()
    durable_paths._atomic_write_0600(target, json.dumps({"entries": dict(entries)}))
```

### Pattern 2: Composite string key for a JSON document (D-69-04)

**What:** JSON object keys must be strings. `held_queue.json`/`run_manifest.json` both
key on a single string (`row_id`). This store's key is a *pair*
(`company_id`, `name_key`) — `name_key` itself is already a tuple
(`suggest_contacts._name_key` returns `(first, last)`, suggest_contacts.py:161-169). The
on-disk key must be a single deterministic string composed from both halves, e.g.
`f"{company_id}::{first}|{last}"`, with a documented separator that cannot collide with a
real company id or name (company ids are numeric HubSpot ids; `::` cannot appear in one).

**When to use:** Only here — no other store in this codebase has a composite key today.

### Anti-Patterns to Avoid

- **Importing `confidence.ALL_HOLD_CODES` into the new module, even transitively.** D-69-02
  is explicit: the two vocabularies must stay disjoint by construction, not by convention.
  The new store's own validation vocabulary must be its own frozenset (see "Don't
  Hand-Roll" below for where that frozenset should live).
- **Calling `extraction.write_dispatch_csv` for the `export` action.** It raises
  `ExtractionError("emailless_row_cannot_ingest", ...)` on any row without a usable email
  (extraction.py:924-930) — the exact shape most held rows are in. Use a small dedicated
  `csv` writer instead (see "Don't Hand-Roll").
- **Feeding a stored entry's `row` straight into `preingest.build_rows_spec` without
  first stripping any leftover `row_id`.** `build_rows_spec` refuses a row that already
  carries one (preingest.py:219-221). D-69-04 already establishes the reasoning
  ("`row_id` is explicitly NOT the key"); the store's persisted `row` should never carry
  one at all, so this failure mode should not arise if the entry is built correctly —
  worth a defensive strip anyway if the row is ever round-tripped through export/re-import.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic, 0600, crash-safe file write | A custom `open()`/`os.rename()` dance | `durable_paths._atomic_write_0600` | Already closes the exact partial-write window this plugin's own `33-RESEARCH.md` Finding 3 identified; used by every sibling store (held_queue.py:224, run_manifest.py:238). |
| Per-operator state directory resolution | A new env var or a hardcoded path | `durable_paths.resolve_state_path().parent` | The single resolution authority (`durable_paths.py:1-22`'s own stated purpose) — a second resolution rule reintroduces exactly the drift problem this module exists to prevent. |
| Name-collapsed person identity | A new fuzzy-match / Levenshtein scheme | `suggest_contacts._name_key` | D-69-04 explicitly reuses this — the same key `select_people`'s D-62-18 dedupe already trusts (suggest_contacts.py:161-169). |
| Grant/secret name refusal on a new persisted field set | A bespoke regex or allowlist | Reimplement `_FORBIDDEN_NAME_MARKERS` + `_looks_forbidden`/`_first_forbidden` verbatim (do not import) | Matches the established precedent (`held_queue.py:68-70`, `run_manifest.py:22-24, 112-123`) exactly — reimplementation, not import, is the deliberate discipline here. |
| A closed vocabulary for the store's own `hold`-equivalent field | Hardcoded string literals scattered per call site | A new named frozenset, e.g. `suggest_contacts.PARTITION_REASON_CODES = frozenset({"no_email", "email_domain_freemail", "email_domain_mismatch", "company_domain_unknown", "search_source_not_strong"})` | **Does not exist today** (verified: no such constant anywhere in `suggest_contacts.py` or `search_fallback.py` — `"no_email"` is a bare literal at suggest_contacts.py:870, the other three come from `_RELATION_REASON_CODES.values()` at suggest_contacts.py:678-682, and `search_fallback.SOURCE_TIER_HOLD_CODE = "search_source_not_strong"` at search_fallback.py:64 is separate). This is the natural mirror of `confidence.ALL_HOLD_CODES` for the OTHER vocabulary, and HELD-02's disjointness test needs both sides named to compare. |
| Mapping a held row's `index` back to its owning company's HubSpot id | A parallel per-row cache built ad hoc | A small pure helper reading the SAME `rounds[]` `{start, count}` ranges the terminal `round_outcome` classify already uses (`skills/suggest-contacts/SKILL.md:628-634`) | The mapping already exists implicitly in `rounds[]`; a new helper (e.g. `suggest_contacts.company_id_for_index(rounds, index)`) reuses that structure rather than re-deriving company ownership a second way. |
| Spreadsheet export for `contact-upload` round-trip | A bespoke ad-hoc column scheme | `extraction.canonical_props()` as the header (includes `company_id`, `company`, `firstname`, `lastname`, `jobtitle`, `linkedin_url`, `phone`, `email` — verified live via `config/column_mapping.yaml`'s `aliases` values, column_mapping.yaml:14-59) | `contact-upload`'s own column mapper already accepts these exact header names case-insensitively (column_mapping.yaml:1-13); using them verbatim means the exported file needs no bespoke re-import logic on the other end. |

**Key insight:** every piece of this phase composes existing, already-tested machinery.
The only genuinely new code is: the store itself (a fourth copy of a four-times-proven
pattern), the composite-key encoding, the company-id-lookup helper, the new closed
reason-code vocabulary, the CSV export writer, and the two SKILL.md surfaces. Nothing
about matching, scoring, enrichment, dispatch, or grant logic needs touching.

## Common Pitfalls

### Pitfall 1: Treating the new store's forbidden-name check as importable from `held_queue`
**What goes wrong:** A future change to `held_queue._FORBIDDEN_NAME_MARKERS` (e.g.
widening it to catch a new secret-shaped name) silently fails to protect the new store,
or — worse — an import creates a coupling that makes `held_queue.py` unable to evolve
independently.
**Why it happens:** DRY instinct, reinforced by CONTEXT.md's "Claude's Discretion" note
that sharing is preferred.
**How to avoid:** Follow the codebase's own stated precedent (held_queue.py:68-70):
reimplement the constant and the two functions verbatim in the new module. This is a
~15-line duplication, not a real cost.
**Warning signs:** A plan task that imports `held_queue._looks_forbidden` or
`held_queue._FORBIDDEN_NAME_MARKERS` directly.

### Pitfall 2: Keying the new store on `row_id`
**What goes wrong:** `row_id` is minted fresh per batch by `preingest.build_rows_spec`
(preingest.py:195-220) — the same person gets a different `row_id` every round they are
re-found in, so keying on it would never dedupe across runs, defeating D-69-03's whole
point.
**Why it happens:** `held_queue.json` itself keys on `row_id` (held_queue.py's schema),
so it is the nearest visible precedent and easy to copy reflexively.
**How to avoid:** D-69-04 is explicit and already anticipates this exact mistake
("`row_id` is explicitly NOT the key... it changes every run"). Key on
`(company_id, name_key)` per Pattern 2 above.
**Warning signs:** Any code path threading `record["row"]["row_id"]` into the new
store's key construction.

### Pitfall 3: Reusing `extraction.write_dispatch_csv` for `export`
**What goes wrong:** `ExtractionError("emailless_row_cannot_ingest", ...)` raised on the
first held row with no email — which, per the live Roma case, is most of them.
**Why it happens:** It is the only CSV writer already in the codebase, so it looks like
the obvious reuse.
**How to avoid:** Write a small dedicated exporter using stdlib `csv.DictWriter` over
`extraction.canonical_props()` headers, with no email-presence guard — the whole point of
export is to hand the operator an incomplete row to fix by hand.
**Warning signs:** A plan task that calls `extraction.write_dispatch_csv` anywhere on the
`export` code path.

### Pitfall 4: Letting a `send` skip the ceiling/grant machinery because "it's just one row"
**What goes wrong:** A drained entry bypasses `write_grant.authorize_send` /
`authorize_ungranted_send`, the pre-call ceiling check, or `n8n_arming.armed_window` —
exactly the "back door" D-69-06 forbids in its own text.
**Why it happens:** A single-row send feels like it should be simpler than a batch send.
**How to avoid:** Re-enter `enrich-before-ingest/SKILL.md` steps 5's confidence-assess-
equivalent (not applicable here — a drained entry has already been through that decision;
it's a `send`, not a re-enrichment) and step 7's dispatch block verbatim
(enrich-before-ingest/SKILL.md:770-889), scoped to the one row. The block is written to
work over `sendable_rows` as a list — a list of one is not a special case.
**Warning signs:** New code that calls `dispatch.dispatch(...)` without first calling
`write_grant.authorize_send`/`authorize_ungranted_send`, or that skips
`n8n_arming.armed_window`.

### Pitfall 5: Missing the `strip_enrichment_extras` → `strip_row_id` order
**What goes wrong:** A widened contact field (`seniority`, `mobilephone`, ...) that
`preingest.merge_enriched` allows onto a row but the deployed ingest lane has no column
header for reaches `extraction.write_dispatch_csv`'s STRUCT-01 guard and raises.
**Why it happens:** Easy to strip `row_id` first out of habit (it's the more familiar
call) and forget `strip_enrichment_extras` needs to run first, at the same boundary
(preingest.py:762-767 states the ordering explicitly).
**How to avoid:** Copy `enrich-before-ingest/SKILL.md:780-786`'s two-line sequence
verbatim: `strip_enrichment_extras` then `strip_row_id`.
**Warning signs:** A `send` path that calls `extraction.strip_row_id` without a preceding
`preingest.strip_enrichment_extras` call.

## Code Examples

### Old (defective) routing — SKILL.md step 8, prose only, no executable code today
```
# Source: operator-claude-plugin/skills/suggest-contacts/SKILL.md:440-442 (verbatim prose,
# NOT inside the fenced python block that follows it -- the held routing is currently
# described in words only, never actually coded in the block at SKILL.md:454-639)
"The held half is handled exactly as `enrich-before-ingest/SKILL.md`'s own held-row path:
`confidence.assess()`, then `held_queue.build_entry()`, then `run_manifest.save()`."
```
This is HELD-01's defect: `held_queue.save`'s own validation
(`held_queue.py:200-205`, `HeldQueueError` when `hold_code` is not in
`confidence.ALL_HOLD_CODES`) raises on any of the 5 partition reason codes, none of which
are in that set (confirmed: `confidence.ALL_HOLD_CODES` = `{"unparseable",
"unadjudicated_conflict", "unknown_tier", "no_match", "ambiguous_candidates",
"no_table_row_matched"}`, confidence.py:74-77 — zero overlap with `{"no_email",
"email_domain_freemail", "email_domain_mismatch", "company_domain_unknown",
"search_source_not_strong"}`).

### Reference sequence to reuse verbatim — enrich-before-ingest's held-row path (shape, not codes)
```python
# Source: operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:661-691
# (COPY THE SHAPE -- path resolution, load-before-merge, validate-before-write -- do NOT
# copy the confidence.assess()/held_queue call itself; that is the OTHER vocabulary.)
held_entries = held_queue.load()
verdict = confidence.assess(parsed)
if verdict.verdict == confidence.CONFIDENT:
    continue
entry = held_queue.build_entry(row, verdict.hold_code, verdict.reason, parsed)
held_entries[row_id] = entry
held_queue.save(run_id, held_entries)
```

### Reference sequence to reuse verbatim — the `send` action's whole dispatch block
```python
# Source: operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:770-889 (the full
# block -- CSV build, authorize_send/authorize_ungranted_send, pre-call ceiling check,
# armed_window, dispatch.dispatch, record_dispatch_outcome). Reuse this block UNCHANGED,
# scoped to the drained row(s); it already handles a one-row list correctly (`would_be =
# 1 + len(sendable_rows)`, SKILL.md:820).
sendable_rows, held = extraction.hold_emailless(merge_report.rows)
sendable_rows = preingest.strip_enrichment_extras(sendable_rows)
sendable_rows = extraction.strip_row_id(sendable_rows)
extraction.write_dispatch_csv(sendable_rows, out_path)
decision = (
    write_grant.authorize_send(grant, lane="contacts", record_ids=send_ids, record_domains=send_domains)
    if grant is not None else
    write_grant.authorize_ungranted_send(cfg, lane="contacts", object_type="contacts",
        record_ids=send_ids, record_domains=send_domains, allow_create=allow_create, label="this write")
)
# ... pre-call ceiling check, n8n_arming.armed_window, dispatch.dispatch, record_dispatch_outcome
```

### The company-id lookup a held entry needs (new helper, not yet written)
```python
# Composed from operator-claude-plugin/skills/suggest-contacts/SKILL.md:628-634's own
# range-slicing idiom (the terminal round_outcome classify uses the identical pattern):
def company_id_for_index(rounds, index):
    for entry in rounds:
        if entry["start"] <= index < entry["start"] + entry["count"]:
            return entry["company"].get("id")
    return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| SKILL.md step 8 prose says "route the held half through `held_queue`" | Route through the new sibling store instead | This phase | `HeldQueueError` no longer fires live on a suggestion-round decline (the Roma defect) |
| No frozenset names the 5 partition reason codes together | `suggest_contacts.PARTITION_REASON_CODES` (or similar) named and importable | This phase (new) | Gives HELD-02's disjointness test and the new store's own validation a single source of truth |

**Deprecated/outdated:** none — nothing in the existing codebase is being removed, only
the SKILL.md routing and a new sibling store are being added.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The new standalone skill should be its own skill directory rather than a mode of `review-triage`. | Architecture Patterns / recommendation | If wrong, the plan instead adds a mode branch to `review-triage/SKILL.md` step 1, and the `test_disclosure_audit.py`/`test_skill_sequence_coverage.py` consequences below shift from "new AUDIT row" to "review-triage's existing row must be re-verified". Recommendation is `[ASSUMED]` because D-69-08's discretion note leaves it open and this research did not consult the operator; the mechanism mismatch (server-side HubSpot queue vs local JSON file) argues strongly for a new skill but is not itself a locked decision. |
| A2 | `suggestion_declines.py` and `suggestion_declines.json` are reasonable placeholder names to plan against. | throughout | Purely cosmetic if wrong — CONTEXT.md explicitly says these names are placeholders, not decisions. |
| A3 | Editing SKILL.md step 8 to make the held routing **executable code** (not just prose) is the right level of rigor, matching `enrich-before-ingest`'s own held-row block. | Common Pitfalls / Code Examples | If the plan instead only rewrites the prose (leaving it non-executable, as it is today), `test_skill_sequence_coverage.py`'s ratchet is NOT triggered (today's held routing has zero module-call sequences in the fenced block) and no new COVERED/NOT_A_PIPELINE entry is needed. Recommendation to add real code is `[ASSUMED]` — it is a consistency argument (parity with enrich-before-ingest, and testability), not itself required by any of D-69-01..08. |

**If this table is empty:** N/A — see above.

## Open Questions

1. **Should the new store's `run_id` field be validated against anything, or accepted as
   an opaque string?**
   - What we know: `held_queue.json`/`run_manifest.json` validate `run_id` only as
     "whatever `run_state.new_run_id()` minted" — no closed vocabulary.
   - What's unclear: whether D-69-03's "each entry carries its own `run_id`" implies any
     cross-check against `run_state`.
   - Recommendation: treat it the same as every other store — an opaque string, no
     validation beyond type-checking, consistent with existing precedent.

2. **Retention of the accumulating store** (explicitly deferred in CONTEXT.md's "Deferred
   Ideas") — not this phase's concern, flagged here only so the plan does not
   accidentally scope it in.

## Environment Availability

Not applicable — no external dependency (tool, service, runtime, database) beyond what
every other plugin script already assumes (Python 3, filesystem access under
`durable_paths.durable_dir()`). No probe was run because nothing new is introduced.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already in use across `operator-claude-plugin/tests/`) |
| Config file | `operator-claude-plugin/tests/conftest.py` (existing; the `no_durable_writes` autouse fixture applies to any new store test the same way it applies to `test_held_queue.py`) |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines.py -q` (new file, name TBD by plan) |
| Full suite command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HELD-01 | Step 8's held routing no longer raises `HeldQueueError` on a partition reason code; it persists into the new store instead | unit + composition | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines.py -q` | ❌ Wave 0 (new file) |
| HELD-02 | `suggest_contacts.PARTITION_REASON_CODES` (or equivalent) and `confidence.ALL_HOLD_CODES` are disjoint, pinned by a test | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_held_queue.py::test_partition_reason_codes_are_disjoint_from_all_hold_codes -q` (new test, likely file) | ❌ Wave 0 |
| HELD-03 | A `send`/`defer`/`delete`/`export` round-trips correctly against a fixture store; `send` re-enters the existing write path unchanged | unit + composition (AST-checked per `test_skill_sequence_coverage.py`'s own idiom if the SKILL.md gains executable code) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` | ❌ Wave 0 for the store tests; `test_skill_sequence_coverage.py` already exists and will need a new COVERED/NOT_A_PIPELINE entry if code is added to the fenced block |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines.py operator-claude-plugin/tests/test_held_queue.py -q`
- **Per wave merge:** `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
- **Phase gate:** `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` AND
  `.venv/bin/python -m pytest -q --tb=short` (repo root, per `.planning/config.json`'s
  `test_command`) both green before `/gsd-verify-work`. Nothing armed, no live HubSpot
  writes — every test in this phase runs offline against fixtures, matching
  `conftest.py`'s `no_durable_writes` fixture discipline already enforced on
  `test_held_queue.py`.

### Wave 0 Gaps
- [ ] `operator-claude-plugin/tests/test_suggestion_declines.py` — the new store's own
      unit tests (path resolution, save/load round-trip, validate-before-write, forbidden-
      name refusal, composite-key encoding, `classify_read`), mirroring
      `test_held_queue.py`'s structure test-by-test.
- [ ] A disjointness test between `confidence.ALL_HOLD_CODES` and the new partition
      reason-code frozenset (HELD-02) — likely added to `test_held_queue.py` (it already
      imports `confidence`) or a new small file; either is fine, neither exists today.
- [ ] `test_disclosure_audit.py`'s `AUDIT` dict — needs a new key for the new skill
      directory once created (`test_audit_table_covers_every_skill_on_disk` fails
      otherwise; see "Q6" below for the exact mechanism).
- [ ] If the plan adds executable code to `suggest-contacts/SKILL.md`'s step-8 fenced
      block for the held routing: `test_skill_sequence_coverage.py`'s `COVERED` dict
      needs its `suggest-contacts` entry's tuple extended (or a new composition test
      registered), since today's tuple (test_skill_sequence_coverage.py:400-418) has no
      held-routing calls in it at all.
- [ ] A composition test for the new standalone skill's `send` action re-entering the
      write path, mirroring `test_suggest_contacts_composition.py`'s pattern of driving
      the SKILL.md-documented sequence against real (not mocked) functions with a fake
      transport.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface added; this is local file I/O only |
| V3 Session Management | no | N/A |
| V4 Access Control | no | Single-operator local file, same as every existing sibling store |
| V5 Input Validation | yes | `ROW_FIELD_ALLOWLIST`-equivalent (persist only allowlisted row fields, mirroring `held_queue.ROW_FIELD_ALLOWLIST = ("row_id",) + enrichment.MATCH_LOOKUP_KEYS`, held_queue.py:98) plus the closed reason-code vocabulary check at save time |
| V6 Cryptography | no | No crypto need; 0600 file permission via `durable_paths._atomic_write_0600` is the existing control, unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| An arming grant, secret, or API key smuggled into a persisted entry via an unexpected row column | Information Disclosure | Reimplement `_looks_forbidden`/`_first_forbidden`/`_FORBIDDEN_NAME_MARKERS` verbatim (Pitfall 1) — the SAME belt-and-braces check every sibling store already runs |
| A drained `send` bypassing the ceiling/grant machinery because it is "only one row" | Elevation of Privilege (a write landing without the authority checks a normal batch send gets) | Reuse `enrich-before-ingest/SKILL.md` steps 5+7's exact call sequence unchanged (Pitfall 4) — D-69-06's own explicit rule |
| A held row's email later resolving to a DIFFERENT, wrong person's mailbox after a `defer`→`send` cycle (the store accumulates across runs, so time has passed) | Tampering / Spoofing (of identity, not of the file) | Out of scope for this phase's own STRIDE surface — the email-domain-relatedness gate (`partition_for_dispatch`) already ran once to produce the hold; a `send` from the drain re-enters `extraction.validate()` and every other gate a normal send clears, so no NEW gate is skipped, but note this as an open question for the plan: does `send` re-run `partition_for_dispatch`'s own domain check, or does the operator's "supplied what was missing" implicitly satisfy it? D-69-06's text ("dispatch to HubSpot after the operator supplies what was missing") suggests the operator is expected to have fixed the underlying reason, and the standard `extraction.validate()`/`hold_emailless` gates re-apply naturally since `send` re-enters the normal path — so a still-bad email is still held, not sent, by the pre-existing machinery. |

## Sources

### Primary (HIGH confidence — read directly this session, path:line cited throughout)
- `operator-claude-plugin/scripts/held_queue.py` (full file)
- `operator-claude-plugin/scripts/run_manifest.py` (full file)
- `operator-claude-plugin/scripts/durable_paths.py` (full file)
- `operator-claude-plugin/scripts/confidence.py` (full file)
- `operator-claude-plugin/scripts/suggest_contacts.py` (targeted: `_name_key`,
  `_normalize_name`, `synthesise_rows`, `mint_row_ids`, `rejoin_enriched`,
  `round_artifact`, `partition_for_dispatch`, `_relation_reason`,
  `_RELATION_REASON_CODES`, `round_outcome`)
- `operator-claude-plugin/scripts/search_fallback.py` (targeted: `hold_weak_sources`,
  `SOURCE_TIER_HOLD_CODE`)
- `operator-claude-plugin/scripts/extraction.py` (targeted: `canonical_props`,
  `write_dispatch_csv`, `_load_mapping`)
- `operator-claude-plugin/scripts/preingest.py` (targeted: `build_rows_spec`,
  `strip_enrichment_extras`)
- `operator-claude-plugin/config/column_mapping.yaml` (full file)
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` (full file)
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (targeted: steps 5, 6, 7,
  lines 640-899)
- `operator-claude-plugin/skills/review-triage/SKILL.md` (full file)
- `operator-claude-plugin/tests/test_held_queue.py` (test name inventory)
- `operator-claude-plugin/tests/test_suggest_contacts.py` (targeted: partition-related
  test names)
- `operator-claude-plugin/tests/test_report_sufficiency.py` (targeted: `_has_while_loop`,
  `_POLL_LOOP_ALLOWED`)
- `operator-claude-plugin/tests/test_autonomy_switch_prose.py` (targeted: `TARGETS`,
  `test_no_icp_or_tier_substring_anywhere_in_the_file`)
- `operator-claude-plugin/tests/test_disclosure_audit.py` (targeted: `AUDIT`,
  `test_audit_table_covers_every_skill_on_disk`)
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` (targeted: `COVERED`,
  `NOT_A_PIPELINE`, `GRANDFATHERED_UNCOVERED`, the `suggest-contacts` tuple)
- `operator-claude-plugin/tests/test_mandatory_report_call_sites.py`,
  `test_autonomy_levels.py`, `test_implicit_approval_contract.py`,
  `test_interrupt_semantics.py` (targeted: whether they enumerate skills by a fixed dict
  vs a glob — confirmed fixed dict of the 4 existing batch skills, no automatic sweep of
  a new skill)
- `.planning/phases/69-held-rows-survive-the-round/69-CONTEXT.md` (full file)
- `.planning/REQUIREMENTS.md` (HELD section)
- `.planning/phases/64-*/64-CONTEXT.md` (targeted: D-64-08)
- `.planning/config.json` (full file — `nyquist_validation: true`,
  `security_enforcement: true`)

### Secondary (MEDIUM confidence)
- None — every claim above traces to a directly-read file this session.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency, every module cited was read directly this
  session.
- Architecture: HIGH — the store's shape and the send path's call sequence are both
  copied verbatim from existing, live, tested code, cited by path:line.
- Pitfalls: HIGH — all five are grounded in code actually read this session (raised
  exceptions, docstring-stated conventions), not speculation.
- Test-coverage consequences (Q6/Q8/Wave 0 gaps): HIGH for what exists today
  (confirmed by reading the test files directly); MEDIUM for what the plan will need to
  add, since the exact shape of the new code (prose-only vs executable) is a planning
  decision this research flags but does not make (see A3).

**Research date:** 2026-09-07
**Valid until:** 30 days (stable, internal-only codebase; no external API surface to
drift) — but re-verify if any of the cited files (`held_queue.py`, `suggest_contacts.py`,
`extraction.py`, the four scanned test files) change before planning executes, since
several claims are load-bearing on exact current line numbers and dict contents.
