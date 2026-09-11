# Phase 71: A held new person lands in HubSpot with one reply - Pattern Map

**Mapped:** 2026-09-12
**Files analyzed:** 9 (all modification, zero new files)
**Analogs found:** 9 / 9 — this phase has an in-repo sibling for every touched seam;
RESEARCH.md's Seam Map already carries file:line for each, this file adds the concrete
excerpts to copy from.

## File Classification

| File to modify | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/held_queue.py` | model / durable-store | CRUD (accumulate-across-runs) | `operator-claude-plugin/scripts/suggestion_declines.py` | exact — sibling store, same author discipline |
| `operator-claude-plugin/scripts/run_manifest.py` (`rows_to_resume`) | service (pure function) | transform (resume decision) | itself — already implements the `CONFIDENCE_HELD` branch this phase edits | exact — same function, add a call to the shared stable-key derivation |
| `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (steps 2, 5, 6) | controller (skill prose) | request-response (render + persist) | `operator-claude-plugin/skills/review-triage/SKILL.md` steps 2b/2c/4a-4c | role-match — sibling skill, same read/bucket/facet idiom |
| `operator-claude-plugin/skills/review-triage/SKILL.md` (steps 2b, 2c, 4a-4c) | controller (skill prose) | request-response (render + settle) | `enrich-before-ingest/SKILL.md` step 6/9 | role-match — reverse direction of the pair above |
| `operator-claude-plugin/scripts/preingest.py` (new: `confirmed_company_domains` collector) | service | transform | `preingest.index_company_dependencies` / `assign_same_run_company_ids` | role-match — same module, same "collect a set from a bucket" shape |
| `operator-claude-plugin/tests/test_held_queue.py` | test | unit | itself (existing file, extend) | exact |
| `operator-claude-plugin/tests/test_held_queue_facets.py` | test | unit + fixture | itself (existing file, extend) | exact |
| `operator-claude-plugin/tests/test_review_triage_facets.py` | test | composition | itself (existing file, extend) | exact |
| `operator-claude-plugin/tests/test_run_manifest.py` | test | unit | itself (existing file, extend — needs a NEW cross-run stable-key test, does not exist today) | exact |

No "no analog found" files — every touched file already has a live sibling or is itself
the analog (research-verified this session, no speculative matches).

---

## Pattern Assignments

### `operator-claude-plugin/scripts/held_queue.py`

**Analog:** `operator-claude-plugin/scripts/suggestion_declines.py` — the ALREADY-SHIPPED
sibling store that solves the exact three problems this phase gives `held_queue.py`:
accumulate-across-runs (D-69-03), a stable composite key instead of a positional one
(D-69-04 precedent), and the forbidden-marker refusal on that key.

**Store-shape docstring pattern to copy (module header)** — `suggestion_declines.py:1-38`:
```python
"""operator-claude-plugin/scripts/suggestion_declines.py

The plugin's next persisted artifact. A SIBLING of `held_queue.json`, never a section
inside it (D-69-01): it follows every convention `held_queue.py` established --
resolved under `durable_paths.resolve_state_path().parent`, written with
`durable_paths._atomic_write_0600`, whole-document overwrite, validate-every-entry
before anything is written, the secret/grant-name refusal (`_looks_forbidden`), and a
`classify_read`-style reader.
...
**The document ACCUMULATES; each entry carries its OWN `run_id` (D-69-03).**
Deliberately diverges from `held_queue`'s single-`run_id` document, where a new run
overwrites and `classify_read` reports `another_run` as a rejection. A deferred entry
has to survive a run boundary, so run scope moves from the document to the entry --
this document carries NO run id and NO timestamp of its own. A new run's declines
MERGE into the document; they never overwrite it.
...
**The forbidden-name refusal is REIMPLEMENTED, not imported**, per `held_queue.py`'s
own stated discipline (held_queue.py:68-70) -- a future change to one cannot silently
weaken another.
"""
```
This is the exact shape `held_queue.py`'s own module docstring will need updating to
once it moves onto D-69-03's already-established accumulate contract — copy the
"ACCUMULATES / each entry carries its own run_id" framing verbatim, adjusted for
`held_queue`'s pre-existing `run_id` document field (which this phase does NOT remove —
`record_verb`'s doc already explains it keeps the LAST-touched run's id, see below).

