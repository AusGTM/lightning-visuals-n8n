# Changelog — Operator Claude Plugin

Changes to **this client only**. Backend changes (n8n workflows, enrichment logic, HubSpot
schema, provider adapters) are recorded in the repository-root `CHANGELOG.md`.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
client is versioned independently of the backend — it is one of potentially several front ends
over the same n8n system, so its version says nothing about backend capability.

> **Releasing this client means bumping `.claude-plugin/plugin.json`'s `version` in the SAME
> commit as the CHANGELOG entry.** Claude Desktop decides whether to offer an update purely by
> comparing that string against the installed copy's — an unbumped version means the Update
> button stays greyed out no matter what shipped, and a stale marketplace clone means even a
> bumped one is invisible until the clone is fetched. Both halves are required. See the
> release checklist at the bottom of this file.

## [Unreleased]

## [0.7.1] - 2026-08-04

### Fixed

- **A spreadsheet with no rows in it now says so, instead of previewing a healthy-looking
  zero.** Found by the autonomous UAT sweep of step 2.6. An unsupported file type already
  refused cleanly, but an empty `.csv` previewed as `0 rows` with no error and no
  explanation — and the cost block reported it as "a real, explainable zero", which reads
  as reassurance about a file that could not be read. The documented flow then carried on
  to ask for approval and offer the arming phrase for a batch containing nothing.

  The skill now stops at the preview when `row_count` is 0, names the causes an operator
  can actually act on (an empty file, a header row with no data under it, an export of the
  wrong sheet), distinguishes "headers present, no rows" from "nothing at all" by checking
  what parsed, and asks for a different file. It does not ask for approval and does not
  offer the arming phrase — the same rule 0.6.2 applied to a config that cannot send:
  never invite a decision that cannot be honoured.

  Nothing could ever have been damaged by this — sending zero rows writes nothing. The
  defect was that "your file could not be read" and "everything is fine, nothing to send"
  were presented identically, which is the same silence-means-healthy shape NOTICE-04 and
  the sweep's own design exist to prevent.

## [0.7.0] - 2026-08-04

### Changed

- **Your settings and your dashboard link now survive a plugin update.** Both used to
  resolve to a path inside this plugin's own versioned install folder, so a version bump
  moved the folder and stranded whatever was in it — an operator's first action after
  updating was an unconfigured refusal, and a bookmarked dashboard link stopped
  resolving. Both now resolve to one durable home outside any install folder:
  `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`. The first
  time you use the plugin after an update, it finds your newest previous install's copy,
  moves it into that durable home at file permission `0600`, verifies it byte-for-byte,
  and only then removes the copy it moved from — automatically, with nothing for you to
  do. `/operator-claude-plugin:initialize` now names the real, resolved path instead of
  a location inside the install folder.
- **The unattended sweep never performs this migration.** It always resolves your
  settings read-only, so a scheduled sweep firing against a freshly updated install
  before you have opened the plugin yourself reports the existing `sweep_not_configured`
  notice — loud, by design — rather than moving your credentials on your behalf with
  nobody watching.

### Fixed

- **The dashboard's same-link guarantee (STATUS-05) is true again.** It had been
  silently false since this plugin's very first update: the dashboard pointer lived
  inside the versioned install folder, so every update landed in a folder with no
  pointer in it, and asking for the dashboard again minted a new link instead of
  returning the one you'd bookmarked. Fixed by the same durable-home change above — the
  pointer resolves through the identical mechanism your settings file now does.

## [0.6.2] - 2026-08-04

### Fixed

