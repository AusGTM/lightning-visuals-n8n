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

## [0.15.1] - 2026-08-25

### Fixed

- **A grant now removes BOTH asks, not one of them (D-53-06).** 0.15.0 made the arming phrase
  conditional on an open grant but left the older "Ask for approval" step unconditional, so the
  first grant ever opened was followed immediately by "want to run the send now?" — half the
  friction removed and none of the protection given back. Under an open grant covering the lane
  and the records, `enrich-records`, `contact-upload` and `enrich-before-ingest` now proceed
  straight to the send, naming the grant it runs under. With no grant open, every ask is
  unchanged. The approval a grant carries is the yes given to the envelope before the run; the
  preview is still rendered under a grant but informs rather than gates, because the gate moved
  earlier rather than disappearing. Pinned by contract assertions in both skill-contract tests
  so it cannot regress into a re-ask.

## [0.15.0] - 2026-08-25

### Added

- **An admin can enable write grants with one key, and an operator can then authorize
  HubSpot writes from inside Claude with no terminal.** Set `"allow_write_grants": true`
  (the JSON boolean, not the string) in `operator.local.json` and the interactive path no
  longer needs the `ALLOW_N8N_ARM` shell variable. This is what made the documented write
  path reachable at all: it required a variable set in the shell the session runs in, which
  an operator in Claude Desktop cannot set — so every documented operator path to a live
  write ended in a refusal only an admin with terminal access could clear.
- **The write grant itself.** You name a batch of records and the lanes it covers; the
  plugin shows the record count, worst-case provider credits per provider, worst-case
  Anthropic dollars, projected n8n executions and the configured monthly allowance; you
  say yes once. The grant is bounded to exactly those records on exactly those lanes, and
  it ends on completion, revocation, session end, an error, a ceiling breach, or two
  consecutive failures to turn writes back off. It is never written to disk.
- **Opening a grant first reads the live write-safety state and refuses to open if writes
  are already armed**, naming what it found and offering to turn them off.

### Changed

