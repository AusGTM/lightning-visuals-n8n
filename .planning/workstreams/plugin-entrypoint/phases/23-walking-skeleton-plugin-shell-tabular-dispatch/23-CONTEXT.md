# Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 23 delivers the **plugin shell itself** plus exactly one working lane: a contact
spreadsheet (CSV or XLSX) goes in conversationally, the operator sees and approves a preview of
what would be sent, and — only after explicitly arming — it POSTs to `hubspot/contact-upload`.

Everything the backend already does stays in the backend. The plugin does **not** map columns,
normalize phones, verify emails, resolve identity, dedupe, or route create/update. Those live in
`n8n/wf_contact_ingest_cloud.json` and forking any of them would create a second source of truth.

In scope: plugin packaging under `operator-claude-plugin/`, admin/operator configuration and its
refusal path, file ingestion for tabular input, preview + approve, conversation-scoped arming,
and dispatch to one endpoint.

Out of scope this phase: non-tabular adapters (Phase 24), the enrichment lane and cost guard
(Phase 25), per-record outcome parsing and retry (Phase 26), status/control/notice/triage
(Phases 27–30).

</domain>

<decisions>
## Implementation Decisions

### Plugin runtime and shape
- **D-01:** The plugin is a **Claude skill (markdown `SKILL.md`) driving thin Python scripts**
  under `operator-claude-plugin/scripts/`. The skill owns the conversation; Python owns
  spreadsheet parsing and the HTTP POST. The plugin carries its **own** `requirements.txt` so it
  stays independently replaceable — it does not import from the repo's `src/` or reuse the
  backend's dependency set. — **Reversibility:** costly — swapping runtimes after the skill,
  scripts, README, and CHANGELOG exist means rewriting every executable file in the plugin
  directory, though nothing outside `operator-claude-plugin/` is touched.
- **D-02:** Invocation is **both** a slash command and an intent trigger. A discoverable slash
  command is the handle a non-technical operator can remember; the `SKILL.md` description also
  fires on natural phrasing like "load these contacts into HubSpot". Both paths enter the same
  code — the slash command is not a second implementation.

### Configuration provisioning
- **D-03:** Configuration lives in a **plugin-local gitignored file** with a **committed example
  file** alongside it (e.g. `operator-claude-plugin/config/operator.local.json` gitignored, and
  `operator.local.example.json` tracked). The README documents the setup step and points at the
  example.
- **D-04:** The filename must **not** be a dotfile. Dotfiles are permission-blocked in this
  environment (see `.env` — unreadable to tooling), so a dotfile config would be unreadable at
  runtime. This is an environment constraint, not a style preference.
- **D-05:** **The operator performs setup once, from the example file.** This is a deliberate
  amendment to **PLUGIN-02**, which currently states the configuration is admin-provisioned and
  the operator never sees or pastes a secret. The user was shown that conflict and chose
  operator self-setup. REQUIREMENTS.md PLUGIN-02 should be reworded to match before this phase
  is marked complete. — **Reversibility:** reversible — moving back to admin-provisioned is a
  README change plus a wording change in the refusal message; no code shape depends on which
  human edits the file.
- **D-06:** When configuration is missing or rejected, the plugin **refuses before any network
  call** and says in plain language what is not configured and how to fix it. It never shows a
  key, never asks the operator to paste one into chat, and never surfaces a raw socket error.
  (PLUGIN-03.)

### Preview
- **D-07:** Tabular input is **passed through unchanged** — the plugin POSTs the file as read and
  lets n8n's `Map Columns` node do the mapping. The preview shows canonical shape by reading
  `config/column_mapping.yaml` as a **read-only lookup table**, rendering e.g.
  `Company Name → company`, `Mobile → phone`, `Notes → dropped`. This is display-only: the plugin
  reads that YAML but never transforms rows with it, so no second mapper exists.
  — **Reversibility:** costly — the alternative (client-side mapping to canonical CSV) changes
  what bytes go over the wire and what the preview means, so switching later invalidates the
  preview contract and any tests written against it.
