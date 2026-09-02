# Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 23-walking-skeleton-plugin-shell-tabular-dispatch
**Areas discussed:** Plugin runtime & shape, Config provisioning, Preview rendering, Arming mechanism, File handoff

---

## Plugin runtime

| Option | Description | Selected |
|--------|-------------|----------|
| Skill (markdown) + Python scripts | SKILL.md drives conversation; thin Python parses XLSX/CSV and POSTs. Repo already Python with a .venv. Plugin keeps its own requirements.txt. | ✓ |
| Skill + inline bash/curl only | No Python, zero new deps — but XLSX becomes unreadable without a library, degrading to CSV-only. | |
| Node/TypeScript client | Self-contained from the Python backend; adds a second toolchain for no gain. | |

**User's choice:** Skill + Python scripts
**Notes:** Recommended option taken as-is.

---

## Invocation

| Option | Description | Selected |
|--------|-------------|----------|
| Both: slash command + intent trigger | Discoverable handle plus natural-language firing. | ✓ |
| Intent-triggered skill only | Nothing to memorize, nothing to discover. | |
| Slash commands only | Predictable, but reads like a CLI. | |

**User's choice:** Both
**Notes:** Recommended option taken as-is.

---

## Config provisioning

| Option | Description | Selected |
|--------|-------------|----------|
| Plugin-local gitignored file | Self-contained, replaceable with the client. Non-dotfile name required — dotfiles are permission-blocked in this environment. | ✓ (modified) |
| Reuse repo root .env | Couples client to a backend file; .env is permission-blocked. | |
| Environment variables only | Operator in Claude Desktop cannot set env vars. | |

**User's choice:** Plugin-local gitignored file, **plus a git-versioned example file** referenced in the plugin README as part of documented setup.
**Notes:** User added the committed example-file requirement, which was not in the presented options.

---

## Setup role (follow-up — surfaced requirement conflict)

| Option | Description | Selected |
|--------|-------------|----------|
| Admin provisions; README documents it as an admin task | Keeps PLUGIN-02 intact. | |
| Operator does setup once, from the example file | One less person in the loop, but hands a non-technical operator a webhook secret — direct conflict with PLUGIN-02. | ✓ |
| Either — README covers both paths | Leaves the requirement ambiguous for the planner. | |

**User's choice:** Operator does setup once
**Notes:** Chosen with the PLUGIN-02 conflict stated explicitly. Recorded in CONTEXT.md as D-05, an accepted requirement amendment. REQUIREMENTS.md PLUGIN-02 still needs rewording.

---

## Preview — canonical shape vs mapping ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Pass raw, preview via read-only YAML lookup | Plugin POSTs the file unchanged; preview reads config/column_mapping.yaml purely as a lookup to show canonical shape and dropped columns. Display-only, no second mapper. | ✓ |
| Plugin maps to canonical CSV before sending | Satisfies criterion 2 literally but forks the mapping logic the scope anchor forbids. | |
| Pass raw, preview raw only | Zero coupling, weakest trust story — operator can't tell what n8n will keep. | |

**User's choice:** Pass raw, preview via read-only YAML lookup
**Notes:** This was the pivotal question of the discussion — Phase 23's success criterion 2 ("canonical contact props only") pulls against the milestone scope anchor ("tabular inputs pass through to the existing mapper"). The chosen option satisfies both by separating what is *sent* from what is *shown*.

---

## Preview scope

| Option | Description | Selected |
|--------|-------------|----------|
| Adaptive: full if small, sample if large | ≤ ~20 rows shows all; above that first 10 + last 3 + count + fill rates. | ✓ |
| Always full table | Buries chat on a 500-row batch. | |
| Always sample + counts | Annoying for a 6-row batch. | |

**User's choice:** Adaptive
**Notes:** Recommended option taken as-is.

---

## Preview rendering surface

| Option | Description | Selected |
|--------|-------------|----------|
| Chat by default, Artifact on request | Mirrors the STATUS-05 convention Phase 27 will set. | ✓ |
| Always publish an Artifact | Publish round-trip on every preview; approval still happens in chat. | |
| Chat only | Wide tables wrap badly in Claude Desktop. | |

**User's choice:** Chat by default, Artifact on request
**Notes:** Recommended option taken as-is.

---

## Arming mechanism (interim, pre-Phase-28)

| Option | Description | Selected |
|--------|-------------|----------|
| Confirmation held in conversation only | Operator types an arm phrase; skill passes a flag for that send. Nothing written to disk, so the grant cannot outlive or be inherited. | ✓ |
| Armed-until timestamp in a local state file | Survives compaction, but a file-backed grant can outlive the conversation — forbidden by DISPATCH-03/CONTROL-04. | |
| Admin-only config flag, no operator arming yet | Safest, but leaves the operator no path, failing success criterion 3. | |

**User's choice:** Confirmation held in conversation only
**Notes:** Deliberately the weaker mechanism; Phase 28 supersedes it with the real n8n-side implementation.

---

## File handoff

| Option | Description | Selected |
|--------|-------------|----------|
| Filesystem path, operator says where | Works today, no upload plumbing. | |
| Desktop attachment, plugin reads attached file | Most natural for a non-technical operator; depends on attachments being exposed to skills as a readable path. | |
| Both, path as fallback | Widest coverage, most surface to build in a walking-skeleton phase. | ✓ |

**User's choice:** Both, path as fallback
**Notes:** Research must confirm whether Claude Desktop exposes attachments to a skill as a readable path. If not, the attachment leg degrades to the path leg and the phase still works — flagged as an open research item, not a blocker.

---

## Claude's Discretion

- Exact slash-command name and skill trigger phrasing
- Python module layout under `operator-claude-plugin/scripts/`, and the XLSX library choice
- Wording of preview table, arming prompt, and not-configured refusal message
- Whether fill rates are computed per column or only for canonical props
- HTTP client, timeout, and retry posture for the single POST

## Deferred Ideas

- PLUGIN-02 rewording to match D-05 (operator self-setup)
- Real conversation-scoped arming — Phase 28 / CONTROL-04
- Per-record outcome reporting — Phase 26 / REPORT-01
- Cost estimation before send — Phase 25 / PREVIEW-02
- Chunking large batches — Phase 25 / PREVIEW-03
- Identity-rule failures separated and reported — Phase 24 / STRUCT-02