- **An operator who cannot send is told so before they read a preview, not after.** Loose end of
  0.6.1, found by re-walking the same UAT step that produced it. Loosening `load_config()` also
  opened the upload lane's step-1 preflight (`config_gate.py`'s `__main__`), which had been
  refusing a secret-less config purely as a side effect of the shared gate. With that gone, asking
  to upload rendered a full preview and closed with *"say **arm the upload**"* — an invitation to
  arm a send `dispatch()` would then refuse. Nothing could be sent at any point (that guard landed
  in 0.6.1 and was verified), so this was a misleading flow rather than a safety hole.

  The preflight now reports **send-readiness instead of refusing**: `can_send` plus a
  `send_blocked_reason` naming the missing key, the file, and who has the value. Previewing still
  works without a webhook secret — showing an operator their own file parsed costs nothing and is
  useful even when sending is unavailable, the same reasoning the review lane already applies to
  its dry run. But when `can_send` is false the skill states it in its first message and **never
  offers the arming phrase**, because inviting a decision that cannot be honoured wastes it.

  Pinned by tests that drive the **CLI entrypoint as a subprocess against an isolated plugin
  root** — the layer the operator actually reaches. Asserting on `load_config()` alone is what let
  both this and the 0.6.1 defect ship: in one direction the CLI refused where the function
  degraded, in the other it stopped refusing where the skill still needed a verdict. The new tests
  were confirmed to fail against a mutated verdict before being kept.

## [0.6.1] - 2026-08-04

### Fixed

