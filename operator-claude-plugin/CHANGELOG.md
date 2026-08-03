# Changelog — Operator Claude Plugin

Changes to **this client only**. Backend changes (n8n workflows, enrichment logic, HubSpot
schema, provider adapters) are recorded in the repository-root `CHANGELOG.md`.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
client is versioned independently of the backend — it is one of potentially several front ends
over the same n8n system, so its version says nothing about backend capability.

## [Unreleased]

### Changed

- The 23-06 armed create canary PASSED (2026-08-03): one plugin-driven dispatch created
  the canary contact inside a domain-bounded armed window, closed with a verified
  full-coverage disarm. On the way it surfaced the stored-vs-running reload gap (arm and
  disarm ceremonies now bounce workflows) and BUG 27 (the create gate read fields Decide
  Action never emits — fixed and pinned by two-sided flow tests).

- The enrichment preview's chunk-ceiling caption no longer reads PROVISIONAL: probe B4
  ran the full waterfall live (2026-08-03, 37.44 s/record) and confirmed the ceiling of
  2 as a measured bound.

### Added

- Directory established as the home for the operator-facing client, separate from the n8n
  backend. README states the position explicitly: this is a suggested default thin client, not
  the interface — the backend is reachable over plain HTTP and other front ends (Slack, web app,
  CLI, scheduled script) can be built against the same contract, concurrently.
- Documented client contract: the two ingestion webhooks, the new `hubspot/backend-status`
  health endpoint, and the n8n Public API surfaces for read, activate/deactivate, and
  allowlisted workflow mutation — plus a five-point checklist of what a replacement client must
  reimplement.
- Documented operator model (non-technical, Claude Desktop, no terminal, no secrets), safety
  posture (disarmed by default, conversation-scoped live-write permission, confirm-then-verify
  on every mutation, read-only unattended monitoring), and cost posture (previewed estimates
  from measured rates, warn against remaining credits, chunking plan before send).
- **Phase 23 — plugin shell and the contact-upload lane.** A loadable Claude Code plugin
  (`.claude-plugin/plugin.json` + `skills/contact-upload/SKILL.md`, auto-triggered and
  slash-invocable) driving four thin, independently-testable Python modules:
  `config_gate.py` (refuses before any network call on missing/invalid config),
  `tabular.py` (reads CSV/XLSX headers and rows verbatim, converts XLSX to CSV bytes for
  the wire), `preview.py` (adaptive, display-only preview — reads
  `config/column_mapping.yaml` only as a read-only lookup for labelling, never to
  transform a row; ≤20 rows renders every row, larger batches render first-10/last-3 plus
  per-column fill rates), and `dispatch.py` (the one POST to `hubspot/contact-upload`;
  `armed` has no default, so a forgotten argument is a `TypeError`, never a silent send).
  Config setup is a one-time operator step from a tracked example file
  (`config/operator.local.example.json`); see this file's README for the full setup,
  file-handoff, and preview walkthrough.
- **Phase 24 — non-tabular input adapters.** Four new ways to hand the skill contacts without a
  spreadsheet: pasted freeform text, a foreign-shaped JSON blob, a public URL (fetched with the
  native `web_fetch` tool only — no HTTP client, no user-agent choice, no viewport, no
  authenticated fetch), and operator-supplied screenshots (never captured by the plugin itself).
  Extraction is Claude reading the source in-session — no Anthropic API call, no API key anywhere
  in the plugin — governed by one no-invention rule stated once in the new
  `skills/contact-upload/extraction.md` bundled resource: absent data stays absent, an unclear
  value goes to a single per-batch ambiguity list instead of being guessed, and a row is never
  completed just to pass the identity check. `extraction.py` (the validator, not the extractor)
  enforces the checkable half: every accepted row carries provenance, a non-canonical key is
  stripped and reported rather than silently dropped, overlapping screenshot reads of the same
  person collapse on the same identity rule the backend uses, and a value an extraction itself
  flagged as ambiguous cannot also be asserted as a fact. `test_extraction_contract.py` pins
  `extraction.md`'s documented examples to the real validator so the two halves of the contract
  cannot silently drift apart. One preview, one dispatch path, unchanged — this phase adds
  producers in front of Phase 23's choke point, nothing behind it.