- **D-08:** Preview scope is **adaptive**: roughly ≤ 20 rows renders every row; above that, first
  10 + last 3 + total row count + per-column fill rates. Small batches stay fully inspectable,
  large batches stay readable.
- **D-09:** Preview renders as a **markdown table in chat by default, with a published Artifact on
  request**. This matches the convention STATUS-05 sets in Phase 27, so one rendering convention
  covers both surfaces.
- **D-10:** Declining the preview sends nothing and costs nothing beyond reading the file.
  (PREVIEW-04.)

### Arming
- **D-11:** Live-write permission is held **in the conversation only**. The operator types an
  explicit arming phrase and the skill passes an armed flag to the dispatch script for that send.
  **Nothing is written to disk** — no timestamp file, no state file — so the grant cannot outlive
  the session or be inherited by a later one. This satisfies DISPATCH-03 with no persisted state
  to leak. Phase 28 replaces this with the real n8n-side conversation-scoped mechanism
  (CONTROL-04); Phase 23's version is deliberately the weaker, stateless one.
  — **Reversibility:** reversible — Phase 28 supersedes it by design; the arming call site is a
  single flag on the dispatch path.
- **D-12:** The plugin **states up front** which endpoint it targets and whether dispatch is
  currently armed, before any work is done. (Success criterion 1.)
- **D-13:** With live writes off — the default — an *approved* batch is still not sent. The
  operator is told plainly that sending is off and how to turn it on for this conversation.

### File handoff
- **D-14:** **Both** paths are supported, attachment first with filesystem path as fallback: try
  to read a file the operator has attached in the session; if that is unavailable, ask for and
  resolve a filesystem path.
- **D-14a (resolved by 23-RESEARCH.md and confirmed with the user):** The operator works in the
  **Claude Desktop Code tab**, so the plugin packaging in D-01 applies as designed
  (`.claude-plugin/plugin.json` + `skills/<name>/SKILL.md` + `scripts/*.py`, GUI-installable, no
  terminal). Research could **not** confirm from documentation that a Code-tab attachment resolves
  to a real filesystem path for a skill's Python scripts, and an open upstream issue describes
  exactly that gap for images. Therefore: build the **`@mention` autocomplete path as the reliable
  mechanism**, attempt attachment opportunistically, and gate any attachment-specific plumbing
  behind **one early live smoke test**. Do not build attachment plumbing beyond that test.
- **D-14a-RESOLVED (smoke test executed 2026-07-31 — see `23-02-SUMMARY.md`):** The probe ran in a
  live Code-tab session and **all four observations came back positive**, refuting the pessimistic
  assumption above:
  - **Attachment resolves to a real filesystem path** — `/Users/robertli/Desktop/lv-smoke-test.csv`,
    with a shell command successfully reading its first line. Not conversation-content-only.
  - **`@mention` resolves to a real path** — confirmed on a repo file. Note `@` indexes the
    **workspace only**, so it cannot reach files outside the repo.
  - `python3` 3.14.5 is available in-session, and `openpyxl` / `requests` / `PyYAML` **import
    directly with no install step**.
  **Revised instruction for 23-04:** build a genuine **two-legged file handoff** — `@mention` for
  workspace files, attachment for files anywhere else (the realistic operator case: a spreadsheet
  in Downloads, not committed to the repo). This supersedes D-14a's single-leg-plus-try/except
  degradation. **Still build no speculative plumbing**: the probe licenses reading a path the
  session hands over, not temp-directory scanning, upload shims, or guessing at storage
  conventions. If no path is supplied, ask — do not hunt.
- **D-14c (interpreter discipline, recorded by the operator):** the session's system `python3`
  carries the plugin's three dependencies, but the **repo's test suite still requires
  `.venv/bin/python -m pytest`** — system python lacks the suite's broader dependency set. Two
  interpreters, two purposes; conflating them breaks test runs.
- **D-14b:** Research also found a free win for D-02: a plugin skill is **already both
  auto-triggered and slash-invocable** as `/plugin-name:skill-name`. No separate `commands/`
  directory is needed to satisfy D-02.