- **While a grant is open, the per-send arming phrase is not asked again.** `enrich-records`,
  `contact-upload` and `enrich-before-ingest` each say so in their own arming step, and each
  says what a grant does *not* remove: the preview still runs, the records are still named,
  every send still turns writes on and off around itself bounded to **that send's** records
  (never the grant's whole set), and a failed disarm is still reported as its own state.
- **With no grant open, nothing changes.** The phrases, the previews and the per-send gates
  are exactly what they were.
- **`backend-control` now lists opening, revoking and closing a grant** among the actions it
  can take, inside its existing one-action-one-confirmation shape.

### Honest limits

- **`ALLOW_N8N_ARM` is unchanged and remains the authority for the scheduled and cron
  paths.** It was not replaced — it was narrowed to where it belongs, the unattended paths
  that have no operator to confirm anything. Do not remove it.
- **The cost figure shown at grant open discloses what the batch can cost; it does not
  prevent it.** It is computed from the batch you named, so it cannot refuse anything that
  batch already implies, and the remaining monthly execution allowance is not checked before
  a run starts. Refusing on the allowance is a later phase. This is not a spend guard.
- **One grant may cover both lanes of `enrich-before-ingest`, which means the HubSpot write
  is authorized before the enriched preview exists** (D-53-05, the operator's decision,
  2026-08-25, taken deliberately for speed). Rows held for review, and merge conflicts where
  the source file's own value was kept over a differing provider value, are authorized before
  anyone has seen them. The enriched preview is still rendered and still worth reading; under
  a two-lane grant it is a report rather than a gate.
- **Revoking a grant refuses the next send. It does not stop a dispatch already running.**
  At the two-record chunk ceiling a forty-record send is twenty chunks, and all twenty go out
  after a revoke.

## [0.14.0] - 2026-08-25

### Added

- **A companies form for `enrich-records`.** The operator can now name companies that may
  not be in HubSpot yet — `{"companies": [{"name": "...", "domain": "..."}]}` — and the
  backend's existing company lane matches each on its domain, enriches an existing record
  in place, and creates one only where nothing matched and creation is armed. This is the
  first client path that can create a HubSpot record other than a contact, and the preview
  says so in those words before anything is armed. **Domain is mandatory** and a company
  given without one is refused by name: domain is the identity anchor the backend searches
  on, so a domainless company could only ever be created, never matched — the duplicate
  shape the form exists to avoid. The envelope carries no `mode`, deliberately: a
  `propose` mode would have the backend report success having written nothing.
  `chunking.plan_chunks` chunks the form and `preview_enrichment.records_block` prices it
  like any other batch.

### Changed

- **`contact-upload` and `enrich-before-ingest` now report the company association.** The
  backend stopped creating unassociated contacts on 2026-08-25: a new contact whose
  company cannot be resolved is held for review instead of landing orphaned. The preview
  step says what that means for the file in hand *before* arming (a company that is not in
  HubSpot yet will hold every one of its rows), and the outcome step reports each row's
  `association` — `associated`, `not_confirmed`, `not_attempted` or `none` — alongside the
  write, names held rows individually with their reason, and offers the one-line manual
  override (`<row>. company: <hubspot company id>`) that resolves them on a re-send.
- **`company_id` is a recognised column** (`company id`, `hubspot company id`,
  `associatedcompanyid`). It is not a HubSpot contact property and is never written as
  one: it carries the operator's manual contact -> company association for a held row.

## [0.13.0] - 2026-08-10

### Added

- **Burn-rate alarm.** The unattended sweep now samples the recent n8n execution rate and
  fires when it projects, over a 30-day month, to exhaust the plan's monthly allowance —
  the same failure mode the 2026-08-09 incident hit (a runaway lane spending 253
  executions/hour, ~182,000/month against a 2,500/month plan). When it has something to
  report, the condition names one of three outcomes: `burn_rate_alarm` (the sampled rate,
  the actually-observed span — naming the sweep's own read bound when that shortened it,
  since n8n's own pruning can't be told apart from a system with no older execution yet —
  the projection, and the allowance), `burn_rate_not_configured` (the allowance key is
  missing or unusable — names the key, never a value, and every other sweep condition
  keeps running), or `burn_rate_unreadable` (the execution history itself could not be
  read). A healthy rate — including a sample too short to project from yet, such as the
  first sweep after a deploy — stays silent, same as every other condition in this sweep.
  The alarm re-notifies on every sweep while a burn persists — the one condition where
  repetition is deliberate, because an active burn costs money hourly and a missed signal
  here has already cost 73x the plan once.

- **Time-windowed execution lookback**, replacing the sweep's fixed 100-row page for every
  condition that reads execution history. A terminal failure that ended outside the window
  now ages out of the notice stream instead of re-notifying for days after it was fixed; an
  in-flight run that started outside the window is still retained and still fires as stuck.
  Every notice that names a workflow now resolves its real name instead of falling back to
  "an unnamed workflow," wherever a name is resolvable.

- **Runtime cadence budget floor.** Re-timing any of the five schedule triggers through the
  plugin's cadence action now sums the WHOLE schedule's projected monthly cost — not just
  the one trigger being changed — against the configured budget ceiling, before any change
  reaches n8n. Five individually-affordable triggers that together bust the ceiling are
  refused, naming the requested job's own cost, the whole-schedule cost, the ceiling, and
  the allowance, in that order. A disabled trigger contributes zero; an unreadable workflow
  list or a hand-edited `cronExpression` node refuses as an unknown cost rather than being
  treated as free. A single-shot conversational override phrase, `"override the budget
  floor"`, lets exactly one over-budget change through — restating the arithmetic and the
  consequence at the moment it is taken — and never persists to a later change or a later
  session. This floor guards only the plugin's own cadence action; a trigger re-timed
  directly in the n8n editor is what the burn-rate alarm above backstops instead.

### Upgrade step required

An existing `operator.local.json` predates this release and therefore lacks its three new
keys. **The FIRST sweep after upgrading will fire `burn_rate_not_configured`, by design, not
as a bug**, until you add all three to your real config file (the shipped
`operator.local.example.json` documents each with its required value and provenance):

- `n8n_monthly_execution_allowance` — must currently be `2500`, and must match
  `config/execution_budget.yaml`'s `monthly_execution_allowance` in the backend repo.
- `n8n_schedule_floor_max_share` — must currently be `0.25`, and must match
  `config/execution_budget.yaml`'s `idle_floor_max_share` in the backend repo.
- `burn_rate_alarm_threshold` — must currently be `1.0`.

`tests/test_execution_budget_drift.py` in the backend repo now enforces that the first two
values agree with `config/execution_budget.yaml` mechanically — the two cannot silently
drift apart. Until all three keys are added, the cadence action will also refuse every
schedule change it is asked to make, for the same reason: it cannot judge a budget it
cannot read.

**This release ships the alarm INERT.** No cron or launchd schedule is installed by this
release — the sweep only fires when it is invoked. Scheduling it on a recurring cadence is
an admin action you take on your own machine; this plugin does not do it for you.

## [0.12.0] - 2026-08-07

### Added

- **New skill: `loss-reason-report`.** Builds a report of why closed-lost deals were
  lost, cross-tabulated against the lost company's ICP tier and score, so the operator
  can see patterns like "we lose Tier A deals on price" — the signal a future rubric
  revision needs. This is the first skill that reaches a backend-repo script rather than
  the n8n webhook surface: it shells out to `scripts/build_loss_reason_report.py` in the
  backend repo checkout as a subprocess and reads back the markdown file it wrote. It
  never imports backend code and this plugin gains no HubSpot credential from it — the
  aggregator reads `HUBSPOT_PRIVATE_APP_TOKEN` from the backend repo's own `.env`, sourced
  by the documented command, not from anything this plugin stores.

  An empty report (zero closed-lost deals with a loss reason filled yet) is reported as
  exactly that — a complete, successful answer, not a failure — and is kept distinct from
  a run that could not reach HubSpot at all, which this skill never presents as "zero
  found."

## [0.11.1] - 2026-08-05

### Fixed

- **A row the backend never answered is now reported as `unanswered`, never as held for
  "no usable email".** Observed live on the nine-directors walk: a two-row enrichment chunk
  came back with only one row's verdict (the backend's response fires on first arrival), and
  the silent row was mislabelled with a reason about its data when the truth was about the
  response. `unanswered` is its own group in the enriched preview (after held rows, never
  sampled away), the run manifest treats it as non-terminal so a resume re-requests it, and
  one automatic re-request pass runs at the end of the batch — exactly once, never a loop.
  An unanswered row with a source email stays unanswered rather than being promoted to SEND:
  sending it would write a partially-enriched contact, which the governing rule forbids.

