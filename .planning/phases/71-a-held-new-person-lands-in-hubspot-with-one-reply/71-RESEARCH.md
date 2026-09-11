# Phase 71: A held new person lands in HubSpot with one reply - Research

**Researched:** 2026-09-12
**Domain:** Python plugin state stores (`operator-claude-plugin/scripts/`), two SKILL.md
consumers, no new external dependency
**Confidence:** HIGH — every claim below is grep/Read-verified against the live tree this
session; no web research was needed (this is a pure internal-seam integration phase).

## User Constraints

<user_constraints>
### Locked Decisions (verbatim from 71-CONTEXT.md — do not relitigate)

- **F2 ruling (operator, 2026-09-11)** — `no_match` holds are faceted at READ time (new
  person / needs company / nothing found); `review-triage` reads both queues in ONE
  continuously-numbered table; `create` lands through the contact-ingest lane under a
  review-lane grant; the batch renders the ready answer and never asks. Criterion: most
  frictionless operator experience with relative safety, **review over approve**, both
  routes offered with equal weight. Rejected there and still rejected: export-to-
  `contact-upload`, an in-flow approve question.
- **D-69-03** — a client-side durable store ACCUMULATES across runs; each entry carries its
  own `run_id`. `held_queue.json` moves to this shape.
- **D-69-04** — `row_id` is explicitly NOT a key (minted per batch, positional).
- **D-70-11** — `confidence.assess` is the ONLY per-row verdict; a facet is a read, never a
  verdict, never a hold code. `confidence.ALL_HOLD_CODES` stays closed.
- **CLAUDE.md §13.0.1** — the ingest lane resolves company by email domain then exact name,
  holds ONE implementation of the association rule; an absent company is downgraded to
  review server-side and never lands. The plugin never reproduces that downgrade
  client-side and never creates a company through the ingest lane.
- **Backload human gates** — the live proof is ONE end-of-phase UAT gate, not a mid-phase
  probe. Nothing armed before it. SAFE-01..05 unchanged.

### Seed for `classify_facet` (D-71-01..03)
- **D-71-01: Stamp it on the held entry at persist time.** At `enrich-before-ingest` step 6
  the batch already knows whether the row's cleaned email domain is among step 2's confirmed
  domains or this run's own company creates (`preingest` same-run dependency index). That
  fact is written onto the held entry when it is persisted; `classify_facet` reads it from
  the entry on BOTH surfaces. Zero lookups. **Reversibility: costly** — becomes part of the
  on-disk entry schema every reader validates.
- **D-71-02: No backend read at facet time.** Rejected — a lookup would need a second
  company resolver, the drift §13.0.1 refused.
- **D-71-03: `known_company_domains` stays an argument, sourced from the stamp.** The pure
  signature `classify_facet(entry, known_company_domains)` is kept; callers derive the set
  from the entry's stamp (and may still ADD a domain the operator confirms in-conversation,
  per `review-triage` 2c — unchanged). The default empty set remains the safe direction.

### Stable held-entry identity (D-71-04..05)
- **D-71-04: The key is the row's satisfied identity group, normalised.** Derived from
  `required_identity.any_of` in `config/column_mapping.yaml` — `email` when present
  (cleaned, case-folded), else `firstname+lastname+company` through the same case-folded,
  whitespace-collapsed name key D-69-04 trusts (`suggest_contacts.name_key` — see Correction
  below), else `linkedin_url`. `row_id` is carried on the entry as source position only.
  Settlement (`record_verb`), `is_settled`, `open_entries` and
  `run_manifest.rows_to_resume`'s `confidence_held` branch all key on the stable key.
  **Reversibility: one-way** — a published on-disk schema on operator machines.
- **D-71-05: Wipe once, no migration code.** The live `held_queue.json` (run `a254d1e`, 4
  UAT entries) is deleted in the gate's clean-up step; the second-round CSVs repopulate it
  under the new key. No lazy rekey on `load()`. A legacy document (positional keys, no
  stamp) is refused by `load()` as `anomalous` with a one-line reason naming the wipe —
  never silently read as empty.

### Folded Todos (must be moved `pending/` → `completed/` when this phase closes, §31 rule 2)
- `2026-09-11-known-company-domains-never-seeded-so-no-held-row-reads-new-person.md` —
  closed by D-71-01..03.
- `2026-09-11-held-queue-row-id-is-positional-not-a-stable-identity.md` — closed by
  D-71-04..05.
- `2026-09-11-forbidden-name-marker-whole-token-still-refuses-grant-token.md` — folded under
  §31 rule 3 (adjacent residual, same function this phase edits). Fix once, through the
  shared matcher, so a person named Grant or a company named Token persists in ALL SEVEN
  stores the todo names, while an actual grant token / secret value is still refused. **As
  of this research session, this file is still in `pending/`** — it has not yet been
  triaged closed; confirm this explicitly at plan-close time.

### Claude's Discretion
- Field name and shape of the persist-time stamp; whether it records the source
  (`step2_confirmed` / `same_run_create`) beside the boolean.
- Exact normalisation of the stable key and its serialisation in the JSON map.
- How `classify_read` reports a legacy document.

### Deferred Ideas (OUT OF SCOPE)
- `2026-09-04-company-domain-has-no-candidate-source.md` — n8n enrichment lane; adjacent by
  keyword only.
- `2026-08-04-enrichment-throughput-ceiling.md`,
  `2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` — n8n runtime; unrelated.
- Any new hold code; client-side company creation through the ingest lane; a second
  company-resolution implementation anywhere (§13.0.1); arming outside the gate.
</user_constraints>

## Summary

This phase does not add new logic — `classify_facet`, the four verbs, and the one-table
render already ship (0.47.0). It closes two gaps quick batch `260911-w6n` left, both because
no plan owned the seam between four parallel items: (1) both real callers of
`held_queue.classify_facet` seed `known_company_domains = set()` and never populate it, so
`FACET_NEW_PERSON` is unreachable in production; (2) `held_queue.json`'s entries map is keyed
by `row_id`, a per-batch positional string (`row-1`, `row-2`, ...) that is guaranteed to
collide across separate runs — a second run's own row 1 silently OVERWRITES a prior run's
held row-1 entry in the accumulated map (see Seam Map §2), which is data loss under D-69-03's
accumulate contract, not merely a resume-time comparison failure — so `rows_to_resume`'s
`confidence_held` fingerprint branch, `record_verb`, and every settlement read are also keyed
on a value with no cross-run meaning.

D-71-01..03 close gap (1) by having `enrich-before-ingest` step 6 stamp, at persist time,
whether the row's cleaned email domain is a step-2 confirmed company domain or a same-run
company create — `classify_facet` itself does not change (its signature and the
`known_company_domains` argument are untouched); only the CALLERS change, deriving the set
from the new stamp instead of a hardcoded `set()`.

D-71-04..05 close gap (2) by rekeying `held_queue.json`'s entries map onto the row's own
`required_identity.any_of` group (email, else the normalized `firstname+lastname` name key,
else `linkedin_url`) and wiping the 4-entry on-disk file rather than migrating it.

