# Phase 24: Non-Tabular Input Adapters - Research

**Researched:** 2026-07-30
**Domain:** Claude-Skill-driven data extraction (in-session, no API call) + Anthropic native tool mechanics (`web_fetch`, vision) feeding an existing tabular-dispatch shell
**Confidence:** MEDIUM — the extraction/tool mechanics are well-documented (HIGH); the exact runtime surface ("Claude Desktop") the plugin ships into has one open unresolved-upstream question flagged below (MEDIUM/LOW)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Extraction engine**
- **D-01:** Extraction is performed by **Claude in-session, with no Anthropic API call**. The
  `SKILL.md` instructs Claude to read the prose, JSON, fetched page, or image and emit canonical
  rows directly into the conversation. Python's role is narrow: validate row shape, apply the
  identity rule, dedupe, and assemble the payload. — **Reversibility:** costly.
- **D-02:** Consequences of D-01 that the planner must honor: **no Anthropic API key ever enters
  the plugin** (keeps PLUGIN-02's spirit intact even after the Phase 23 amendment), extraction
  costs nothing per batch, and images are read natively rather than base64-shipped. The trade-off
  accepted: extraction quality tracks whatever model runs the session rather than being pinned to
  a version.
- **D-03:** The no-invention guarantee (STRUCT-04) is therefore a **prompt-and-validation
  contract**, not a model property. The skill must state the rule explicitly, and the Python
  validator must reject any row carrying a field the operator's source demonstrably could not
  have supplied where that is checkable. Absent stays absent.

**Provenance**
- **D-04:** Provenance is a **preview-only sidecar, stripped before dispatch**. Each extracted row
  carries a parallel provenance record (which input, which span of text / which image and where on
  it) that renders as extra columns in the preview and is **removed from the POST body**. This
  keeps STRUCT-01 exactly true — n8n receives canonical props only.
- **D-05:** Provenance does **not** persist beyond the session and is **not** written to HubSpot.
  Its audience is the operator deciding whether to approve, at the moment they decide.

**Ambiguity handling**
- **D-06:** Ambiguous values are **collected into a single list presented with the preview** — one
  "needs your eyes" block covering every ambiguous cell in the batch. The operator confirms or
  corrects them in one reply before approving. One interruption per batch, never one per row.
- **D-07:** An unconfirmed ambiguity is **not** silently resolved. If the operator approves without
  addressing it, the affected value stays absent rather than being filled with the model's best
  guess. (Direct consequence of STRUCT-04.)

**Screenshot overlap**
- **D-08:** Duplicate detection across a scrolled screenshot sequence uses **the existing identity
  rule**: same `email`, or same `firstname` + `lastname` + `company`. One dedupe concept across
  the whole system — the same rule n8n applies server-side. *(See Priority Question 4 below for a
  correction to which n8n node actually implements this rule.)*
- **D-09:** Near-duplicates that differ only in a truncated or unreadable field surface as
  **ambiguities** (D-06), not as silent collapses. The operator decides whether two partial
  captures are one person.

### Claude's Discretion
- Foreign-JSON key-translation approach, and how unmappable keys are reported (criterion 2
  requires only that they are reported, not silently dropped).
- Wording and shape of the per-row rejection reasons for identity-rule failures (STRUCT-02).
- How provenance columns are laid out in the preview table.
- Error taxonomy for unreadable / empty / unsupported input (INGEST-06) — the requirement is a
  named error, not a specific naming scheme.
- Whether the URL adapter summarizes the fetched page before extraction or extracts directly.

### Deferred Ideas (OUT OF SCOPE)
- **Persistent provenance / audit archive** — D-05 keeps provenance session-scoped. A durable
  per-batch audit file was considered and deferred; it raises a retention question this milestone
  has not scoped.
- **Pinned-model extraction** — D-01 accepts session-model variance. Revisit if extraction quality
  proves unstable across model versions.
- **Company-object ingestion** — out of milestone (v0.6 is contacts + enrichment triggers only).
- **Automated screenshot capture** — permanently out of scope, not deferred. Explicit exclusion.
- **Cost estimation for extraction** — Phase 25 / PREVIEW-02. D-01 makes extraction free of
  provider and API cost, so the cost guard covers dispatch, not extraction.

**Also binding from Phase 23's CONTEXT.md** (the shell this phase plugs into): D-07 (tabular
pass-through + read-only mapping preview), D-08 (adaptive preview scope, ≤20 rows full / above
that first-10+last-3+counts), D-09 (chat-first markdown table, Artifact on request), D-11
(conversation-only, stateless arming — nothing persisted to disk). Phase 24 adds producers in
front of this shell; it does not alter any of these.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | Paste freeform text and have contact rows extracted | Priority Question 1 (extraction handoff mechanics apply identically to prose) |
| INGEST-03 | Foreign-shaped JSON translated to canonical rows, unmappable keys reported | Priority Question 1 (failure-mode table) + Question 5 (canonical-key diff/report requirement) |
| INGEST-05 | Public URL fetched via native `web_fetch`, robots.txt respected | Priority Question 3 (full tool contract, error taxonomy, fence compliance) |
| INGEST-06 | Unreadable/empty/unsupported input yields a named error, never a silent drop | Priority Question 1 (failure-mode table) + Question 3 (fetch-failed vs. nothing-usable distinction) |
| INGEST-07 | Operator-supplied screenshot(s) yield rows with provenance, no-invention guarantees; scrolled-sequence overlap not duplicated | Priority Question 2 (image reading mechanics, attachment limitation) + Question 4 (dedupe key for overlap) |
| STRUCT-02 | Rows failing the identity rule separated and reported, not sent | Priority Question 4 (exact rule location + semantics + a correction to the CONTEXT's pointer) |
| STRUCT-03 | Extraction records per-row provenance (which input, which span/URL) | Priority Question 1 (handoff design carries provenance alongside each row) + Question 6 (strip point, so provenance exists pre-strip) |
| STRUCT-04 | No invention — absent stays absent; ambiguity flagged, not guessed | Priority Question 1 (structural vs. prompt-contract ceiling) + Pitfall 5 |
</phase_requirements>

## Summary

Phase 24 is not a new pipeline — it is four producers (prose, JSON, URL, screenshots) that all
funnel into Phase 23's existing preview→approve→arm→dispatch shell. The one genuinely new
mechanic is the **extraction handoff**: per D-01, extraction happens inside the live conversation
— Claude itself (the model running the session) reads the source and emits canonical rows as
text/JSON, and a thin Python script only validates and assembles. This is exactly the same
"instructions → model output → script validates" pattern the Agent Skills architecture already
documents (Level 2 instructions drive the model; Level 3 scripts run via bash and only their
*output* re-enters context) — nothing new needs to be invented, but the plan must pin down the
concrete artifact shape (a JSON file on disk, not a chat-parsed blob) so validation is
deterministic and testable.

Two Anthropic-native capabilities do the actual reading: `web_fetch` (URL adapter) and the
model's own multimodal vision (screenshot adapter, and — per Phase 23's still-open D-14 — the
attachment leg of file ingestion generally). Both are well-specified at the API level; what's
harder to pin down is which of those semantics survive into "Claude Desktop" specifically. This
research treats the API-level `web_fetch` contract (robots.txt, error codes, URL-must-already-be-
in-context) as authoritative for **what the tool can do**, and treats a documented, reproduced
Claude-Desktop/Claude-Code limitation — **attached images are visible to the model's vision but
their bytes/path are not exposed to scripts** — as the load-bearing fact for **how the plugin must
be built**: Python must never need image bytes. It only ever needs the JSON rows Claude already
extracted by looking at the image itself.

