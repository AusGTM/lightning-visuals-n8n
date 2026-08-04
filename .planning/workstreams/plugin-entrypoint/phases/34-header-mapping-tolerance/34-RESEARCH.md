# Phase 34: Header Mapping Tolerance - Research

**Researched:** 2026-08-04
**Domain:** CSV/XLSX header aliasing (backend YAML+JS alias table) and a client-side
suggest-and-confirm correction layer over an existing read-only preview pipeline
**Confidence:** HIGH (every claim below is grounded in a file this session opened, not
training-data recall — this is a small, fully-vendored codebase, not a library-research phase)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Half A — widen the alias table (deterministic, backend-owned).** Add the unambiguous
near-misses: `e-mail address`, `org.`, `linkedin profile`, and consider `company name`,
`work email`, `mobile phone`, `e-mail address:`. These are lookups, not judgment. This is a
BACKEND change — two files must move together: `config/column_mapping.yaml` (repo copy AND
`operator-claude-plugin/config/column_mapping.yaml`, pinned byte-identical by
`test_column_mapping_shipped.py`) and `n8n/code/columnMap.js` (the backend's own alias map).
The two alias sets agree today by hand, not by construction — `build_cloud_workflows.py` does
NOT generate the JS from the YAML. Widening one without the other makes the preview lie about
the backend. Add a test pinning the YAML alias map equal to `columnMap.js`'s before changing
either — that test is the real deliverable of Half A. Then rebuild workflows, disarmed
redeploy + bounce every active workflow.

**Half B — suggest-and-confirm for the genuine tail (client).** Modelled explicitly on Phase
31's `_hintLabels` in `n8n/code/hubspotEnums.js` ("MESSAGE HINT ONLY … Never consulted by
`normalizeEnumValue`; only used to make the refusal sentence actionable"). Same rule one layer
up: fuzzy suggests, human decides, the deterministic engine executes. Operator confirms each
non-exact match — no silent renames, ever. After correction, re-preview so the operator sees
the real mapping prediction before approving. The client corrects the header row of the file it
sends; it does NOT map data. The backend's `Map Columns` remains the single authority.

**What Half B must REFUSE, not guess:** `Ph.` is the cautionary case, not the easy one — it
could plausibly be a photo column; silently guessing puts image URLs into a phone field.
`Full Name` is not a header problem — splitting it is a data transform, and there is
deliberately no name-splitter anywhere in this system. Say so plainly; do not offer a split
that handles "van der Berg" or "Maria de los Santos" badly. A refusal that names the reason
beats a guess.

**The scope amendment — required, not optional.** Record as entry 6 in STATE.md's "Accepted
requirement amendments" table, worded precisely: *"Header-alias suggestion with per-header
operator confirmation is permitted in the client. Silent client-side column mapping remains
excluded. The backend's `Map Columns` stays the single authority on what a header means; the
client only helps the operator produce a file the backend can read, and never rewrites a
header without an explicit yes."*

**Non-negotiables (from CONTEXT.md §5):**
1. Pin behaviour at the layer the operator reaches — drive the CLI as a subprocess against an
   isolated plugin root; unit tests only for pure logic. Harness to reuse:
   `tests/test_config_gate.py::_run_cli` (takes `env=`, fake `HOME`).
2. Never fix a test by making its premise false.
3. Red-check every new test — revert the fix, confirm it fails, restore.
4. Commit explicit paths only. Never `git commit -a`.
5. Never touch `~/.claude/plugins/` in tests or scripts.
6. Release checklist: bump `.claude-plugin/plugin.json` in the SAME commit as the CHANGELOG
   cut → push → refresh the marketplace clone.

**Backend redeploy ceremony (Half A only, CONTEXT.md §6):**
```bash
.venv/bin/python scripts/build_cloud_workflows.py
DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('.env'); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
# BOUNCE every active workflow — deploy PUTs but never activates; n8n serves the pre-PUT
# body until a deactivate→activate cycle. (4 active; LV Review Decision stays inactive.)
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('.env'); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```
No arming is needed for this phase — header aliases are not a write gate.

**Definition of done (CONTEXT.md §8):**
1. `e-mail address`, `org.`, `linkedin profile` map, in both YAML and `columnMap.js`, pinned
   equal by a test.
2. `tests/samples/22-messy-headers.csv` previews with those headers mapping; `Ph.` and
   `Full Name` are handled by Half B (suggest / honest refusal), not silently.
3. A test proving no header is rewritten without confirmation.
4. STATE.md amendment #6 recorded.
5. UAT 2.2 re-walked by the operator and re-marked — do not flip it to PASS in code/research.
6. Suites green, plugin version bumped with the CHANGELOG cut, clone refreshed.

**Test commands (exact forms — alternatives are broken here):**
```bash
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q   # 960 passed, 5 skipped
.venv/bin/python -m pytest -q                                  # 1841 passed, 6 skipped
node --test tests/n8n/*.test.mjs                                # 550 pass (FILE glob only)
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json             # must be 0
```

### Claude's Discretion

- Exact `difflib` cutoff value and whether to widen the candidate set beyond the 7 canonical
  props (CONTEXT.md names the mechanism's shape — fuzzy suggest, human confirm — but not the
  numeric cutoff or the precise refusal-shape allowlist for name-splitting headers).
- Whether `company name`, `work email`, `mobile phone`, `e-mail address:` (CONTEXT.md's
  "consider" list) land in Half A (deterministic) or are left to Half B (suggest-and-confirm).
- Exact module/function names and file layout for the new client-side suggestion code, so
  long as it never adds fuzzy logic inside `preview.py`'s `label_headers()` and never performs
  canonical-prop row mapping (both explicitly excluded by existing code comments and
  REQUIREMENTS.md's Out of Scope line respectively).
- SKILL.md authoring choice of exactly where the per-header confirmation loop sits relative to
  the existing preview render (see Open Question 1).

### Deferred Ideas (OUT OF SCOPE)

- `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path` — do not absorb into this phase.
- `2026-08-04-enrichment-throughput-ceiling` — do not absorb into this phase.
- `2026-08-03-sweep-lookback-has-no-time-window` — do not absorb into this phase.
- RB-10 leftovers (stale credential copies in `0.1.0`/`0.6.1`) — do not absorb into this phase.
- Any full mapping/normalization/verification/dedupe re-implementation in the client —
  permanently out of scope per REQUIREMENTS.md, not just deferred for this phase.
- Any fuzzy-matching **mapping** mechanism (as opposed to a message-hint/suggestion mechanism)
  — explicitly deferred per 31-CONTEXT.md's "Deferred Ideas" precedent, which this phase's
  Half B is designed to stay on the correct side of, not reopen.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-02 | Operator can point the plugin at a CSV or XLSX file and have its rows read without pre-cleaning the headers | Half A widens the deterministic alias table so more real-world headers read cleanly with zero operator action; Half B covers the remaining tail conversationally. Grounded by the alias-parity test already covering Half A structurally (any widened YAML key is automatically walked through `mapRow`) |
| INGEST-06 | Operator gets a clear, actionable error when an input is unreadable, empty, or unsupported — never a silent drop | Extended here to header-level: `Full Name` and any unresolvable header must get a named reason (Pitfall 1's refusal pre-check), never a silent drop from `label_headers()` alone |
| STRUCT-01 | Extracted rows are emitted over the canonical contact props only, so the existing n8n `Map Columns` node accepts them unchanged | Pattern 3 explicitly restricts the new writer to a header-string swap only — no row restructuring, no canonical-prop value writing, preserving the existing invariant `write_dispatch_csv()` enforces structurally for the extraction path |
| STRUCT-04 | Extraction never invents field values — absent data stays absent; an ambiguous value is flagged for operator confirmation, not resolved by guessing | This is the core of Half B: `Ph.` must be suggested-and-confirmed, never auto-resolved (CONTEXT.md's explicit photo-column caution) — Pitfall 1/2 give the concrete mechanism and its measured limits |
| PREVIEW-01 | Operator sees the exact structured payload and row count before anything is sent, and must approve it | Pattern 1 + Pitfall 3 establish that re-preview must run against the corrected file's real on-disk path (not an in-memory representation) so what's approved is provably what gets sent |
</phase_requirements>

## Summary

This phase has two independent halves living in different runtimes, and the research below
is organized the same way. **Half A** (backend) is a pure data-table edit to two
hand-maintained files (`config/column_mapping.yaml` and `n8n/code/columnMap.js`) that are
proven identical today only by eyeballing — the alias-parity guard test named in the task
brief (`tests/n8n/columnMapAliasParity.test.mjs`, commit `634fe31`) already exists and
passing it is what proves both files moved together. **Half B** (client) is new code: a
suggest-and-confirm layer that sits **between** the existing file-read step and the existing
preview step, never inside either. The single most load-bearing finding from this session is
a code comment already in the file the new code must sit beside:

> `preview.py:39-44` — *"Do not improve on this with fuzzy matching — a smarter matcher would
> mislabel a column the backend really does map, which is the one thing the preview must
> never do."*

This means Half B **cannot** be built by adding fuzzy logic to `preview.py`'s
`label_headers()`. It has to be a new, separate module that runs *before* `build_preview()`
is ever called, proposes corrections, gets them confirmed conversationally, physically
rewrites the header row into a **new** file, and only then hands that new file's path to the
unmodified `preview.py`/`dispatch.py` pair — the same two functions, unmodified, now pointed
at a different path.

The second major finding, produced by actually running `difflib.SequenceMatcher` against this
repo's real alias table (not assumed from memory), is that a naive similarity cutoff **cannot
distinguish `Full Name` from a legitimate single-field alias** — `"full name"` scores `0.714`
against `"fname"`, higher than `"ph."` scores (`0.5`) against its own correct answer,
`"phone"`. Any cutoff generous enough to catch the UAT criterion's own `Ph.` example will also
propose `firstname`/`lastname` for `Full Name` — a suggestion that looks plausible, invites a
wrong confirmation, and silently drops half the name. This is exactly why `34-CONTEXT.md`
insists `Full Name` be *refused with its reason named*, not merely left to the fuzzy
suggester and an alert operator: the plan needs a **dedicated pre-check that refuses
name-splitting-shaped headers before fuzzy matching ever sees them**, not a cutoff tuned to
avoid them.

**Primary recommendation:** Build Half A as a data-only change gated by the already-existing
alias-parity test plus the redeploy-and-bounce ceremony in `34-CONTEXT.md` §6 (verified
below against the actual scripts). Build Half B as one new module
(`header_suggest.py` or similar) using `difflib.get_close_matches` at `cutoff=0.5` over the
**canonical prop set only** (not raw alias keys, which would surface `columnMap.js`
implementation detail like `"tel"` to the operator), with an explicit pre-check that refuses
any header matching a name-splitting shape before fuzzy matching runs, and a corrected-file
writer that reuses the exact `csv.writer` pattern `extraction.py:514-542`
(`write_dispatch_csv`) already uses to produce a scratch CSV that `preview.py`/`dispatch.py`
then both consume unmodified.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Alias widening (`e-mail address`, `org.`, `linkedin profile`) | Backend (n8n `Map Columns` + build step) | Client (`preview.py` display lookup) | The backend is the single mapping authority (REQUIREMENTS.md "Scope anchor"); the client only *predicts* what the backend will do |
| Fuzzy header suggestion | Client (new module, plugin-local) | — | Must never touch the backend's mapping logic (REQUIREMENTS.md Out of Scope: "Re-implementing column mapping ... must stay single-source-of-truth"); this is a **suggestion**, not a mapping — the amendment CONTEXT.md §4 requires records this distinction explicitly |
| Header-row rewrite before send | Client (new module) | — | Correcting the *file the operator sends*, not adding a second mapping layer — the backend's `Map Columns` node still does the only real mapping, now against a corrected header string it already recognizes |
| Per-header operator confirmation | Client (conversational, SKILL.md-driven) | — | No code-enforced gate is needed here (unlike dispatch arming) because nothing leaves the machine until dispatch; the existing preview-approval step (SKILL.md step 4) is the natural confirmation surface to extend |
| Re-preview after correction | Client (`preview.py`, unmodified) | — | Reused as-is against the corrected file's new path — this is why "one point of correction" matters: `preview.py` must never see two different representations of the same batch |

## Standard Stack

No new dependency. `difflib` is stdlib and already present in the sandbox's own Python
(`.venv/bin/python3`), confirmed by running it directly this session — no `pip install`
needed, no version to pin.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `difflib.get_close_matches` | `rapidfuzz` / `fuzzywuzzy` (new pip dependency) | Would add a dependency for a 7-candidate lookup table this small — ladder rung 3 (stdlib) wins outright; no installed alternative exists in this repo already (`[VERIFIED: no difflib/fuzzy usage outside .venv site-packages]` — grep run this session found zero first-party usage) |
| Candidate set = alias keys (25 entries) | Candidate set = canonical props only (7 entries) | Alias keys leak backend implementation detail (`"tel"`, `"li"`, `"fname"`) into an operator-facing suggestion; canonical props (`email`, `firstname`, `lastname`, `jobtitle`, `linkedin_url`, `phone`, `company`) are what the operator actually needs to hear, and restricting to them also removes some (not all — see Pitfall 1) false positives |

**No installation step required for this phase.**

**Version verification:** N/A — stdlib only, no package to check against a registry.

## Package Legitimacy Audit

No external packages are introduced by this phase. `difflib` and `csv` are Python stdlib;
`yaml` (PyYAML) is an existing dependency already imported by `preview.py:81`. This section is
not applicable.

## Architecture Patterns

### System Architecture Diagram

```
Operator attaches/@mentions a spreadsheet
        │
        ▼
tabular.read_table(path)  ──────────────────────────────────────────────┐  (unchanged,
        │  headers, rows                                                │   verbatim read,
        ▼                                                                │   tabular.py:19-53)
Half A: exact alias lookup (preview.label_headers, unchanged)            │
        │  header_labels: [{header, canonical, dropped}]                │
        ▼                                                                │
  ── any header still `dropped: true`? ──                               │
        │ no                    │ yes                                   │
        ▼                       ▼                                       │
  build_preview()      NEW: header_suggest.py                           │
  (unchanged)           for each dropped header:                        │
        │                  - refuse-shape check (Full Name etc) first   │
        │                  - difflib.get_close_matches(header,          │
        │                      canonical_props, n=1, cutoff=0.5)        │
        │                  - if a match: propose it, else: leave dropped│
        │               skill renders one confirmation turn per header  │
        │               (mirrors SKILL.md step 4's existing approval    │
        │                idiom — see Pattern 2)                         │
        │                       │                                      │
        │                       ▼                                      │
        │               operator confirms / declines, per header       │
        │                       │                                      │
        │                       ▼                                      │
        │               NEW: write corrected file to SCRATCH_DIR        │
        │               (same dir + same csv.writer idiom as            │
        │                extraction.write_dispatch_csv, extraction.py:  │
        │                514-542) — ONE write, header row only changes  │
        │                       │                                      │
        │                       ▼                                      │
        │               build_preview(corrected_path)  ← RE-preview,   │
        │◄──────────────────────┘  same function, new path              │
        ▼
  operator approves (SKILL.md step 4, unchanged)
        ▼
  dispatch.dispatch(SAME path preview.py just used, armed, config)
        │  (dispatch.py:26-57, unchanged — to_csv_bytes() re-reads
        │   the corrected file's bytes from disk)
        ▼
  POST hubspot/contact-upload  →  n8n Map Columns (deterministic, Half A widened)
```

### Recommended Project Structure

```
operator-claude-plugin/scripts/
├── preview.py            # unchanged — label_headers stays fuzzy-free (its own comment forbids it)
├── tabular.py             # unchanged — read_table/to_csv_bytes untouched
├── dispatch.py            # unchanged — takes whatever path it's given
├── extraction.py          # unchanged — write_dispatch_csv is the pattern to mirror, not import (different input shape: rows-of-dicts vs headers+rows)
└── header_suggest.py       # NEW — the only new module Half B needs
    - REFUSE_SHAPES / a name-splitting pre-check
    - suggest_headers(headers, canonical_props) -> [{header, suggestion, reason?}]
    - apply_confirmed_corrections(path, confirmed: dict[str,str]) -> corrected_path (str)
```

### Pattern 1: Fuzzy suggestion stays out of `preview.py` by design

**What:** `label_headers()` in `preview.py` performs only an exact, case/whitespace-normalized
alias lookup, and its own docstring/comment explicitly forbids adding fuzzy matching to it
(`preview.py:39-44`, quoted in Summary). `header_suggest.py` must be a separate module that
runs **before** `build_preview()`, never inside it.

**When to use:** Any time a phase is tempted to "improve" `label_headers()` — don't. The
correction has to happen at the file level (rewrite the header row), not inside the labeling
function, because the labeling function's contract (display-only, byte-identity of the source
file preserved) is pinned by `test_column_mapping_shipped.py` and the module's own
`resolve_mapping_path()` docstring (`preview.py:1-13`: *"never feeds it anything derived from
the mapping"*).

**Example (existing code establishing the constraint — read, not modified):**
```python
# preview.py:39-44
def _normalize_header(header: str) -> str:
    """Mirror Map Columns' own rule exactly (see config/column_mapping.yaml's own
    comment): strip, collapse internal whitespace, lowercase. Do not improve on this with
    fuzzy matching — a smarter matcher would mislabel a column the backend really does
    map, which is the one thing the preview must never do."""
    return re.sub(r"\s+", " ", header.strip()).lower()
```

### Pattern 2: Reuse the existing preview-approval turn, don't invent a second confirmation mechanism

**What:** This plugin has exactly two existing confirmation idioms:
1. **Dispatch arming** — binary, session-scoped, code-enforced (`dispatch(..., armed, ...)`
   has no default; `dispatch.py:26-36`). Wrong shape for this: Half B isn't a send/no-send
   toggle, it's N independent per-header yes/no decisions before a file is even built.
2. **Control-action confirmation** — "shows exactly what it would write and requires explicit
   confirmation... one yes, one change" (`skills/backend-control/SKILL.md:20,68,93`). Also the
   wrong weight: that idiom exists because `CONTROL-05` mutates a **live backend workflow**
   and needs a post-mutation read-back verification (`CONTROL-06`). Half B never touches the
   backend — it only rewrites a local scratch file, so the heavier round-trip machinery in
   `n8n_control.py`/`n8n_arming.py` is unneeded ceremony here.

The right-sized existing idiom is the **preview-approval step itself**
(`skills/contact-upload/SKILL.md` step 4: *"Ask for approval. If the operator declines, STOP
here"*), extended with one confirmation turn per suggested header, before that step. This is a
SKILL.md-authored conversational pattern, not a new code-enforced gate — matches CONTEXT.md
§3's own framing ("Operator confirms each non-exact match. No silent renames, ever") which is
worded as an instruction to Claude, the same register as the existing step 4 text.

**When to use:** Any Half-B suggestion. No new Python-level "confirmation" object/state is
needed; the confirmed set is just a `dict[str, str]` (source header → chosen canonical prop)
Claude assembles conversationally and passes into `apply_confirmed_corrections()`.

### Pattern 3: One write point for the corrected file, mirroring `extraction.write_dispatch_csv`

**What:** `extraction.py:514-542`'s `write_dispatch_csv()` is the only place in this codebase
that already writes a header+rows CSV under the `SCRATCH_DIR` convention
(`extraction.py:71`: `SCRATCH_DIR = Path(__file__).resolve().parent.parent / "scratch"`). It
takes a different input shape (list of flat dicts, one row = one canonical-prop dict) than
Half B needs (headers list + a raw rows-of-lists table from `tabular.read_table()`, with only
the header row's *strings* changing, not restructuring into canonical-prop dicts — Half B must
NOT do canonical mapping, only header-string correction). Do not import
`write_dispatch_csv()` directly; write a new, smaller function in `header_suggest.py` that
takes the exact `(headers, rows)` tuple `tabular.read_table()` returns, replaces only the
confirmed header strings, and writes via the same `csv.writer` pattern into the same
`SCRATCH_DIR`.

**Critical gotcha this pattern must respect** — see Pitfall 1 below: `tabular.to_csv_bytes()`
for a `.csv` source does **not** reconstruct from `read_table()`'s parsed rows; it returns
`path.read_bytes()` verbatim (`tabular.py:56-63`). This means the corrected file must be a
**real file on disk** that both `preview.py` and `dispatch.py` are then pointed at by path —
there is no way to hand dispatch an in-memory corrected header without writing it out first,
because dispatch's CSV path re-reads raw bytes from whatever path it's given.

**Example (the existing pattern to mirror, not the code to import):**
```python
# extraction.py:514-542 — the pattern (csv.writer, SCRATCH_DIR, header row + str/empty cells)
def write_dispatch_csv(rows, out_path, mapping_path=None) -> None:
    header = canonical_props(mapping_path)
    allowed = set(header)
    for i, row in enumerate(rows):
        extra = sorted(set(row.keys()) - allowed)
        if extra:
            raise ExtractionError("non_canonical_key_in_row", ...)
    out_path = Path(out_path)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if row.get(col) is None else row.get(col) for col in header])
```

A Half-B equivalent (header-row-only correction, no canonical restructuring) would look like:
```python
# header_suggest.py — proposed shape, NOT existing code
def apply_confirmed_corrections(path, confirmed: dict[str, str], scratch_dir=SCRATCH_DIR) -> str:
    """confirmed maps ORIGINAL header string -> the corrected header string the operator
    approved (e.g. {"Ph.": "phone"}). Headers not in `confirmed` pass through unchanged —
    this function corrects header text only; it never restructures rows or maps values."""
    headers, rows = tabular.read_table(path)
    corrected = [confirmed.get(h, h) for h in headers]
    out_path = scratch_dir / f"corrected-{Path(path).stem}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(corrected)
        writer.writerows(rows)
    return str(out_path)
```

### Anti-Patterns to Avoid

- **Adding a fuzzy-match branch inside `label_headers()`:** Forbidden by the function's own
  comment (`preview.py:39-44`). Keep suggestion logic in a separate module that runs earlier.
- **Suggesting against the raw alias-key set (25 entries) instead of canonical props (7):**
  Surfaces backend implementation detail (`"tel"`, `"li"`, `"fname"`) as if it were a target
  the operator should recognize; it isn't — the operator only ever sees canonical props in the
  preview (`header_labels`'s `canonical` field is always one of the 7).
- **Letting fuzzy matching decide `Full Name`:** Measured this session — `"full name"` scores
  `0.714` against `"fname"` (higher than `"ph."`'s own correct match). A cutoff loose enough
  to catch `Ph.` will also propose a wrong, plausible-looking split for `Full Name`. Needs an
  explicit refusal pre-check, not cutoff tuning (see Pitfall 1).
- **Mapping data in the client (Half B doing more than a header-string swap):** REQUIREMENTS.md
  Out of Scope line and CONTEXT.md §4's required amendment both draw this line explicitly —
  the client corrects the *header row of the file it sends*; it must never write per-row
  canonical-prop values itself, which would fork a second mapping authority.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Header-to-canonical-prop similarity scoring | A custom token-overlap scorer (like `hubspotEnums.js`'s `_tokenize`/`_hintLabels`, which is JS and exists for a 148-value enum problem) | `difflib.get_close_matches` / `difflib.SequenceMatcher` (Python stdlib, already used elsewhere in this Python ecosystem via dependencies — `click`, `pip` — though not yet first-party in this repo) | 7 candidates is too small a problem to justify porting or reimplementing the JS token-overlap approach; stdlib ratio-based matching is adequate and requires zero new code to maintain |
| Name splitting ("Full Name" → firstname/lastname) | A name-parsing heuristic (splitting on whitespace, handling "van der Berg", "Maria de los Santos") | Nothing — refuse, name the reason | CONTEXT.md §3 states this explicitly: "there is deliberately no name-splitter anywhere in this system." Building one now reopens a decision already closed for `hubspotEnums.js`'s enum-mapping precedent (31-CONTEXT.md "no full mapping layer... judgment, not lookup") |
| Corrected-file writer | A generic "row transform" abstraction | The narrow header-swap function shown in Pattern 3 | `write_dispatch_csv()` already proves the narrow, single-purpose function is this codebase's convention over a generic transformer — matches existing style, smaller diff |

**Key insight:** every piece of "don't hand-roll" guidance in this phase reduces to the same
rule already established by `hubspotEnums.js`'s Phase-31 precedent: *fuzzy matching is a
message-hint mechanism, never a mapping mechanism.* Half B is that same rule one layer up
(headers instead of enum values), and the codebase already contains a worked, tested example
of exactly how far to take it (`_hintLabels`, `n8n/code/hubspotEnums.js:39-59`) and exactly
where to stop (`normalizeEnumValue` never consults it, `hubspotEnums.js:96` area).

## Common Pitfalls

### Pitfall 1: A single similarity cutoff cannot separate `Ph.`→phone from `Full Name`→(wrong single field)

**What goes wrong:** Tuning `difflib`'s cutoff loose enough to surface the UAT-named example
(`Ph.` → `phone`, ratio `0.5`) also surfaces a wrong, plausible-looking suggestion for
`Full Name` (→ `fname`/`lastname`, ratio `0.714` — `[VERIFIED: measured this session against
config/column_mapping.yaml's real alias table via difflib.SequenceMatcher]`). The `Full Name`
suggestion is worse than a false positive on an obviously-irrelevant column (see Pitfall 2)
because it is *directionally correct* (Full Name genuinely relates to name fields) while being
*factually wrong* (mapping it to a single field silently discards the other name component) —
exactly the kind of plausible-but-wrong suggestion an operator is most likely to confirm
without reading closely.

**Why it happens:** Similarity scoring measures string closeness, not semantic correctness.
`"full name"` and `"fname"` share `f`, `n`, `a`, `m`, `e` in similar sequence; the scorer has
no concept that a "full name" header structurally cannot resolve to one of two split fields.

**How to avoid:** A dedicated pre-check (a small allowlist of name-splitting shapes: header
normalizes to `"full name"`, `"name"`, `"contact name"`, or similar — exact set is a planning
decision, not a research one) must run **before** fuzzy matching and produce the refusal
CONTEXT.md §3 requires, verbatim in spirit: *"there is no name-splitter... say so plainly."*
Only headers that pass the pre-check should ever reach `difflib.get_close_matches`.

**Warning signs:** If a test asserts `Full Name` produces *any* suggestion (even one the
operator could decline), that test has the wrong shape — CONTEXT.md's definition of done
(§8.2) is explicit that `Full Name` gets a refusal, not a suggest-and-confirm turn.

### Pitfall 2: `"Notes"` scores identically to `"Ph."` against the canonical-prop candidate set

**What goes wrong:** `[VERIFIED: measured this session]` — restricting the candidate set to
the 7 canonical props, `"notes"` scores `0.462` against `"jobtitle"`, below a `0.5` cutoff (no
suggestion fires) — but with the fuller alias-key candidate set, `"notes"` scores `0.5`
against `"tel"`, tied with `"ph."`'s own correct match. If the candidate set is not restricted
to canonical props (see Standard Stack "Alternatives Considered"), a genuinely irrelevant
free-text column like `Notes` will get an operator-facing suggestion.

**Why it happens:** Alias keys include short/generic-looking strings (`"tel"`, `"li"`) that
sit closer to arbitrary short headers in edit-distance space than the canonical prop names do.

**How to avoid:** Restrict the fuzzy candidate set to the 7 canonical props (already the
recommendation above for a separate reason — not leaking backend implementation detail). This
does not fully eliminate spurious suggestions (a `Notes`-shaped false positive is a lower-harm
category than Pitfall 1's, since the operator can just decline it — no data loss risk, one
extra confirmation turn), but it removes the worst offenders.

**Warning signs:** A suggestion firing for a header that's clearly free text (`Notes`,
`Comments`, `Misc`) — worth a UAT check but not a hard test assertion, since "declines
harmlessly" is an acceptable outcome for this category, unlike Pitfall 1.

### Pitfall 3: `tabular.to_csv_bytes()` does not reconstruct from parsed rows for CSV sources

**What goes wrong:** A caller might assume "correct the headers in the parsed row list,
then dispatch as normal" — but `dispatch.py:38` calls `tabular.to_csv_bytes(file_path)`,
which for a `.csv` extension is `path.read_bytes()` — the **original file's raw bytes**, not a
re-serialization of anything `read_table()` returned (`tabular.py:56-63`,
`[VERIFIED: tabular.py:62-63]` `"if suffix == '.csv': return path.read_bytes()"`). Correcting
an in-memory header list and handing dispatch the *original* path sends the *uncorrected*
file.

**Why it happens:** `tabular.py`'s own docstring explains the design intent (verbatim
round-trip for CSV, since n8n's `Extract From File` node parses CSV itself) but a reader
skimming only `read_table()` could miss that `to_csv_bytes()` diverges from it for the CSV
branch specifically.

**How to avoid:** The corrected header row must be written to a **new physical file** (Pattern
3), and that new file's path — not the original — must be the single path handed to *both*
`build_preview()` and `dispatch()`. This is also why CONTEXT.md's "correcting the header row"
and "re-preview" instructions in §3 are sequenced the way they are: re-preview has to run
against the corrected path to prove what will actually be sent.

**Warning signs:** A test that patches/mocks `to_csv_bytes` instead of writing a real corrected
file and checking its on-disk bytes would not catch this class of bug — the test needs to
assert on the actual file `dispatch()` reads, mirroring `test_to_csv_bytes_csv_source_is_the_
original_bytes_unchanged` (`operator-claude-plugin/tests/test_dispatch_multipart.py:33-34`),
now pointed at the corrected path.

### Pitfall 4: The YAML/JS alias tables agree "by hand, not by construction"

**What goes wrong:** Editing `config/column_mapping.yaml` alone (or `n8n/code/columnMap.js`
alone) makes the client's preview predict a mapping the backend will not actually perform —
`[VERIFIED: scripts/build_cloud_workflows.py:85]` `MAP_COLUMNS = inline("columnMap.js") + ...`
— the build step **inlines** `columnMap.js`'s literal text into the deployed workflow JSON; it
does not generate it from the YAML. There is no single source of truth here structurally, only
by the alias-parity test now pinning them equal.

**Why it happens:** Two hand-maintained files were kept in sync by discipline until this
phase, and 0.7.3 was the first release where the client's preview could even read the YAML at
all (`preview.py:23-27` comment on `PLUGIN_MAPPING_PATH`), making the drift risk newly
visible/consequential.

**How to avoid:** The alias-parity test (`tests/n8n/columnMapAliasParity.test.mjs`, already
built and committed per the task brief — `[VERIFIED: read this file directly this session]`)
must stay green through every edit to either file. It asserts three things: (1) `ALIASES`
deep-equals the YAML's `aliases` key, (2) every YAML key is pre-normalized (lowercase,
whitespace-collapsed), (3) every alias actually round-trips through the real `mapRow()`
lookup. Widen both files in the same commit; run `node --test tests/n8n/*.test.mjs` before
and after.

**Also note:** `operator-claude-plugin/config/column_mapping.yaml` (the shipped copy) must be
re-copied byte-identical from the repo-root copy after editing — `[VERIFIED: diff of the two
files this session returned "Files are identical"]` and
`test_column_mapping_shipped.py:29-39` pins that identity as a test, explicitly warning
*"if this fails, re-copy, do not edit one side."* Three files move together for Half A, not
two: `config/column_mapping.yaml`, `operator-claude-plugin/config/column_mapping.yaml`, and
`n8n/code/columnMap.js`.

### Pitfall 5: A `.env` file's active-workflow count is not provable from the checked-in build artifact

**What goes wrong:** `[VERIFIED: grepped n8n/wf_*_cloud.json this session]` — of the 5
`*_cloud.json` build artifacts, only `wf_review_decision_cloud.json:789` and
`wf_scheduled_maintenance_cloud.json:950` declare an `"active"` key at all (both `false`); the
other three (`backend_status`, `contact_ingest`, `enrichment`) carry no `active` key in the
built JSON. This is consistent with — but does not independently confirm — `34-CONTEXT.md`
§1's claim of "4 active; LV Review Decision is inactive at rest." `deploy_n8n_workflows.py`'s
own docstring states activation is a separate operator step never performed by the deploy
script itself (`"Activation (POST .../activate) is a separate operator-runbook step, not
performed here"`), so the build artifact's `active` field (when present) does not govern live
state either way.

**Why it happens:** PUT-based deploys and activate/deactivate toggles are independent API
calls against independent state; a build artifact is a snapshot of intended node content, not
of live activation status.

**How to avoid:** Do not infer "which workflows to bounce" from the build JSON. Read live
state immediately before the bounce step (the existing `n8n_read.py`/`status.describe_all()`
surface, or the runbook's own read-back script), and treat `34-CONTEXT.md`'s "4 active"
figure as the operator's own live observation to re-confirm at execution time, not a fact
this research independently re-derives.

## Code Examples

### Existing pattern: candidate-set derivation, safe to reuse via the existing function

```python
# preview.py:72-89 — _load_aliases already derives canonical_props from the YAML;
# header_suggest.py should call this (or preview.resolve_mapping_path() +
# preview._load_aliases()) rather than re-parsing the YAML a third time.
def _load_aliases(mapping_path):
    if mapping_path is None:
        return None, None
    mapping_path = Path(mapping_path)
    if not mapping_path.exists():
        return None, None
    try:
        import yaml
        with mapping_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        aliases = dict(data.get("aliases") or {})
        canonical_props = sorted(set(aliases.values()))
        return aliases, canonical_props
    except Exception:
        return None, None
```

### Measured fuzzy-suggestion behavior (this session's actual run, not assumed)

```python
# Ran this session against the real config/column_mapping.yaml — canonical-props-only
# candidate set, difflib.SequenceMatcher, top match per header:
#   'full name' -> [(0.588, 'lastname'), (0.556, 'firstname'), (0.286, 'phone')]
#   'ph.'       -> [(0.5,   'phone'),    (0.2,   'company'),   (0.0,   'linkedin_url')]
#   'org.'      -> [(0.222, 'phone'),    (0.182, 'company'),   (0.167, 'jobtitle')]
#   'notes'     -> [(0.462, 'jobtitle'), (0.4,   'phone'),     (0.308, 'lastname')]
#   'linkedin profile' -> [(0.714, 'linkedin_url'), (0.286, 'email'), (0.25, 'lastname')]
#
# Conclusions a cutoff alone cannot fix:
#  - 'ph.' needs cutoff <= 0.5 to surface 'phone' at all (the UAT-named example).
#  - 'full name' scores HIGHER (0.588) than 'ph.' does (0.5) at that same cutoff —
#    confirms Pitfall 1: a pre-check must exclude name-splitting-shaped headers before
#    fuzzy matching runs; cutoff tuning cannot separate the two cases.
#  - 'org.' scores below any defensible cutoff (0.222 max) — confirms it belongs in
#    Half A (deterministic widening), not Half B; fuzzy alone would leave it unmapped
#    with no suggestion at all, which is worse than today.
```

### Existing test pattern to follow for the corrected file (direct import, not subprocess)

```python
# operator-claude-plugin/tests/test_dispatch_multipart.py:33-34 — the existing pattern
# that a Half-B test should mirror, now against a CORRECTED path:
def test_to_csv_bytes_csv_source_is_the_original_bytes_unchanged(sample_csv):
    assert tabular.to_csv_bytes(str(sample_csv)) == sample_csv.read_bytes()
# A Half-B equivalent: write a corrected file via apply_confirmed_corrections(), then
# assert tabular.to_csv_bytes(corrected_path) == corrected_path.read_bytes() AND that
# the corrected header row — not the original — appears in those bytes.
```

## State of the Art

Not applicable in the conventional sense (no external library/framework churn to track) — the
only "old approach vs current approach" in scope is internal:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `column_mapping.yaml` unpackaged, preview labels always "unavailable" | Shipped inside the plugin package, byte-pinned to the repo copy | `0.7.3` (2026-08-04), `test_column_mapping_shipped.py` | This is *why* UAT 2.2's gap only became visible now — before 0.7.3 the preview could never predict a drop, so the same messy-headers file would have shown "labels unavailable" instead of exposing the alias gap |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cutoff=0.5` and the canonical-props-only candidate set is the right default for `header_suggest.py` | Standard Stack / Pitfall 1/2 | Measured against this repo's real alias table and the actual UAT sample this session, but the exact cutoff is still a planning/product judgment call, not a provably-optimal number — a slightly different cutoff (e.g. 0.45–0.55) would shift which of `notes`/`org.` produce a spurious suggestion. Low risk: any value in that range is survivable because every suggestion still requires operator confirmation (Pitfall 2's harm class), except for the Full Name case which needs a hard pre-check regardless of cutoff (Pitfall 1) |
| A2 | The exact set of headers that should trigger the "no name-splitter" refusal (`full name`, `name`, `contact name`, etc.) | Pitfall 1 / Don't Hand-Roll | This session identified the *mechanism* (a pre-check gate, not cutoff tuning) but did not exhaustively define the allowlist of shapes to refuse — the planner/discuss-phase should confirm the exact set with the operator or scope it to just `"full name"` (the only shape named in both the UAT criterion and CONTEXT.md) |
| A3 | Half A's exact final alias additions beyond the three CONTEXT.md names outright (`e-mail address`, `org.`, `linkedin profile`) — `company name`, `work email`, `mobile phone` are only "considered" in CONTEXT.md §3, not locked | User Constraints / Standard Stack | These three "consider" candidates were measured this session (all resolve cleanly via difflib against existing canonical props: `company name`→`company` 0.6+, `work email`→`email`, `mobile phone`→`mobile`/`phone`) but whether to add them to Half A (deterministic) vs. leave them to Half B (suggest-and-confirm) is a decision CONTEXT.md leaves open — low risk either way since both paths lead to the same eventual mapping, just with or without a confirmation turn |

**If this table is empty:** N/A — see rows above; all are low-risk, bounded judgment calls
already narrowed by measurement, not open technical unknowns.

## Open Questions

1. **Where does the per-header confirmation loop live in SKILL.md — before or interleaved
   with step 3's existing preview render?**
   - What we know: the existing preview step (`skills/contact-upload/SKILL.md` step 3) already
     shows `header_labels` with `dropped: true` flagged per header; Half B needs to intercept
     exactly those dropped headers before offering them to the operator as sendable-or-not.
   - What's unclear: whether the cleanest phrasing is "run preview once, then a
     suggest-and-confirm sub-step only for dropped headers, then re-preview" (three preview.py
     invocations if there are multiple correction rounds) or a single combined
     read-file → suggest → confirm → correct → preview flow that never shows an uncorrected
     preview to the operator at all. Both satisfy CONTEXT.md's "re-preview after correction"
     requirement; this is a SKILL.md authoring decision, not a code architecture one.
   - Recommendation: plan for the simpler flow (suggest before the first preview render, so
     the operator only ever sees one preview — the corrected one) since it avoids showing a
     "6 of 7 headers drop" preview that the operator would find alarming before the fix is
     even offered.

2. **Should the "no header rewritten without confirmation" test (definition-of-done item 3)
   be a subprocess-CLI test (`_run_cli`-style) or a direct-import pytest, given the two
   different existing conventions in this codebase?**
   - What we know: `test_config_gate.py::_run_cli` (`operator-claude-plugin/tests/
     test_config_gate.py:110`) drives `config_gate.py` as a real subprocess against a fake
     `HOME` specifically because that module's behavior depends on OS-level path resolution
     (`Path.home()`) that only diverges correctly at the process boundary. `tabular.py`/
     `dispatch.py`, by contrast, are tested via direct import with a `stub_transport` fixture
     and an autouse `no_network` guard (`test_dispatch_multipart.py`), because their behavior
     is pure-function/pure-logic with no OS-resolution dependency.
   - What's unclear: `header_suggest.py`'s planned shape (Pattern 3) has no `Path.home()` or
     config-resolution dependency — it's pure file I/O against an explicit path, same category
     as `tabular.py`. CONTEXT.md §5.1 says "harness to reuse: `_run_cli`" but that guidance was
     written before this specific module's shape was known.
   - Recommendation: use the direct-import + fixture pattern (`test_dispatch_multipart.py`'s
     style) for `header_suggest.py`'s unit tests, since it matches the module's actual
     dependency profile; reserve `_run_cli` for anything that genuinely resolves config or
     durable paths. State this explicitly in the plan so it isn't silently over- or
     under-applied.

## Environment Availability

Not applicable — this phase adds no new external tool, service, or runtime dependency.
`difflib`, `csv`, and `yaml` are already available in the project's `.venv` (confirmed by
running Python directly against them this session).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python, `operator-claude-plugin/`) + `node --test` (JS, `tests/n8n/`) |
| Config file | none dedicated — plugin tests run from `operator-claude-plugin/`, repo-root tests from repo root; both auto-discovered |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (plugin-only, ~960 baseline) |
| Full suite command | `.venv/bin/python -m pytest -q` (repo-wide, ~1841 baseline) + `node --test tests/n8n/*.test.mjs` (~550 baseline) |

### Phase Requirement → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|-------------|
| INGEST-02 | `E-mail Address`/`org.`/`linkedin profile`-style headers read without pre-cleaning | unit (Half A) | `node --test tests/n8n/columnMapAliasParity.test.mjs` (already green, extend its assertions if new aliases are added — it walks every YAML key through `mapRow`, so a widened YAML is covered automatically) | ✅ exists (`tests/n8n/columnMapAliasParity.test.mjs`) |
| INGEST-06 | Operator gets a clear, actionable message for `Full Name` (refused, reason named) rather than a silent drop or a bad guess | unit (Half B) | new: `.venv/bin/python -m pytest operator-claude-plugin/tests/test_header_suggest.py -x` | ❌ Wave 0 — module and test both new |
| STRUCT-01 | Corrected file still emits canonical-prop-only headers (nothing beyond a header-string swap; no row/value invention) | unit (Half B) | same new test file — assert `apply_confirmed_corrections()` never changes row cell values, only the header row | ❌ Wave 0 |
| STRUCT-04 | Ambiguous header (`Ph.`) flagged for operator confirmation, never resolved by guessing; no header rewritten without an explicit per-header confirmation | unit (Half B) — this is definition-of-done item 3 verbatim | new test asserting `apply_confirmed_corrections()` only rewrites headers present as keys in the `confirmed` dict, and a companion test asserting the suggest step never calls the writer itself (writer takes explicit confirmation input, is never auto-invoked from `suggest_headers()`'s own output) | ❌ Wave 0 |
| PREVIEW-01 | Operator sees the exact structured payload (the corrected file, re-previewed) before anything is sent | integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preview_rendering.py -x` extended with a corrected-path case, or a new test asserting `build_preview(corrected_path)["header_labels"]` shows no `dropped: true` for a header that was confirmed | ❌ Wave 0 (extend existing file) |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (plugin
  suite only — fast, covers everything under `operator-claude-plugin/`)
- **Per wave merge:** full suite per `34-CONTEXT.md` §7's exact commands — all four, in order:
  `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`,
  `.venv/bin/python -m pytest -q`, `node --test tests/n8n/*.test.mjs`,
  `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` (must print `0`)
- **Phase gate:** all four green, plus the alias-parity test specifically re-run after any
  Half A edit (it is the "real deliverable of Half A" per CONTEXT.md §3), plus the disarmed
  redeploy read-back (`verify_live_write_safety.py --expectation disarmed`) after the bounce.

### Wave 0 Gaps

- [ ] `operator-claude-plugin/scripts/header_suggest.py` — does not exist yet; this phase's
      only new source module
- [ ] `operator-claude-plugin/tests/test_header_suggest.py` — covers INGEST-06, STRUCT-01,
      STRUCT-04 (the "no header rewritten without confirmation" property named in CONTEXT.md
      §8 item 3)
- [ ] Extension to `operator-claude-plugin/tests/test_preview_rendering.py` (or a new file) —
      covers PREVIEW-01's re-preview-after-correction case
- [ ] Extension to `tests/n8n/columnMapAliasParity.test.mjs` is **not** required as a new
      file — it already covers any Half A alias widening structurally (it walks every YAML
      key), so Half A needs no new JS test, only the existing one to stay green
- [ ] Framework install: none — pytest and `node --test` are both already the project's
      harnesses, no new install

## Security Domain

`security_enforcement` is not set to `false` in `.planning/config.json` (absent = enabled), so
this section is included, kept proportionate to the phase's actual attack surface (a local
file read/write and a conversational suggestion — no new network egress, no new credential, no
new write to a live system for Half B; Half A's redeploy already goes through the existing
disarmed-by-default write gate).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no | No new auth surface — Half B never touches n8n auth (`webhook_secret`/`n8n_api_key`); Half A's redeploy reuses the existing `ALLOW_N8N_DEPLOY` two-key gate |
| V3 Session Management | no | Conversation-scoped confirmation only, same non-persistence property as the existing dispatch-arming flag (`dispatch.py:26-36` — `armed` is a call argument, never written to disk) |
| V4 Access Control | no | No new privilege boundary; Half B runs entirely client-local |
| V5 Input Validation | yes | The corrected-file writer (Pattern 3) must validate that `confirmed` values are drawn only from `canonical_props()` — never an arbitrary operator-typed string written straight into the header row, which would let a malformed or malicious canonical-looking string reach the backend's `Map Columns` node under a false label. Mirrors `extraction.py:514-542`'s own `extra = sorted(set(row.keys()) - allowed)` guard pattern |
| V6 Cryptography | no | Not applicable — no new secret or crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Operator confirms a wrong suggestion, silently losing data (e.g. `Full Name` → `firstname` drops the surname) | Tampering (of data integrity, not an attacker-driven threat, but the same STRIDE bucket applies to unintentional data corruption via a plausible-looking bad suggestion) | The pre-check refusal in Pitfall 1 — this IS the mitigation; there is no confirmation-UX mitigation that fully substitutes for refusing the suggestion outright, per CONTEXT.md's own reasoning |
| A corrected-file writer accepting an unconstrained target value | Tampering | Validate against `canonical_props()` before writing (V5 row above) |
| Scratch file left on disk after the conversation ends carrying operator's spreadsheet data | Information Disclosure | Existing convention already handles this — `SKILL.md` step 10: *"delete the scratch artifact you wrote once the batch ends"*; `header_suggest.py`'s corrected file should be treated identically (same `SCRATCH_DIR`, same cleanup instruction extended to cover it) |

## Sources

### Primary (HIGH confidence — files opened and read this session)

- `operator-claude-plugin/scripts/preview.py` — `resolve_mapping_path()`, `label_headers()`,
  `_normalize_header()`, `build_preview()`, `build_extracted_preview()`
- `operator-claude-plugin/scripts/tabular.py` — `read_table()`, `to_csv_bytes()`
- `operator-claude-plugin/scripts/dispatch.py` — `dispatch()`, arming contract
- `operator-claude-plugin/scripts/extraction.py` — `write_dispatch_csv()`, `SCRATCH_DIR`
- `config/column_mapping.yaml`, `n8n/code/columnMap.js` — the two alias tables (read in full,
  diffed byte-for-byte against the plugin's shipped copy)
- `n8n/code/hubspotEnums.js` — `_hintLabels()`, `_tokenize()`, `enumRefusalMessage()` (the
  Phase-31 precedent Half B is explicitly modelled on)
- `tests/n8n/columnMapAliasParity.test.mjs` — the already-built alias-parity guard
- `operator-claude-plugin/tests/test_column_mapping_shipped.py` — the two-copy drift guard
- `operator-claude-plugin/tests/test_config_gate.py` — `_run_cli()` signature and rationale
- `operator-claude-plugin/tests/test_dispatch_multipart.py` — the direct-import test
  convention for pure-logic modules
- `operator-claude-plugin/tests/conftest.py` — `sample_csv`, `stub_transport`, `no_network`,
  `fake_config` fixtures
- `operator-claude-plugin/skills/contact-upload/SKILL.md` — the existing preview/approval/
  dispatch conversational flow
- `operator-claude-plugin/skills/backend-control/SKILL.md` — the existing "show diff, one
  yes, one change" confirmation idiom (rejected as too heavy for Half B; documented why)
- `scripts/build_cloud_workflows.py` — `MAP_COLUMNS = inline("columnMap.js") + ...` (line 85)
  confirming no YAML→JS generation exists
- `scripts/deploy_n8n_workflows.py` — docstring confirming activation is a separate step, and
  the `DRY_RUN`/`ALLOW_N8N_DEPLOY` two-key gate CONTEXT.md §6's ceremony relies on
- `scripts/verify_live_write_safety.py` — `--expectation disarmed`/`armed` CLI confirmed to
  exist and match CONTEXT.md §6's read-back command
- `n8n/wf_*_cloud.json` (all 5) — grepped for `"active"` to check Pitfall 5's claim
- `operator-claude-plugin/.claude-plugin/plugin.json`, `operator-claude-plugin/CHANGELOG.md`
  — current version `0.7.3`, release-checklist convention confirmed
- `.planning/workstreams/plugin-entrypoint/phases/34-header-mapping-tolerance/34-CONTEXT.md`
  — the locked decisions this research builds on
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md`,
  `.planning/workstreams/plugin-entrypoint/STATE.md`,
  `.planning/todos/pending/2026-08-04-uat-22-names-aliases-the-mapping-lacks.md`

### Secondary (MEDIUM confidence)

None — no web/docs lookups were needed for this phase; the entire domain is this repo's own
already-vendored code and configuration.

### Tertiary (LOW confidence)

None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib-only, no version to verify against a registry, behavior
  measured directly this session against the repo's real data
- Architecture: HIGH — every file/line cited was opened this session; the "preview stays
  fuzzy-free" constraint is a direct quote from the code, not an inference
- Pitfalls: HIGH — Pitfall 1/2's numbers are measured (`difflib` run live against
  `config/column_mapping.yaml`), not estimated; Pitfall 3/4/5 are quotes/greps from the actual
  files

**Research date:** 2026-08-04
**Valid until:** No expiry driver — this is a closed, fully-vendored codebase with no external
dependency churn risk for this phase; re-verify only if `config/column_mapping.yaml`,
`n8n/code/columnMap.js`, or `preview.py`/`tabular.py`/`dispatch.py` change before planning
executes.