- **Phase 25 — the enrichment lane, and a cost guard over both lanes.** A
  `/operator-claude-plugin:enrich-records` skill for records that are already in HubSpot:
  paste record IDs or name a **HubSpot list**, and the client passes that identifier through
  verbatim for n8n to resolve with the one HubSpot credential that exists. A **saved view is
  refused** with a redirect to saving it as a list — HubSpot exposes no view API, and silently
  trying the list endpoint with a view's name would enrich the wrong records with no error.
  That is a recorded scope amendment to INGEST-04, not a silent omission.
  `scripts/enrichment.py` always sends an explicit provider selection (the backend enables
  nothing when a request names nothing), resolved from a per-batch override over an admin
  default that **ships as the full waterfall** — so the preview states the resolved selection
  every time, whatever it resolved to.
  Every preview on **both** lanes now carries a cost block, rendered through one shared helper
  so the two cannot drift: per-provider estimated credits against the credits actually
  remaining, the Anthropic dollar figure, and the date the rates were measured with their age,
  from a dated plugin-local `config/cost_rates.json` rather than a runtime read of any repo doc.
  The figures say *at most* — Lusha is priced at its first-time rate, never its cheaper
  re-enrich rate. **A balance that could not be read renders as `unknown`, never as zero and
  never as healthy**, and its warning says headroom could not be *confirmed*; a genuine zero
  renders as zero and warns like any other insufficiency. Apollo's `unknown` is the normal
  answer there — it exposes rate limits rather than a credit pool — and the copy says so
  instead of presenting it as a fault. Balances come only from the n8n-side
  `hubspot/backend-status` endpoint; the client holds no provider credential and never asks a
  provider directly, and the preview renders in full when that endpoint is unreachable.
  Oversized batches are split before approval — `scripts/chunking.py` shows the chunk count and
  the rows in each chunk, and dispatch iterates exactly that plan with no splitting path of its
  own. Chunks go sequentially, a failing chunk is skipped rather than aborting the run, and the
  failures come back as a **re-sendable batch** rather than a list of errors. The per-request
  ceiling is read from config with no fallback constant anywhere, and is labelled
  **PROVISIONAL**: it derives from single-record, company-lane timings against the backend's
  ~100 s response window, and the full-waterfall timing probe has not been run. The tabular
  lane's cost block is a stated **zero with its reason** rather than an omitted block — that
  lane calls no provider and makes no model call, so its zero is a fact rather than an unread
  balance.

- **Phase 26 — per-record outcome reporting and safe retry.** After a send, the operator sees
  what happened to each row — created, updated-matched, needs-review, rejected, or
  not-confirmed — read from the decision the backend actually made (`scripts/report.py`), not a
  bare HTTP status; falling back to one read of `scripts/executions_client.py`'s executions API
  when the synchronous response is thin or the Cloudflare ~100s webhook ceiling is hit, and
  saying plainly when a report came from that fallback and may still be progressing. Every
  failing row is now told apart by whether re-sending it can help: a row with no usable email
  and an ambiguous identity outcome is named permanently stuck — the deployed workflow resolves
  identity by email only, so it needs an email address or manual handling in HubSpot, never
  another attempt — while a genuine transport failure is offered back for retry. Retry reuses
  the one existing `scripts/dispatch.py` entry point verbatim, arming gate intact; duplicate
  safety on a re-send is the backend's own identity resolution, not a client-side ledger, and an
  AST-based guard now keeps it that way by construction. Re-checking a run by its printed handle
  happens only when the operator asks — no poll loop, here or anywhere else in this client.

- **Phase 27 — backend status surface.** A `/operator-claude-plugin:backend-status` skill that
  answers "what is the backend doing?" without the operator opening n8n and without this client
  holding a provider or HubSpot credential. The picture is split along that credential boundary:
  the client reads `/api/v1/workflows` and `/api/v1/executions` itself for on/off state, live-write
  arming, what is in flight and how the last run ended, while the n8n-side `hubspot/backend-status`
  endpoint supplies only what needs credentials the client does not have — provider balances,
  credential health, and HubSpot queue/review counts. Every workflow the API key can see is
  reported with no allowlist, so a newly deployed or renamed workflow appears without a config
  edit. "Stuck" is an execution-age verdict that always carries both the run's age and the
  threshold, because that threshold is a carried convention rather than a measured figure.
  Failures are read out of per-node output rather than run status — every provider-facing node is
  configured to carry on when it errors, so a rejected credential leaves the run reading `success`
  — and are translated to one plain sentence naming who can fix it, with an unrecognised signature
  labelled as an interpretation, shown beside its raw text, and attributed to an admin rather than
  to the operator. A datum the backend could not supply reads `unknown`, never zero and never
  healthy. **On request only**, the same reading publishes as a dashboard Artifact stamped with
  when the data was fetched (not when the page was drawn), republishing to the same link on
  refresh — including from a new conversation, backed by the client's first and only piece of
  persisted state: one artifact identifier and its timestamp, gitignored, expiring after
  `dashboard_artifact_ttl_days` (default 30) and collected on the next skill open. The whole
  surface reads: it turns nothing on or off, starts nothing, and writes to no record.