### Backend blocker found by research — must be fixed for this phase to meet its goal
- **D-15 (26-RESEARCH.md, verified in deployed workflow JSON):** `Set Config` in
  `wf_contact_ingest_cloud.json` **hardcodes `allow_create: false` unconditionally**, and it is
  **not** one of the four deploy-time-overlayable flags in `scripts/deploy_n8n_workflows.py`. Every
  net-new contact row is therefore forced to `needs_review` regardless of arming state — **the lane
  cannot create a contact today**, which is exactly what this phase's goal requires.
- **D-16:** Resolution: arming must actually enable creation. This is small, matches the two-key
  write-gate convention already in place, and is admin work in this repo rather than the client
  reaching into the backend.
- **D-16a (SUPERSEDES D-16's mechanism — found during planning, verified against deployed JSON):**
  Do **not** add a fifth overlayable flag. The lane already has **two create gates in series**:
  `HubSpot Create Write Gate` already declares and reads the **existing overlayable**
  `ALLOW_HUBSPOT_CREATE`; only `Set Config`'s `allow_create: false` blocks the decision upstream of
  it. So the fix **reuses `ALLOW_HUBSPOT_CREATE`**. Reason: `tests/test_enabled_build_invariants.py`
  pins `_OVERLAYABLE_FLAGS` to exactly four names and `CONFIG_FLAG_DEFAULTS` is parity-guarded
  across both builders — a fifth flag would mean editing a pinned safety assertion. Reuse also keeps
  `_requested_overlay_flags`' "no writes without a `TEST_RECORD_*` allowlist" fail-safe applying to
  contact creation for free.
- **D-16b (SUPERSEDES D-15's placement):** The fix is **not** applied at `Set Config`.
  `Extract From File` emits **fresh items** parsed from the binary CSV, so a value seeded on the
  webhook item upstream of it does not survive — this is the **BUG 12 / BUG 21 row-loss family that
  already cost this repo two armed windows**. The constant is baked into **`Decide Action`**:
  contact-lane, Cloud-only, downstream of every transform, and already the node that computes
  `allow_create`. Composition happens at the build site (`build_cloud`'s chain list), not at
  `DECIDE_CLOUD`'s module-level definition, because `_write_safety_const` is defined later in the
  module.
- **D-17:** Scope note the planner must respect: this is a **backend change inside a phase whose
  criterion 4 says no backend file is modified to make the client work**. It is not that — the
  client works either way; the *backend gate* is what is broken. Criterion 4 still binds the
  client's own files. Record this as a deliberate, separately-justified backend fix rather than
  letting it erode PLUGIN-04.
- **D-18:** Sequencing: this fix must land **before** Phase 23 can demonstrate its stated flow.
  Treat it as an early task, not a trailing one — otherwise the walking skeleton demonstrates a
  flow that stops short of its own goal.

### The arm/disarm read-back — corrected mid-window, plan 23-07
- **D-19 (three defects in `scripts/verify_live_write_safety.py`, found by three independent routes
  on 2026-07-31; fixed as one coherent change):** this script is the read-back that closes an armed
  window — in this repo a window is closed by an independent re-read, never by a deploy's exit code
  (Phase 19's BUG 26). It was unfit for the two windows that depend on it, 23-06 Section B and 30-07.
  - **Finding 1, found by the operator walking 23-06 Section B live:** it hardcoded one workflow
    name and a two-name `Decide*` node tuple and took no workflow argument, so it inspected **2 of
    the 11 declaring nodes** and **no node at all in `LV Contact Ingest (Cloud template)`** — the
    lane the canary fires at. Its `disarmed PASS` was therefore not evidence that lane was disarmed:
    a confident pass for something it never looked at.
  - **Finding 2, found by reading Step 3b against the script:** the armed branch baked in Phase 22's
    canary scope (record writes only, everything else must read disabled), so it reported **FAILURE
    for a backend armed exactly as its own runbook intended** — 23-06 arms record writes *and*
    create on purpose, because the create path is Phase 23's whole goal. A read-back that fails a
    correct state trains an operator to fire through a failure, which is worse than no read-back.
  - **Finding 3, found earlier by 30-01 and already fixed:** the checked boolean set was re-typed as
    a literal list, so `ALLOW_HUBSPOT_REVIEW_WRITES` — added as the fifth overlay constant — was
    invisible and an armed instance reported `disarmed PASS`. 30-01 replaced it with
    `tuple(c for c in CHECKED_CONSTANTS if c not in ALLOWLIST_CONSTANTS)`. **23-07 preserves that
    derivation rather than redoing it**, and grep-gates it so it cannot be re-hardcoded.
- **D-19a (coverage is discovered, never listed):** the script fetches every deployed workflow,
  re-fetches each by id for node detail, and inspects every node whose `jsCode` declares at least one
  checked constant. A workflow deployed or renamed later appears with no code edit. It deliberately
  carries **no workflow-selection or filter argument** — 27-04's D-07 no-allowlist reasoning applies:
  the moment the scan can be narrowed, the read-back can go blind again, one flag at a time, which is
  precisely the failure 23-06 found live. A scan discovering **zero** declaring nodes is an explicit
  failure, never a quiet pass: a scan that matched nothing is otherwise indistinguishable from a
  disarmed instance, and the vacuous pass is a shape this milestone has hit repeatedly.
- **D-19b (a node is judged on what it declares):** the old rule required every inspected node to
  declare all five constants. The contact lane's `Decide Action` declares **only**
  `ALLOW_HUBSPOT_CREATE` — that is exactly what 23-01 built (D-16a/D-16b) — so the old rule would
  report a legitimate node as broken on every run under discovery. Nothing is lost by dropping it:
  which node declares what is pinned separately by `tests/test_write_gate_coverage.py` and by the
  all-disabled scan over the committed artifacts. Every finding names **workflow then node**, because
  two workflows contain a node named `Decide Action`.
- **D-19c (`--expect-armed` is symmetric, not a filter):** the operator states which flags they
  expect armed, in the same comma-separated shape they already type into `ENABLE_BAKED_FLAGS`. Naming
  a flag says it must read enabled and says **nothing else** — every write-enabling boolean not named
  is still asserted disabled, in every declaring node of every workflow. Weakening this into "ignore
  what I did not name" would delete the property the check exists for. Omitting the argument keeps
  Phase 22's exact meaning (record writes alone), so every pre-existing call site — including the
  completed Phase 22 runbook's three invocations — stays correct, and an operator who forgets the
  argument gets the **stricter** verdict, never a permissive one. An unknown or empty flag set raises
  rather than expecting nothing. An **empty allowlist under an armed expectation is its own finding**:
  `_writeSafetyAllows()` returns false on empty, so that state grants nothing while every flag reads
  `true` — it must never read as a passing armed window.
- **D-19d (a runbook command line and the CLI are one contract):** both operator runbooks were
  updated in the same change. A runbook that tells an operator to work around behaviour that no
  longer exists — or to pass a flag the script rejects — is the same defect class this fixes, and it
  is executed verbatim by a human under time pressure inside an armed window. The script remains
  read-only throughout: it arms nothing, deploys nothing, activates nothing and never touches
  HubSpot, and its whole test suite runs with zero live network calls.

### Claude's Discretion
- Exact slash-command name and skill trigger phrasing.
- Python module layout inside `operator-claude-plugin/scripts/`, and which library reads XLSX.
- Wording of the preview table, the arming prompt, and the not-configured refusal message.
- Whether the preview computes fill rates per column or only for the canonical props.
- HTTP client choice, timeout, and retry posture for the single POST.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — v0.6 requirements; §"Scope anchor —
  what already exists (do NOT rebuild)" is the binding constraint for this phase, and the
  Endpoints table gives the auth model per endpoint.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 23" — goal and the five success
  criteria this phase is verified against.

### Backend contract (read-only for this phase — do not modify)
- `n8n/wf_contact_ingest_cloud.json` — the deployed `hubspot/contact-upload` workflow. Node order
  that matters here: `Webhook Trigger` → `Set Config` → `Extract From File` → `Map Columns` →
  `Normalize Phone` → `Build Verify Batch` → `Verify Emails (batch)` → `Apply Email` →
  `HubSpot Search by Email` → `Resolve Identity` → `Merge Contacts` → `Decide Action` →
  create/update gates. `Extract From File` is what parses the binary body the plugin POSTs.
- `config/column_mapping.yaml` — the alias table `Map Columns` mirrors. Phase 23 reads this as a
  display-only lookup for the preview (D-07). Never write to it, never transform rows with it.
- `n8n/README.md` — webhook paths and auth conventions.

### Plugin surface
- `operator-claude-plugin/README.md` — already written; states the plugin is one replaceable
  client of an HTTP contract, deliberately thin, with no enrichment logic. Phase 23 must not
  contradict it.
- `operator-claude-plugin/CHANGELOG.md` — plugin-local changelog to update as part of this phase.

### Repo conventions
- `CLAUDE.md` — project instructions, including the two-key write-gate convention every write
  path in this repo follows.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config/column_mapping.yaml` — the single source of truth for header aliasing. The preview
  reads it; nothing else in the plugin touches it.
- `operator-claude-plugin/README.md` and `CHANGELOG.md` — already exist and already state the
  design posture. The directory is otherwise empty, so this phase is greenfield inside a
  pre-declared boundary.
- The repo has an established `.venv` and Python toolchain, which is why D-01 chose Python for
  the executable half.

### Established Patterns
- **Two-key write gate.** Every write path in this repo (phases 19–22) is disarmed by default and
  requires deliberate arming. D-11 is this phase's expression of that pattern.
- **Backend owns transformation.** `hubspot/contact-upload` performs mapping, normalization,
  verification, identity resolution, and dedupe server-side. The plugin sits either side of that
  pipe and never inside it.
- **Provider and HubSpot credentials live in n8n**, managed by an admin. The plugin holds only the
  n8n base URL and the webhook auth secret — it cannot read provider balances directly, which is
  why Phase 27 later adds an n8n-side status endpoint.

### Integration Points
- Outbound: one POST to `hubspot/contact-upload` with header auth and a binary CSV body that
  `Extract From File` parses. This is the only network call Phase 23 makes.
- Inbound: none. Phase 23 does not parse per-record outcomes — that is Phase 26.
- Filesystem: reads the operator's spreadsheet, reads its own config file, reads
  `config/column_mapping.yaml`. Writes nothing outside `operator-claude-plugin/`.

</code_context>

<specifics>
## Specific Ideas

- The committed example config file is explicitly wanted — the operator should have a template to
  copy rather than a blank file and a prose description of its keys.
- The preview's value to the operator is answering "did you lose any of my data" — which is why
  the dropped-column disclosure in D-07 matters more than showing every row.

</specifics>

<deferred>
## Deferred Ideas

- **PLUGIN-02 rewording** — D-05 changes who provisions configuration from admin to operator.
  REQUIREMENTS.md still says admin-provisioned and "the operator never sees, pastes, or handles a
  secret". Reconcile the wording before Phase 23 is marked complete.
- **Real conversation-scoped arming** — Phase 28 / CONTROL-04. D-11 is a deliberate stateless
  placeholder.
- **Per-record outcome reporting** — Phase 26 / REPORT-01. Phase 23 reports only that the POST
  was accepted.
- **Cost estimation before send** — Phase 25 / PREVIEW-02. Phase 23's preview shows content and
  row count, not cost.
- **Chunking large batches** — Phase 25 / PREVIEW-03. D-08 caps what the preview *displays*, not
  what a single POST carries.
- **Identity-rule failures separated and reported** — Phase 24 / STRUCT-02.

</deferred>

---

*Phase: 23-walking-skeleton-plugin-shell-tabular-dispatch*
*Context gathered: 2026-07-30*