**The load-bearing risk this research surfaces, not previously written down anywhere:**
rekeying the entries map onto a stable identity means the dict KEY can now legitimately BE a
person's own name or email local-part (e.g. `"grant dewsbury"` or `"grant@..."`), and
`held_queue.save()` runs `_looks_forbidden(row_id)` — a raw value scan — against every dict
key before writing. Today `row-1`/`row-2` never trips a marker; after this phase's own change,
a stable key literally named `"grant"` WILL trip it, turning today's *positional-key* store
into a store where a `create`-shaped person named Grant can no longer be persisted at all —
worse than today, and the exact UAT person (Grant Dewsbury) this phase's own CONTEXT.md
names as the person the folded todo must let through. The three items (D-71-04's rekey, the
folded forbidden-name-marker todo, and the UAT's own named test subject) are one seam, not
three — see Pitfall 1 and the Seam Map §6 below for the seven-way fix cost this collision was
scoped for.

**Primary recommendation:** land the stamp (D-71-01..03), the stable key (D-71-04..05), and
the forbidden-key-vs-value narrowing for `held_queue.py`'s top-level entry key (the same
narrowing `260911-w6o` already gave `row`'s own fields) in ONE plan, driven by the SAME
composition tests that already pin the `a254d1e` shape — do not split the stamp and the
rekey across parallel plans a second time.

<phase_requirements>
## Phase Requirements

No requirement IDs are mapped — `ROADMAP.md`'s Phase 71 entry states "Requirements: TBD".
The phase's own headline claim (Jimmy Busteed reads `new_person` on both surfaces and lands
with one `create all 1` reply) is the acceptance criterion in place of a REQ table; treat it
as the single requirement the plan-checker verifies against.
</phase_requirements>

## Correction to CONTEXT.md (verified this session, factual not a decision)

`71-CONTEXT.md`'s `<code_context>` section names `suggest_contacts._name_key` twice. **The
actual function is `suggest_contacts.name_key`** (no leading underscore) —
`operator-claude-plugin/scripts/suggest_contacts.py:161`, explicitly marked
`PUBLIC (Phase 69, D-69-04)` in its own docstring: `"the same key select_people's dedupe
already trusts is also half of suggestion_declines's composite entry key — a cross-module
contract now, not an internal helper."` Grepping `_name_key` (with underscore) returns zero
hits anywhere in `operator-claude-plugin/`. Use `suggest_contacts.name_key(row)` verbatim; it
returns `(first, last)` normalised via `" ".join(str(value or "").strip().casefold().split())`,
or `None` when either half is missing.

## Seam Map

### 1. Every reader and writer of `held_queue.json` entries

**Writers of `held_queue.build_entry` / `held_queue.save`:**

| Call site | File:line | Wired into a SKILL.md today? |
|---|---|---|
| Step-5 confident-verdict loop | `skills/enrich-before-ingest/SKILL.md:764-770` | **Yes** — the only live production writer. `entry = held_queue.build_entry(merged_by_id.get(row_id, row), verdict.hold_code, verdict.reason, parsed); held_entries[row_id] = entry; held_queue.save(run_id, held_entries)` |
| `preingest.hold_ingest_no_company(row, item)` | `operator-claude-plugin/scripts/preingest.py:1338-1355` | **No.** Builds a `held_queue.build_entry(..., confidence.HOLD_NO_MATCH, ...)` entry for the REVIEW-10 ingest-lane no-company case. Tested only (`test_unattended_pair_composition.py`), never called from any SKILL.md. **Dormant but contract-relevant**: if this phase changes `build_entry`'s call contract (e.g. requiring the new stamp), this dormant call site must keep compiling against the new signature even though nothing exercises it live. |

**Readers of `held_queue.load()` / `held_queue.classify_read()` / `held_queue.open_entries()`
/ `held_queue.entry_verb()`:**

| Call site | File:line |
|---|---|
| `enrich-before-ingest` step 6 render | `skills/enrich-before-ingest/SKILL.md:863-876` |
| `review-triage` step 2b read/bucket | `skills/review-triage/SKILL.md:93-102` |
| `run_manifest.rows_to_resume`'s `confidence_held` branch | `operator-claude-plugin/scripts/run_manifest.py:362-455` (reads `held_entries` — see §2, not `held_queue.load()` itself; the CALLER is responsible for loading and passing it in) |

**Writers of `held_queue.record_verb` (the ONLY settlement writer):**

| Call site | File:line |
|---|---|
| `review-triage` step 4c, after independent re-read confirms the create landed | `skills/review-triage/SKILL.md:365-370`: `for row_id, email in created_by_row_id.items(): if email and email in landed: held_queue.record_verb(row_id, held_queue.VERB_CREATE, run_id)` |