- **Phase 29 — notices: the in-session watch and the unattended sweep.** Two mechanisms
  so the operator learns something needs them without asking. After a dispatch, `watch.py`
  keeps polling until the run settles and reports back through Phase 26's own per-record
  renderer plus the credit actually spent, bounded by a measured `watch_bound_seconds`
  (600 s default) that never simply goes quiet — a run still in flight past the bound is
  reported as still running with how to re-check, never silence.

  With no session open, a new `backend-sweep` skill runs on a `cron`/`launchd`-triggered
  headless `claude -p` fire (`skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` — an explicit
  second admin step after installing the plugin, never an implicit side effect of it) and
  watches for exactly five conditions plus one backstop: a failed scheduled run including
  one that silently swallowed a read failure behind a reported `success`, a rejected
  credential, an exhausted provider quota, a stuck lock, a review backlog past its
  threshold, and a stuck-armed backend left over from a crash between arming and
  disarming. **A healthy fire produces nothing at all** — no heartbeat, no all-clear — and
  every notice it does send is read-only by construction: an AST guard asserts the
  sweep's entire import graph and the shipped skill body both name nothing beyond a
  single allowlisted bodyless status read, and fails the build the moment either one
  grows a path to a write, a dispatch, or an arm. A misconfigured sweep (missing any of
  the three keys it needs) produces its own admin-attributed notice rather than raising
  or going quiet, so an unconfigured sweep is never mistakable for a healthy backend.
  Fixed a long-standing bug on the way: the live `hubspot/backend-status` endpoint
  answers array-wrapped, and the client only accepted a bare object — every queue count
  and provider balance the sweep and the status check both depend on was reading
  `unknown` until this was unwrapped and pinned both ways with a regression test.

- **Phase 30 — review-queue triage.** A `/operator-claude-plugin:review-triage` skill that turns
  the records the pipeline flagged for a human into something a non-technical operator can
  actually adjudicate in conversation: per record, what HubSpot holds now, what the pipeline
  wants to set instead, which source proposed it and how sure it was, why it was held back, the
  evidence link, and a link to the record. `scripts/review_queue.py` reads the backlog through
  the new read-only `hubspot/review/queue` endpoint and `scripts/review_decision.py` adjudicates
  one record through `hubspot/review/decision` — the client holds no HubSpot credential in
  either direction. A failed search is reported as a failure and never rendered as an empty
  backlog. Fields the policy marks protected are **labelled** before the operator decides, read
  display-only from `config/field_policy.yaml`; the backend remains the single authority on what
  may be written, and the label is scoped to the endpoint this client submits to. **Rejecting
  records the operator's reason and leaves the record in the queue** — nothing is ever silently
  cleared. Every decision shows the exact property write first, and that write is the backend's
  own dry-run patch rather than a client-side reconstruction; after a write the record is
  independently re-read and the result reported verified or failed, so an accepted HTTP response
  is never reported as success on its own. Writing passes **three** independent gates, all of
  which must be open: the `ALLOW_REVIEW_SUBMIT` environment variable an admin sets (exact string
  `true`, checked before a request is even built, and gating *submitting* only — previewing and
  rejecting stay reachable without it), a session arm the operator gives in conversation which is
  never written to disk and is separate from the contact-upload arm in both directions, and the
  backend's own `ALLOW_HUBSPOT_REVIEW_WRITES` constant plus its record allowlist, which a deploy
  opens and this plugin cannot.

  **Known limitation, deferred rather than fixed:** the queue names the one source the pipeline
  resolved to, not the provider-by-provider disagreement behind it. That disagreement is computed
  during scoring and never persisted, so no client can show it today; persisting it is a cheap
  backend fast-follow and is recorded as deferred, not as a defect in this client.

### Planned

Milestone v0.6, phases 25–30 — see `.planning/workstreams/plugin-entrypoint/ROADMAP.md`:

- **25** Enrichment lane on existing records + cost guard (credit/token estimate, chunking)
- **26** Per-record outcome reporting and safe retry without duplicates
- **27** Backend status surface: n8n-side health endpoint, plain-language read, dashboard artifact
- **28** Control actions: run now, workflow on/off, schedule cadence, conversation-scoped arming
- **29** Notices: in-session run watch and unattended sweep that speaks up only when needed
- **30** Review-queue triage with gated writeback, stamped as a human decision

### Notes

- No implementation files yet; this directory is documentation-only until phase 23.
- Known constraint carried from planning: agent tooling in this repo is blocked from performing
  arming writes, so the armed path needs a human executing it even though the operator-facing
  design is a yes/no in chat.
- Known dependency: the credit figures the cost guard needs cannot be read by this client
  directly (it holds no provider credentials), so they arrive through the n8n-side status
  endpoint. Phase 25 builds the credit-only slice; phase 27 grows the same endpoint to full
  health.
