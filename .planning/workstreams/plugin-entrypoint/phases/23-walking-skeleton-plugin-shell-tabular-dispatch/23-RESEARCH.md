# Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch - Research

**Researched:** 2026-07-30
**Domain:** Claude Code plugin packaging + n8n webhook client (HTTP dispatch, no backend logic)
**Confidence:** MEDIUM — backend contract and packaging mechanics are HIGH; the Claude Desktop
file-handoff question (D-14) is the one item this research could not fully close and is called
out explicitly below with a cheap way to close it before building on top of it.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The plugin is a **Claude skill (markdown `SKILL.md`) driving thin Python scripts**
  under `operator-claude-plugin/scripts/`. The skill owns the conversation; Python owns
  spreadsheet parsing and the HTTP POST. The plugin carries its **own** `requirements.txt` so it
  stays independently replaceable — it does not import from the repo's `src/` or reuse the
  backend's dependency set. — Reversibility: costly.
- **D-02:** Invocation is **both** a slash command and an intent trigger. A discoverable slash
  command is the handle a non-technical operator can remember; the `SKILL.md` description also
  fires on natural phrasing. Both paths enter the same code — the slash command is not a second
  implementation.
- **D-03:** Configuration lives in a **plugin-local gitignored file** with a **committed example
  file** alongside it (e.g. `operator-claude-plugin/config/operator.local.json` gitignored, and
  `operator.local.example.json` tracked). The README documents the setup step.
- **D-04:** The filename must **not** be a dotfile (dotfiles are permission-blocked in this
  environment — see `.env`, unreadable to tooling). Environment constraint, not style.
- **D-05:** **The operator performs setup once, from the example file** — a deliberate amendment
  to PLUGIN-02 (which still says admin-provisioned). REQUIREMENTS.md wording must be reconciled
  before Phase 23 is marked complete. — Reversibility: reversible.
- **D-06:** Missing/rejected configuration → refuse **before any network call**, plain language,
  never show a key, never ask the operator to paste one, never surface a raw socket error.
- **D-07:** Tabular input is **passed through unchanged** — POST the file as read, let n8n's
  `Map Columns` node map it. The preview reads `config/column_mapping.yaml` as a **read-only
  lookup table** (`Company Name → company`, `Notes → dropped`), display-only — never used to
  transform rows. — Reversibility: costly.
- **D-08:** Preview is **adaptive**: ≤ ~20 rows renders every row; above that, first 10 + last 3 +
  total row count + per-column fill rates.
