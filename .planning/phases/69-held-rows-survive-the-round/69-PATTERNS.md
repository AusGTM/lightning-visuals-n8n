# Phase 69: Held rows survive the round - Pattern Map

**Mapped:** 2026-09-07
**Files analyzed:** 6 (new/modified)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/suggestion_declines.py` (new; name placeholder) | model/store | CRUD (file-I/O) | `operator-claude-plugin/scripts/held_queue.py` | exact (shape); diverges deliberately on run-scoping (D-69-03) and key (D-69-04) |
| `suggest_contacts.py` — new `PARTITION_REASON_CODES` frozenset | model/config | transform (validation vocabulary) | `confidence.py` — `ALL_HOLD_CODES` | exact (same "closed vocabulary constant" pattern, different domain) |
| `suggest_contacts.py` — new `company_id_for_index(rounds, index)` helper | utility | transform | `skills/suggest-contacts/SKILL.md:628-634` (`rounds[]` range-slicing idiom used by the terminal `round_outcome` classify) | role-match (prose today, not yet a function) |
| `skills/suggest-contacts/SKILL.md` step 8 (held half, rewritten) | route/controller (skill prose+code) | request-response | `skills/enrich-before-ingest/SKILL.md:661-691` (held-row path) | exact (shape to copy), NOT the vocabulary (`confidence.assess`/`held_queue` calls excluded) |
| new standalone drain skill `skills/<drain-skill-name>/SKILL.md` | controller (skill) | CRUD + request-response | `skills/review-triage/SKILL.md` (shape: fetch → operator picks → decide → confirm → report) | role-match (shape only; review-triage's HubSpot-backend `review_queue.fetch_queue` mechanism is NOT the analog — swap for local JSON store reads) |
| `send` action's dispatch call sequence (inside new drain skill) | controller → service (write path) | request-response (external write) | `skills/enrich-before-ingest/SKILL.md:770-889` (full dispatch block) | exact — reuse verbatim, unchanged |
| `operator-claude-plugin/tests/test_suggestion_declines.py` (new) | test | CRUD | `operator-claude-plugin/tests/test_held_queue.py` | exact (mirror test-by-test) |
| disjointness test (HELD-02) | test | transform | likely added to `test_held_queue.py` (already imports `confidence`) | exact |
| `test_disclosure_audit.py` AUDIT dict | test/config | transform | existing `AUDIT` dict, new key required for the new skill dir | exact |
| `test_skill_sequence_coverage.py` COVERED dict | test/config | transform | existing `suggest-contacts` tuple, extend if step 8 gains executable code (A3) | exact (conditional) |

## Pattern Assignments

### `operator-claude-plugin/scripts/suggestion_declines.py` (new store)

**Analog:** `operator-claude-plugin/scripts/held_queue.py` (full file read this session)

**Imports pattern** (held_queue.py, top of file):
```python
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import confidence
import durable_paths
import enrichment
```
For the new module: drop the `confidence` import entirely (D-69-02 — the two
vocabularies must stay disjoint by construction). Import `durable_paths` and
`enrichment` (for `MATCH_LOOKUP_KEYS`, the allowlist basis) only. Import
`suggest_contacts` for `_name_key` if that composition doesn't create a circular
import (`suggest_contacts.py` does not import `held_queue.py` or vice versa today, so
check before assuming — if circular, the plan should have `suggest_contacts.py` call
INTO this new module rather than the reverse).

**Path resolution** (held_queue.py:150-153, copy verbatim pattern):
```python
def queue_path() -> Path:
    """Resolved fresh on every call — the same durable directory
    `run_manifest.manifest_path()` and `artifact_store.state_path()` both resolve into,
    never a second resolution rule."""
    return durable_paths.resolve_state_path().parent / QUEUE_FILENAME
```

**Forbidden-name refusal — REIMPLEMENT, do not import** (held_queue.py:112-135):
```python
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

def _looks_forbidden(value) -> bool:
    lowered = str(value).lower()
    return any(marker in lowered for marker in _FORBIDDEN_NAME_MARKERS)

def _first_forbidden(value):
    if isinstance(value, dict):
        for key, sub in value.items():
            if _looks_forbidden(key):
                return key
            found = _first_forbidden(sub)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_forbidden(item)
            if found is not None:
                return found
    elif isinstance(value, str) and _looks_forbidden(value):
        return value
    return None