## [0.11.0] - 2026-08-05

### Added

- **New skill: `enrich-before-ingest`.** This is now the default way to load a contact list
  that has no email column — the exact shape of the case that motivated it: nine directors of
  a club, extracted from a board page with names, roles and a company, and no email address
  anywhere. Previously every one of those nine rows evaporated silently on upload. Now the
  flow is: extract, match each row against HubSpot before spending anything, confirm what the
  match found, enrich only what is still unmatched, read an enriched preview, then upload —
  and a row still without an email at the end is held and named, never silently dropped.

  The flow asks you to arm it **twice, at two different moments** — once before the
  enrichment spend, once before the HubSpot write — because those are two different
  irreversible actions and the second arm is your response to the enriched preview sitting
  between them. A single combined phrase would grant the write before you had seen what you
  were approving, so the two cannot be said together, and saying both up front still gets you
  asked again for the second one when its moment arrives.

  Matching against HubSpot reports exactly four outcomes, by name: **auto-matched** (an exact
  email hit), **proposed** (a same-surname, same-company candidate you confirm one row at a
  time, never batched), **unmatched** (no candidate at all — this row goes to enrichment), and
  **unchecked** — a chunk the search itself could not complete. "We did not find one" and "we
  could not look" are different answers, and this flow never collapses the second into the
  first.

  A confirmed match with no email is not a dead end either: it now has a HubSpot object id,
  which is what the existing `enrich-records` skill needs, and the flow hands those ids to it
  directly.

- **Idempotent resume for a broken enrichment batch.** A run now persists a small manifest —
  which row reached which terminal outcome (matched, enriched, held, or a chunk that could not
  be checked) — beside the existing dashboard state, at the same restrictive file permission.
  If a batch is interrupted partway, resuming it re-requests only the rows that are still open;
  a row already matched or already enriched is skipped, so a broken run never re-spends
  provider credit re-enriching a row it already finished. The manifest never stores an arming
  grant — that still lives only in the conversation turn that grants it — and any entry shaped
  like one causes the whole manifest to be refused rather than partially trusted.

- **Records created by an upload now queue themselves for the backend's own enrichment
  sweep**, with no action from you and no third arming phrase. This closes the loop for any
  row this flow could not enrich before ingest (or that a resumed batch left held-then-filled) —
  the already-deployed 15-minute poller picks it up on its own schedule the same way it already
  does for everything else it queues.

### Changed

- **A contact row with no email address is no longer written to the outgoing HubSpot upload
  file. This is a breaking change**, not a bug fix, for anyone whose workflow depended on that
  row going out with a blank email cell: HubSpot's own identity resolution only recognises
  email, so a blank cell was never actually reaching a real record — it dead-ended into an
  unreachable `needs_review` state with no way back. The refusal now happens loudly, before the
  file is written at all, naming the row and explaining why: the only way to send a held row is
  to give it an email.