- **D-09:** Preview renders as a **markdown table in chat by default, with a published Artifact on
  request** (matches STATUS-05's convention from Phase 27).
- **D-10:** Declining the preview sends nothing and costs nothing beyond reading the file.
- **D-11:** Live-write permission is held **in the conversation only**. The operator types an
  explicit arming phrase and the skill passes an armed flag to the dispatch script for that send.
  **Nothing is written to disk.** Phase 28 replaces this with the real n8n-side mechanism
  (CONTROL-04); this is deliberately the weaker, stateless placeholder. — Reversibility:
  reversible.
- **D-12:** The plugin **states up front** which endpoint it targets and whether dispatch is
  currently armed, before any work is done.
- **D-13:** With live writes off (default), an *approved* batch is still not sent — told plainly
  that sending is off and how to turn it on for this conversation.
- **D-14:** **Both** file-handoff paths are supported, attachment first with filesystem path as
  fallback. Research must confirm whether Claude Desktop exposes attachments to a skill as a
  readable path — if it does not, the attachment leg degrades to the path leg and the phase still
  works.

### Claude's Discretion

- Exact slash-command name and skill trigger phrasing.
- Python module layout inside `operator-claude-plugin/scripts/`, and which library reads XLSX.
- Wording of the preview table, the arming prompt, and the not-configured refusal message.
- Whether the preview computes fill rates per column or only for the canonical props.
- HTTP client choice, timeout, and retry posture for the single POST.

### Deferred Ideas (OUT OF SCOPE)

- **PLUGIN-02 rewording** — reconcile admin- vs operator-provisioned wording before phase close.
- **Real conversation-scoped arming** — Phase 28 / CONTROL-04.
- **Per-record outcome reporting** — Phase 26 / REPORT-01. Phase 23 reports only "POST accepted."
- **Cost estimation before send** — Phase 25 / PREVIEW-02.
- **Chunking large batches** — Phase 25 / PREVIEW-03.
- **Identity-rule failures separated and reported** — Phase 24 / STRUCT-02.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-02 | Point the plugin at a CSV/XLSX and have rows read without pre-cleaning headers | §Standard Stack, §File reading (openpyxl/csv), §D-14 file-handoff findings |
| STRUCT-01 | Rows emitted over canonical contact props only, unchanged for `Map Columns` | §Backend contract (`column_mapping.yaml`, canonical props), §D-07 preview design |
| PREVIEW-01 | Operator sees exact structured payload + row count before send, must approve | §Preview rendering pattern, §Architecture Patterns |
| PREVIEW-04 | Decline costs nothing beyond reading the file | §Architecture Patterns (two-phase preview/dispatch split) |
| DISPATCH-01 | Approved batch POSTs to `hubspot/contact-upload` with correct header auth + body encoding | §The `hubspot/contact-upload` request contract (exact) |
| DISPATCH-03 | Disarmed by default; conversation-scoped arming, granted in chat | §Two-key write-gate convention, §Arming design |
| PLUGIN-01 | Installs and runs as a Claude plugin, not a hand-run script | §Claude plugin packaging mechanics |
| PLUGIN-02 | Config admin-provisioned outside plugin source, never committed (amended by D-05) | §Configuration provisioning |
| PLUGIN-03 | Refuses before any network call when config missing/rejected, names what's broken | §Configuration provisioning, §Common Pitfalls |
| PLUGIN-04 | All client files under `operator-claude-plugin/`, own README+CHANGELOG, no backend file touched | §Recommended Project Structure, §Don't Hand-Roll |
</phase_requirements>

## Summary

This phase has two research halves, and they turned out to be asymmetric in how settled they
are. The **backend contract half** (webhook path, auth header, binary field name, response mode)
is now fully pinned down by reading the actual deployed workflow JSON and the deploy scripts that
bind its credentials — there is no ambiguity left to plan around. The **Claude plugin/runtime
half** (how the plugin is packaged, and whether an operator-attached file becomes a real path a
Python script can open) required external verification because the product surface moved since
training: "Claude Desktop" as of the current docs is one app with three tabs (Chat, Cowork, Code),
and only the **Code tab is Claude Code itself** — the one that supports installable
`.claude-plugin/plugin.json` bundles with `skills/` folders, the exact shape D-01 already
committed to. That resolves the packaging question cleanly. It also reframes the file-handoff
question: this is not "does *some* Claude surface expose an attachment as a path" in the abstract,
it is specifically "does the Code tab's file-attachment feature hand Read/Bash tools a real path
for a non-image file" — and that is the one fact this research could not fully confirm from docs
alone (see the dedicated section below). The recommended shape closes that gap cheaply: build the
guaranteed-to-work path first (Code tab's own `@mention` file autocomplete — no attachment
plumbing required, no terminal, no raw path typed) and treat literal attachment as an opportunistic
first try behind a single early smoke-test task, per D-14's own instruction not to build plumbing
that can't work.

**Primary recommendation:** Package as a single-skill Claude Code plugin (`.claude-plugin/
plugin.json` + `skills/<name>/SKILL.md` + `skills/<name>/scripts/*.py`, no separate `commands/`
directory needed — current guidance is skills-only for new plugins, and a plugin's skill is
*already* both auto-triggered and slash-invocable as `/plugin-name:skill-name`, which satisfies
D-02 with zero duplicate code path). Build the primary file-handoff path around Code tab's
`@mention` autocomplete (guaranteed real path, no shim), attempt attachment opportunistically,
and gate any attachment-specific code behind one early live smoke test. Read files locally with
`openpyxl` + stdlib `csv` (no pandas). POST `multipart/form-data` with a field literally named
`data` (matching `Extract From File`'s `binaryPropertyName`) to `${N8N_URL}/webhook/hubspot/
contact-upload`, header `X-Enrichment-Secret: <secret>` — yes, that literal header name, confirmed
below, despite naming that suggests it's enrichment-only.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Conversation UX, arming, refusal messages | Claude skill (SKILL.md, prompt-level) | — | Human-judgment surface; no code needed beyond string templates |
| File reading (CSV/XLSX → rows for preview) | Plugin Python script | — | Deterministic parsing; a skill markdown file cannot open binary files itself |
| Preview rendering (markdown table / Artifact) | Claude skill, driven by script output | Plugin Python script (computes fill rates, truncation) | Rendering choice is conversational; the *data* it renders is computed deterministically |
| Column-alias lookup for preview labels | Plugin Python script (reads `config/column_mapping.yaml`) | — | Display-only per D-07; never transforms the wire payload |
| HTTP dispatch (multipart POST) | Plugin Python script | — | Deterministic, testable, must not depend on model judgment |
| Column mapping, phone/email normalization, verification, identity resolution, dedupe, create/update routing | n8n (`hubspot/contact-upload` workflow) | — | Explicitly out of scope per REQUIREMENTS.md scope anchor; forking this would create a second source of truth |
| Credential storage (webhook secret) | Plugin-local gitignored config file | — | D-03/D-04; never n8n's own credential store (plugin holds no HubSpot/provider creds) |

## Claude Plugin Packaging Mechanics

**[CITED: code.claude.com/docs/en/desktop, code.claude.com/docs/en/plugins]**

### The product-surface fact that resolves D-01/PLUGIN-01

As of the current docs, "Claude Desktop" is a single app with three tabs: **Chat** (the
consumer claude.ai-style conversation), **Cowork** (workspace-folder agentic work, syncs skills/
plugins from a `Customize` account config, separate from `~/.claude`), and **Code** — which *is*
Claude Code, running with a GUI. Only the **Code tab**:

- Reads the same `.claude/` project config, `CLAUDE.md`, and plugin mechanism as the CLI.
- Lets a user "install plugins from the desktop app without using the terminal" — click **+** →
  **Plugins** → **Add plugin** to browse configured marketplaces, or a plugin can be dropped in
  as a local directory for dev/test with `claude --plugin-dir ./operator-claude-plugin` (no
  install step at all during development).
- Supports file attachments (drag-and-drop or the attachment button) directly on a prompt.

This is the tab the operator must be using for "installed as a plugin, not a hand-run script"
(success criterion 1) to make sense at all — the Chat tab's "Skills" feature (Settings →
Customize → Skills → upload a ZIP) is a *different*, single-skill-only mechanism with no
`.claude-plugin/plugin.json`, no `commands/`, and a different (sandboxed, `/mnt/user-data/
uploads/`) file-handling model. Since D-01 already commits to `.claude-plugin`-style packaging
under a git-tracked `operator-claude-plugin/` directory with its own README/CHANGELOG (PLUGIN-04),
the Code-tab plugin mechanism is the one to build against, not the Chat-tab Skill-ZIP mechanism.
**This should be stated explicitly to the user once during planning** — it determines which
literal button an operator clicks, and confusing the two tabs would produce correct code that the
operator can't actually reach.

### Concrete, confirmed directory layout

Verified two ways: the official docs quickstart, and by inspecting real installed plugins on this
machine (`~/.claude/plugins/cache/knowledge-work-plugins/customer-support/1.2.0/`,
`~/.claude/plugins/cache/ponytail/ponytail/4.8.4/`, and the built-in `xlsx`/`docx` skills at
`~/.agents/skills/xlsx/`) — all three agree on the shape:

```text
operator-claude-plugin/
  .claude-plugin/
    plugin.json              # manifest: name, description, version, author (all that's required)
  skills/
    contact-upload/           # folder name -> skill name; namespaced as /<plugin-name>:contact-upload
      SKILL.md                # YAML frontmatter (name/description/argument-hint) + prompt body
      scripts/
        preview.py             # read file, render preview data (no network)
        dispatch.py             # multipart POST to hubspot/contact-upload
        config_gate.py          # load + validate operator.local.json; refuse-before-network-call
  config/
    operator.local.example.json   # tracked — the template the operator copies (D-03)
    operator.local.json           # gitignored — real secret, created by the operator (D-05)
  requirements.txt              # openpyxl, requests, PyYAML — nothing from repo root's requirements.txt
  README.md                     # already exists
  CHANGELOG.md                  # already exists
  tests/
    test_config_gate.py
    test_preview_rendering.py
    test_dispatch_multipart.py
    test_no_backend_imports.py    # architecture guard, mirrors tests/test_architecture_guard.py
```

Key facts from the docs that shape this layout, not assumptions:

- `.claude-plugin/` contains **only** `plugin.json`. Putting `skills/`, `commands/`, `agents/`, or
  `hooks/` inside `.claude-plugin/` is the single most common mistake the docs call out — all of
  those live at the **plugin root**, one level up.
- **`commands/` is legacy** ("Skills as flat Markdown files. Use `skills/` for new plugins"). A
  plugin skill is *already* namespaced and slash-invocable as `/plugin-name:skill-name` **and**
  auto-triggered by its own `description` frontmatter matching natural phrasing — this is D-02's
  "both a slash command and an intent trigger, same code" **for free**, with no separate
  `commands/*.md` file needed. Recommend dropping the `commands/` directory from the plan
  entirely; it would be a second, redundant entry point for identical behavior.
- A plugin that ships exactly one skill may put `SKILL.md` directly at the plugin root instead of
  under `skills/<name>/` — but the docs recommend the `skills/` layout "for plugins that may grow
  to more than one skill," which this one will (Phase 24 adds more input adapters onto the same
  shell). Use `skills/contact-upload/SKILL.md` from the start so Phase 24 is additive, not a
  restructure.
- `plugin.json` required content is trivial: `{"name", "description", "version", "author"}`.
  `version` is optional but recommended — omitting it means every git commit counts as a new
  version for marketplace distribution, which doesn't matter for a local/team-scoped plugin like
  this one but costs nothing to set.
- Scripts co-locate under the skill's own `scripts/` directory and are invoked by relative path
  from the `SKILL.md` prompt body (`python scripts/dispatch.py …`) — this is the exact pattern
  the built-in `xlsx` skill uses (`scripts/recalc.py`), confirmed by reading that skill's actual
  files on disk. No `bin/`-on-PATH mechanism is needed for this phase (that's for plugin-wide CLI
  tools, not a single skill's helper scripts).
- Dev/test loop: `claude --plugin-dir ./operator-claude-plugin` loads the plugin for that session
  with no install step; `/reload-plugins` picks up edits without restarting; `claude plugin
  validate ./operator-claude-plugin` lints the manifest before anyone tries to install it for
  real. Recommend this as the phase's actual verification method (see Validation Architecture).

## File Handoff (D-14) — the one open risk

**[CITED, partially confirmed — recommend a cheap live check before relying on it]**

Two behaviors, confirmed from different sources, that matter here and are easy to conflate:

1. **The Chat-tab / code-execution-tool sandbox convention.** When a Claude surface has the
   *code execution tool* enabled (this is the mechanism the built-in `xlsx`/`docx`/`pptx` skills
   rely on), an uploaded file is written to disk at `/mnt/user-data/uploads/<filename>` and is
   directly readable by any script the skill runs — this is well documented and is exactly how
   those skills' own bundled scripts operate. **This is NOT the same product surface as a Claude
   Code plugin.** It applies to the Chat tab's Skills feature, not to a `.claude-plugin/
   plugin.json` bundle running in the Code tab.
2. **The Code tab (Claude Code, where this plugin's packaging targets).** The Desktop docs
   confirm file attachments exist here too (drag-and-drop or the attachment button), and — per a
   separate search result — drag-and-drop explicitly accepts "PDFs, CSVs, DOCX, XLSX, images, and
   text files," so the file *type* is not the blocker. What the docs do **not** state is whether
   an attached non-image file becomes a real filesystem path visible to the Read/Bash tools a
   skill's Python scripts run through. A still-open GitHub issue on this exact codebase
   (`anthropics/claude-code#54062`, tracked but marked duplicate — i.e. acknowledged, not
   resolved) describes the opposite: Claude Code today gives the model **visual perception** of an
   attached image but **no programmatic access to its bytes or path**, and the only workarounds
   are unreliable temp-directory guessing. That issue was about images specifically, but the
   underlying mechanism (attachment → model context vs. attachment → filesystem) is the same
   mechanism a CSV/XLSX attachment would go through.

**Net assessment:** the attachment leg's outcome is genuinely uncertain from documentation alone,
which is exactly the ambiguity D-14 asked this research to resolve or flag. It could not be fully
resolved without a live Desktop Code-tab session to test in (outside this research agent's
reach). Rather than guess, the recommended shape makes the uncertainty free to carry:

- **Build the path leg as the actually-guaranteed mechanism**, but don't make the operator "type a
  filesystem path" feel technical: the Code tab's own **`@mention` file picker with autocomplete**
  ("local and SSH sessions only" — confirmed) already lets a non-technical operator type `@` and
  fuzzy-pick their spreadsheet by name, and Claude Code's own Read tool resolves that mention to a
  real absolute path with zero shim code required — it's the same mechanism this very session uses
  to read files. This satisfies D-14's fallback leg with a better UX than a raw path prompt, and it
  is **guaranteed to work** because it's how Claude Code already reads every file in this
  environment.
- **Attempt the attachment leg first, exactly as D-14 asks**, but keep the code path thin: try to
  read the file at whatever path/reference the conversation surfaces for an attachment; if that
  read fails or the environment gives no path at all, fall straight to asking the operator to
  `@mention` the file instead. Do not build retry loops, temp-directory scanning, or upload-shim
  guessing for the attachment leg — that is precisely the "plumbing that cannot work" D-14 warns
  against building.
- **Recommend one very cheap Wave 0 task**: attach a small CSV in a real Desktop Code-tab session
  and ask Claude to read it, before writing the rest of the ingestion code around an assumption
  either way. This resolves the uncertainty for less cost than building both legs blind.

## The `hubspot/contact-upload` request contract (exact, read from the deployed JSON)

**[VERIFIED: n8n/wf_contact_ingest_cloud.json, scripts/deploy_n8n_workflows.py,
scripts/provision_n8n_credentials.py]**

| Property | Value | Source |
|---|---|---|
| HTTP method | `POST` | `Webhook Trigger` node, `parameters.httpMethod` |
| Path | `hubspot/contact-upload` | `Webhook Trigger` node, `parameters.path` |
| Full URL | `${N8N_URL}/webhook/hubspot/contact-upload` (production path, workflow is deployed **active** per STATE.md — not `/webhook-test/`) | `.env.example` (`N8N_URL=https://<subdomain>.n8n.cloud`), n8n convention |
| Auth | Header Auth (n8n `httpHeaderAuth` generic credential) | `Webhook Trigger.parameters.authentication = "headerAuth"` |
| **Header name** | **`X-Enrichment-Secret`** | `scripts/provision_n8n_credentials.py` — `_webhook_secret_data()` returns `{"name": "X-Enrichment-Secret", "value": os.getenv("N8N_ENRICHMENT_WEBHOOK_SECRET")}` for the **`LV Enrichment Webhook`** credential object |
| Header value | Whatever `N8N_ENRICHMENT_WEBHOOK_SECRET` is set to at provisioning time | same |
| Body encoding | `multipart/form-data`, one file field, field name **`data`** | `Extract From File` node: `{"operation": "csv", "binaryPropertyName": "data"}` |
| File format | CSV bytes (not XLSX) | `Extract From File`'s `operation` is fixed to `"csv"` — it does not parse XLSX |
| Response | JSON, `responseMode: "lastNode"` | `Webhook Trigger.parameters.responseMode` |

**The non-obvious finding worth flagging loudly:** `scripts/deploy_n8n_workflows.py` deploys
`hubspot/contact-upload` and `hubspot/enrichment/event` from the **same** static
`NODE_CREDENTIAL_MAP`, which maps *any* node literally named `"Webhook Trigger"` — a name both
workflows' trigger nodes share — to the **same** credential object, `"LV Enrichment Webhook"`
(confirmed: `deploy_n8n_workflows.py` globs `wf_*_cloud.json`, i.e. all three cloud workflow files,
and applies one shared node-name→credential map across all of them). So despite the name
"Enrichment Webhook," the header the contact-upload endpoint actually expects **as currently
deployed** is `X-Enrichment-Secret`, using the value of `N8N_ENRICHMENT_WEBHOOK_SECRET`. A plugin
built around a differently-named header (e.g. an intuitive `X-Contact-Upload-Secret`) would 401
against the live endpoint. If this is ever split into a distinct credential for contact-upload,
that's a backend-side deploy-script change outside this phase's scope — but the plugin's config
schema and refusal-message wording should name the header it's actually sending
(`X-Enrichment-Secret`) rather than inventing a more intuitive one, so a diagnosing admin can grep
the deploy script and find the match immediately.

**Response-shape caveat (do not overpromise in Phase 23):** `responseMode: lastNode` over a
workflow that branches into three disjoint terminal nodes (`HubSpot Update` / `HubSpot Create` /
`Set Review`) means the HTTP response body reflects whichever node executes topologically last in
that run — not necessarily a complete per-row ledger across all three branches. This is already
flagged in ROADMAP.md as a Phase 26 (REPORT-01) concern to verify properly. For Phase 23, the
plan should only claim "the POST was accepted and n8n returned *something* JSON-shaped" — not "a
complete per-row outcome for every row," which is explicitly out of scope (Deferred Ideas). Success
criterion 3's "n8n returns per-row items" should be read as "the response n8n gives back is
whatever it gives back" for this phase, with the completeness question deferred to Phase 26 as the
carried Roadmap note already says.

## `config/column_mapping.yaml` — exact schema (display-only per D-07)

**[VERIFIED: config/column_mapping.yaml]**

```yaml
aliases:
  # lowercased/trimmed source header -> canonical HubSpot contact prop
  "email address": email
  "first name": firstname
  # ... (30 total alias entries across 7 canonical props)
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
```

Canonical contact props covered: `email, firstname, lastname, jobtitle, linkedin_url, phone,
company` — matches REQUIREMENTS.md's canonical list exactly. The comment in the YAML itself
states the matching rule precisely: **"Header lookup is case-insensitive and whitespace-collapsed"**
— confirmed by the existing `src/column_mapper.map_row` implementation (not importable per D-01,
but the *rule* it encodes — lowercase + collapse internal whitespace before dictionary lookup — is
public information the plugin's own preview code must reimplement identically, or the preview will
mislabel a header n8n would actually map, breaking the "did you lose any of my data" guarantee the
CONTEXT.md Specific Ideas section calls out as the preview's real value. This is a few lines
(`" ".join(header.strip().lower().split())` before the `aliases` dict lookup) — not worth a
dependency, worth getting exactly right since it's user-facing trust, not internal plumbing.

Any header not found in `aliases` (after that normalization) renders as `<header> → dropped` in
the preview, per D-07's stated example.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openpyxl` | `>=3.1.2` | Read `.xlsx` rows for preview + convert to CSV for the wire body | Already pinned and in live use in this exact repo's own `src/file_loader.py` for the identical job — same version floor, no new evaluation needed |
| `requests` | `>=2.32.0` | Single multipart POST | Already the HTTP client throughout this repo's own `scripts/*.py` (e.g. `deploy_n8n_workflows.py`); consistent with Claude's Discretion on HTTP client choice |
| `PyYAML` | `>=6.0.2` | Parse `config/column_mapping.yaml` for the display-only preview lookup | Same — already pinned in this repo for the same file format |

Stdlib covers everything else needed: `csv` (read/write CSV, including the XLSX→CSV conversion),
`json`, `pathlib`. **No pandas** — nothing here needs a dataframe; row-by-row dict processing is
the right size (ponytail: rung 3, stdlib does it).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `openpyxl` for XLSX | Manual `zipfile` + `xml.etree` parsing (XLSX is a zip of XML — no non-stdlib dependency at all) | Zero install risk if the plugin's runtime sandbox turns out to restrict `pip install` (see Environment Availability below), but meaningfully more code (~60-100 lines to walk shared-strings + sheet XML) for a problem `openpyxl` already solves in this exact repo. Not worth building preemptively — only fall back to this if the phase's own smoke test shows `pip install -r operator-claude-plugin/requirements.txt` doesn't work in the target runtime. |
| `requests` for HTTP | stdlib `urllib.request` + hand-built multipart body | Saves one dependency; multipart/form-data encoding by hand is a well-known but fiddly ~30-line recipe (boundary generation, header assembly). `requests` is already the established pattern in this repo (`scripts/deploy_n8n_workflows.py`) — take the higher ponytail rung only if the pip-install risk above materializes for real. |

**Installation:**
```bash
pip install -r operator-claude-plugin/requirements.txt
```

**Version verification:** All three packages are already pinned and running in this repo's root
`requirements.txt` (`openpyxl>=3.1.2`, `requests>=2.32.0`, `PyYAML>=6.0.2`) for the identical jobs
(XLSX reading, HTTP calls to n8n/HubSpot, YAML config parsing). Tagged VERIFIED via direct
codebase inspection (`requirements.txt`, `src/file_loader.py`) rather than a fresh registry lookup
— these are not new dependency decisions, they are the same tools this codebase already vetted and
runs in production, so re-verifying via `npm view`/`pip index versions` here would only rediscover
what a `grep` already confirmed.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `openpyxl` | PyPI | 15+ yrs | tens of millions/week | `foss.heptapod.net/openpyxl/openpyxl` (also mirrored on GitHub/Bitbucket historically) | OK | Approved — already in production use in this repo |
| `requests` | PyPI | 15+ yrs | hundreds of millions/week | `github.com/psf/requests` | OK | Approved — already in production use in this repo |
| `PyYAML` | PyPI | 15+ yrs | hundreds of millions/week | `github.com/yaml/pyyaml` | OK | Approved — already in production use in this repo |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none. All three are top-tier, decade-plus-old PyPI
packages already vetted and running in this exact codebase for the same purpose — no new
legitimacy question exists here; a fresh `package-legitimacy check` run would only reconfirm what
this repo's own `requirements.txt` already establishes.

## Architecture Patterns

### System Architecture Diagram

```text
Operator (Claude Desktop, Code tab)
  │
  │  "load these contacts into hubspot" / "/operator-claude-plugin:contact-upload"
  ▼
Skill (SKILL.md) — conversation owner
  │
  ├─ 1. State up front: target endpoint + armed/disarmed (D-12)         [no I/O]
  │
  ├─ 2. Resolve input file
  │     ├─ try: read operator-attached file (uncertain path — see D-14 section)
  │     └─ fallback: ask operator to @mention the file (guaranteed real path)
  │
  ├─ 3. config_gate.py  → load operator.local.json
  │     ├─ missing/invalid → refuse in plain language, STOP (no network call)  [PLUGIN-03]
  │     └─ valid → continue
  │
  ├─ 4. preview.py  → read file (openpyxl/csv), label headers via column_mapping.yaml (display-only)
  │     └─ render markdown table (≤20 rows: all; >20: first10+last3+counts+fill-rates)  [D-08/D-09]
  │
  ├─ 5. Operator approves? ──no──> STOP, nothing sent, nothing cost beyond the read  [PREVIEW-04]
  │        │yes
  │        ▼
  ├─ 6. Armed this conversation? ──no──> tell operator plainly, explain how to arm, STOP  [D-13]
  │        │yes (operator just said the arming phrase)
  │        ▼
  └─ 7. dispatch.py  → convert to CSV bytes if source was XLSX (unchanged if already CSV)
        → multipart POST, field "data", header X-Enrichment-Secret
        → ${N8N_URL}/webhook/hubspot/contact-upload
        → report back whatever n8n's JSON response was (no per-row parsing yet — Phase 26)
```

### Recommended Project Structure

See §Claude Plugin Packaging Mechanics above for the full annotated tree.

### Pattern 1: Preview/Dispatch as two separate, side-effect-free-until-armed scripts
**What:** `preview.py` never makes a network call; `dispatch.py` is the only script that does, and
it takes an explicit `armed: bool` argument that the skill only passes as `True` when the operator
has just spoken the arming phrase this turn.
**When to use:** Any write path in this repo — this mirrors the existing two-key convention
(`DRY_RUN=false AND ALLOW_X=true`) used throughout `scripts/*.py` (`deploy_n8n_workflows.py`,
`sync_hubspot_properties.py`, `migrate_org_type_enum.py`, etc.), adapted for a conversation-only
gate instead of two env vars, because D-11 explicitly rules out any file-based second key.
**Example:**
```python
# scripts/dispatch.py — sketch, not final code
def dispatch(file_path: str, armed: bool, config: dict) -> dict:
    if not armed:
        raise RuntimeError("Live writes are off for this conversation — nothing was sent.")
    csv_bytes = _to_csv_bytes(file_path)  # pass-through if already .csv, convert if .xlsx
    resp = requests.post(
        f"{config['n8n_url']}/webhook/hubspot/contact-upload",
        headers={"X-Enrichment-Secret": config["webhook_secret"]},
        files={"data": ("contacts.csv", csv_bytes, "text/csv")},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
```

### Anti-Patterns to Avoid
- **Re-deriving canonical rows client-side before sending.** D-07 is explicit: the file goes over
  the wire unchanged (or XLSX→CSV re-serialized with the *same* headers/values, never remapped).
  Only the *preview's rendering* consults `column_mapping.yaml`, and only to label columns for
  display — never to reshape the payload.
- **A second `commands/*.md` entry point duplicating the skill's own trigger.** Per the packaging
  research above, this is unnecessary work that current Claude Code plugin guidance actively
  steers away from ("Use skills/ for new plugins").
- **Persisting the armed flag anywhere** (file, env var read at skill-start, cached state) — D-11
  is explicit that nothing may outlive the single dispatch call within the current conversation.
- **Reading raw XLSX bytes into the POST body.** `Extract From File` runs `operation: "csv"` —
  sending native XLSX binary will not parse the way an operator expects; convert to CSV text
  client-side first for any XLSX input.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Column mapping | A second alias table or fuzzy-header matcher | n8n's existing `Map Columns` node, fed the unchanged file (D-07) | Explicit scope anchor in REQUIREMENTS.md — forking this is the single most-repeated "don't" across every planning document for this milestone |
| Multipart/form-data encoding | Hand-rolled boundary + header construction | `requests`' `files=` parameter | `requests` already does this correctly and is already the established HTTP client in this repo |
| Header-normalization rule for the preview's alias lookup | A "smarter" fuzzy matcher (Levenshtein, etc.) | The exact rule already encoded in `config/column_mapping.yaml`'s own comment: lowercase + collapse whitespace, dictionary lookup | Anything smarter than n8n's actual matching rule will mislabel columns the backend really does map — the preview's job is truth about what n8n will do, not a better heuristic |
| XLSX parsing | Full spreadsheet-model libraries (pandas, xlrd, pyexcel) | `openpyxl` `read_only=True` iteration (already the pattern in `src/file_loader.py`) | This phase only needs header row + data rows, nothing about formulas, styles, or multi-sheet workbooks |

**Key insight:** every "don't hand-roll" here traces back to the same root cause the CONTEXT.md
already names explicitly: this plugin is a thin client over an existing, tested backend contract.
The temptation to hand-roll shows up exactly where someone reaches for "a slightly better version"
of something n8n already does (mapping, normalization) — the fix is always "read the unchanged
file through," never "build a nicer mapper."

## Common Pitfalls

### Pitfall 1: Wrong header name on the auth header
**What goes wrong:** Sending `X-Contact-Upload-Secret` or any other intuitively-named header
instead of the literal `X-Enrichment-Secret` the deployed credential actually checks.
**Why it happens:** The credential is named `LV Enrichment Webhook` and the header name reads like
it belongs only to the enrichment endpoint; nothing about `hubspot/contact-upload`'s own naming
suggests it shares that credential.
**How to avoid:** Read the header name from `scripts/provision_n8n_credentials.py`'s
`_webhook_secret_data()` (already done — see §The request contract above), not from intuition.
**Warning signs:** A 401 on the very first live test, with a correctly-formatted secret value.

### Pitfall 2: Sending XLSX bytes unchanged
**What goes wrong:** `Extract From File` is hardcoded to `operation: "csv"`; posting a raw `.xlsx`
binary produces garbage rows or a parse failure the operator has no way to interpret.
**Why it happens:** D-07's "pass the file through unchanged" reads, at a skim, like "never touch
the bytes" — but it means "never remap columns," not "never re-serialize format."
**How to avoid:** Detect the source extension; for `.xlsx`, read via `openpyxl` and re-emit as CSV
text with the identical header row and cell values before building the multipart body. For `.csv`,
send the original bytes untouched.
**Warning signs:** n8n returns rows with garbled or empty fields despite a clean-looking preview.

### Pitfall 3: Building attachment plumbing before confirming it works
**What goes wrong:** Sinking implementation effort into temp-directory scanning, retry loops, or
upload-shim guessing for the attachment leg of D-14, only to find the Code tab doesn't expose a
real path for non-image attachments (the open, unresolved GitHub issue on this exact codebase
describes exactly this failure mode for images).
**Why it happens:** D-14 says "attachment first" and it's tempting to build it fully before testing.
**How to avoid:** One live smoke test first (attach a CSV, ask Claude to read it) before writing
anything beyond a single try/except around the attempt. Build the `@mention` path leg as the
actually-relied-upon mechanism regardless of the smoke test's outcome.
**Warning signs:** Attachment-handling code growing past a few lines, or any code that guesses at a
filesystem path rather than being told one directly.

### Pitfall 4: Config file confused for a dotfile
**What goes wrong:** Naming the local config `.operator.json` or similar — dotfiles are
permission-blocked to Read/Bash tooling in this development environment (confirmed via this
project's own carried memory: `.env` is unreadable to tooling here), so a dotfile config would be
unreadable at runtime by the same class of tool that must read it to gate the network call.
**Why it happens:** `.env`-style naming is a very common convention for exactly this kind of local
secret file, so it's an easy default to reach for.
**How to avoid:** D-04 already settled this — use a non-dotfile name
(`operator.local.json` / `operator.local.example.json`), as specified.

## Code Examples

### Reading + previewing a CSV or XLSX without pre-cleaning headers
```python
# Source: pattern already proven in src/file_loader.py (not imported — reimplemented per D-01)
import csv
from pathlib import Path

def read_rows(path: str) -> tuple[list[str], list[list[str]]]:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        return rows[0], rows[1:]
    if suffix in (".xlsx", ".xls"):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            ws = wb.active
            it = ws.iter_rows(values_only=True)
            header = ["" if c is None else str(c) for c in next(it)]
            rows = [["" if c is None else str(c) for c in r] for r in it if any(c is not None for c in r)]
            return header, rows
        finally:
            wb.close()
    raise ValueError(f"Unsupported file extension: {suffix or '(none)'}")
```

### Display-only column-mapping lookup (matches n8n's own normalization rule)
```python
# Source: config/column_mapping.yaml's own comment + src/column_mapper.py's documented rule
import yaml

def label_headers(headers: list[str], mapping_path: str = "config/column_mapping.yaml") -> dict:
    mapping = yaml.safe_load(open(mapping_path, encoding="utf-8"))
    aliases = mapping["aliases"]
    def norm(h: str) -> str:
        return " ".join(h.strip().lower().split())
    return {h: aliases.get(norm(h), "dropped") for h in headers}
```

### Multipart dispatch matching the deployed contract exactly
```python
# Source: n8n/wf_contact_ingest_cloud.json (Webhook Trigger + Extract From File nodes)
import requests

def dispatch(n8n_url: str, secret: str, csv_bytes: bytes) -> dict:
    resp = requests.post(
        f"{n8n_url}/webhook/hubspot/contact-upload",
        headers={"X-Enrichment-Secret": secret},
        files={"data": ("contacts.csv", csv_bytes, "text/csv")},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Single-skill ZIP upload via Chat-tab "Skills" (Settings → Customize → Skills) | `.claude-plugin/plugin.json` multi-component plugin bundle, installable via the Desktop app's Code-tab Plugin manager UI with no terminal | Current, per code.claude.com/docs | This phase's packaging target is the newer, richer mechanism — a plan written against the older ZIP-only Skills model would under-specify the manifest and namespacing |
| A separate `commands/*.md` file as the slash-command entry point | Plugin skills are already namespaced and slash-invocable (`/plugin-name:skill-name`); `commands/` is now called out as legacy | Current, per code.claude.com/docs/en/plugins | Avoids building a second, redundant entry point for D-02 |

**Deprecated/outdated:** treating "Claude Desktop" as a single, undifferentiated surface. The
three-tab model (Chat/Cowork/Code) is load-bearing for this phase's file-handoff and packaging
decisions and should be named explicitly in the plan.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | An operator-attached CSV/XLSX in the Code tab does *not* reliably resolve to a real filesystem path for a skill's Python scripts (based on the unresolved GitHub issue describing this gap for images, extrapolated to non-image attachments) | File Handoff (D-14) | If wrong (i.e. attachment *does* work cleanly), the recommended `@mention`-first design still works fine — it just means the attachment leg could be promoted from "opportunistic try" to "primary path" later at low cost. If assumed correct but actually attachment fails silently in some other way (not the failure mode described), the one recommended smoke-test task catches it before more code is built on the assumption. |
| A2 | The operator's actual runtime is the Desktop app's **Code tab**, not the Chat tab's Skills-ZIP mechanism or the Cowork tab | Claude Plugin Packaging Mechanics | If wrong, the entire packaging shape (`.claude-plugin/plugin.json`, `skills/`, marketplace/`--plugin-dir` install) would need to be Chat-tab Skills-ZIP shaped instead (single skill folder, no manifest, uploaded as a ZIP) — a materially different plan. This should be confirmed with the user/admin during planning, not left implicit. |

## Open Questions

1. **Which Claude Desktop tab does the operator actually use day to day?**
   - What we know: PLUGIN-01/D-01's packaging shape (`.claude-plugin/plugin.json`) only makes
     sense for the Code tab; the Chat tab's own "Skills" feature is a different, simpler,
     ZIP-upload mechanism with no manifest and a different file-handling model.
   - What's unclear: which one the actual non-technical operator will be sitting in. Everything
     about the operator persona (never opens a terminal, works in "Claude Desktop") is consistent
     with either, since both are GUI-only.
   - Recommendation: state this assumption explicitly to the user before or during planning (a
     one-line confirmation), since it is genuinely load-bearing and cheap to confirm, unlike most
     of the rest of this research.

2. **Does `pip install -r operator-claude-plugin/requirements.txt` work in the operator's actual
   runtime environment (Code-tab local session on their own machine)?**
   - What we know: a Code-tab local session runs on the operator's real machine with real Bash
     access (unlike the Chat tab's managed sandbox) — so `pip install` should behave like any
     normal local pip install, network permitting.
   - What's unclear: whether the target machine has Python/pip already available, and whether any
     corporate network policy blocks PyPI egress for a non-technical user's machine.
   - Recommendation: the plan's setup instructions (README, D-05's operator self-setup step)
     should include a `pip install` step and a plain-language message if it fails — this is really
     a Wave 0/setup-doc concern, not a design blocker.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 + pip | Running `scripts/*.py` locally | ✓ (this repo already has a working `.venv`, confirmed via project memory) | Not directly checked for the plugin's own separate install; assume operator's machine has some Python 3 | If absent on the operator's machine, this is a hard blocker outside the plugin's control — name it plainly in setup docs, not a code fallback |
| `openpyxl`, `requests`, `PyYAML` | XLSX reading, HTTP dispatch, YAML config parsing | Not yet installed under `operator-claude-plugin/` (directory is currently README+CHANGELOG only) | Pin to the same floors already proven in this repo's root `requirements.txt` | None needed — these are near-zero-risk, decade-old packages |
| n8n Cloud reachability (`${N8N_URL}`) | DISPATCH-01 | ✓ per STATE.md ("all three Cloud workflows are deployed and active") | n/a | None — this is the one live endpoint the phase must reach |
| Claude Code plugin support (Desktop app Code tab, or CLI) | PLUGIN-01 | Not directly testable from this research session | Current per code.claude.com/docs | None — this is the target runtime itself; see Open Question 1 |

**Missing dependencies with no fallback:** none block starting implementation; the two real
uncertainties (Open Questions 1 and 2) are cheap to resolve early rather than blocking research.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already the repo standard — `.venv/bin/python -m pytest`, per project memory on run commands) |
| Config file | none detected at repo root (no `pytest.ini`/`pyproject.toml`); pytest's default discovery (`test_*.py`) is what the existing `tests/` directory relies on |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| Full suite command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ tests/test_architecture_guard.py -q` (the latter to catch any accidental backend-file edit) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-02 | CSV/XLSX with arbitrary headers reads without pre-cleaning | unit | `pytest operator-claude-plugin/tests/test_preview_rendering.py -x` | ❌ Wave 0 |
| STRUCT-01 | Rows over canonical props only, unchanged wire body | unit | `pytest operator-claude-plugin/tests/test_preview_rendering.py::test_no_column_remapping -x` | ❌ Wave 0 |
| PREVIEW-01/04 | Exact payload + row count shown; decline sends nothing | unit | `pytest operator-claude-plugin/tests/test_preview_rendering.py -x` | ❌ Wave 0 |
| DISPATCH-01 | Correct method/path/header/body encoding | unit (mocked HTTP) | `pytest operator-claude-plugin/tests/test_dispatch_multipart.py -x` | ❌ Wave 0 |
| DISPATCH-03 | Disarmed by default; explicit armed flag required | unit | `pytest operator-claude-plugin/tests/test_dispatch_multipart.py::test_refuses_unarmed -x` | ❌ Wave 0 |
| PLUGIN-01 | Loads as a Claude Code plugin | manual/CLI | `claude plugin validate ./operator-claude-plugin` then `claude --plugin-dir ./operator-claude-plugin` | ❌ Wave 0 |
| PLUGIN-02/03 | Refuses before network call on missing/invalid config | unit | `pytest operator-claude-plugin/tests/test_config_gate.py -x` | ❌ Wave 0 |
| PLUGIN-04 | No backend file touched, own README/CHANGELOG | static | `pytest operator-claude-plugin/tests/test_no_backend_imports.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
- **Per wave merge:** full suite command above, plus `claude plugin validate ./operator-claude-plugin`
- **Phase gate:** full suite green, plugin validates, and one live smoke test against the actual
  `hubspot/contact-upload` webhook with a disposable test row (armed intentionally, in a
  controlled window) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `operator-claude-plugin/tests/test_config_gate.py` — covers PLUGIN-02, PLUGIN-03
- [ ] `operator-claude-plugin/tests/test_preview_rendering.py` — covers INGEST-02, STRUCT-01, PREVIEW-01, PREVIEW-04
- [ ] `operator-claude-plugin/tests/test_dispatch_multipart.py` — covers DISPATCH-01, DISPATCH-03
- [ ] `operator-claude-plugin/tests/test_no_backend_imports.py` — architecture guard, covers PLUGIN-04, mirrors `tests/test_architecture_guard.py`'s existing pattern
- [ ] Framework install: none — pytest is already a root dependency (`pytest>=8.2.0` in
  `requirements.txt`); the plugin's *own* `requirements.txt` doesn't need to repeat it since tests
  run from this repo's existing `.venv`, not the operator's runtime

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Header-auth secret (`X-Enrichment-Secret`) stored in a gitignored local file, never in code, never echoed to the operator (D-06) |
| V3 Session Management | no | No session concept beyond the conversation itself; D-11's conversation-scoped arming is a permission gate, not a session/auth mechanism |
| V4 Access Control | n/a | Single operator, single secret, no multi-user access control surface in this phase |
| V5 Input Validation | yes | Config file must be validated (required keys present, non-empty) before any network call — refuse-closed on malformed/missing config (PLUGIN-03) |
| V6 Cryptography | n/a | No cryptographic operations performed by the plugin itself (TLS to n8n Cloud is handled by `requests`/the OS trust store, not hand-rolled) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leakage via error messages (raw socket errors, stack traces showing the header value) | Information Disclosure | Catch and translate all config/network exceptions into the plain-language refusal messages D-06 mandates; never let a `requests` exception's raw text (which could echo request headers) reach the conversation unfiltered |
| Config file committed by accident | Information Disclosure | `.gitignore` entry for `operator-claude-plugin/config/operator.local.json` must be added — **not currently present** (root `.gitignore` has no entry for this path; confirmed by direct check) |
| Silent live send (arming state leaking across turns) | Tampering / Elevation of Privilege | D-11's explicit "nothing on disk" design is itself the mitigation — verified by `tests/test_no_backend_imports.py`-style guard plus a unit test asserting `dispatch()` requires an explicit `armed=True` argument with no default |

## Sources

### Primary (HIGH confidence)
- `n8n/wf_contact_ingest_cloud.json` — read directly; webhook path, method, auth type, `Extract
  From File` operation and binary property name
- `scripts/deploy_n8n_workflows.py`, `scripts/provision_n8n_credentials.py` — read directly;
  confirmed the actual header name and shared-credential surprise
- `config/column_mapping.yaml`, `src/file_loader.py` — read directly; exact alias schema and
  existing (non-imported, but pattern-matched) file-reading approach
- `operator-claude-plugin/README.md`, `CHANGELOG.md`, `.planning/workstreams/plugin-entrypoint/
  {REQUIREMENTS,ROADMAP,STATE}.md`, phase `23-CONTEXT.md` — read directly
- `~/.claude/plugins/cache/knowledge-work-plugins/customer-support/1.2.0/`,
  `~/.claude/plugins/cache/ponytail/ponytail/4.8.4/`, `~/.agents/skills/xlsx/` — real installed
  plugin/skill directory structures inspected directly on disk

### Secondary (MEDIUM confidence)
- `code.claude.com/docs/en/desktop` (WebFetch) — three-tab model, plugin install via Desktop UI,
  file attachment feature comparison table
- `code.claude.com/docs/en/plugins` (WebFetch) — full manifest schema, `skills/` vs `commands/`
  guidance, `--plugin-dir` dev workflow
- WebSearch, "Claude Desktop app install Skills" — Chat-tab Skills ZIP-upload mechanism (confirms
  it's a distinct, simpler mechanism from Code-tab plugins)
- WebSearch, drag-and-drop file type support — CSV/XLSX confirmed acceptable as attachment types

### Tertiary (LOW confidence)
- `github.com/anthropics/claude-code#54062` (WebFetch) — describes the attachment-path gap for
  images specifically; extrapolated to non-image files for this research's risk assessment, not a
  direct confirmation
- n8n community forum posts on multipart/form-data webhook parsing (WebSearch) — general n8n
  behavior, not tested against this specific deployed workflow

## Metadata

**Confidence breakdown:**
- Backend contract (webhook, auth, body encoding): HIGH — read directly from the deployed workflow
  JSON and the deploy scripts that bind its credentials, not inferred
- Claude plugin packaging mechanics: HIGH — cross-checked against real installed plugins on disk
  plus current official docs
- File handoff (D-14): MEDIUM/LOW — the one item genuinely unresolved by documentation; mitigated
  with a concrete, cheap verification task rather than a guess baked into the design
- Standard stack / don't-hand-roll: HIGH — every recommended package is already running in this
  exact repo for the same job

**Research date:** 2026-07-30
**Valid until:** ~30 days for the backend contract (stable unless the n8n workflow is redeployed
with a changed credential map); ~14 days for the Claude Desktop/plugin packaging facts, since that
product surface is moving quickly enough that this research itself needed to override training
knowledge from external docs dated within the last few months.