No other SKILL.md, script, or test calls `record_verb` in production; `skip`/`drop`/`retry`
verbs are implied by step 3's answer vocabulary but this research found no `record_verb(...,
held_queue.VERB_SKIP, ...)` call site wired into review-triage's own steps 5-8 text — the
skill's prose names the verb but the actual call is not shown in the file the way 4c's is.
**Flag for the planner:** confirm whether `skip`/`drop`/`retry` recording is truly wired
before assuming full symmetry with `create`.

### 2. Every place `row_id` is used as a KEY (vs. carried as source position)

**The sharper framing of the D-69-03/D-71-04 defect: silent overwrite, not just a failed
lookup.** Step 5's write is `held_entries = held_queue.load(); ... held_entries[row_id] =
entry; held_queue.save(run_id, held_entries)` (`SKILL.md:749, 766-767`) — under D-69-03 this
is meant to ACCUMULATE across runs (the whole point of moving off `held_queue`'s old
single-`run_id`-document shape). But because `row_id` is positional (`row-1`, `row-2`, ...,
freshly reminted every run by `preingest.build_rows_spec`), a SECOND run's row 1 writes to the
exact same key `"row-1"` a PRIOR run's row 1 used — `held_entries[row_id] = entry` OVERWRITES
the earlier run's entry in the loaded map before `save()` ever runs. This is silent data loss
under the accumulate contract, not merely a failed resume-time comparison: an operator who
held a row in run A, then ran an unrelated batch (run B) whose first row also lands at
position 1, has run B's row-1 entry silently replace run A's held row in the very same
`save()` call — with no error, no warning, and no signal that anything was lost. The
lookup-miss framing below (`rows_to_resume`) is the SECOND-order symptom; the write-side
overwrite is the primary defect the rekey exists to close.

| Site | File:line | Current key | Becomes (D-71-04) |
|---|---|---|---|
| `held_entries[row_id] = entry` (step 5 write) | `SKILL.md:766` | `row_id` (`row-N`) — **overwrites cross-run, see above** | stable key derived from the row |
| `held_queue.save(run_id, held_entries)` — `for row_id, entry in entries.items(): if _looks_forbidden(row_id)` | `held_queue.py:453-459` | `row_id` | stable key — **this is the exact line that will start refusing a name-shaped key; see Pitfall 1** |
| `held_queue.record_verb(row_id, verb, run_id)` — `if row_id not in entries: raise` | `held_queue.py:415-443` | `row_id` | stable key. `record_verb` is already parametric on whatever the caller passes as the first positional arg — no internal change needed, only what callers PASS changes. |
| `run_manifest.rows_to_resume`'s `entry = held_entries.get(row_id)` | `run_manifest.py:424, 439` | `row_id = row.get("row_id")` (freshly minted THIS run — `row-1`, `row-2`, ...) — **this is the concrete defect**: a `confidence_held` verdict recorded under last run's `row-1` is looked up under THIS run's freshly-reminted `row-1`, which by chance may collide by POSITION but never by IDENTITY. The lookup must change to compute the row's stable key fresh (same derivation as D-71-04) and look up `held_entries.get(stable_key)`, not `held_entries.get(row.get("row_id"))`. |
| `review-triage` 2b/2c `by_facet.setdefault(..., []).append(rid)`, 4a `held_entries[rid]["row"]` | `SKILL.md:98-102, 300-303` | dict key `rid` from `held_queue.load()`'s own keys — **already key-agnostic**, iterates over whatever `load()` returns; no change needed beyond the underlying store's key. |
| `held_queue.fingerprint(hold_code, outcome)` | `held_queue.py:258-271` | Hashes `hold_code` + `match_tier` + `candidate_count` only — **never hashes the key at all**. Unaffected by the rekey. |

**Production gap found, not previously documented:** `watch.resume_or_disclose(rows)` is
called at `enrich-before-ingest/SKILL.md:1197` with **no `held_entries=` / `current_outcomes=`
arguments** — both default to `None` → `{}` inside `run_manifest.rows_to_resume`. This means
the `confidence_held` fingerprint-comparison branch (`run_manifest.py:424-461`) **always**
takes the `entry is None` fallback and re-includes the row in `to_resume` — the comparison is
currently dead code in production regardless of what key scheme is used. The planner should
decide explicitly whether wiring `held_entries=held_queue.load()` into this call site is
in-scope for this phase (it is directly downstream of the same identity fix and arguably
required to make the phase's cross-run promise true end to end) or is a separate, deferred
gap — but it must be a DECIDED scope line, not silently inherited.

### 3. Every call site of `classify_facet(entry, known_company_domains)`

Both real (non-test) callers seed the empty set and never add to it — confirmed by grep,
zero exceptions:

- `skills/enrich-before-ingest/SKILL.md:869`: `known_company_domains = set()  # nothing
  confirmed yet this run -- w6p's own safe default; classify_facet reads needs_company until
  a domain is actually resolved`
- `skills/review-triage/SKILL.md:98`: `known_company_domains = set()  # grows during this
  sitting -- see 2c below` (2c's own prose confirms it only ever grows from
  operator-statement or same-sitting company-verb handoff — never a stamp read, today)

`classify_facet`'s own signature and pure-read discipline
(`operator-claude-plugin/scripts/held_queue.py:290-368`) are NOT changed by this phase — the
function already accepts `known_company_domains` as an argument and documents in its own
docstring exactly the derivation this phase adds: *"the caller resolves the domains (a
HubSpot read, or the run's own knowledge) and passes them in."* The fix is 100% caller-side:
both snippets above change from `known_company_domains = set()` to a comprehension that folds
in the new per-entry stamp.

### 4. Data available at `enrich-before-ingest` step 6 persist time to build the stamp

Step 6 is a RENDER step over already-loaded state (`skills/enrich-before-ingest/SKILL.md:825
onward`); the actual PERSIST happens one step earlier, at step 5 (lines 745-777), inside the
per-row `confidence.assess` loop. **D-71-01 names step 6 but the write must happen at step
5's `held_queue.build_entry`/`save()` call, since that is the only place the entry is
constructed** — step 6 only reads what was already written. Confirm this ordering explicitly
in the plan; CONTEXT.md's "at step 6 the batch already knows..." describes the KNOWLEDGE
being available by step 6, not the literal line number the write happens on.

At step 5's loop (`SKILL.md:745-777`), the data available to compute the stamp:

- **`merged_by_id.get(row_id, row)`** — the merged row already handed to `build_entry`.
  Its `email` field is exactly what `classify_facet` itself later parses (`row["email"]`,
  split on `@`, cleaned via `enrichment._clean_domain`). The stamp can derive its own
  cleaned domain the identical way, in the same loop iteration, at zero extra cost.
- **Step 2's company-row confirm table** (`SKILL.md:146-176`) — when the batch's extraction
  pass also yielded company rows (`record_type: companies`), each row's proposed website is
  confirmed in one table before those rows join the batch; `company_domain.
  apply_domain_decisions` → `to_envelope_spec` → `enrichment.build_envelope` is the ONLY
  path a domain travels to a webhook event (`company_domain.py:1-20`). **This research
  found no in-repo variable, at step 5 or step 6, that already collects "the set of domains
  step 2 confirmed."** The plan must either (a) have step 2 build and hand forward a
  `confirmed_company_domains` set explicitly (recommended — it is a small, local addition
  right where the table is confirmed), or (b) derive it after the fact from
  `company_domain`'s own decision records, which are not currently retained past
  `to_envelope_spec`'s call. Treat this as a genuine gap to close, not an existing value to
  wire up.
- **This run's own company creates** — `preingest.index_company_dependencies(company_
  create_responses)` (`preingest.py:1259-1276`) builds `company_dependency_id -> company_id`
  from a companies-object_type dispatch's `Build Response` items (each carrying
  `company_dependency_id`/`company_id` once `Adapt Company Create` has run — n8n side,
  `scripts/build_cloud_workflows.py`'s `ENRICH_DECIDE_CO_CLOUD`/`Adapt Company Create`
  node). **This function, and its sibling `assign_same_run_company_ids`, are NOT called from
  any SKILL.md today** — grep across `operator-claude-plugin/skills/` for
  `index_company_dependencies`/`assign_same_run_company_ids`/`company_dependency_id` returns
  zero hits; both are exercised only by `tests/test_unattended_pair_composition.py`. Do not
  assume this wiring exists — building the "same-run company creates" half of the stamp
  means either wiring this dormant pair into `enrich-before-ingest` for the first time (a
  larger addition than D-71-01's "zero lookups" framing implies) or scoping D-71-01's stamp
  to a narrower set of sources for this phase, and stating that narrowing explicitly as a
  discretion call.
- **A THIRD source, not named in CONTEXT.md, that IS zero-new-lookup and DOES cover the
  Jimmy Busteed acceptance case: step 2's own contact match results.** Step 2's match search
  (`preingest.classify_matches`, `SKILL.md:171-196`) is the propose-mode search EVERY row in
  the batch already goes through, before any enrichment. Its bucket shapes, read verbatim
  from `preingest.py`:
  - `auto_matched` (HIGH tier — the contact already exists in HubSpot):
    `{"row_id": row_id, "row": row, "hs_object_id": item.get("hs_object_id")}`
    (`preingest.py:519-521`).
  - `proposed` (MEDIUM tier — a same-lastname/company candidate, operator confirms at step
    3): `{"row_id": row_id, "row": row, "candidates": [...], "ambiguous": ...}`, where each
    candidate is `{key: candidate.get(key) for key in CANDIDATE_KEYS}` and `CANDIDATE_KEYS =
    ("hs_object_id", "firstname", "lastname", "email", "jobtitle", "company")`
    (`preingest.py:133, 526-537`).
  - `unmatched` (NONE tier — Jimmy's own row, blank email): `{"row_id": row_id, "row": row}`
    only (`preingest.py:539`) — **carries no company signal of its own**, confirmed by
    reading the dict literal directly; a `no_match`/`unmatched` row's own bucket entry has
    nothing to stamp itself with.
  - The `Outcome` dataclass `preingest.parse_outcome` returns per row
    (`preingest.py:158-168`) is `parseable, match_tier, candidate_count,
    provider_agreement, material_conflicts, judge_adjudicated_fields` — **no `company_id`,
    no domain field, anywhere on it.** Confirmed also on the n8n side: `/usr/bin/grep -n
    "company_match\|company_id" n8n/code/matchProposal.js` returns no `company_id`/
    `company_match` field on the propose lane's own response shape — the match response
    never resolves or reports a company at all, for any tier.

  **What this DOES give, for a row OTHER than Jimmy's own:** any row in the SAME BATCH that
  itself lands `auto_matched` — meaning that row's own `row["email"]` already exists as a
  HubSpot contact — has a cleaned email domain that is, by construction, the domain of an
  EXISTING HubSpot record. A `proposed` row's confirmed candidate similarly carries a
  candidate `email` (via `CANDIDATE_KEYS`) once the operator approves it at step 3. Neither
  requires a new HubSpot read: both buckets are already produced by the ONE match call step
  2 already makes for the whole batch. **This is evidence, not proof** — a contact's own
  email domain need not match their employer's canonical company domain, and the UAT's own
  side observation records ATC (`9605284724`) showing `num_associated_contacts: 4` against
  10 contacts carrying `@australianturfclub.com.au` addresses (6 unassociated) — so an
  `auto_matched` contact at a domain does not GUARANTEE that domain is the company's own
  canonical property, only that some existing HubSpot contact record uses it.

**Acceptance-path consequence for the gate's own CSV design (not a blocked headline — a
CSV-design requirement):** for the phase's Jimmy Busteed case specifically (ATC already in
HubSpot, no ATC company row in the CSV, Jimmy's own email blank so his row is `unmatched`),
neither the step-2-company-row-confirm source NOR the same-run-company-create source covers
it (both require something IN THIS BATCH that names ATC as a company — a company row or a
company create — and the acceptance case has neither). **The third source above DOES cover
it, on ONE condition: the gate's CSV must include at least one OTHER row at
`@australianturfclub.com.au` that itself matches HIGH or an approved MEDIUM** — e.g. a second,
real ATC contact already in HubSpot, alongside Jimmy's blank-email row. Present both readings
to the planner as live options, not a single prescribed path: (a) add an ATC company row to
the gate's CSV (the step-2-confirm source), (b) wire the dormant same-run-company-create
functions and have the gate's CSV create a company (larger lift, likely out of scope), or (c)
add a second, already-in-HubSpot ATC contact row to the gate's CSV (the step-2-match source,
zero new plumbing beyond collecting `auto_matched`/approved-`proposed` domains into a set at
step 2 — the lightest of the three). Whichever the plan picks, it is a **CSV-design decision
that must be made explicitly**, since none of the three happens by default from a
contact-only CSV containing only Jimmy's own row.

### 5. Identity groups and the stable-key precedent

`config/column_mapping.yaml:60-63`:
```yaml
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
    - [linkedin_url]