On the backend-contract side, the identity rule the plugin must mirror locally (STRUCT-02, D-08)
lives in `Map Columns`' `requiredIdentity()` — **not** in `Resolve Identity`/`Merge Contacts` as
the CONTEXT's canonical_refs implies (see Priority Question 4 below for the precise correction).
The canonical prop set to validate against is the 7-key list in `config/column_mapping.yaml`'s
alias targets, and the existing Python mirror (`src/file_loader.py::_has_identity`) has a real,
citable whitespace-handling bug relative to the n8n JS original that the client-side validator
must not inherit.

**Primary recommendation:** Build the extraction handoff as: SKILL.md instructs Claude to read the
source, emit a JSON array of `{row, provenance}` objects to a fixed scratch path (e.g.
`operator-claude-plugin/scripts/.extracted_rows.json`), then invoke
`scripts/validate_rows.py <path>` — a script that (a) rejects the whole batch with an actionable
message if the JSON doesn't parse or isn't a list, (b) strips any key not in the 7-prop canonical
set and reports each dropped key rather than silently discarding it, (c) applies the identity
rule with the same trim-and-presence semantics as `Map Columns`, (d) separates rows failing that
rule into a rejects list with a reason, and (e) leaves provenance columns in a `preview`-scoped
structure that a separate, explicitly-tested strip function removes before the row set is hand
ed to Phase 23's existing CSV-serialize-and-POST path.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reading prose / foreign JSON / fetched page text and emitting canonical rows | Browser/Client (Claude in-session) | — | D-01: no API call, no server-side model; the assistant running the conversation IS the extractor |
| Reading screenshot images and emitting canonical rows | Browser/Client (Claude in-session, multimodal vision) | — | Same as above; images are read natively, never base64-shipped to a script (D-02) |
| Fetching a URL's content | Browser/Client (Anthropic native `web_fetch` tool) | — | Server tool invoked by the running conversation, not a Python HTTP client (mandated by criterion 3) |
| Row-shape validation, canonical-prop enforcement, identity-rule pre-flight | Client (Python script under `operator-claude-plugin/scripts/`) | — | D-01: "Python's role is narrow" — deterministic, testable, no model call |
| Provenance sidecar rendering (preview) and stripping (dispatch) | Client (Python, payload-assembly step) | — | D-04: enforcement site for STRUCT-01 |
| Preview render, arming, CSV serialization, POST | Client (Python + SKILL.md, reused from Phase 23) | — | Phase 24 adds no new choke point |
| Column mapping, phone/email normalization, identity resolution vs. CRM, dedupe, create/update | API/Backend (n8n `hubspot/contact-upload`) | — | Explicitly out of scope for this phase; `Map Columns`/`Resolve Identity`/`Merge Contacts` own it |

## Package Legitimacy Audit