- **A blank `webhook_secret` no longer takes down the whole backend-status answer.** Found by
  operator UAT (step 1.2) on the installed 0.6.0 build: `config_gate.load_config()` enforced the
  union of every capability's keys, and every status entrypoint opens with it, so the capability
  matrix the module is built around — where `status` needs only `n8n_url` + `n8n_api_key` — was
  never consulted. Asking what the backend was doing returned a blanket "`webhook_secret` is not
  configured" refusal instead of the workflow and execution half it could read perfectly well.
  That is the over-refusal PLUGIN-03 forbids ("a dead provider credential does not present as
  total failure").

  `load_config()` now enforces only `n8n_url`, the one key every capability needs. Capability-
  specific keys are gated by `require_capability()` at the layer that actually needs them:
  `dispatch.dispatch()` and `dispatch_enrichment()` gained their own guards, mirroring the ones
  `review_queue.fetch_queue()`, `review_decision`, `control_actions` and `run_sweep` already had —
  so loosening the shared gate removed no protection from any transmit path. Verified by reverting
  only the source files and reconfirming the failures, and by exercising each entrypoint against a
  config with the secret blanked.

  **Side effect worth knowing:** `require_capability()`'s "Everything else still works: …" line is
  now reachable. It never was — `load_config()` raised before any caller got there — so every
  refusal an operator has ever seen omitted the one sentence that says what they can still do.

  **Why the test suite missed it:** the degradation was pinned by calling `status.full_report(cfg)`
  with a hand-built dict, which never crosses `load_config()`. The function layer degraded
  correctly; the CLI layer an operator reaches refused first. Tests now drive the entrypoint.

### Added

- `enrichment` capability row (`n8n_url`, `webhook_secret`). The enrichment lane previously had no
  row of its own and would have borrowed `contact-upload`'s, refusing an enrich request with
  "uploading contacts" wording. Its own row follows the same principle as `control` and `review`
  (D-29): same keys as another capability is not the same capability. Visible in
  `/operator-claude-plugin:initialize`, which now lists "enriching records" alongside the rest.

## [0.6.0] - 2026-08-04

First released version of this client. Everything below shipped across milestone v0.6
(phases 23–32, sealed 2026-08-04, 49/49 requirements). The `0.1.0` it replaces was a
hand-written placeholder that never moved during development, so no operator was ever
offered an update; this is the first version string that means anything.

### Changed

- The unattended sweep's trigger no longer runs through an LLM (2026-08-03, Phase 32).
  RB-8 proved the previous `claude -p`-based cron/launchd trigger fails **silently**
  under real cron (an expired credential with no refresh, `node` absent from cron's
  PATH) — measured fact: `scripts/sweep_entry.py` run under `env -i` with zero
  credentials produces the byte-identical notice JSON, exit 0, so the LLM was never
  load-bearing. The trigger is now `skills/backend-sweep/lv-sweep-run.sh`, a
  deterministic `sh` wrapper that runs `sweep_entry.py` directly: no LLM, no Anthropic
  credential, nothing in the path that can expire. Every failure path (bad arguments,
  the python failing to run, output it cannot parse) now exits non-zero **and** posts a
  banner naming the sweep itself as broken — the old trigger's only failure mode was a
  silent one. Install cost: the schedule needs a python with this plugin's own
  `requirements.txt` installed, documented as part of the sweep's two-part admin install
  in `SWEEP-CRON-TEMPLATE.md`.
- The live RB-8 gate re-ran against that trigger the same day and **PASSED**: unattended cron fires with no session open (23:36:10 healthy — exactly one stamped line, no banner; 23:38:00 broken-interpreter — non-zero exit and the could-not-run banner branch, where the old design printed nothing), full silence check observed for the first time, zero provider-credit movement. NOTICE-03 is sealed on that evidence.

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
  fire (originally a headless `claude -p` invocation — **superseded by the deterministic
  LLM-free wrapper in the Phase 32 entry above**; `skills/backend-sweep/SWEEP-CRON-TEMPLATE.md`
  is an explicit second admin step after installing the plugin, never an implicit side
  effect of it) and
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

### Verified

- **Milestone v0.6 sealed 2026-08-04 — 49/49 requirements complete** (`.planning/MILESTONES.md`).
  The RB-9 close proved the last two live: an armed one-record review window (allowlist
  `9604614548` only) landed a valid-enum **approve** — the record's provenance now carries a
  `source: human` / `human_approved` entry with timestamp, the operator's reason verbatim, and
  `superseded_source` preserving the machine attribution it replaced (REVIEW-04); the same
  decision's `manual_protected` candidate field was **withheld by the decision endpoint on both
  preview and real submit** and left unchanged on independent re-read (REVIEW-02 / D-31 —
  endpoint path only; the 15-minute backstop allowlists by key and was not probed). Window
  closed disarmed with read-back PASS, `neighbors_changed: 0`. No client code changed — this
  entry records verification, not behaviour.

### Notes

- Arming is **operator-directed only** (amended 2026-08-03): a second explicit instruction after
  the invariant is named, bounded by a single-record `TEST_RECORD_*` allowlist, verified by a
  symmetric `--expect-armed` read-back. Unattended, scheduled, inferred, or unbounded arming
  stays absolutely blocked. Disarm paths are never gated.
- Known dependency (by design): the credit figures the cost guard needs cannot be read by this
  client directly (it holds no provider credentials); they arrive through the n8n-side
  `hubspot/backend-status` endpoint.

---

## Release checklist — how a change reaches an installed operator

Four steps. Skipping any one leaves the operator running old code while every doc says
otherwise; this is written down because it has already caught us once (the Update button sat
greyed out through ten phases of shipped work).

1. **Bump `.claude-plugin/plugin.json`'s `version`** in the same commit as the CHANGELOG
   entry, following semver against *this client's* surface — not the backend's milestone
   number, which is a different thing that happens to match at 0.6.0. Claude Desktop compares
   only this string; equal strings mean no update is offered, whatever the content says.
2. **Cut the CHANGELOG section**: `## [Unreleased]` stays on top and empty, the shipped work
   moves under `## [<version>] - <date>`.
3. **Push to the branch the marketplace clone tracks** (`master`).
4. **Refresh the marketplace clone** — it never fetches on its own, and a reinstall re-copies
   from whatever it already holds:
   ```
   git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator fetch --depth=1 origin master
   git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator reset --hard FETCH_HEAD
   ```

**Both traps described in earlier versions of this file are gone as of `0.7.0`.** A
same-version reinstall no longer destroys the operator's settings — they live outside the
versioned install directory entirely, at
`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`, so a reinstall
has nothing of the operator's to overwrite there. And updating to a new version no longer
strands them either: the first resolution after an update finds the newest previous
install's copy, moves it into that same durable home at file permission `0600`, and removes
the copy it moved from — automatically, with no operator action. An operator updating from
a version before `0.7.0` gets this migration for free on their first use of the plugin after
updating.