```
Mirrored in `n8n/code/columnMap.js:79-86` (`requiredIdentity(row)`), pinned by
`tests/n8n/columnMapIdentityParity.test.mjs`. D-71-04's three-branch key derivation maps
1:1 onto these three groups, in the SAME priority order (email first).

The precedent store to copy, `suggestion_declines.py:130-142`:
```python
def entry_key(company_id, row):
    if not company_id:
        return None
    name = suggest_contacts.name_key(row)
    if name is None:
        return None
    first, last = name
    return f"{company_id}{KEY_SEPARATOR}{first}{NAME_SEPARATOR}{last}"
```
This keys on `company_id + normalised name`, NOT on `config/column_mapping.yaml`'s
`[firstname, lastname, company]` group directly (it uses a resolved `company_id`, not the
row's raw `company` string) — a held-queue row does not reliably have a `company_id` (a
`needs_company` row has none by definition, per CONTEXT.md's own stated D-69-04 conflict).
**D-71-04 must therefore NOT copy `suggestion_declines.entry_key`'s exact shape** — it must
key on the row's OWN identity fields (email, or normalised `firstname+lastname+company`
STRING, or `linkedin_url`), not a resolved HubSpot id. The precedent to copy is the STORE
DESIGN (accumulate-across-runs, per-entry `run_id`, `classify_read`-style reader,
forbidden-name refusal reimplemented per-module) and the NORMALISATION function
(`suggest_contacts.name_key`), not the composite-key formula itself.

### 6. The forbidden-name marker collision (the load-bearing risk)

**Confirmed live today, independent of this phase:** `suggestion_declines.py` ALREADY keys
its entries map on `f"{company_id}::{first}|{last}"` and its `save()` calls
`first_refusal(key, entry)` → `_looks_forbidden(key)` on that composite string
(`suggestion_declines.py:184, 251`). A person whose normalised firstname is literally
`"grant"` therefore ALREADY fails to persist in `suggestion_declines.json` today, in
production, with no test currently red for it (this session did not run a live repro; the
mechanism is verified by reading the code path, not by an executed failing test — treat this
sentence itself as `[ASSUMED]`-tier until the plan adds a red test proving it, per the
Validation Architecture section below).

**What THIS phase newly introduces to `held_queue.py` specifically:** today,
`held_queue.save()`'s `for row_id, entry in entries.items(): if _looks_forbidden(row_id)`
(`held_queue.py:453-459`) scans a KEY that is always `row-N` — never name-shaped, so this
line has never fired live. Once D-71-04 makes that KEY the row's own normalised
identity, this exact line starts scanning a value that legitimately contains a person's own
name or email local-part. `_looks_forbidden` matches whole tokens (post `260911-any`) against
ten markers including `"grant"` and `"token"` (`held_queue.py:141-166`) — a key like
`"grant dewsbury"` or `"grant|dewsbury|darwin turf club"` trips the `"grant"` token and
`save()` raises `HeldQueueError`, refusing to persist the ENTIRE queue (not just that one
row — `save()` validates every entry before writing anything).

**Is there ONE shared matcher, or many copies?** Confirmed: **nine independent
reimplementations**, deliberately (D-69-01's own stated anti-DRY discipline — "a future
change to one cannot silently weaken another"), pinned behaviourally identical (not by
import) by `operator-claude-plugin/tests/test_forbidden_marker_parity.py`:

| Module | Matcher shape |
|---|---|
| `held_queue.py` | `_looks_forbidden(value)` — key-and-value scan on `reason`/`observed_signals`/`row_id`(→ stable key); KEY-ONLY (`_first_forbidden_key`) on `row`'s own fields since `260911-w6o` |
| `suggestion_declines.py` | `_looks_forbidden(value)`, full key-and-value scan, unchanged by `260911-w6o` |
| `run_manifest.py` | `_looks_forbidden(value)`, scans verdict-map keys |
| `run_state.py`, `run_report.py`, `written_records.py`, `remainder_queue.py`, `match_state.py`, `match_handoff.py` | same `_looks_forbidden(value)` shape each; `run_report.py` additionally splits into `_looks_forbidden_key` (10 markers) / `_looks_forbidden_value` (8 markers, `arm`/`webhook` exempt) |

`test_forbidden_marker_parity.py`'s `MUST_REFUSE` tuple explicitly includes
`held_queue._FORBIDDEN_NAME_MARKERS` itself (i.e. the bare words `"arm"`, `"secret"`, ...,
`"grant"`, `"token"`, ... as VALUES) and asserts every key-matcher module still refuses them
— this is a **currently-shipped, intentional invariant** that a bare marker-shaped VALUE is
refused. The folded todo's own fix note (already written, quoted here since it is the exact
constraint the plan must honour) explains why a naive "just don't scan values" fix cannot
land: three shipped tests pin VALUE refusals as load-bearing
(`test_written_records.py::T-59-02`, `test_held_queue.py:174` `"n8n_api_key=super-secret"`,
`test_run_manifest.py:112` the verdict `"armed"`) — those three regression tests must stay
red-if-broken while a bare marker-shaped NAME (Grant, Token) is exempted. The todo's own
recommended fix (match markers as whole tokens on the FIELD NAME only, never on a value that
is itself a person's or company's own name) is the shape to land; this phase is the forcing
function that makes it non-optional for `held_queue.py`'s top-level entry key specifically,
because D-71-04 is what turns a previously-impossible collision (name-shaped positional key)
into a now-live one (name-shaped stable key). Land the fix in the shared matcher shape (or
equivalently, in the SAME narrow way `260911-w6o` narrowed `row`'s own scan) so all nine
copies move together per D-69-01's own discipline — do not fix `held_queue.py` alone and
leave `suggestion_declines.py`'s already-live defect standing, since the todo's own `files:`
list already names both.

### 7. The live on-disk `held_queue.json` shape and the tests that pin it

Live shape (run `a254d1e...`, per `.planning/UAT-autonomous-batch-2026-09-09.md` and
reproduced verbatim as fixtures in tests): `{"row-1": {...}, "row-2": {...}}` — positional
keys, no stamp field. Tests pinning `"row-1"`/`"row-2"` as literal dict keys, which will need
updating to the new stable-key shape (non-exhaustive grep count, all confirmed present this
session):

- `operator-claude-plugin/tests/test_held_queue.py` — ~15 sites (`test_held_queue.py:118-202`
  and further down)
- `operator-claude-plugin/tests/test_held_queue_facets.py` — the `a254d1e` fixtures
  (`JIMMY_ENRICHED_ENTRY`, `KATIE_ENTRY`, `BARRY_ENTRY`) plus every `rows_to_resume` test
  (lines 136-331) that builds `entries = {"row-1": ..., "row-2": ...}` /
  `held_entries={"row-1": entry}`
- `operator-claude-plugin/tests/test_review_triage_facets.py` — `_entry()` helper fixture
  (`resume_fingerprint`, `row` shape) plus its own `JIMMY_ENTRY`/`KATIE_ENTRY` dict literals
  and `test_one_held_new_person_end_to_end_read_render_create_confirm_mark` (the composition
  test named directly by `test_skill_sequence_coverage.py`'s COVERED registry — see §8)
- `operator-claude-plugin/tests/test_held_facet_render_composition.py` — the step-6 fence
  test named by the same registry

**`load()`'s refusal of a legacy document (D-71-05):** today, `load()`'s
`_validated_entries()` (`held_queue.py:502-525`) already validates `hold_code` and
`resume_fingerprint` per entry but has NO opinion on the KEY's shape at all — a positional
`"row-1"` key and a future stable key both pass `isinstance(row_id, str)` identically. To
implement "a legacy document (positional keys, no stamp) is refused by `load()` as
`anomalous`," the plan must add an explicit shape check — most likely on the presence of the
new stamp field on every entry, or a key-shape check (`"row-1"`-pattern keys are always
legacy) — since nothing in the current schema distinguishes "old-shape valid document" from
"new-shape valid document" otherwise. Decide and record which signal `load()`/`classify_read()`
use to detect "legacy" — Claude's Discretion per CONTEXT.md, but it needs an actual
implementation, not an assumption that the existing validator already catches it (it does
not).

### 8. Test fences that will bite

- **`test_skill_sequence_coverage.py`'s COVERED registry**
  (`operator-claude-plugin/tests/test_skill_sequence_coverage.py:520-563`) keys on the EXACT
  tuple of scripts-module calls each skill step makes, per skill (registry is skill-scoped,
  not shared). Both `review-triage`'s and `enrich-before-ingest`'s held-queue read/bucket
  fences are registered as
  `("held_queue.classify_read", "held_queue.load", "held_queue.open_entries",
  "held_queue.entry_verb", "held_queue.classify_facet")`. **Inserting a stamp-read step
  before `classify_facet` (to build `known_company_domains` from the entry) changes this
  tuple** — the registry entry must be updated to match, and its covering test
  (`test_review_triage_facets.py::test_one_held_new_person_end_to_end_read_render_create_confirm_mark`
  and `test_held_facet_render_composition.py::test_step_6_fence_loads_the_queue_and_facets_
  what_it_loaded_not_a_dict_literal` respectively) must be extended to actually drive the new
  call sequence, not just re-pinned.
- **`test_enrich_before_ingest_skill_contract.py`** and **`test_review_triage_facets.py`** —
  general skill-contract fences; re-run after any SKILL.md prose change in steps 5/6/2b/2c/4a-4c.
- **The D-10b ICP/tier substring ban** — `test_autonomy_switch_prose.py:220-221`,
  `test_mandatory_report_call_sites.py:215-216`, `test_suggestion_declines_skill.py:259`
  each assert `"icp" not in lowered` / `"tier" not in lowered` over rendered skill/report
  prose. **This research found no equivalent scanning test that already covers
  `review-triage/SKILL.md` or `enrich-before-ingest/SKILL.md`'s own prose** — confirm before
  writing new prose in either file whether a D-10b-shaped test needs extending to cover them,
  or whether they are out of that ban's scope entirely (their subject matter — contact
  identity, not ICP scoring — makes accidental "tier"/"icp" mentions unlikely but not
  impossible; avoid the substrings regardless as a matter of house style).
- **`tests/test_todo_triage.py::test_every_pending_todo_is_triaged`** (repo root, not the
  plugin) — fails the WHOLE root suite if any file in `.planning/todos/pending/` is
  untriaged. The three folded todos must be moved to `completed/` (with their fold reason)
  by the phase's own close, not left pending — this is a real CI-shaped gate, not prose.
- **Disclosure-audit tests from Phase 67/68** — this research did not find a test file named
  for "disclosure audit" by that exact phrase; if the parent task's phrasing refers to a
  specific file, grep `operator-claude-plugin/tests/` for `disclos` at plan time before
  assuming a match — this claim is `[ASSUMED]` and should be re-verified rather than acted on.

### 9. Release mechanics

Confirmed live: `plugin.json` version is `0.47.0`
(`operator-claude-plugin/.claude-plugin/plugin.json:4`); CHANGELOG's `[Unreleased]` section
is currently empty (`operator-claude-plugin/CHANGELOG.md:17`). The release checklist
(`CHANGELOG.md`, tail) is FOUR required steps, in order: (1) bump `plugin.json`'s `version`
in the SAME commit as the CHANGELOG entry — Claude Desktop compares only this string; (2) cut
the `[Unreleased]` section to `## [0.48.0] - <date>`; (3) push to `master` (the branch the
marketplace clone tracks); (4) refresh the marketplace clone with `git -C
~/.claude/plugins/marketplaces/lightning-visuals-operator fetch --depth=1 origin master &&
git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator reset --hard FETCH_HEAD`,
then restart Claude Code before the gate — the marketplace clone never fetches on its own.
Both traps from earlier plugin versions (settings loss on reinstall/update) are fixed as of
`0.7.0` and need no special handling here.