Not applicable. Phase 24 adds no new dependency: its `requirements.txt` is the same one Phase 23
establishes for the plugin (its own, separate from the backend's), and this phase's only new
capabilities are Anthropic-native (no library) and pure-Python validation logic (stdlib `json`,
`csv`; no new package). If Phase 23's plan already pins an HTTP client or XLSX reader, Phase 24
adds no packages on top of it — confirm during planning that no adapter accidentally reaches for
`requests`, `beautifulsoup4`, or a scraping library; none is needed or in scope.

## Priority Research Questions — Findings

### 1. Skill-driven extraction handoff mechanics

**How Agent Skills actually move data (verified against Anthropic's Agent Skills documentation,
HIGH confidence):**

- A Skill is a directory containing `SKILL.md` (+ optional bundled scripts/resources). Claude
  reads `SKILL.md` via its own filesystem/bash access when the skill triggers; that's "Level 2"
  content and is the only thing that consumes real context tokens beyond the ~100-token
  name+description always loaded at startup. `[CITED: platform.claude.com/docs/en/agents-and-tools/agent-skills/overview]`
- "When instructions mention executable scripts, Claude runs them through bash and receives only
  the output ... the script code itself never enters context." This is the exact mechanism this
  phase needs: Claude (the model) does the extraction work described in prose in SKILL.md, then
  *invokes* a validator script and only sees that script's stdout/stderr/exit code.
  `[CITED: platform.claude.com/docs/en/agents-and-tools/agent-skills/overview]`

**Concrete handoff design (recommendation, not yet verified live — flag for a plan-time smoke
test):**

1. SKILL.md instructs Claude: read the pasted prose / JSON blob / fetched page / attached
   image(s); for each row you can construct, emit an object `{"row": {...canonical fields...},
   "provenance": {...}}`; assemble the full list; **write it as JSON** to a fixed scratch file
   (e.g. `operator-claude-plugin/scripts/.tmp/extracted_<batch-id>.json`) using Claude's own
   file-write capability (not shipped as a chat message Python has to re-parse out of prose).
2. SKILL.md then instructs Claude to run `python scripts/validate_rows.py .tmp/extracted_<id>.json`.
3. The script is the only place STRUCT-01/02/03/04 are mechanically enforced: it parses the file,
   validates shape, strips/report unknown keys, applies the identity rule, splits accepted vs.
   rejected, and writes back a second JSON artifact (accepted rows + provenance, rejected rows +
   reasons) that the SKILL.md then renders as the preview.
4. Nothing about this requires an Anthropic API call — the "model" in step 1 is the assistant
   already running the conversation, which is precisely D-01/D-02's point.

**Why a file, not inline chat parsing:** Regex-parsing a fenced code block out of Claude's own
prior turn is exactly the kind of fragile contract INGEST-06 exists to prevent (STRUCT-04's
sibling failure mode — "the extractor silently mis-shaped the data" rather than "the source had
no data"). A file on disk that a script opens and either parses or explicitly errors on is the
only version of this contract that fails loudly. This mirrors the pattern already used
by this very research pipeline (an agent writes a JSON plan/digest to a scratch path, then a
tool/script consumes exactly that file) — well-established in this environment.

**Failure modes and how the validator must handle each (STRUCT-04/INGEST-06 territory):**

| Failure | Detection | Required behavior |
|---|---|---|
| Model emits prose instead of JSON, or wraps JSON in markdown fences | `json.loads()` raises, or the file isn't valid JSON after best-effort fence-stripping | Fail the whole batch with a named, actionable error ("extraction did not produce structured rows — see the model's own summary above and try again"); never guess-parse partial JSON |
| Model emits a JSON object instead of a top-level array | `isinstance(data, list)` check fails | Same as above — reuse `src/file_loader.py::_load_json`'s existing pattern of accepting `{"rows": [...]}`/`{"contacts": [...]}` as an escape hatch, since that convention already exists in this repo, but still error on anything else |
| Model emits extra/invented fields not in the canonical 7-prop set | Per-row key diff against the alias-target set from `config/column_mapping.yaml` | Strip the field from the row **and report it** (mirrors "reported rather than silently dropped" — criterion 2's requirement, generalized to every adapter, not just JSON) |
| Model invents a value where the source had none (STRUCT-04 core guarantee) | Not fully mechanically checkable — this is a prompt contract (D-03), not a code guarantee, except where explicitly checkable (e.g. a value with no corresponding provenance span/image region) | Validator can enforce the *structural* half (every accepted row must carry non-empty provenance); it cannot verify truthfulness of the extraction itself — document this ceiling explicitly in the plan, don't oversell what Python checks |
| One bad row in an otherwise good batch | Per-row try/except, exactly as `src/file_loader.py::ingest_file` already does | One malformed row goes to rejects with a reason; it must never crash the whole batch — reuse this repo's existing per-row-isolation pattern rather than reinventing it |

### 2. Image reading in a skill context

**Resolves Phase 23's open D-14 question, and answers it for the image case too (MEDIUM
confidence — based on a reproduced, filed limitation, not a guaranteed-permanent doc):**

A filed and reproduced GitHub issue against `anthropics/claude-code`
(`anthropics/claude-code#54062`) confirms the asymmetry directly: **when a user attaches an image
inline in the conversation, the assistant can perceive it multimodally (describe its contents
fully) but there is no tool or API that exposes that attachment's raw bytes or filesystem path to
a script the assistant invokes.** The reporter's workaround attempts (guessing `%TEMP%` paths,
matching by mtime) are explicitly called out as unreliable and are exactly the kind of hack this
phase must not build toward. `[CITED: github.com/anthropics/claude-code/issues/54062]`

Separately, Anthropic's own "Desktop and filesystem access" documentation describes a **different,
more reliable** mechanism: **workspace folders**. If the operator attaches a folder (not a single
inline image) to the session, the agent gets full read/write filesystem access to every file
inside it, and a script *can* open those files by path. `[CITED: claude.com/docs/third-party/claude-desktop/local-access]`

**What this means for D-01/D-02 and INGEST-07 — and why it is actually fine:**

D-02 already decided "images are read natively rather than base64-shipped" — i.e., Python was
never going to touch image bytes in this design. The finding above confirms that decision was not
just a preference but a **hard platform constraint**: an inline-attached screenshot's bytes are
*not reliably reachable* by a script at all. The extraction step must be 100% "Claude looks at the
image and writes down what it sees" (per Question 1's handoff), and the validator script only ever
receives the JSON rows Claude already produced — never the image itself. This makes the
attachment-vs-workspace-folder distinction (the open question in Phase 23's D-14) **irrelevant for
Phase 24's image adapter specifically**, because the image never needs to reach Python either way.
It only matters if a *future* phase needs the raw image bytes for something Python must do (e.g.
re-hosting it) — out of scope here.

**Practical count/size limits (HIGH confidence, from Anthropic's Vision docs):** a single request
supports up to 20 images before a stricter per-image dimension cap (2000px per side) applies, and
up to ~100 on the raw API / ~600 with aggressive size constraints, with a 32 MB request-size
ceiling typically hit first. `[CITED: platform.claude.com/docs/en/build-with-claude/vision]`
For a Claude-Desktop conversation turn, plan for the conservative ~20-image practical ceiling: if
an operator's scrolled-page sequence exceeds that, the SKILL.md should instruct them to submit in
batches, extracting and merging (via the identity rule, D-08/D-09) across batches rather than
assuming one unbounded turn. **This is a planning constraint to surface to the operator, not a
code guardrail Python can enforce** (Python never sees the images to count them) — the SKILL.md's
prose instructions are the only enforcement point.

### 3. Native `web_fetch` for URL ingestion

**Mechanics (HIGH confidence, from Anthropic's Web Fetch tool documentation):**

- `web_fetch` is a **server tool**: when enabled, the underlying Messages API call fetches the
  content and inserts the result into the conversation directly — the calling application (here,
  Claude Desktop) does not run any HTTP client of its own and does not return a `tool_result`
  block for it. This is the mechanical reason D-01/D-02 can claim "no new dependency, no HTTP
  scraping client is built here" — the tool *is* the fetch. `[CITED: platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool]`
- **Security constraint that keeps this inside the requirements' fence:** Claude cannot
  dynamically construct a URL to fetch — it can only fetch a URL that has *already appeared* in
  the conversation (typed by the user, or returned by an earlier `web_search`/`web_fetch`). Since
  the operator is the one pasting the URL, this constraint is automatically satisfied and needs no
  extra plan-time guardrail. `[CITED: platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool]`
- **robots.txt / access-denial behavior:** a blocked fetch (whether due to robots.txt, a private
  address, or domain-filtering configuration) returns error code `url_not_allowed`. A different
  error code, `url_not_accessible`, covers an ordinary HTTP failure (404, 5xx, etc.), and
  `unsupported_content_type` covers a fetch that succeeded but wasn't text/HTML/PDF. All of these
  come back as a `web_fetch_tool_result_error` **content block** — not an exception — so Claude
  sees the error inline and must decide what to tell the operator. There is no way to distinguish
  "blocked by robots.txt" from "blocked by an admin's `blocked_domains` config" from the error
  code alone — both collapse into `url_not_allowed`. Document this ambiguity in the SKILL.md's
  error wording rather than pretending the distinction is knowable.
  `[CITED: platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool]`
- **The tool does not render JavaScript.** A page that is a client-rendered shell will fetch
  "successfully" (no error code) but return near-empty text content — this is the "fetch that
  yields nothing usable" case named in success criterion 3, and it is **not** a tool-level error;
  it's an extraction-level judgment call Claude must make ("this page's fetched content contains
  no legible contact/company data") and report as a *named* result distinct from a fetch failure.
  Plan for two distinct reportable outcomes: (a) fetch failed (tool error code surfaced verbatim,
  translated to plain language) vs. (b) fetch succeeded but extraction found nothing (a
  zero-row result with an explicit "nothing usable on this page" message, never a silent empty
  success). `[CITED: platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool]`
- **Fence compliance (REQUIREMENTS.md "Out of Scope"):** the tool definition has no user-agent
  parameter, no viewport/rendering option, and cannot be pointed at an authenticated session — it
  fetches with whatever access an anonymous fetch gets and nothing more. There is no design
  decision needed to "stay inside the fence" here; the tool structurally cannot do the excluded
  things (no JS rendering rules out most anti-bot detection surfaces entirely, since those key off
  a rendered DOM). `[CITED: platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool]`
- Successful fetch returns `content.source.data` (plain text for HTML/text; base64 for PDF) plus
  `retrieved_at`. No cost beyond ordinary token usage — consistent with D-01/D-02's "extraction
  costs nothing per batch" framing (there is no metered *tool* cost, only the ambient conversation
  tokens, same as any other read).

**Open item to verify at plan time, not resolvable from docs alone:** whether "Claude Desktop" as
this repo's operator surface literally exposes a `web_fetch` tool toggle to the end user/skill the
same way the API's `tools: [{"type": "web_fetch_..."}]` array does, or whether the desktop app
wires this in ambiently whenever a URL appears and "web browsing" is enabled in the user's
settings. Either way the *mechanics* above (robots.txt behavior, error taxonomy, no dynamic URL
construction) are Anthropic's stated behavior for the underlying tool and are the right contract
to design the SKILL.md's error-translation prose against.

### 4. The identity rule as local pre-flight and dedupe key — CORRECTION to CONTEXT's pointer

**Important finding: the CONTEXT's canonical_refs slightly mis-locates the rule.** Re-reading both
`n8n/wf_contact_ingest_cloud.json` nodes named:

- **`Map Columns`** — contains `requiredIdentity(row)`, which is **exactly** the presence rule
  STRUCT-02/D-08 need: `email` present, OR (`firstname` AND `lastname` AND `company`) all present.
  This is the rule the *reject* decision is based on, applied immediately after header-aliasing,
  before any HubSpot search happens.
- **`Resolve Identity`** — contains `resolveIdentity(row, searchResultsByKey)`, a **separate,
  later** step that matches a row *against existing HubSpot records* using strong keys (email,
  linkedin_url — auto-match) and weak keys (phone+lastname, firstname+lastname+company — always
  routes to `ambiguous`/needs_review, never auto-matched). This is CRM dedupe logic, explicitly
  out of scope for the plugin per the phase's own domain boundary ("Phase 24's identity-rule check
  is a local pre-flight ... it is not a dedupe against the CRM").

So: **the rule D-08/STRUCT-02 must mirror locally is `requiredIdentity()` from `Map Columns`, not
anything in `Resolve Identity`/`Merge Contacts`.** The latter two implement HubSpot-side matching
that stays entirely server-side; the plugin has no HubSpot search results to run that logic
against anyway.

**Exact semantics of `requiredIdentity()` (verified by reading the embedded jsCode, HIGH
confidence):**

```javascript
function _present(v) {
  return v !== null && v !== undefined && String(v).trim() !== "";
}
function requiredIdentity(row) {
  if (!row) return false;
  if (_present(row.email)) return true;
  return _present(row.firstname) && _present(row.lastname) && _present(row.company);
}
```

- **Presence only, not validity** — an obviously malformed email (e.g. `"not-an-email"`) still
  counts as "present" at this stage; real email validation happens later, downstream, via the
  rapid-email-verifier API. The identity pre-flight is not an email-format check.
- **Whitespace handling: trims before checking.** A value of `"   "` (all spaces) is treated as
  absent (`.trim() !== ""` fails).
- **No case-folding needed** — this is a presence check, not an equality/match check, so casing is
  irrelevant here (it only matters for `Map Columns`'s *header* lookup, which is already
  case-insensitive/whitespace-collapsed per `config/column_mapping.yaml`'s own comment).

**A real, citable discrepancy the client must not inherit:** `src/file_loader.py::_has_identity`
(this repo's existing Python mirror, used by the CLI/backend ingestion path) does **not** trim:

```python
def _has_identity(mapped, required):
    for group in required.get("any_of", []):
        if all(mapped.get(key) not in (None, "") for key in group):
            return True
    return False
```

A value of `"   "` (whitespace-only) passes this Python check but would be rejected by the n8n
JS `requiredIdentity()` the same row eventually reaches server-side. **Phase 24's client-side
validator must trim before the presence check** (matching the n8n JS, which is authoritative
since it's what the live backend actually runs) rather than copying `_has_identity` verbatim. This
is exactly the kind of "client disagrees with backend" gap the priority question anticipated —
flag it as a required behavior in the plan, and consider a unit test asserting
`validate_rows.py`'s identity check treats `"   "` as absent, agreeing with the n8n node and
diverging deliberately from `_has_identity`'s current behavior.

### 5. Canonical prop set and validation

**The exact set (verified, HIGH confidence, from `config/column_mapping.yaml`'s alias *targets*,
cross-checked against REQUIREMENTS.md's stated canonical list — they match exactly):**

```
email, firstname, lastname, jobtitle, linkedin_url, phone, company
```

**What the backend does with an unexpected key:** `Map Columns`' JS only copies a key into the
output row if it has an alias-table hit (`if (canonical) out[canonical] = rawRow[key];`); anything
else is **silently dropped** — no error, no report, at the backend level. This means: if Phase
24's Python assembled a CSV/row set containing an invented key like `twitter_url`, the backend
would just quietly drop it — which satisfies STRUCT-01 by accident but violates the *spirit* of
"reported rather than silently dropped" that recurs across this phase's criteria. **Conclusion:
the client-side validator, not the backend, is the only place that can honor the "report, don't
silently drop" requirement** — it must diff each row's keys against the 7-prop set itself and
surface anything outside it to the operator, rather than relying on `Map Columns` to quietly
absorb the discrepancy. This directly informs how strict D-03's validator must be: strict enough
to catch and report every non-canonical key, not just strict enough to avoid a backend error
(since the backend won't error on this — it will silently comply).

### 6. Provenance strip point

**Where the strip must happen:** Phase 23's dispatch path POSTs a **binary CSV body** to
`hubspot/contact-upload` (`Extract From File` runs `operation: csv`, per ROADMAP's explicit note
that XLSX is not a wire format — the same applies here: whatever canonical rows this phase
produces must be serialized to CSV bytes before POST, not sent as JSON). The provenance sidecar
(D-04) is only ever needed for the **preview render**, which happens in-conversation as a markdown
table or Artifact (Phase 23 D-09) — never in the wire payload.

**Concrete enforcement point:** the row-assembly step that turns the validator's accepted-row list
into (a) a preview data structure and (b) CSV bytes for dispatch must be **two separate
functions**, not one function with a flag:

- `render_preview(rows_with_provenance) -> markdown/table` — includes provenance columns.
- `to_dispatch_csv(rows_with_provenance) -> bytes` — must literally not have access to the
  provenance fields (e.g., takes a plain `dict[canonical_prop] -> value` per row with provenance
  already excluded at the type level, rather than trusting a runtime filter to always remember to
  strip it).

**How to test it (STRUCT-01 as a runnable assertion):** a unit test that constructs a row carrying
both canonical fields and a `provenance` key, calls `to_dispatch_csv`, parses the resulting CSV's
header row, and asserts the header set is a subset of the 7 canonical props with zero
provenance-named columns present. This mirrors the existing repo pattern (e.g.
`test_builder_flag_parity.py`) of asserting exact JS/Python/wire-format parity rather than
eyeballing serialized output.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fetching a public URL's content | An HTTP client + HTML parser in Python | The native `web_fetch` tool, invoked by Claude in-session | Mandated by criterion 3; also the only way to get robots.txt-respecting fetch without hand-rolling a compliance layer |
| Extracting fields from prose/JSON/HTML/images | A regex/NLP pipeline, or a call to the Anthropic Messages API from Python | Claude's own in-session reading, per D-01 | The whole point of D-01 is that the model already running the conversation is the extractor — a second model call would contradict "no Anthropic API call" |
| CSV/XLSX row loading (if a fallback path ever needs it) | A new parser | `src/file_loader.py::load_rows` (already handles csv/tsv/json/xlsx) | Already exists, tested, and explicitly named as a reuse candidate in ROADMAP's Notes for Planning — though note it's a *co-location convenience*, not license to import merge/scoring/provider code |
| Row-shape/identity validation | A hand-rolled ad hoc check per adapter | One shared `validate_rows.py`/`_has_identity`-equivalent function, called by every adapter | Four adapters (prose/JSON/URL/screenshot) all need the *same* canonical-prop + identity-rule check; writing it once avoids four slightly-different reimplementations drifting apart |

**Key insight:** every "don't hand-roll" item above is really the same insight stated four ways:
this phase's Python surface is a validator, not an extractor, a scraper, or a second model client.
Any code that starts to look like it's doing extraction (parsing HTML, calling an LLM API, OCR-ing
pixels) is out of the design D-01 committed to.

## Common Pitfalls

### Pitfall 1: Treating the extraction handoff as "parse whatever Claude says in chat"
**What goes wrong:** the validator script tries to regex a JSON blob out of Claude's own
conversational reply, which is fragile the moment Claude adds a sentence of commentary before or
after the JSON.
**Why it happens:** it feels like less scaffolding than instructing Claude to write a file first.
**How to avoid:** SKILL.md explicitly instructs "write the extracted rows to `<path>` as a JSON
array, then run `validate_rows.py <path>`" — a file boundary, not a chat-parsing boundary.
**Warning signs:** the validator script accepts a string via stdin/argv that's expected to *be*
JSON but sometimes has markdown fences or leading prose around it.

### Pitfall 2: Assuming the backend will catch what the client doesn't
**What goes wrong:** shipping a lenient client-side validator on the theory that `Map Columns`
will drop anything malformed anyway.
**Why it happens:** `Map Columns` genuinely does silently drop unmapped keys (see Question 5) —
so a lazy validator "still produces a correct row" downstream, just without ever telling the
operator what got dropped.
**How to avoid:** treat "reported rather than silently dropped" as this phase's validator's job
specifically, not the backend's, because the backend structurally cannot report anything (it's a
pure-function Code node with no channel back to the operator).
**Warning signs:** a plan that has the client "just pass through" whatever Claude emitted without
a canonical-key diff step.

### Pitfall 3: Mirroring `_has_identity`'s whitespace behavior instead of the n8n node's
**What goes wrong:** copying `src/file_loader.py::_has_identity` verbatim as "the" Python identity
check, inheriting its missing `.trim()` and accepting whitespace-only fields as present — client
accepts a row the backend would reject.
**Why it happens:** `_has_identity` is the closest, most obviously reusable existing code, and
looks authoritative because it's already in the repo.
**How to avoid:** mirror `Map Columns`' `requiredIdentity()` (trim-then-check) specifically, since
that is what actually runs against the live workflow; treat `_has_identity` as a close-but-stale
reference, not a copy source. Cross-check with a unit test using a whitespace-only field.
**Warning signs:** a rejected-row report that never fires for whitespace-only input during manual
testing (because the check silently passed it through).

### Pitfall 4: Confusing "fetch failed" with "fetch succeeded but page has nothing"
**What goes wrong:** both cases get reported to the operator as the same generic "couldn't get
data from that URL," losing the distinction success criterion 3 explicitly asks for.
**Why it happens:** both surface as "zero rows" from the operator's point of view if not
deliberately separated.
**How to avoid:** treat the `web_fetch_tool_result_error` content block (tool-level failure,
translate `error_code` to plain language) and a successful-fetch-but-empty-extraction result
(model-level judgment, "nothing usable on this page") as two distinct, separately-worded outcomes
in the SKILL.md.
**Warning signs:** the SKILL.md has only one generic "URL didn't work" message for every failure
shape.

### Pitfall 5: Screenshot dedupe implemented against the wrong rule
**What goes wrong:** building bespoke "are these two screenshot rows probably the same person"
fuzzy logic instead of reusing the exact identity presence rule.
**Why it happens:** screenshots feel like they need fuzzier matching than clean CSV rows because
OCR/vision reads are noisier.
**How to avoid:** D-08 is explicit that overlap dedupe uses the *same* identity rule as
STRUCT-02's rejection filter — same email, or same firstname+lastname+company (post-trim,
presumably also worth normalizing case for a *match*, unlike the presence-only reject rule, since
two screenshot reads of "John Smith" and "john smith" should collapse). Anything short of an exact
identity-key match should surface as an ambiguity (D-06/D-09), not a silent collapse.
**Warning signs:** a dedupe implementation that tries to fuzzy-match on similarity score rather
than exact identity-key equality.

## Code Examples

### `web_fetch` tool definition and response shape (server tool)
```json
// Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
{
  "type": "web_fetch_20260318",
  "name": "web_fetch"
}
```
Successful result (abridged):
```json
{
  "type": "web_fetch_tool_result",
  "content": {
    "type": "web_fetch_result",
    "url": "https://example.com/article",
    "content": {
      "type": "document",
      "source": { "type": "text", "media_type": "text/plain", "data": "Full text content..." }
    },
    "retrieved_at": "2026-07-06T15:44:00Z"
  }
}
```
Error result (abridged — note: a `200`-level content block, not an exception):
```json
{
  "type": "web_fetch_tool_result",
  "content": { "type": "web_fetch_tool_result_error", "error_code": "url_not_allowed" }
}
```

### `Map Columns`' identity presence rule (n8n, authoritative — mirror this, not `_has_identity`)
```javascript
// Source: n8n/wf_contact_ingest_cloud.json, node "Map Columns"
function _present(v) {
  return v !== null && v !== undefined && String(v).trim() !== "";
}
function requiredIdentity(row) {
  if (!row) return false;
  if (_present(row.email)) return true;
  return _present(row.firstname) && _present(row.lastname) && _present(row.company);
}
```

### Existing per-row-isolation pattern to reuse for the JSON validator
```python
# Source: src/file_loader.py::ingest_file (this repo)
for i, raw in enumerate(load_rows(path)):
    try:
        if not isinstance(raw, dict):
            rejects.append(RejectedRow(row_index=i, reason="row is not an object", raw={"value": repr(raw)}))
            continue
        mapped = map_row(raw, mapping)
        if not _has_identity(mapped, required):
            rejects.append(RejectedRow(row_index=i, reason="no identity key", raw=raw))
            continue
        accepted.append(mapped)
    except Exception as e:  # one bad row must never crash the batch
        rejects.append(RejectedRow(row_index=i, reason=f"parse error: {e}", raw=raw if isinstance(raw, dict) else {"value": repr(raw)}))
```
(Phase 24's validator should follow this exact shape — try/except per row, structured rejects with
a reason — swapping `_has_identity` for the trim-corrected version described in Priority Question
4, and adding the canonical-key-diff/report step from Priority Question 5.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Server-side model call (Python → Anthropic Messages API → `web_search`/model) for extraction, as `src/web_research.py` does for backend enrichment | In-session Claude extraction, zero API calls, per D-01 | This phase's own decision, 2026-07-30 | The two "web research" mechanisms in this repo are deliberately different: backend enrichment (`src/web_research.py`) is a programmatic API call; the plugin's URL/prose/JSON/screenshot adapters are the *ambient conversation's own* tool use. Do not conflate them when planning — they share no code path |
| `web_fetch_20250910` (basic fetch) | `web_fetch_20260318` (adds dynamic filtering + response-inclusion control) | Progressive tool versions through 2026 | Not load-bearing for this phase's minimal use (plain text extraction), but note it if a future phase wants token-cost control on large fetched pages |

**Deprecated/outdated:** none identified as directly relevant; the `web_fetch` tool has only grown
capability (dynamic filtering, cache bypass) across versions, all backward-compatible with the
plain-fetch use case this phase needs.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Claude Desktop" (this repo's stated operator surface) exposes the native `web_fetch` tool and multimodal image-reading to a running Skill with the same mechanics documented for the Claude API / claude.ai surfaces | Priority Questions 2 & 3 | If Claude Desktop's Skill runtime differs (e.g. no ambient web-fetch, or a different attachment model), the URL and screenshot adapters need a different design; verify with a live smoke test in Claude Desktop before or during Wave 0 of planning |
| A2 | The GitHub issue's "no programmatic path/bytes for inline attachments" finding, filed against Claude Code, generalizes to Claude Desktop's Skill runtime | Priority Question 2 | If Claude Desktop's attachment model differs from Claude Code's, the "images never need to reach Python" conclusion could be wrong — re-verify if the plan's Wave 0 smoke test shows otherwise |
| A3 | The client-side identity-rule validator should trim whitespace to match `Map Columns`' `requiredIdentity()`, diverging from `src/file_loader.py::_has_identity`'s current (untrimmed) behavior | Priority Question 4 | Low risk if wrong — worst case is an inconsistency between client accept/reject and backend accept/reject on a whitespace-only edge case; a unit test closes this either way |

## Open Questions

1. **Does Claude Desktop's Skill runtime literally surface a `web_fetch` toggle/tool, or is
   "fetch this URL" ambient conversational behavior gated by a user-level web-browsing setting?**
   - What we know: the API-level tool contract (robots.txt, error codes, no dynamic URL
     construction) is fully documented.
   - What's unclear: whether the SKILL.md needs to say anything special to *enable* this, or
     whether it can just instruct "fetch the URL the operator gave you" and trust the surrounding
     app to wire it up.
   - Recommendation: plan a Wave 0 smoke test — paste a URL in a live Claude Desktop session
     running a draft SKILL.md and confirm a fetch actually happens and reports a `retrieved_at`
     or an error, before building the rest of the URL adapter around a specific error-handling
     shape.

2. **Exact per-turn image count Claude Desktop will accept in one message before erroring or
   silently dropping the excess.**
   - What we know: API-level limits (~20 before a dimension cap, ~100 raw ceiling, 32 MB request
     cap).
   - What's unclear: what Claude Desktop's own UI enforces (it may cap uploads well below the API
     ceiling, e.g. per-message attachment limits in the client itself).
   - Recommendation: treat ~20 as the planning ceiling and have the SKILL.md ask the operator to
     batch beyond that; confirm the actual UI-enforced number empirically once, not deduce it.

## Environment Availability

Not applicable as a blocking dependency — this phase adds no new external tool, service, or
package beyond what Phase 23 already establishes for the plugin (its own `requirements.txt`,
whatever HTTP client and XLSX reader Phase 23 already chose). The only "dependencies" this phase
introduces are Anthropic-native capabilities (`web_fetch`, vision) that are either present in the
Claude Desktop runtime or not — there is no local install step or fallback library to probe for.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Native `web_fetch` tool | URL adapter (INGEST-05) | Assumed ✓ (A1) — verify live per Open Question 1 | n/a (tool version, not a package) | None — this phase has no HTTP-client fallback by requirement; a missing tool means the URL adapter cannot ship, not that it silently degrades |
| Multimodal image reading | Screenshot adapter (INGEST-07) | Assumed ✓ (A2) | n/a | None — same reasoning; screenshot ingestion has no OCR-library fallback in scope |

**Missing dependencies with no fallback:** if A1/A2 prove false in the target Claude Desktop
runtime, both the URL and screenshot adapters are blocked as designed and need a design change,
not a fallback library — flag this to the user rather than quietly reaching for `requests`/OCR,
which would violate D-01/D-02.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo-wide convention; run via `.venv/bin/python -m pytest`, per this repo's established test-runner note) |
| Config file | none detected (`pytest.ini`/`pyproject.toml` not present) — pytest runs on defaults; no Wave 0 gap since the existing `tests/` suite already runs this way |
| Quick run command | `.venv/bin/python -m pytest tests/test_<new_file>.py -x` |
| Full suite command | `.venv/bin/python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STRUCT-01 | Dispatch CSV never contains a provenance column | unit | `pytest tests/test_provenance_strip.py -x` | ❌ Wave 0 |
| STRUCT-02 | Row missing email AND missing (firstname+lastname+company) is rejected with a reason; whitespace-only fields count as absent | unit | `pytest tests/test_identity_preflight.py -x` | ❌ Wave 0 |
| STRUCT-04 | Accepted row structurally requires non-empty provenance; absent-in-source stays absent (structural half only — truthfulness is a prompt contract, not code-checkable) | unit | `pytest tests/test_no_invention_structural.py -x` | ❌ Wave 0 |
| INGEST-03 (JSON adapter) | A row carrying an unmapped key gets that key stripped and reported, not silently dropped | unit | `pytest tests/test_canonical_key_diff.py -x` | ❌ Wave 0 |
| INGEST-06 | Malformed/non-JSON extraction artifact produces a named error, never a zero-row silent success | unit | `pytest tests/test_extraction_handoff_errors.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant single test file above (`-x`, fail fast)
- **Per wave merge:** full suite (`.venv/bin/python -m pytest`)
- **Phase gate:** full suite green before `/gsd-verify-work`, plus the two live-smoke Open
  Questions (web_fetch, image count) manually confirmed at least once in the actual Claude Desktop
  runtime — these are not pytest-automatable since they depend on the live model/tool runtime.

### Wave 0 Gaps
- [ ] `tests/test_provenance_strip.py` — covers STRUCT-01
- [ ] `tests/test_identity_preflight.py` — covers STRUCT-02, including the whitespace-trim
      correction relative to `_has_identity`
- [ ] `tests/test_no_invention_structural.py` — covers STRUCT-04's checkable half
- [ ] `tests/test_canonical_key_diff.py` — covers INGEST-03's "report, don't drop" requirement
- [ ] `tests/test_extraction_handoff_errors.py` — covers INGEST-06 for the extraction-artifact
      failure modes in Priority Question 1's table
- [ ] No new framework install needed — pytest already used repo-wide

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This phase makes no auth decisions; the webhook auth secret is Phase 23's concern, reused unchanged |
| V3 Session Management | No | No session state introduced by this phase |
| V4 Access Control | No | No new access-control surface |
| V5 Input Validation | Yes | The `validate_rows.py` script IS this phase's V5 control — canonical-key allowlisting (reject/report anything outside the 7-prop set) and identity-rule pre-flight before any data leaves the machine |
| V6 Cryptography | No | No cryptographic operation in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Skill-instruction injection via fetched page content or a malicious "screenshot" (a page/image crafted to make Claude emit attacker-controlled instructions rather than contact data) | Tampering / Elevation of Privilege | Anthropic's own Agent Skills security guidance flags exactly this class of risk for skills that fetch external content: "Skills that fetch data from external URLs pose particular risk, as fetched content may contain malicious instructions." `[CITED: platform.claude.com/docs/en/agents-and-tools/agent-skills/overview]` Mitigation available to this phase: the validator script's canonical-key allowlist means even if extraction were manipulated into emitting extra fields, only the 7 canonical props can ever reach the dispatch payload — the allowlist is a containment boundary, not just a data-quality one |
| Data exfiltration via `web_fetch` combined with sensitive conversation context | Information Disclosure | Anthropic's own warning: enabling `web_fetch` "in environments where Claude processes untrusted input alongside sensitive data poses data exfiltration risks." `[CITED: platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool]` Not directly actionable by this phase (the operator conversation is the trust boundary), but worth a one-line callout in the SKILL.md/README that the URL adapter should be used with URLs the operator trusts, consistent with the "public URL" framing already in INGEST-05 |
| A crafted JSON blob or "screenshot" causing the validator to accept a row with a forged/attacker-supplied email that isn't actually the operator's data | Spoofing | The identity pre-flight (STRUCT-02) only checks *presence*, not truthfulness — this is a known, accepted ceiling (per Priority Question 1's "cannot verify truthfulness" note), not a gap this phase is expected to close; downstream email verification (out of scope, n8n-side) is the actual integrity check |

## Sources

### Primary (HIGH confidence)
- `platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool` — full tool contract: invocation, response shape, error codes, robots.txt/URL-validation behavior, max_uses, no-JS-rendering limitation
- `platform.claude.com/docs/en/agents-and-tools/agent-skills/overview` — Skill architecture (progressive disclosure, script-output-only context loading), Claude Code vs. claude.ai vs. API surface differences, security warnings re: external-content skills
- `platform.claude.com/docs/en/build-with-claude/vision` — per-request image count/size limits
- `claude.com/docs/third-party/claude-desktop/local-access` — workspace-folder filesystem access model for Claude Desktop
- This repo: `config/column_mapping.yaml`, `n8n/wf_contact_ingest_cloud.json` (`Map Columns`,
  `Resolve Identity`, `Merge Contacts` nodes, read directly), `src/file_loader.py`,
  `src/column_mapper.py`, `src/schemas.py`, `src/identity.py`, `operator-claude-plugin/README.md`

### Secondary (MEDIUM confidence)
- `github.com/anthropics/claude-code/issues/54062` — filed, reproduced limitation on attached-file
  byte/path access vs. multimodal visibility; a live GitHub issue, not a stable doc page, so
  treated as evidence of a real limitation rather than a permanent contract

### Tertiary (LOW confidence)
- `mikhail.io/2025/10/claude-code-web-tools/` — third-party blog describing Claude Code's own
  (distinct) `WebFetch`/`WebSearch` tools; used only for background contrast, not relied on for any
  claim in this document since it describes a different tool from the API-level `web_fetch` this
  phase's SKILL.md targets

## Metadata

**Confidence breakdown:**
- Standard stack / extraction mechanics: HIGH — directly sourced from Anthropic's own current tool
  and Skills documentation
- Architecture (handoff design, provenance strip point): MEDIUM — the *mechanics* are HIGH
  confidence, but the specific file-handoff design is this research's own recommendation, not yet
  smoke-tested live in the target Claude Desktop runtime
- Pitfalls / identity-rule correction: HIGH — verified directly by reading the live n8n workflow
  JSON and this repo's existing Python code side by side

**Research date:** 2026-07-30
**Valid until:** ~30 days for the identity-rule/backend-contract findings (stable, code-verified);
~7-14 days for the Anthropic tool-mechanics findings, since `web_fetch` tool versions and Claude
Desktop's Skill runtime are both actively evolving areas per the docs' own version-history notes
