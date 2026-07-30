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
  resolve a filesystem path. Research must confirm whether Claude Desktop exposes attachments to
  a skill as a readable path — if it does not, the attachment leg degrades to the path leg and
  the phase still works.

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