### 10. The UAT gate

`docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` §1d's "Second round, `contact-upload`" CSVs (built
2026-09-11, after plugin 0.46.0) already exist and already ran (executions 12365-12376, 0
writes, disarmed) — but as §4 above shows, that existing CSV sends Jimmy Busteed's email
ALREADY REVEALED through `contact-upload` directly, which is a straight `create` with no
`no_match` hold at all, and therefore proves nothing about `classify_facet`/`new_person`. **A
fresh CSV, run through `enrich-before-ingest` (not `contact-upload`) with the target person's
email BLANK, is what D-71-06 actually requires** — the existing §1d rows are the identity/
company-resolution proof (already done), not the facet-and-one-reply proof this phase needs
live. The clean-up step named in CONTEXT.md (delete `held_queue.json`, hand-delete UAT
contacts) is unchanged from every prior gate's own discipline. Arming stays per-send,
disarmed after, exactly as SAFE-01..05 already require.

## Common Pitfalls

### Pitfall 1: The rekey makes `held_queue.py` newly subject to the forbidden-marker defect
**What goes wrong:** landing D-71-04 alone (rekey the entries map) without landing the
forbidden-marker fold in the SAME plan makes `held_queue.save()` start refusing to persist
ANY entry whose stable key contains a whole-token marker — including the exact UAT person
(Grant Dewsbury) this phase's own CONTEXT.md names.
**Why it happens:** `_looks_forbidden` scans dict KEYS as raw values; today's positional
`row-N` keys never collide with a marker, so the scan has been latent, not absent.
**How to avoid:** land both in one plan (already CONTEXT.md's own instruction, via the
fold); implement the same key-vs-value narrowing `260911-w6o` gave `row`'s own fields, but
for the top-level entries-map key this time, and re-run
`test_forbidden_marker_parity.py` plus a NEW test asserting a `"grant dewsbury"`-shaped
stable key persists.
**Warning signs:** any composition test using a Grant/Token-named fixture starts raising
`HeldQueueError` once the rekey lands but before the marker fix does — treat this as the
RED half of the RED-first guard, not a surprise.