### Test coverage

- One existing extraction test changed its own assertion on purpose, to match the change above:
  it used to assert that a row with an empty email cell (the exact shape of the live bug) was
  written into the upload file, and now asserts that the write is refused instead. This is the
  intended behaviour change, recorded here rather than silently overwritten.

## [0.10.0] - 2026-08-05

### Added

- **A page whose content comes back empty is no longer a dead end.** Plenty of club and
  association sites are built so that their visible text doesn't survive being converted to
  plain text — you get the page title and nothing else. Previously that ended the attempt.

  Now the plugin offers to try the structured representation the site itself publishes of
  that same page. You see every candidate address **before** any of them is fetched, in
  order, with the limit named — at most 5 follow-up fetches across the whole attempt, never
  off the site you gave it. It stops at the first one that returns people.

  Measured on a real page during acceptance: the ordinary fetch returned **0 people**; the
  first candidate returned **all 9 directors**, and the attempt stopped there.

- **Where a row came from is now recorded exactly.** If a row was read from a page's
  structured representation rather than the address you pasted, the record names that
  address in full, plus where in the response it sat. An audit trail pointing at a page that
  visibly contains nothing would be wrong by omission — someone checking it would fetch the
  page, see nothing, and reasonably conclude the row was made up.

### Changed

- **The plugin no longer tells you why a page came back empty.** It used to say the page was
  "likely rendered with JavaScript". That explanation was built into its instructions, it was
  repeated to an operator during testing, and it was **wrong** — the content was available
  the whole time, just not in the form first requested. It now reports only what it actually
  observed: the fetch succeeded and the content carried nothing extractable.

- **It no longer retries the same address.** Fetches are cached for about 15 minutes, so a
  second attempt at the same address reads identical content — asking differently changes
  nothing. That retry has been removed in favour of the candidates above.

### Unchanged, deliberately

No scraping library, no browser automation, no user-agent or viewport control, no
authenticated or paywalled page. A structured address the site serves anonymously is none of
those things — it is the same anonymous fetch pointed at a different path the site publishes
itself. An address that fails outright still stops at the existing refusal; the fallback runs
only when a fetch **succeeded** and carried nothing, because escalating past a refusal would
turn a fence into a suggestion.

## [0.9.0] - 2026-08-05

### Added

- **A full-name column can now be split into first and last name — with you checking it,
  row by row.** `0.8.0` refused these outright. That was stricter than the behaviour
  sitting right next to it (an unrecognised header gets *proposed* and confirmed), and it
  left rows failing the identity rule for want of a split you could have made in one turn.

  You get a table: the original value, the proposed first and last name, and a confidence.
  The rows the tool cannot settle are listed **first**, each saying what is ambiguous about
  it — a single word that could be a given name or a surname, or three parts where a middle
  name and a two-word surname are indistinguishable. You correct anything you like, and
  only then is a file written.

  A surname carrying a particle stays whole: `Jan van der Berg` splits to `Jan` +
  `van der Berg`, not `Jan` + `van`. That mangling was the reason the old version refused,
  and it is now handled rather than avoided.

- **The splitter has no splitter of its own at write time.** `--apply` writes exactly the
  pairs you resolved and nothing else, so a split you never saw cannot reach a file. It
  refuses outright if the number of resolved names does not match the number of rows —
  a misaligned split attaches one person's surname to another person's row and is invisible
  in the output, so it is blocked rather than reported.

### Changed

- **This is a local, this-file-only transform.** It is never sent to the backend as a rule,
  never stored, and never indexed. `Map Columns` in n8n still has no name-splitter, and a
  name column still never becomes a one-header-to-one-property guess.

- **The UAT sample now carries all three name shapes** so a walkthrough demonstrates them:
  a particle surname that must stay whole, a three-part name that needs a person, and a
  single word that cannot be assigned to either field.

## [0.8.0] - 2026-08-05

### Added

- **A header the alias table does not recognise is now worked out with you, not guessed at
  and not dead-ended.** Before the preview, the plugin sorts every header into four
  outcomes: the ones that map, the ones it can propose a match for, the ones it refuses,
  and the ones it can only report as dropped.

  A proposal is shown with **that column's own values beside it**, and you confirm **one
  header at a time**. A single batched yes is not a confirmation and is not accepted as
  one. This is deliberate rather than fussy: `Ph.` scores as a near-match for `phone`, but
  `photo` scores *higher* against `phone` than `Ph.` does — so a confirmation made without
  seeing what is in the column would be a rubber stamp, and the one thing this feature must
  never do is put image URLs into a phone field.

  Declining costs nothing: the header stays as it is and the backend drops it, which is the
  honest outcome. Nothing is ever renamed silently.

