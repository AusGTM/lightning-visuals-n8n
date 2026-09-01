# Phase 62: Suggest the contacts nobody named - Pattern Map

**Mapped:** 2026-09-02
**Files analyzed:** 8 (new/modified, derived from CONTEXT.md D-62-01..18 + phase_shape)
**Analogs found:** 8 / 8

**Scope reminder for the planner:** per `<phase_shape>`, this phase is an **operator-attended
plugin skill**, not a backend/n8n change (beyond one narrow provenance-parameter fix). Every
analog below is picked from `operator-claude-plugin/scripts/` and `operator-claude-plugin/skills/`
except the two n8n-side provenance files, which are the one deliberately narrow exception
(D-62-17).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` (new) | skill (operator flow) | request-response, multi-step conversational | `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` | exact — same shape: discover → confirm → grant → dispatch → report |
| `operator-claude-plugin/scripts/role_vocabulary.py` (new) | utility (offline batch script) | batch, read-only HubSpot inventory + one cached Haiku call | `scripts/inventory_org_type_values.py` | exact — same read-only paged-inventory idiom; classification step is genuinely new (Haiku, no in-repo precedent) |
| `operator-claude-plugin/scripts/role_classify.py` (new) | utility (pure classifier) | transform (one title string → one family or none) | `operator-claude-plugin/scripts/company_domain.py` (`needs_research`/`_validate_decision` shape) + `src/taxonomy.py`/`n8n/code/taxonomy.generated.js` (one-vocabulary-two-access-modes pattern) | role-match — no direct precedent; compose from these two |
| `operator-claude-plugin/scripts/suggest_contacts.py` (new) — ladder-driven discovery→row synthesis, zero-contacts check, dedupe pre-filter | service (orchestration, pure where possible) | CRUD-adjacent: reads company batch, calls ladder + waterfall, emits synthesised rows | `operator-claude-plugin/scripts/company_domain.py` (propose/confirm/decide two-pass discipline) + `operator-claude-plugin/scripts/url_fallback.py` (the ladder itself, called not modified) | exact for the propose/decide discipline; the ladder is consumed, not re-implemented |
| `operator-claude-plugin/scripts/write_grant.py` (modified — `envelope()`, `plan_grant()`) | service (cost disclosure / grant) | request-response, pure arithmetic over counts | itself — extend in place, do not fork | exact — D-62-11 says fold the suggestion allowance into the SAME figures, not a second lane |
| `n8n/code/mergeContacts.js` (unmodified — already supports `opts.source`) | model/merge | transform | itself | exact — no change needed, confirms the hook exists |
| `scripts/build_cloud_workflows.py` § `MERGE_CONTACTS` constant (modified, ~line 293) | config/wiring (n8n Code-node body composition) | transform (build-time string composition) | itself | exact — one-line change: read `source` from the row instead of the literal `"csv"` |
| `operator-claude-plugin/scripts/extraction.py` (unmodified — consumed as a library) | controller (validation entry point) | CRUD (validate → accept/reject) | itself | exact — `validate()` already takes an in-memory dict; no change required (Research Priority 3) |

## Pattern Assignments

### `operator-claude-plugin/skills/suggest-contacts/SKILL.md` (new skill)

**Analog:** `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (full file read, 987
lines) — the closest existing composition of "discover/resolve → price once → grant once → dispatch
→ report", and explicitly the skill CONTEXT.md's canonical refs point at for both the grant shape
and the "refuse rather than substitute" precedent.

**Frontmatter pattern** (copy shape, not text):
```yaml
---
name: enrich-before-ingest
description: Load a contact spreadsheet, match it against HubSpot, enrich anything HubSpot does
  not already have, and only then create it... Use when the operator asks to... — or invoke it
  directly as /operator-claude-plugin:enrich-before-ingest.
---
```
The new skill's description must name its trigger explicitly (auto-offered after batch completion
per D-62-15) since this skill's invocation is different in kind from every existing skill — it is
raised by the assistant, not requested by the operator. Say that difference in the description
itself, the same way `contact-upload`/`enrich-records` name their own trigger phrases.

**One-grant-covers-everything pattern to copy verbatim** (step 1, lines 26-102): the "state the
target and how many times this flow will ask" framing, `config_gate.py`'s `can_send` gate, and the
explicit naming of every lane a grant spans — copy this shape for D-62-11's "one session grant
covers this whole session including suggestions": name the allowance in the SAME sentence that
names the enrichment/contacts/review lanes, never a separate ask.