### Pitfall 2: `rows_to_resume`'s lookup key mismatch survives the rekey if only the WRITE side changes
**What goes wrong:** if the plan changes what key `held_entries[key] = entry` writes under
but does not also change `run_manifest.rows_to_resume`'s `held_entries.get(row_id)` lookup
(which currently reads `row.get("row_id")`, the freshly-minted per-run positional id) to
compute the SAME stable-key derivation fresh from the row, the lookup silently misses every
time and the `confidence_held` branch permanently falls to its `entry is None` →
re-include-and-re-spend-credit path — functionally unchanged from today's dead-code state,
but now for a subtly different reason (key mismatch instead of never-wired).
**Why it happens:** `row_id` is read in two unrelated places (the write side inside
`enrich-before-ingest`, and the read side inside `run_manifest.rows_to_resume`) that must
independently agree on "what is the stable key for this row," and nothing enforces that
agreement except a shared derivation function.
**How to avoid:** put the stable-key derivation in ONE function (e.g.
`held_queue.stable_key(row)`, mirroring `suggest_contacts.name_key`'s own "PUBLIC,
cross-module contract" precedent) and call it from both the write site and
`rows_to_resume`'s read site — never re-derive it independently in two places.
**Warning signs:** a `rows_to_resume` test that constructs `held_entries` keyed on a
pre-computed stable key but calls the function with rows whose `row_id` is still `row-N`
passes falsely if the test itself doesn't call the shared derivation function to build its
own fixture keys.

### Pitfall 3: Treating "step 2 confirmed domains" and "same-run company creates" as already-available values
**What goes wrong:** CONTEXT.md's D-71-01 describes both sources as things "the batch
already knows" — but neither is actually collected into an accessible variable today (see
Seam Map §4). A plan that assumes `assign_same_run_company_ids`/
`index_company_dependencies` are already wired into `enrich-before-ingest` will write a
stamp-read line against data that does not exist at runtime.
**Why it happens:** both functions exist and are well-tested in isolation
(`test_unattended_pair_composition.py`), which reads like "shipped and wired," but they have
zero call sites in any SKILL.md.
**How to avoid:** explicitly wire (or explicitly narrow scope away from) the
same-run-company-create half of the stamp; explicitly build a `confirmed_company_domains`
collector at step 2 for the step-2-confirmed half.
**Warning signs:** the phase's own headline case (Jimmy Busteed, no company row in the CSV
at all) is not covered by either of D-71-01's two named sources alone — see Seam Map §4's
third source (step 2's own match results) and its CSV-design consequence; if the gate's CSV
is built with only Jimmy's own row and none of the three covering conditions §4 lists, the
live UAT will not observe `FACET_NEW_PERSON` at all.

## Runtime State Inventory

*(Included because this phase changes an on-disk store's key shape — a lighter version of
the rename-phase inventory, since D-71-05 already resolves the migration question with a
wipe.)*

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `held_queue.json` (repo-root-resolved via `durable_paths.resolve_state_path().parent`), 4 UAT entries under positional keys `row-1`..`row-4`-equivalent, run `a254d1e` | **Data migration: NONE (D-71-05 wipe).** Delete the file in the gate's own clean-up step; do not write rekey/migration code. |
| Live service config | None — this phase touches no n8n workflow, no HubSpot schema, no scheduled job. | None. |
| OS-registered state | None. | None. |
| Secrets/env vars | None — `held_queue.py` refuses to persist anything marker-shaped; no secret is stored by this store in either the old or new key shape. | None. |
| Build artifacts | Plugin version bump only (`plugin.json` 0.47.0 → 0.48.0); no compiled artifact, no installed package changes. | Release checklist (§9 above). |

## Package Legitimacy Audit

Not applicable — this phase installs no new external package in any ecosystem. No `npm
view`/`pip index versions` check is needed; all touched modules
(`held_queue.py`, `run_manifest.py`, `preingest.py`, `suggest_contacts.py`,
`suggestion_declines.py`, both SKILL.md files) are already in-repo, first-party code.

## Environment Availability

Not applicable — no external tool, service, runtime, or CLI dependency is introduced. All
work is pure-Python plugin code plus two Markdown skill files; the existing `.venv` (already
present at repo root, confirmed this session) is sufficient.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (plugin), verified this session: `.venv/bin/python -m pytest -q -p no:cacheprovider operator-claude-plugin/tests/` → **3006 passed, 5 skipped** (baseline, 2026-09-12) |
| Config file | none dedicated found beyond `operator-claude-plugin/tests/conftest.py` (adds `scripts/` to `sys.path`) |
| Quick run command | `.venv/bin/python -m pytest -q --tb=short -x -p no:cacheprovider operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_held_queue_facets.py operator-claude-plugin/tests/test_review_triage_facets.py operator-claude-plugin/tests/test_held_facet_render_composition.py` — **verified green this session** (66 passed) |
| Full suite command | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/` |
| Todo-triage gate | `.venv/bin/python -m pytest -q tests/test_todo_triage.py` (repo root — fails on any untriaged pending todo) |

**Always use `.venv/bin/python`, never system python** (per the project's own memory note —
system python lacks the plugin's test deps). Use `/usr/bin/grep`, not shell `grep`, for any
count/pipe command (`grep` is rtk-wrapped in this shell and drops zero-match files under
multi-file `-c`).

### Phase Requirements → Test Map

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| D-71-01..03 stamp + caller fix | `enrich-before-ingest` step-6 render, and `review-triage` step-2b render, both compute `known_company_domains` from the entry's own stamp (not a hardcoded empty set), and a `no_match` entry for Jimmy-shape data reads `FACET_NEW_PERSON` | unit + composition | `pytest -x operator-claude-plugin/tests/test_held_queue_facets.py operator-claude-plugin/tests/test_held_facet_render_composition.py operator-claude-plugin/tests/test_review_triage_facets.py` | ✅ files exist; extend, don't just re-pin |
| D-71-04 stable key | `held_queue.json`'s entries map is keyed by the row's identity-group derivation (email, else normalised name, else linkedin_url), not `row_id`; `record_verb`/`is_settled`/`open_entries`/`rows_to_resume` all key on it | unit | `pytest -x operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_held_queue_facets.py operator-claude-plugin/tests/test_run_manifest.py` | ✅ `test_run_manifest.py`'s `rows_to_resume` tests will need a NEW test asserting cross-run lookup by stable key (does not exist today — every existing test uses matching `row_id`s on both sides by construction) |
| D-71-05 wipe / legacy refusal | `load()` returns `{}` and `classify_read()` returns `ANOMALOUS` (with a wipe-naming reason) for a document shaped like the OLD `row-N`-keyed schema | unit | new test in `test_held_queue.py` — ❌ does not exist yet, `load()`/`classify_read()` currently have no legacy-shape detector at all (see Seam Map §7) |
| Forbidden-marker fold | A stable key containing `"grant"`/`"token"` as a whole token (a real firstname/company) persists; a genuinely marker-shaped key (`"webhook_secret"`, an armed run id) is still refused | unit, RED-first | `pytest -x operator-claude-plugin/tests/test_forbidden_marker_parity.py` plus a new `held_queue`-specific test for the entries-map KEY (not `row`'s fields, already covered) | ✅ parity test exists; ❌ the entries-map-key-specific test does not — write it RED first against current `held_queue.save()`, confirm it fails with `HeldQueueError`, then land the narrowing |
| `test_skill_sequence_coverage.py` fence | Registry tuple matches the actual call sequence in both skills' held-queue read/bucket fences | unit | `pytest -x operator-claude-plugin/tests/test_skill_sequence_coverage.py` | ✅ exists; update the registry tuple + its two covering tests when the stamp-read call is inserted |
| Todo triage | The three folded todos are moved to `completed/` before phase close | unit | `pytest -x tests/test_todo_triage.py` (repo root) | ✅ exists |

### RED-first guard, per decision (what "RED first" looks like concretely)
- **D-71-01..03:** write a test asserting `known_company_domains` derived from a stamped
  `entry` yields `FACET_NEW_PERSON` for a Jimmy-shaped entry — run it against the CURRENT
  code (no stamp field exists yet) and confirm it fails with a `KeyError`/`AssertionError`
  before adding the stamp.
- **D-71-04:** write a `rows_to_resume` test where the held entry is saved under a stable
  key computed from the row's email, and the resume call passes a row whose freshly-minted
  `row_id` differs from a prior run's — confirm it currently reads `still_held == ()` /
  `to_resume` includes the row (proving the CURRENT positional-key lookup fails to find the
  entry) before changing the lookup to use the stable-key derivation.
- **Pitfall 1's guard:** write a test that calls `held_queue.save()` with an entries map
  keyed `{"grant dewsbury": entry}` (or whatever the actual normalised shape is) against
  CURRENT `held_queue.py` — confirm it raises `HeldQueueError` — before landing the
  key-vs-value narrowing that lets it through.
- **D-71-05:** write a test loading a `row-1`/`row-2`-keyed legacy document through the NEW
  `load()`/`classify_read()` — confirm it currently returns `PARSEABLE`/non-empty (today's
  actual behaviour, since nothing distinguishes old from new shape yet) before adding the
  legacy-shape detector that flips it to `ANOMALOUS`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `suggestion_declines.py` ALREADY fails to persist a decline for a person whose normalised firstname is a whole-token marker (e.g. "Grant") — inferred by reading `entry_key`/`first_refusal`/`save()` together, not by running a live failing test this session | Seam Map §6 | If wrong (some earlier guard already exempts this), the plan may spend a task re-fixing an already-fixed store, or under-scope the forbidden-marker fold by assuming `suggestion_declines.py` needs no change |
| A2 | "Disclosure-audit tests from Phase 67/68" (named in the parent task's own prompt) refers to a specific, existing test file — this research found no file matching that description by name | Seam Map §8 | If such a test exists under a different name and is not re-checked, a prose change to either SKILL.md could break it unnoticed |
| A3 | `skip`/`drop`/`retry` verbs are NOT wired to any `held_queue.record_verb(..., held_queue.VERB_SKIP/VERB_DROP/VERB_RETRY, ...)` call site in `review-triage/SKILL.md`'s own text — only `create` (step 4c) has a visible call. Inferred from reading the file's steps 1-8 in full, not from an executed test | Seam Map §1 | If wrong (the call exists elsewhere, e.g. folded into prose this research read past), the plan may add a duplicate or redundant wiring for `skip`/`drop`/`retry` |

**If this table is short:** most claims in this research were verified by direct file read or
grep this session (file:line cited throughout); these three are the ones resting on absence
of a match (no test found, no call site found) rather than a positive read of the relevant
code path succeeding or failing.

## Open Questions

1. **Is `held_entries=`/`current_outcomes=` wiring into `watch.resume_or_disclose` in scope
   for this phase?**
   - What we know: `enrich-before-ingest/SKILL.md:1197` calls `resume_or_disclose(rows)` with
     neither keyword argument, so `run_manifest.rows_to_resume`'s `confidence_held` branch
     always takes its `entry is None` fallback in production today, independent of the D-71-04
     rekey (Seam Map §2).
   - What's unclear: whether making the phase's cross-run promise fully true (a settled held
     row is never silently re-resumed) requires wiring this call site in the SAME phase, or
     whether it is intentionally deferred as a separate gap.
   - Recommendation: decide explicitly in the plan; do not let it default to "unwired" by
     omission a second time.

2. **Which of the three CSV-design options closes the gate on the Jimmy Busteed case?**
   - What we know: neither of D-71-01's two named stamp sources (step-2 company-row confirm,
     same-run company create) covers a contact-only CSV where the target person's company has
     no company row and was not created this run; a third source (an `auto_matched`/approved-
     `proposed` row at the same domain, from step 2's own contact match) does cover it with
     the least new plumbing (Seam Map §4).
   - What's unclear: which option the plan picks, and therefore what the gate's own CSV must
     contain.
   - Recommendation: pick option (c) (add a second, already-in-HubSpot ATC contact row to the
     gate's CSV) unless the plan has a reason to wire the dormant same-run-company-create pair
     for other reasons — it is the lightest lift and requires no new SKILL.md wiring beyond
     collecting a set at step 2.

3. **What signal does `load()`/`classify_read()` use to detect a "legacy" (pre-rekey)
   document, per D-71-05?**
   - What we know: today's `_validated_entries()` has no key-shape or stamp-presence check at
     all — a positional `"row-1"` key and a future stable key both validate identically
     (Seam Map §7).
   - What's unclear: whether the plan detects legacy by key pattern (`row-\d+`) or by the
     absence of the new stamp field on every entry, or some other signal.
   - Recommendation: CONTEXT.md leaves this as Claude's Discretion — pick one, implement it
     explicitly (it does not fall out of existing code), and pin it with a RED-first test per
     the Validation Architecture section.

4. **Is the forbidden-name-marker fold's scope the full nine-module set, or `held_queue.py` +
   `suggestion_declines.py` only, for this phase?**
   - What we know: the folded todo's `files:` list names seven modules (not including
     `match_state.py`/`match_handoff.py`, added by later quick tasks per
     `test_forbidden_marker_parity.py`'s own header comment); D-69-01's discipline says all
     copies should move together when the matcher shape changes.
   - What's unclear: whether landing the fix in all nine in one plan is proportionate to this
     phase's own boundary, versus fixing the two this phase's own code path actually touches
     (`held_queue.py`, `suggestion_declines.py`) and leaving the rest to the todo's own
     original scope.
   - Recommendation: at minimum, fix `held_queue.py`'s entries-map key (this phase's own
     defect) and `suggestion_declines.py` (already-live, same todo, same shared discipline);
     treat the remaining modules as the todo's pre-existing scope unless a plan reviewer
     argues otherwise.

## Sources

### Primary (HIGH confidence — read/grepped this session)
- `operator-claude-plugin/scripts/held_queue.py` (full file read)
- `operator-claude-plugin/scripts/run_manifest.py` (`rows_to_resume`, lines 362-461)
- `operator-claude-plugin/scripts/preingest.py` (`index_company_dependencies`,
  `assign_same_run_company_ids`, `hold_ingest_no_company`, `build_rows_spec`, `Outcome`
  dataclass, `parse_outcome`, `classify_matches`, `CANDIDATE_KEYS`)
- `n8n/code/matchProposal.js` (grepped for `company_match`/`company_id` — confirmed absent
  from the propose lane's own response shape)
- `operator-claude-plugin/scripts/suggestion_declines.py`, `suggest_contacts.py`
  (`name_key`, lines 161-173)
- `operator-claude-plugin/scripts/watch.py` (`resume_or_disclose`, lines 724-757)
- `operator-claude-plugin/scripts/company_domain.py`
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` (steps 2, 5, 6, 8)
- `operator-claude-plugin/skills/review-triage/SKILL.md` (steps 1-6, full)
- `config/column_mapping.yaml`, `n8n/code/columnMap.js`
- `operator-claude-plugin/tests/test_forbidden_marker_parity.py`,
  `test_held_queue.py`, `test_held_queue_facets.py`, `test_review_triage_facets.py`,
  `test_held_facet_render_composition.py`, `test_skill_sequence_coverage.py`,
  `test_unattended_pair_composition.py`, `test_todo_triage.py`
- `operator-claude-plugin/.claude-plugin/plugin.json`, `CHANGELOG.md`
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` §1d
- `.planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-CONTEXT.md`,
  `71-DISCUSSION-LOG.md`
- Live pytest run this session: `.venv/bin/python -m pytest -q -p no:cacheprovider
  operator-claude-plugin/tests/` → 3006 passed, 5 skipped

No web research, no external documentation lookup, and no package-legitimacy check were
needed — this phase has zero external dependencies.

## Metadata

**Confidence breakdown:**
- Seam map (readers/writers/keys): HIGH — every claim is a direct file read or grep this
  session, with file:line citations.
- The stamp-source gap (§4) and the acceptance-path mismatch: HIGH confidence that the gap
  exists (grep found zero call sites), but the RECOMMENDED fix (wire step 2 to collect
  confirmed domains explicitly; build the gate CSV with a company row) is a judgment call for
  the planner, not a verified requirement.
- Forbidden-marker collision (Pitfall 1): HIGH confidence in the mechanism (code read
  directly); the claim that `suggestion_declines.py` ALREADY fails live for a name like
  "Grant" is inferred from reading `entry_key`/`first_refusal`/`save()` together, not from an
  executed failing test — treat the "already live" framing as strongly-supported-but-not-
  executed until the plan's RED-first test proves it.

**Research date:** 2026-09-12
**Valid until:** This is internal-repo state, not a third-party API — valid until the next
commit touches any of the files in the Sources list above. Re-grep before planning if more
than a few days pass or if a quick task lands in the interim.