- **A `Full Name` column is refused with its reason named, not split.** This system
  deliberately has no name-splitter. Splitting on whitespace would mangle a surname
  carrying a particle — "van der Berg" would become separate fragments instead of one
  field — so the plugin says so and offers you the two things that actually work: split the
  column yourself, or send the file without it. It does not offer a split it cannot do
  correctly.

  The refusal runs *before* the matcher is ever consulted. That ordering is the whole
  mechanism: "full name" scores higher against `fname` than "ph." does against `phone`, so
  no matching threshold could ever separate them.

### Changed

- **Three more headers now read with nothing typed:** `E-mail Address`, `Org.` and
  `LinkedIn Profile`. Against the spreadsheet that failed UAT 2.2, four of seven headers
  now map deterministically where two did before.

  This half is not client-only — the alias table lives in the backend too, and the widened
  prediction here is only true once the backend is redeployed and its running workflows
  bounced. The backend change is recorded in the repository-root `CHANGELOG.md`; a new test
  pins the client's copy of the table equal to the backend's so the preview can never
  confidently promise a mapping the backend will not perform.

- **The corrected file is the one file.** When you confirm a header, the plugin writes a
  corrected copy, previews *that*, and sends *that* — so what you approve is provably the
  bytes that go on the wire. Your original file is never modified, and the corrected copy is
  deleted with the rest of the scratch artifacts when the batch ends.

## [0.7.3] - 2026-08-04

### Fixed

- **Prose, JSON, URL and screenshot ingestion were dead on every installed copy.**
  `config/column_mapping.yaml` existed only at the repository root and was never packaged
  with the plugin, so an install with no repo beside it resolved to nothing. `preview.py`
  degraded quietly (column labels unavailable), but `extraction.py` **refused outright**
  with `mapping_unavailable` — the canonical-prop allowlist cannot be built without that
  file, and it correctly declines to run on an empty allowlist rather than validating
  against nothing.

  The file now ships inside the plugin and is preferred over the repo copy, which stays in
  the resolution order for dev checkouts and as the drift oracle. A new test pins the two
  **byte-identical**: the backend's `Map Columns` node reads the repo copy, so a drifted
  plugin copy would mean the preview labels and the extraction allowlist describe a
  contract the backend does not implement.

  **Found by an operator walking UAT session 2 against the 0.7.2 install.** It had been
  recorded days earlier as a *minor, display-only* packaging gap, on the strength of
  `preview.py`'s graceful degradation — the second consumer was never checked. Both
  conclusions came from reading one caller and generalising, which is the same mistake
  shape as the 0.6.1 and 0.7.2 defects: the behaviour was verified one layer away from
  where it mattered.

## [0.7.2] - 2026-08-04

### Fixed

- **A first-ever settings file or dashboard link is no longer created inside the install
  folder.** Found live by RB-10, the release gate for 0.7.0 — the migration itself worked
  perfectly (config moved up, `0600`, verified, source removed, no permission prompt), but
  creating a dashboard immediately afterwards wrote its pointer to
  `0.7.1/state/dashboard_artifact.json`: the exact location 0.7.0 exists to stop using.

  Both resolvers ended with "fall back to the install folder" when the file existed
  nowhere. An operator who already had settings was rescued by the migration step just
  before it; an operator creating something for the **first time** — every new operator,
  and anyone's first dashboard — got the old stranding behaviour back. They now resolve to
  the durable home as the write target, degrading to the install folder only when the
  durable home cannot be created, so the plugin still works on a read-only HOME rather than
  refusing.

  **Why the tests missed it, recorded because the pattern keeps recurring:** every existing
  test seeded the durable file before asserting, so "nothing anywhere yet" was never
  exercised. Two of those fixtures were changed *during* 0.7.0 to pre-create the file,
  because the bare call fell through in a dev checkout — that fallthrough was the defect,
  and adjusting the fixture to get past it hid it for one release. The new tests point
  `PLUGIN_ROOT` at an empty directory instead, so the premise is actually true, and were
  confirmed to fail against the reverted fix.

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
2. **Cut the CHANGELOG section**: the Unreleased heading stays on top and empty, the
   shipped work moves under `## [<version>] - <date>`.
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