**Stable-key derivation pattern to copy (NOT the exact formula — the shape)** —
`suggestion_declines.py:141-155`:
```python
def entry_key(company_id, row):
    """The composite string key for `entries` (D-69-04), or `None` when `company_id`
    is `None`/empty or `suggest_contacts.name_key(row)` is `None` -- an incomplete
    identity is never a key. Uses `str(company_id)`.
    """
    if not company_id:
        return None
    name = suggest_contacts.name_key(row)
    if name is None:
        return None
    first, last = name
    return f"{company_id}{KEY_SEPARATOR}{first}{NAME_SEPARATOR}{last}"
```
Per RESEARCH.md §5, **do not copy this formula directly** — it keys on a resolved
`company_id`, which a `needs_company` held row does not have. Write a new
`held_queue.stable_key(row)` (Pitfall 2's naming) that branches on
`config/column_mapping.yaml`'s `required_identity.any_of` order (email cleaned/case-
folded first, else `suggest_contacts.name_key(row)` joined with `company`, else
`linkedin_url`), called from BOTH the write site (`enrich-before-ingest` step 5) and
the read site (`run_manifest.rows_to_resume`) — never re-derived independently in two
places (Pitfall 2's exact warning).

**Validate-before-write / accumulate `save()` pattern to copy** —
`suggestion_declines.py:216-245` (the CR-01 anomalous-refusal guard is new territory
`held_queue.save` does not yet have and does not need for this phase — D-71-05's wipe
makes it moot; do not add it unless a future phase asks):
```python
def save(entries, path=None) -> None:
    """...mirrors `held_queue.save`'s contract: the caller assembles the full
    `{key: entry}` map (typically `load()`'s own return, with this run's new/updated
    entries merged in) and this function overwrites the file atomically. Validates
    every entry BEFORE anything is written, so a save that raises leaves the previous
    document untouched.
    """
    target = Path(path) if path is not None else queue_path()
    for key, entry in entries.items():
        refusal = first_refusal(key, entry)
        if refusal is not None:
            raise SuggestionDeclineError(refusal)
    document = {ENTRIES_FIELD: dict(entries)}
    durable_paths._atomic_write_0600(
        target, json.dumps(document, sort_keys=True, ensure_ascii=False)
    )
```
`held_queue.save` (`held_queue.py:446-...`) already has this exact shape — validate
every entry first, then one atomic write. No structural change needed there; only the
per-entry KEY check changes (see below).

**Forbidden-marker key-vs-value narrowing pattern to copy** — `held_queue.py:226-...`
already has `_first_forbidden_key` (added by `260911-w6o` to narrow the scan on
`row`'s own fields). The SAME narrowing must now apply to the top-level entries-map
key in `held_queue.save`, which today does a raw whole-value scan:
```python
# held_queue.py:453-459 (CURRENT — must change)
for row_id, entry in entries.items():
    if _looks_forbidden(row_id):
        raise HeldQueueError(
            f"refusing to persist a held-queue entry keyed {row_id!r} — its name "
            "suggests an arming grant, a live-write permission, a secret, or an "
            "API key. Nothing was written."
        )
```
Copy the key-vs-value split `_first_forbidden_key` already gives `row`'s fields
(`held_queue.py:226-`) rather than inventing new logic — the fold's job is to make the
entries-map key subject to the SAME narrower rule already proven for `row` fields, per
RESEARCH.md Seam Map §6 and Pitfall 1. Do this for BOTH `held_queue.py` and
`suggestion_declines.py` (Open Question 4's minimum scope) since the same
`entry_key`/`save()` pairing in `suggestion_declines.py` has the identical live defect.

**`entry_verb` / `is_settled` / `open_entries` — unchanged, key-agnostic already** —
`held_queue.py:355-378` (excerpted above in RESEARCH.md) iterate over whatever
`entries` dict they're handed; no edit needed here beyond what the rekey implies at
the CALL sites.

---

### `operator-claude-plugin/scripts/run_manifest.py` (`rows_to_resume`)

**Analog:** itself — the `CONFIDENCE_HELD` branch already exists and already reads
`held_entries.get(row_id)`. The only change is WHAT is looked up with.

**Current lookup to change** — `run_manifest.py:438-461` (excerpted above):
```python
if verdict == CONFIDENCE_HELD:
    entry = held_entries.get(row_id)   # <-- row_id is row.get("row_id"), freshly
                                        #     minted THIS run — must become the
                                        #     shared stable-key derivation instead
    if held_queue.is_settled(entry):
        skipped.append({"row_id": row_id, "verdict": verdict})
        continue
    if held_queue.entry_verb(entry) == held_queue.VERB_RETRY:
        to_resume.append(row)
        continue
    current = current_outcomes.get(row_id)
    ...
```
Change `entry = held_entries.get(row_id)` to `entry = held_entries.get(held_queue.stable_key(row))`
— call the SAME function the write side calls (Pitfall 2). The reported `row_id` in
`skipped`/`still_held`/`to_resume` dicts stays `row.get("row_id")` (source position,
D-69-04) — only the DICT LOOKUP key changes.

---

### `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (steps 2, 5, 6)

**Analog:** `operator-claude-plugin/skills/review-triage/SKILL.md` steps 2b/2c — the
sibling skill already reads `held_queue.load()`, buckets by `classify_facet`, and
documents exactly the "grows during this sitting" pattern this phase's stamp
generalizes to "already known at persist time."

**Current (to change) — the hardcoded empty set** — `SKILL.md:869`:
```
known_company_domains = set()  # nothing confirmed yet this run -- w6p's own safe
                                # default; classify_facet reads needs_company until
                                # a domain is actually resolved
```
Becomes a comprehension folding in the per-entry stamp written at step 5's persist
time (D-71-01), e.g.:
```
known_company_domains = {
    entry["company_domain_hint"]
    for entry in held_entries.values()
    if entry.get("company_domain_hint")
}
```
(exact field name is Claude's Discretion per CONTEXT.md — pick one, document it once).

**Persist-site pattern to copy (where the stamp is actually written)** —
`SKILL.md:764-770` (the ONLY live production writer of `held_queue.build_entry`):
```
entry = held_queue.build_entry(merged_by_id.get(row_id, row), verdict.hold_code, verdict.reason, parsed)
held_entries[row_id] = entry
held_queue.save(run_id, held_entries)
```
The stamp must be added to `build_entry`'s output (or attached to `entry` right after
the call, before `held_entries[...] = entry`) at THIS call site — step 6 only renders
what step 5 already wrote (RESEARCH.md §4's ordering correction).

**Sibling render pattern to copy (how review-triage already renders a facet)** —
`SKILL.md` (review-triage) steps 2b/2c per RESEARCH.md §3, same idiom
`enrich-before-ingest` step 6 already partially implements — copy the "grows during
this sitting" comment style for whichever prose documents the stamp's provenance
(`step2_confirmed` vs `same_run_create`, Claude's Discretion).

---

### `operator-claude-plugin/skills/review-triage/SKILL.md` (steps 2b, 2c, 4a-4c)

**Analog:** `enrich-before-ingest/SKILL.md` step 6/9 (the reverse pairing above) plus
its OWN existing step 4c, which is the ONLY live `record_verb` call site to copy the
settlement idiom from — `SKILL.md:365-370`:
```
for row_id, email in created_by_row_id.items():
    if email and email in landed:
        held_queue.record_verb(row_id, held_queue.VERB_CREATE, run_id)
```
Once `row_id` becomes a stable key end to end, `created_by_row_id` must be keyed the
same way — same `held_queue.stable_key(row)` call, not a re-derivation (Pitfall 2).

**Current (to change) — same hardcoded empty set as the sibling skill** —
`SKILL.md:98` (review-triage):
```
known_company_domains = set()  # grows during this sitting -- see 2c below
```
Same fix shape as `enrich-before-ingest` above: fold in the stamp read from
`held_queue.load()`'s entries FIRST, then still allow 2c's existing in-conversation
ADD-a-domain path to grow the set further (CONTEXT.md D-71-03 — unchanged).

---

### `operator-claude-plugin/scripts/preingest.py` (new: confirmed-domains collector)

**Analog:** `preingest.index_company_dependencies` (`preingest.py:1259-1276`) — same
module, same "fold a bucket's own responses into a lookup set" shape, for the
same-run-company-create half of the stamp (if the plan wires it — RESEARCH.md §4
flags this as a larger lift, Claude's Discretion whether to scope it in).

For the LIGHTER, zero-new-lookup third source RESEARCH.md recommends (Open Question
2, option c): collect a set from `preingest.classify_matches`'s own `auto_matched`/
approved-`proposed` buckets at step 2 — same shape as the `auto_matched` dict literal
already produced (`preingest.py:519-521`):
```python
{"row_id": row_id, "row": row, "hs_object_id": item.get("hs_object_id")}
```
A `confirmed_company_domains` collector reads `row["email"]` off each `auto_matched`
item (and each operator-approved `proposed` candidate) the same way `classify_facet`
itself parses email domains — via `enrichment._clean_domain`, never re-implemented.

---

## Shared Patterns

### The forbidden-name marker matcher (nine-copy discipline, D-69-01)

**Source:** `operator-claude-plugin/scripts/held_queue.py:141-166` (`_FORBIDDEN_NAME_MARKERS`,
`_tokenised`, whole-token matching) and its already-narrowed sibling
`_first_forbidden_key` (added by `260911-w6o`).

**Apply to:** `held_queue.py`'s top-level entries-map key (this phase's own defect,
mandatory) and `suggestion_declines.py`'s `entry_key`/`first_refusal` (already-live
defect, same todo, same discipline — RESEARCH.md Open Question 4 recommends this
minimum scope). Each module REIMPLEMENTS its own copy — do not import a shared
function; pin behavioral parity instead via
`operator-claude-plugin/tests/test_forbidden_marker_parity.py`.

```python
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)
_CAMEL_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_TOKEN = re.compile(r"[^a-z0-9]+")
_INFLECTION_SUFFIXES = ("", "s", "ed", "ing")

def _tokenised(value) -> str:
    broken = _CAMEL_BREAK.sub(" ", str(value)).lower()
    tokens = [token for token in _NON_TOKEN.split(broken) if token]
    return f" {' '.join(tokens)} "
```

### Stable-key normalization primitive

**Source:** `operator-claude-plugin/scripts/suggest_contacts.py:161-173` (`name_key`,
PUBLIC cross-module contract since Phase 69/D-69-04):
```python
def name_key(person):
    """`(firstname, lastname)`, case-folded and whitespace-collapsed, or `None` when
    either half is missing..."""
    first = _normalize_name(person.get("firstname"))
    last = _normalize_name(person.get("lastname"))
    if not first or not last:
        return None
    return (first, last)
```
**Apply to:** the new `held_queue.stable_key(row)` (or wherever it lives) — call this
function for the name-branch of the identity-group derivation, never re-normalize
names independently.

### Identity-group priority order

**Source:** `config/column_mapping.yaml:60-63`:
```yaml
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
    - [linkedin_url]
```
**Apply to:** the D-71-04 stable-key branch order (email first, then
firstname+lastname+company, then linkedin_url) — mirrored in `n8n/code/columnMap.js:79-86`,
pinned by `tests/n8n/columnMapIdentityParity.test.mjs`. Do not invent a different
priority order.

### Domain cleaning

**Source:** `operator-claude-plugin/scripts/enrichment.py` (`_clean_domain`,
`FREEMAIL_DOMAINS`) — already imported and used by `held_queue.classify_facet` itself.
**Apply to:** any new domain-set collector (step 2's `confirmed_company_domains`,
the `auto_matched`-bucket collector) — never re-implement domain cleaning.

---

## No Analog Found

None — every file this phase touches has a direct sibling analog or is itself the
analog to extend (confirmed by RESEARCH.md's exhaustive Seam Map).

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/skills/`,
`operator-claude-plugin/tests/`, `config/column_mapping.yaml`, `n8n/code/columnMap.js`
**Files scanned:** 9 target files + 5 analog source files (all read this session)
**Pattern extraction date:** 2026-09-12

## PATTERN MAPPING COMPLETE

**Phase:** 71 - a-held-new-person-lands-in-hubspot-with-one-reply
**Files classified:** 9
**Analogs found:** 9 / 9

### Coverage
- Files with exact analog (same module, extend in place, or direct sibling store): 7
- Files with role-match analog (sibling skill, reverse pairing): 2
- Files with no analog: 0

### Key Patterns Identified
- `held_queue.py`'s rekey to a stable, accumulate-safe key is a near-verbatim port of
  `suggestion_declines.py`'s already-shipped store shape (D-69-01/03 discipline) —
  copy the docstring framing and the validate-then-atomic-write `save()` shape, but
  NOT `entry_key`'s exact composite formula (it keys on `company_id`, which a
  `needs_company` row lacks).
- The forbidden-name-marker fold must apply the SAME key-vs-value narrowing
  `260911-w6o` already gave `row`'s own fields (`_first_forbidden_key`) to the
  top-level entries-map key in both `held_queue.py` and `suggestion_declines.py` —
  reimplemented per-module, pinned by `test_forbidden_marker_parity.py`, never
  imported cross-module.
- The stable-key derivation must be ONE function called from both the write site
  (`enrich-before-ingest` step 5) and the read site (`run_manifest.rows_to_resume`) —
  built from `suggest_contacts.name_key` (name branch) and `config/column_mapping.yaml`'s
  `required_identity.any_of` priority order (email, then name+company, then linkedin_url).

### File Created
`/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files.