**Propose-never-auto-create pattern to copy** (steps 2-3, lines 104-253, and the domain-confirm
table pattern from `company_domain.py`): render one table, decisions are per-item with a fixed
closed vocabulary (`approve`/`deny`/`pick <sub-label>`), a bare blanket approval is refused, one
malformed line refuses the whole table before anything applies. D-62-10 ("no per-person and no
per-company confirmation... satisfied by held/needs_review gates, not a second confirmation step")
means this specific per-row confirm/deny table pattern is **NOT** what D-62-10 wants for the
suggestion round itself — copy it only for the upstream company-website-style single up-front
disclosure (the round-level "here is what will be spent, yes/no"), not for a second per-person gate
downstream of it. The precedent to copy for D-62-10's actual shape is closer to `company_domain.py`'s
`decided_name_only`/`undecided` fallthrough: an item nobody explicitly confirmed still resolves
through the SAME downstream mechanism (here: `needs_review`), never blocked pending a second
decision.

**Two-phase ask pattern to copy** (step 5, lines 277-343): "if a grant covering this lane is open,
ask for nothing here... with no grant open, disarmed is the default... an affirmative answering that
question arms this run and nothing else." Copy this verbatim for the suggestion round's own
disclosure-then-yes, scoped to whatever the grant envelope now discloses (D-62-11's folded
allowance).

**Async dispatch + `run_state` recovery pattern to copy** (step 5, lines 344-465): the suggestion
round's stage-2 enrich leg is architecturally identical to this skill's own enrich pass — same
`chunking.dispatch_plan(..., async_ack=True, execution_ceiling=...)`, same
`watch.recover_async_dispatch`, same `run_state.new_run_id()` minted before any HTTP call. Do not
build a second dispatch mechanism for stage 2; call the same functions this skill already calls.

**Held/hold-not-block pattern to copy** (step 5, lines 567-635): `confidence.assess()` → 
`held_queue.build_entry()` → `run_manifest.save()` twice (shared path + run-scoped path). A
suggestion-round row that fails identity or confidence is HELD exactly like a match/enrich-lane
row — no special-casing (D-62-09's own words).

**What NOT to copy:** step 2's spreadsheet/CSV-column resolution (`preingest.rows_from_table`) —
this phase's rows never come from a file; they are synthesised in memory from the ladder + waterfall
(D-62-08's "no new lane" applies to the *landing* mechanism, not the *sourcing* mechanism, which is
genuinely new for this phase).

---

### `operator-claude-plugin/scripts/role_vocabulary.py` (new — D-62-05, offline clustering)

**Analog:** `scripts/inventory_org_type_values.py` (full file read, 183 lines).

**Skeleton to copy** (lines 47-52, the credential/portal guard):
```python
def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))

def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID
```

**Paged sweep to copy** (lines 72-104), substituting `properties: ["jobtitle"]` on the **contacts**
object instead of `lv_org_type` on companies:
```python
def _search_companies_page(after, limit=PAGE_LIMIT):
    body = {"filterGroups": [], "properties": [ORG_TYPE_PROPERTY], "limit": limit}
    ...
    r = requests.post(f"{BASE_URL}/crm/v3/objects/companies/search", ...)
```
→ becomes `crm/v3/objects/contacts/search` with `properties: ["jobtitle"]`.

**What differs (cannot copy):** `classify_value()` (lines 55-69) classifies against
`src/taxonomy.py`'s static 9-key vocabulary — `jobtitle` has no static taxonomy to classify against.
This is exactly the gap D-62-05's Haiku clustering fills; there is no in-repo precedent for that
step (Research Amendment Priority 5, confirmed by a repo-wide grep for `cluster` — zero hits).

**Caching pattern to copy:** `config/taxonomy.yaml` — a committed config artifact the code reads,
rebuilt by a script invocation, not computed at runtime. Mirror this for the cached role-family
list (satisfies D-62-05's "cached... not re-clustered per run").

**Read-only exit convention to copy** (lines 151-178, `main()`): credential-skip → exit 0;
portal-mismatch → refuse, exit 1, no API call; a finding (here: portal too sparse, D-62-07's
fallback trigger) → non-crash, explicit summary line, not an exception.

---

### `operator-claude-plugin/scripts/role_classify.py` (new — Amendment Priority 5, item 2)

**Analog:** no direct precedent exists (confirmed by research). Compose from two:

1. **`operator-claude-plugin/scripts/company_domain.py`**'s pure-transform, no-I/O discipline
   (module docstring: *"no I/O, no network... mirroring `preingest.py`'s two-pass discipline"*) —
   this module classifies one already-extracted jobtitle string against the cached family list
   with zero network calls; it takes the family list as a parameter, never re-derives it.
2. **`src/taxonomy.py` / `n8n/code/taxonomy.generated.js`** — the one-vocabulary-two-access-modes
   pattern already used for `lv_org_type`: one definitions block (here: `role_vocabulary.py`'s
   cached output), consumed by both a build-time/offline path (`role_vocabulary.py` itself) and
   a runtime/online path (`role_classify.py`). Do not build a second independent clustering
   pipeline for this — Amendment Priority 5's explicit warning against "a second implementation
   of the same rule."

**Interface shape to copy** from `company_domain.py::needs_research()` (pure, named rows only, no
side effects):
```python
def classify_title(title, family_list):
    """Pure. No I/O, no network, no classification call itself — this only decides which
    cached family a title matches, or none. The classification CALL (if online, this is a
    single cheap model call per discovered title) is a separate, cost-guarded concern,
    mirroring how needs_research() names rows without researching them."""
```

---

### `operator-claude-plugin/scripts/suggest_contacts.py` (new — orchestration: zero-contacts check,
ladder-driven discovery, dedupe pre-filter, row synthesis)

**Analog:** `operator-claude-plugin/scripts/company_domain.py` (full file, 226 lines) for the
propose/decide two-pass discipline, plus `operator-claude-plugin/scripts/url_fallback.py` (full
file, 227 lines) as the **called, not modified** discovery mechanism.

**Two-pass validate-then-apply discipline to copy** (`company_domain.py` lines 73-151,
`apply_domain_decisions`): validate every entry in a batch BEFORE applying any of it, so a raise
leaves nothing partially applied. Apply this to "which companies in the batch have zero contacts
and get a discovery attempt" — validate the whole batch's eligibility first, then run the ladder
per company.

**Ladder call pattern to copy** (`url_fallder.py` — actually `url_fallback.py` — `__main__` CLI
shape, lines 184-226): `plan_ladder(url)` → `filter_candidates(pasted_url, urls,
already_fetched=N)` → `give_up_message(pasted_url, attempts)`. **Do not re-implement this
sequence** — call the three functions directly as a library (same "library, not just a CLI"
pattern `preingest.py` already establishes for `extraction.py`'s functions). The budget parameter
(`already_fetched`) must be threaded per-company, reset to 0 at the start of each company's own
ladder walk — `MAX_FOLLOWUP_FETCHES` bounds one company's whole ladder, not the whole round
(confirmed in the module docstring and D-62-14's cost table).

**Refusal discipline to copy** (`url_fallback.py`'s `give_up_message`, lines 158-181): "reports what
was tried and draws no conclusion about the cause." D-62-03's "record 'no candidates found' and
move on... do not escalate past a refusal" is this exact function's contract — call it verbatim for
the per-company give-up case, never substitute a second search.

**Row synthesis target shape to copy** (from `extraction.py`, Research Priority 3, confirmed live):
```json
{
  "record_type": "contacts",
  "row": {"firstname": "...", "lastname": "...", "company": "...", "jobtitle": "..."},
  "provenance": {"input": "suggest_contacts_ladder", "locator": "<company id or domain>"}
}
```
Stage-1 rows (from the ladder) carry no `email`/`phone` — identity resolves via group 2
(`firstname+lastname+company`), confirmed by `config/column_mapping.yaml`'s
`required_identity.any_of`. Stage-2 (waterfall) fills `email`/`phone` onto the SAME row before it
reaches `extraction.validate()` — do not call `validate()` twice per row; enrich first, validate
once, matching `enrich-before-ingest`'s own step ordering (match/enrich before validate/ingest).

**Zero-associated-contacts read** (D-62-16): `[ASSUMED, per research A3]` `GET
/crm/v4/objects/companies/{company_id}/associations/contacts`, mirroring the live WRITE path
CLAUDE.md §13.0.1 confirms (`PUT .../associations/default/companies/{id}`). Flag as a
`checkpoint:human-verify` or disarmed probe before the plan locks this endpoint name — not
independently probed this research/pattern pass either.

**Dedupe pre-filter (D-62-18) to copy the shape of, not the code of:** filter a company's
already-known contacts out of role targeting before spending — same "filter before you price" shape
`company_domain.py`'s `needs_research()` uses ("A row Claude already proposed a domain for... is not
in this set: the free in-conversation proposal is the primary path and spends nothing").

---

### `operator-claude-plugin/scripts/write_grant.py` — `envelope()` / `plan_grant()` (modify in place)

**Analog:** itself — D-62-11 says widen the existing figures, not fork a parallel path.

**Read before touching (live gotcha, confirmed by direct read this session):**
```python
# write_grant.py:455-461
# CR-01 fix (Phase 60 review): this used to share the name `ceiling` with the
# sampled-allowance verdict dict assigned below, so `figures["chunk_ceiling"]`
# ended up holding the verdict dict instead of this int...
chunk_record_ceiling = None   # int — the per-chunk record cap
...
ceiling = figures["ceiling"]  # dict — the CEILING_OK/CEILING_OVER/... verdict
```
**Do not reuse either key name for the new suggestion-allowance figure.** Pick a third name, e.g.
`figures["suggestion_allowance"]`, confirmed by direct grep as free (`chunk_ceiling` read as int at
line 579; `ceiling` read as dict at line 1037).

**`_affordable_record_count` split-offer, reused verbatim (D-62-13):**
```python
# write_grant.py:746
def _affordable_record_count(total, ceiling, remaining):
    """The largest N (0 <= N <= total) such that ceil(N/ceiling) + N ... is at or under
    remaining. A linear scan ... never a while loop ..."""
```
No new code needed here — D-62-11's suggestion allowance must fold into the SAME `record_count`
this function already prices, or `CEILING_OVER`'s refusal-with-split-offer (lines ~1034-1080) will
never see the suggestion round's own weight.

**Refusal text pattern to copy verbatim in shape** (lines ~1050-1080): "refusing to open this
grant: it projects N execution(s)... A smaller batch is available now: X of Y record(s) would fit
this run, with the other Z queued for a future run..." — this is D-62-13's whole mechanism; the
suggestion round gets this exact refusal for free once its cost is folded into `figures`.

---

### `n8n/code/mergeContacts.js` + `scripts/build_cloud_workflows.py` § `MERGE_CONTACTS` (D-62-17)

**No new file — one existing hardcode to parameterize.** Confirmed by direct read:

```js
// mergeContacts.js:174 — the hook ALREADY EXISTS, unmodified, reused as-is
function mergeContacts(existingProps, candidateRow, fieldPolicy, opts) {
  ...
  const source = (opts && opts.source) || "csv";
```

```js
// scripts/build_cloud_workflows.py:293 — the ONE hardcode that needs to change
const merged = mergeContacts({}, candidate, undefined, { source: "csv", confidence: 80 });
```

**The change is narrow:** derive `source` from a value the row itself carries (e.g. `row.origin`,
set by `suggest_contacts.py` to `"claude_web"` for stage-1 fields or the provider name for stage-2
fields — D-62-17's "mixed provenance" requirement) instead of the literal `"csv"`. This ONE constant
(`MERGE_CONTACTS`) is registered in **both** `build_local()` (line ~730) and `build_cloud()` (lines
~766/877) — the change lands once, both templates pick it up automatically (the same "one
implementation" discipline CLAUDE.md §13.0.1 states for the association rule).

**Pitfall, confirmed by direct read of `operator-claude-plugin/scripts/resolution_sources.py:26-31`:**
```python
RESOLUTION_SOURCES = frozenset({
    "hubspot_lookup", "operator_statement", "provider_result", "same_row_derivation",
})
```
This is a DIFFERENT, closed vocabulary from `mergeContacts.js`'s `opts.source` — `"lusha"` or
`"claude_web"` must NEVER be added here; if `suggest_contacts.py` sets an `extraction.py`
`resolutions` entry at all, its `source` must be `"provider_result"`, never the provenance-blob
value.

---

### `operator-claude-plugin/scripts/extraction.py` (unmodified — consumed as library)

**Analog:** itself. **No change needed.** Confirmed live (Research Priority 3, full read of
`validate()`'s pre-flight, lines ~560-660): `validate(artifact: dict, mapping_path=None)` already
operates on a plain in-memory dict; `preingest.py` already imports and calls sibling `extraction`
functions directly (`extraction.hold_emailless`, `extraction.canonical_props()`), confirming
library-style consumption is the established pattern, not a special case to build.

**Canonical prop set to target** (`extraction.canonical_props()`, derived from
`config/column_mapping.yaml`'s `aliases`): `email`, `firstname`, `lastname`, `jobtitle`,
`linkedin_url`, `phone`, `company`, `company_id`. `suggest_contacts.py`'s synthesised rows must use
exactly these keys — anything else is silently stripped into `dropped_keys`, never a crash but never
silently kept either.

## Shared Patterns

### Read-only-then-priced-then-armed (the whole phase's shape)
**Source:** `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` steps 1-7, and
`write_grant.py`'s `envelope()`/`plan_grant()`.
**Apply to:** `suggest-contacts/SKILL.md` end-to-end. Discovery (ladder) and role-vocabulary
sampling are unarmed reads; stage-2 enrich and the final ingest write are the only two gated sends,
each under the SAME session grant (D-62-11), never a third lane.

### One implementation, never a second copy
**Source:** CLAUDE.md §13.0.1 (association rule) and this phase's own D-62-08.
**Apply to:** every file above. `suggest_contacts.py` calls `url_fallback.py`, `extraction.py`,
`chunking.py`, `held_queue.py`, `write_grant.py` — it must not re-implement any of their contracts,
mirroring Phase 61-06 Task 1's precedent of refusing/downgrading rather than duplicating.

### Refuse rather than guess / do not escalate past a refusal
**Source:** `url_fallback.py::give_up_message`, `company_domain.py::DomainDecisionError`.
**Apply to:** D-62-03 (no candidates found → record and move on, never a second search) and D-62-07
(sparse-portal fallback → disclosed, never silently substituted).

### Worst-case, never under-priced
**Source:** `write_grant.py`'s measured "a real 2-record chunk projected 3 executions" discipline.
**Apply to:** D-62-14's two-component ceiling (stage-1 fetch count bounded by
`MAX_FOLLOWUP_FETCHES`, stage-2 provider credits bounded by companies × per-company cap) — both
components must round up, never down, and the plan must not invent an isolated per-company dollar
figure for stage 1 (no measured rate exists; ship a new rate key `null` until probed, following
`company_domain_research`'s convention in `cost_rates.json`).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| Haiku clustering call inside `role_vocabulary.py` | model_classifier invocation | batch, one call | No clustering module exists anywhere in this repo (confirmed by grep); the offline-inventory *skeleton* has a strong analog (`inventory_org_type_values.py`), but the clustering step itself is genuinely new work with no precedent to copy from — follow `src/classifier_haiku.py`'s general shape (system prompt + JSON-only contract) if a closer analog is wanted, but that module classifies against a FIXED taxonomy, not a self-derived one, so treat it as a distant cousin, not a template. |
| Company→leadership-page-URL derivation | (deliberately absent) | n/a | Confirmed absent by negative grep (Research Amendment Priority 2) and explicitly out of scope per the phase's re-scope: discovery starts from an operator-approved starting point inside the ladder's own rungs (sitemap-first), never from a guessed conventional path (`/team`, `/about`) — CONTEXT.md D-62-01 rev 3 explicitly forbids building a "conventional-path guesser." |

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/skills/`,
`n8n/code/`, `scripts/build_cloud_workflows.py`, `scripts/inventory_org_type_values.py`,
`src/taxonomy.py` (referenced, not opened this pass).
**Files scanned (read in full or targeted):** `url_fallback.py`, `inventory_org_type_values.py`,
`company_domain.py`, `extraction.py` (targeted sections), `write_grant.py` (targeted sections),
`mergeContacts.js` (targeted sections), `build_cloud_workflows.py` (targeted sections),
`enrich-before-ingest/SKILL.md` (full).
**Pattern extraction date:** 2026-09-02
**Gitignored-mirror check:** all analog paths above are repo-tracked source under
`operator-claude-plugin/`, `n8n/`, `scripts/`, `src/` — none live under a `.gsd/capabilities/`
install mirror; no substitution needed.