```
The module docstring at held_queue.py:68-70 states explicitly this is
reimplemented, not imported, from `run_manifest.py`'s own copy — "so a future change
to one cannot silently weaken another." The new module's copy is a third instance of
the same discipline.

**Validate-before-write, whole-document overwrite** (held_queue.py `save()`,
lines ~186-224 — quoted above in full in the research). The load-bearing shape:
```python
def save(run_id, entries, path=None) -> None:
    for row_id, entry in entries.items():
        if _looks_forbidden(row_id):
            raise HeldQueueError(...)   # nothing written yet
        hold_code = entry.get("hold_code") if isinstance(entry, dict) else None
        if hold_code not in confidence.ALL_HOLD_CODES:   # <-- swap for
                                                          #     PARTITION_REASON_CODES
            raise HeldQueueError(...)
        offender = _first_forbidden(entry.get("row"))
        ...
        if offender is not None:
            raise HeldQueueError(...)

    target = Path(path) if path is not None else queue_path()
    document = {...}
    durable_paths._atomic_write_0600(target, json.dumps(document))
```
For the new store: the loop key changes from a bare `row_id` string to the D-69-02
composite string key (`f"{company_id}::{first}|{last}"`, per RESEARCH.md Pattern 2);
the `hold_code not in confidence.ALL_HOLD_CODES` check becomes
`reason_code not in suggest_contacts.PARTITION_REASON_CODES`; D-69-03 means `run_id`
moves from the document-level field into each entry, so the loop must also check each
entry carries its own `run_id` string, and the document itself has no single
`RUN_ID_FIELD` to stamp — `save()` here takes only `entries`, no `run_id` positional
argument (`save(entries, path=None)`, RESEARCH.md's own skeleton).

**Atomic write primitive** (`durable_paths.py:57-72`):
```python
def _atomic_write_0600(path: Path, content: str) -> None:
    """... tempfile in the target's OWN directory, chmod 0600, fsync, os.replace ..."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    ...
```
Call this exactly the way `held_queue.save()` does — never build a custom
open/rename dance (RESEARCH.md "Don't Hand-Roll" table).

**`classify_read`-style reader** (held_queue.py:260-279 — quoted in full above).
Copy the shape (`ABSENT`/`PARSEABLE`/`ANOMALOUS` states, probe-before-degrade). Drop
`ANOTHER_RUN` — D-69-03 makes the document inherently multi-run, so there is no
"wrong run" to detect at the document level (RESEARCH.md Pattern 1's own note); an
individual entry's own `run_id` is still informative in the batch report but is not a
`classify_read` state.

**Composite key encoding** (D-69-04, RESEARCH.md Pattern 2 — new, no existing
precedent to copy verbatim, but the discipline it must follow mirrors the allowlist
discipline above):
```python
def _entry_key(company_id, name_key) -> str:
    first, last = name_key
    return f"{company_id}::{first}|{last}"
```

**Row allowlist** (held_queue.py:98):
```python
ROW_FIELD_ALLOWLIST = ("row_id",) + enrichment.MATCH_LOOKUP_KEYS
```
Reuse verbatim for the new store's own row snapshot — same reasoning (RESEARCH.md
"Don't Hand-Roll" table: "persisting only allowlisted row fields").

---

### `suggest_contacts.py` — `PARTITION_REASON_CODES`

**Analog:** `confidence.py` `ALL_HOLD_CODES` (the sibling closed-vocabulary constant
this new one must stay disjoint from, per HELD-02).

```python
# confidence.py:74-77 (verified this session)
ALL_HOLD_CODES = {
    "unparseable", "unadjudicated_conflict", "unknown_tier", "no_match",
    "ambiguous_candidates", "no_table_row_matched",
}
```

New constant, same shape, disjoint contents (RESEARCH.md "Don't Hand-Roll" table
gives the exact 5-member set, sourced from `suggest_contacts.py:870`,
`suggest_contacts.py:678-682` `_RELATION_REASON_CODES.values()`, and
`search_fallback.SOURCE_TIER_HOLD_CODE` at `search_fallback.py:64`):
```python
PARTITION_REASON_CODES = frozenset({
    "no_email",
    "email_domain_freemail",
    "email_domain_mismatch",
    "company_domain_unknown",
    "search_source_not_strong",
})
```

---

### `skills/suggest-contacts/SKILL.md` step 8 (held routing, rewritten)

**Old (defective) routing** — SKILL.md:440-442, prose only, never executable:
```
"The held half is handled exactly as `enrich-before-ingest/SKILL.md`'s own held-row
path: `confidence.assess()`, then `held_queue.build_entry()`, then
`run_manifest.save()`."
```
This is the defect HELD-01 fixes — `held_queue.save`'s own `hold_code not in
confidence.ALL_HOLD_CODES` check raises `HeldQueueError` on all 5 partition codes,
zero overlap.

**Shape to copy (not the vocabulary)** — `enrich-before-ingest/SKILL.md:661-691`:
```python
held_entries = held_queue.load()
verdict = confidence.assess(parsed)
if verdict.verdict == confidence.CONFIDENT:
    continue
entry = held_queue.build_entry(row, verdict.hold_code, verdict.reason, parsed)
held_entries[row_id] = entry
held_queue.save(run_id, held_entries)
```
New version swaps `confidence.assess`/`held_queue.*` for
`suggestion_declines.load()` / `suggestion_declines.build_entry(row, reason_code,
reason, run_id)` / `suggestion_declines.save(entries)`, keyed by
`(company_id, name_key)` via the new `company_id_for_index` helper (below), never
`row_id`.

**Company-id lookup helper** (new, composed from the existing round-slicing idiom at
`skills/suggest-contacts/SKILL.md:628-634`):
```python
def company_id_for_index(rounds, index):
    for entry in rounds:
        if entry["start"] <= index < entry["start"] + entry["count"]:
            return entry["company"].get("id")
    return None
```

---

### New standalone drain skill

**Analog (shape only):** `skills/review-triage/SKILL.md` — fetch → operator picks →
decide → confirm → report. Its mechanism (`review_queue.fetch_queue`, a HubSpot-backend
queue) is explicitly NOT the analog — swap for `suggestion_declines.load()` reading the
local JSON file.

**`send` action — reuse verbatim, unchanged** —
`skills/enrich-before-ingest/SKILL.md:770-889` (full dispatch block, already the
research's own "Reference sequence to reuse verbatim"):
```python
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
Order matters (Pitfall 5): `preingest.strip_enrichment_extras` MUST run before
`extraction.strip_row_id` (preingest.py:762-767 states the ordering explicitly).

**`export` action — do NOT reuse `extraction.write_dispatch_csv`** (it raises
`ExtractionError("emailless_row_cannot_ingest", ...)` on any row without a usable
email, `extraction.py:924-930` — exactly what most held rows are). Use stdlib
`csv.DictWriter` over `extraction.canonical_props()` headers instead, no email guard.

**`defer`/`delete`** — no analog needed; `defer` is a no-op (entry untouched),
`delete` is `del entries[key]; suggestion_declines.save(entries)` — no tombstone
(D-69-07).

---

## Shared Patterns

### Durable, atomic, 0600 state file
**Source:** `operator-claude-plugin/scripts/durable_paths.py` — `resolve_state_path()`,
`_atomic_write_0600()`
**Apply to:** `suggestion_declines.py`'s `save()` — the ONE resolution rule, never a
second path-derivation scheme.

### Validate-before-write
**Source:** `held_queue.py::save()` — every entry checked (forbidden-name,
vocabulary membership) BEFORE `_atomic_write_0600` is called, so a raising save leaves
the previous file untouched.
**Apply to:** `suggestion_declines.py::save()`.

### Forbidden-name refusal (reimplemented, never imported)
**Source:** `held_queue.py:112-135` (`_FORBIDDEN_NAME_MARKERS`, `_looks_forbidden`,
`_first_forbidden`), itself a reimplementation of `run_manifest.py`'s own copy —
module docstring states the discipline explicitly (held_queue.py:68-70).
**Apply to:** `suggestion_declines.py` — copy verbatim as a third instance, do not
import from `held_queue`.

### Closed-vocabulary validation constant
**Source:** `confidence.py::ALL_HOLD_CODES`
**Apply to:** `suggest_contacts.py::PARTITION_REASON_CODES` — the mirror-image
constant for the OTHER vocabulary (D-69-02's disjointness is enforced by these two
frozensets never sharing a member, pinned by a new test).

### Skill disclosure audit table (registration requirement)
**Source:** `operator-claude-plugin/tests/test_disclosure_audit.py` — `AUDIT` dict
(lines ~72+), a `Skill: Verdict: Reason` row per skill directory on disk, asserted
complete by `test_audit_table_covers_every_skill_on_disk` (line ~137-139).
**Apply to:** the new standalone drain skill — it MUST get a new row in `AUDIT` or
that test fails. Example row shape (from the existing table):
```
| review-triage | decision-point-preserved (verified non-change) | Unmodified by this phase... |
```
The new skill's row should state its own verdict (likely
`decision-point-preserved` if it keeps an explicit per-entry send/defer/delete/export
confirmation, matching the `send` action's write-path confirmation discipline).

---

## No Analog Found

None — every file this phase touches has a directly-applicable existing analog,
confirmed by RESEARCH.md's own exhaustive precedent search (`held_queue.py`,
`run_manifest.py`, `durable_paths.py`, `enrich-before-ingest/SKILL.md`,
`review-triage/SKILL.md`, `confidence.py`, `test_held_queue.py`,
`test_disclosure_audit.py`).

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/skills/*/SKILL.md`, `operator-claude-plugin/tests/`
**Files scanned this session:** `held_queue.py` (full), `durable_paths.py` (targeted:
`_atomic_write_0600`), `test_disclosure_audit.py` (targeted: `AUDIT`,
docstring), `test_skill_sequence_coverage.py` (targeted: `suggest-contacts` entry) —
plus everything RESEARCH.md already read directly this session (see its own Sources
list; not re-read here to avoid duplicate ranges).
**Pattern extraction date:** 2026-09-07
