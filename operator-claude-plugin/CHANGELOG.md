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

## [0.33.0] - 2026-08-30

### Added

- **One grant across ingest, enrich, create and associate — including what the batch
  creates (Phase 61 Plan 06 Tasks 1-3, RUN-02, AFTER-02).** The 2026-08-25 association
  contract now holds unconditionally: `wf_enrichment_cloud`'s own contacts-create path,
  which had no company-resolution mechanism at all, downgrades any armed create to
  `review` rather than land an unassociated contact — one implementation of the rule
  (the contact-upload ingest lane), not two. `Adapt Company Create` (new node, companies
  branch) captures a company create's own returned id and joins it to its planned
  dependency by value; `preingest.py` gained the client-side coalescing
  (`assign_same_run_company_ids`), a bounded index-lag classifier
  (`classify_company_resolution_hold`, 3 attempts), and the REVIEW-10 consumer that
  writes an n8n-returned no-company hold into `held_queue.py` (n8n cannot write a local
  file). REVIEW-11's "one grant is prose-only" verified against the real `covers()`: a
  same-run create is already covered via the domain this skill's own step 2 confirms
  before the grant opens — no widening of `write_grant.py` was needed. A resumed run
  gets a fresh grant, always (GRANT-06 unchanged). The end-of-run account now reads
  `written_records.written_records_path(run_id)`, never the aggregating path-less
  `load()` (REVIEW-C16).

## [0.32.0] - 2026-08-30

### Added

- **Resume-or-fail-loudly, and a per-chunk manifest merge that cannot erase a prior
  chunk (Phase 61 Plan 05 Task 3, RUN-03, REVIEW-08/C13/C15).** `run_manifest.py`
  itself is unchanged — its `load()`/`save()`/`rows_to_resume` all keep their existing,
  correct degrade-whole behaviour. Two new caller-side pieces close the gap around it:
  `chunking.merge_chunk_verdicts` reads the accumulated manifest, folds one chunk's
  verdicts on top, and saves the whole document, so a per-chunk write (meant to bound a
  crash's replay window to one chunk) cannot instead erase every earlier chunk's
  verdicts the way a bare `run_manifest.save` would. `watch.classify_manifest_read` /
  `watch.resume_or_disclose` classify the manifest FILE ITSELF — absent, parseable,
  anomalous, or stamped with a different run's id — before trusting a resume, so a
  corrupted or foreign-run manifest reruns everything with a named, spoken disclosure
  sentence rather than presenting as a first run or a partial resume.
  `watch.build_resume_completion_report` distinguishes rows completed in this pass from
  rows already done when it started. `enrich-before-ingest/SKILL.md` step 8 now calls
  both instead of `run_manifest.save`/`load`/`rows_to_resume` directly. No poll loop was
  added anywhere; `_POLL_LOOP_ALLOWED` stays `{"watch.py"}` unchanged.

## [0.31.0] - 2026-08-30

### Added

- **A real confidence self-assessment, and hold-don't-block (Phase 61 Plan 04,
  D-61-07).** The absence of any confidence signal was Finding F — with none, every
  row became a per-row conversation. `preingest.parse_outcome` turns a response item
  into a typed outcome carrying five named signals the backend already computes (match
  tier, verified candidate count, provider agreement, material conflicts, judge
  adjudication), version-stamped by `Build Response` and pinned by a real flow test
  driving the committed lane — a missing signal or an unrecognised version parses as
  unparseable, never as a good value. `confidence.py`'s `assess()` is a total,
  deterministic decision table over those signals: only a strong-key auto-match with
  no unadjudicated conflict is confident; everything else is held, with a
  closed-vocabulary `hold_code` and a reason. `held_queue.py` is a fourth durable
  artifact collecting held rows for one end-of-run review, with a per-hold_code resume
  fingerprint (hashing only what a zero-credit free match pass can itself re-derive)
  so a resume never re-spends provider credit re-reaching an identical hold.
  `run_manifest.py` gained a sixth verdict word, `confidence_held`, distinct from the
  existing no-email `held` since a confidence-held row usually has an email and would
  otherwise be re-sent on every resume. `enrich-before-ingest/SKILL.md` documents the
  sequence and reuses step 3's own approve/deny/pick/email vocabulary for the
  end-of-run review — no second decision vocabulary.

## [0.30.0] - 2026-08-30

### Added

- **A LinkedIn-URL-only row is no longer refused by the front end (Phase 61 Plan 03,
  D-61-06/D-61-05 CORRECTED, second half).** `config/column_mapping.yaml`'s
  `required_identity.any_of` gained a third group, `[linkedin_url]`, mirrored in
  `n8n/code/columnMap.js`'s hand-written `requiredIdentity()` and pinned equal by a new
  parity test — the exact walk-failure row (`53-WALK-RECORD-3.md` FINDING D) now passes
  every gate that used to reject it. `extraction.py`'s rejection reason is now COMPOSED
  from the configured groups rather than a hard-coded sentence, so a future group can
  never again leave the message stale. `enrich-before-ingest/SKILL.md` documents that
  such a row proceeds without a company (D-61-01), and that a value the waterfall finds
  for it is proposed through the existing `resolutions`/`provider_result` loop
  (D-59-08) — never a second proposal surface. A new capability, not a patch — this
  ships as a minor version bump.

## [0.29.0] - 2026-08-30

### Added

- **`linkedin_url` widened into `MATCH_LOOKUP_KEYS` (Phase 61 Plan 02 Task 3, D-61-05
  CORRECTED).** A contact given only a LinkedIn URL — the exact row that failed walk run 4
  (`53-WALK-RECORD-3.md` FINDING D) — can now have that key sent to the backend's match
  search. It is a strong match key `Build Identity` reads into `identity_keys` and the
  backend's new "HubSpot Linkedin Search" node (61-02 Tasks 1-2) filters on; withholding it
  client-side meant the operator's own supplied key could never be used to find their own
  contact. `phone` and `jobtitle` still never cross this boundary. A new capability, not a
  patch — this ships as a minor version bump.

## [0.28.6] - 2026-08-29

### Added

- **P2 of the 2026-08-29 backlog handover, Task 3 of 3 (final): all 5
  `GRANDFATHERED_UNCOVERED` entries in `test_skill_sequence_coverage.py` are now
  closed.** The last entry — `chunking.chunk_ceiling(cfg,
  key='max_rows_per_match_request')`'s real return never flowed into `plan_chunks` in
  any test that also drove `preingest.match_batch -> preingest.classify_matches` — is
  now `COVERED`.
  - New `test_chunking.py::test_chunk_ceilings_real_match_key_return_flows_into_match_batch_and_classify_matches`,
    added immediately after the pre-existing isolated-ceiling unit test (left
    byte-identical), reads the ceiling from `config/operator.local.example.json` at
    runtime (never a hardcoded literal — confirmed by `grep -nE
    "plan_chunks\(row_spec, *[0-9]+\)"` matching nothing), plans a 3-row batch at that
    real ceiling, and asserts a three-way tier split (auto-matched / unmatched /
    proposed) that only holds if both `match_batch`'s real response and
    `plan_chunks`'s real ceiling-derived chunking reached `classify_matches` correctly.
  - `test_run_manifest.py` is untouched (`git diff` shows zero changes) — the near-miss
    test the registry named (`test_a_resume_re_requests_only_rows_that_still_needed_work`,
    which passes `plan_chunks` a literal ceiling) stays exactly as it was.
  - `GRANDFATHERED_UNCOVERED` is now the empty dict and `MAX_GRANDFATHERED` is `0` — the
    ratchet's own "shrinks by one each time" rule, taken to its correct end state
    rather than left at a headroom-preserving non-zero count.
  - Full plugin suite: 1725 passed / 5 skipped (baseline 1721 + 4 new tests across all
    three releases in this P2 series).
  - Zero production-code changes across all three releases (0.28.4-0.28.6) — every
    change was test-file additions plus this release metadata.

## [0.28.5] - 2026-08-29

### Added

- **P2 of the 2026-08-29 backlog handover, Task 2 of 3: closes 2 more of the 5
  `GRANDFATHERED_UNCOVERED` entries in `test_skill_sequence_coverage.py`.** The
  `enrich-before-ingest` (with `preingest.merge_enriched`) and `enrich-records` (no
  `merge_enriched`) entries for the documented enrichment waterfall — `resolve_providers
  -> plan_chunks/chunk_ceiling -> authorize_send|authorize_ungranted_send ->
  armed_window -> dispatch_plan[-> merge_enriched]` — are now `COVERED`. The nearest
  existing test drove `plan_chunks -> dispatch_plan` with a literal provider list and no
  authorization layer at all; no test chained the real `resolve_providers` return, or
  either authorize branch, into `dispatch_plan`.
  - New `test_chunking.py::test_the_enrich_before_ingest_waterfall_chains_resolve_providers_through_merge_enriched`
    (grant-present `authorize_send` branch) drives the real waterfall into a scripted
    `dispatch_plan` response and flows it through `merge_enriched` — confirmed to fail
    when the scripted response value is changed without updating the assertion.
  - New `test_chunking.py::test_the_enrich_records_waterfall_chains_resolve_providers_through_dispatch_plan`
    (`authorize_ungranted_send` branch, deliberate diversity) asserts the real chunked
    `record_ids` and the real `resolve_providers` return both reach the wire, checked
    against an independent expectation (`enrichment.FULL_WATERFALL`) rather than the
    test's own `providers` variable — confirmed to fail when `resolve_providers`'s call
    is replaced with a literal list.
  - Zero production-code changes. `MAX_GRANDFATHERED` decrements from 3 to 1.

## [0.28.4] - 2026-08-29

### Added

- **P2 of the 2026-08-29 backlog handover, Task 1 of 3: closes 2 of the 5
  `GRANDFATHERED_UNCOVERED` entries in `test_skill_sequence_coverage.py`.** The
  `contact-upload` and `enrich-before-ingest` entries sharing the identical call tuple
  `config_gate.load_config -> write_grant.authorize_send ->
  write_grant.authorize_ungranted_send -> n8n_arming.armed_window -> dispatch.dispatch`
  are now `COVERED`. Neither existing test drove `dispatch.dispatch` INSIDE an
  `armed_window` body: the grant-present `authorize_send` branch was never chained into
  `armed_window` at all, and the ungranted branch's `with armed_window(...): pass`
  stopped one call short of it.
  - New `test_write_grant.py::test_authorize_send_and_authorize_ungranted_send_each_drive_dispatch_inside_their_own_armed_window`
    drives BOTH branches to a real `dispatch.dispatch` call inside their own
    `armed_window`, asserting on the returned result — confirmed to fail (a `NameError`
    on the unset `result` reference) when one branch's body is reverted to `pass`.
  - Zero production-code changes. `MAX_GRANDFATHERED` decrements from 5 to 3.

## [0.28.3] - 2026-08-29

### Added

- **Sequence-inventory meta-test: the ratchet against the composition-boundary blind
  spot.** Five defects in one week (`.planning/debug/knowledge-base.md`,
  `composition-boundary-blind-spot`) all shipped past three fully green suites
  because every unit was correct and individually tested, while the documented
  `SKILL.md` call SEQUENCES joining those units were tested nowhere. New
  `tests/test_skill_sequence_coverage.py` extracts every `module.function(...)`
  sequence of two-or-more scripts-module calls from every `skills/*/SKILL.md` python
  block and fails when a sequence is neither claimed by a named composition test
  (`COVERED`) nor deliberately excluded with a reason (`NOT_A_PIPELINE` /
  `GRANDFATHERED_UNCOVERED`). A block that will not parse (even after prose-
  placeholder substitution) fails loudly, naming the skill and line, rather than
  being silently skipped.
  - Honest census on today's corpus: 8 documented sequences, 2 genuinely covered,
    1 not a pipeline (two independent read-only lookups), 5 grandfathered with a
    specific undriven join named for each -- writing those composition tests is
    follow-on work, tracked by `MAX_GRANDFATHERED` (shrink-only).
  - Zero production-code changes -- this test reads `SKILL.md` and test-file text
    only; it never imports, executes, or modifies anything under `scripts/`.

## [0.28.2] - 2026-08-29

### Fixed

- **bug_004 (normal): the `written_records-<run_id>.json` artifact silently omitted every
  contacts-lane write, and could report `not_written` for a run that had actually
  written.** `written_records.append_chunk`'s only call site was
  `chunking.dispatch_plan`'s per-chunk loop, so recording covered one TRANSPORT (the
  enrichment lane) rather than covering writes — `dispatch.dispatch`, the sole network
  call for `hubspot/contact-upload` and the write step of both `contact-upload` and
  `enrich-before-ingest`, never touched `written_records` at all. Live during the
  2026-08-29 operator walk (FINDING C, `53-WALK-RECORD-2.md`): HubSpot contact
  `348695309760` was created, and the run's own artifact reported the enrichment lane's
  `proposed`/`not_written` entry and said nothing about the write that actually landed —
  a false negative in exactly the direction D-59-07 exists to prevent.
  - `dispatch.dispatch` now flushes its own response into `written_records` at the write
    site, mirroring `chunking.dispatch_plan`'s D-59-07 inline-flush precedent and its
    D-59-10 catch/record/continue guard verbatim — a bookkeeping failure here never stops
    the dispatch and is never swallowed.
  - `dispatch.dispatch` gained a keyword-only `run_id=None` parameter (defaulting to a
    freshly generated one, mirroring `chunking.dispatch_plan`'s own default) and now
    returns `{"body": <the raw response>, "run_id": <str>, "written_records_failures":
    [...]}` instead of the bare body — there is nowhere to smuggle a bookkeeping-failure
    signal into a body that is sometimes a bare list of row items, and D-59-10 requires it
    be surfaced rather than swallowed. Every consumer now reads `result["body"]`.
  - This is a deliberate widening: `contact-upload` sends now also produce a
    `written_records-<run_id>.json` artifact, where before this fix they produced none.
    `write_grant.py`'s own consequence sentence already promises this artifact for every
    write grant regardless of lane count, so the promise was already false for a granted
    contact-upload-only send — this fix makes it true.
  - `enrich-before-ingest/SKILL.md` step 7 now threads `run_id=outcome.run_id` from its
    own earlier `chunking.dispatch_plan` call into `dispatch.dispatch`, so one run's
    enrichment-lane entries and its write entry land in the SAME file, per D-59-09.
  - New regression tests: `test_dispatch_multipart.py` drives `dispatch.dispatch` itself
    with a `Build Ingest Response`-shaped create and asserts the artifact names the
    written record (red before this fix, green after), plus D-59-10 guard-parity tests
    mirroring `test_chunking.py`'s own; `test_chunking.py` adds a cross-transport test
    proving `chunking.dispatch_plan` and `dispatch.dispatch` share one file when the same
    `run_id` is threaded through both.

## [0.28.1] - 2026-08-29

### Fixed

- **bug_002 (normal): the documented enrich-before-ingest step 7 sequence could not
  reach a HubSpot write.** `preingest.build_rows_spec` mints a `row_id` join key into
  every row; `merge_enriched` and `hold_emailless` both preserve it on purpose, since
  every stage upstream of dispatch still joins by it. `write_dispatch_csv`'s STRUCT-01
  guard correctly refuses any row carrying a key outside the canonical set — `row_id`
  is not a HubSpot property — so the documented sequence raised
  `Row 0 carries key(s) outside the canonical set: ['row_id']` before writing a byte,
  reproduced live during the 2026-08-29 operator walk. Each of the four functions was
  individually correct and individually tested; no test drove all four in sequence.
  **Exempting `row_id` from the canonical check was considered and rejected** — it
  blurs what STRUCT-01 means and every future internal key would inherit the
  exemption by precedent. **Carrying `row_id` beside rows rather than inside them is
  the better end state and is recorded as a follow-up**, but touches
  `build_rows_spec`, `merge_enriched`, `classify_matches`, `chunking`, and every
  row_id-joining lane — too wide a blast radius for this release.
  - `extraction.strip_row_id` — drops the `row_id` key from a list of rows,
    non-mutating. Called between `hold_emailless` and `write_dispatch_csv`, the only
    boundary where every upstream stage's need for the key and the dispatch CSV's need
    for its absence can both be honoured.
  - `enrich-before-ingest/SKILL.md` step 7 now calls it in that sequence.
  - New composition test (`test_preingest_merge.py`) drives
    `build_rows_spec` → `merge_enriched` → `hold_emailless` → `strip_row_id` →
    `write_dispatch_csv` end to end — the sequence-level gap no unit test covered.
- **bug_001 (nit): the plugin test suite wrote hundreds of files into the operator's
  real durable state directory.** `chunking.dispatch_plan`'s inline
  `written_records.append_chunk` flush resolves its path via
  `written_records_path(run_id)` when nothing overrides it — with `LV_OPERATOR_CONFIG`
  / `CLAUDE_PLUGIN_DATA` unset (the normal test environment), that lands in the
  operator's real
  `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`
  directory. Five tests added for D-59-08/59-09 monkeypatched this correctly for
  themselves; the ~25 pre-existing `dispatch_plan` callers never were — measured at
  413 stray `written_records-*.json` files from one session's test runs.
  `written_records.load()` has zero shipped callers, so this was latent pollution of
  the operator's directory, never an operator-visible data-quality failure.
  - New autouse `no_durable_writes` fixture (`tests/conftest.py`) redirects
    `written_records.written_records_path` to a per-test `tmp_path` by default,
    mirroring the existing `no_network` idiom — applies to every test by
    construction. Yields to a test's own more specific isolation
    (`durable_paths.resolve_state_path` patched directly, the pre-existing
    `_patch_durable_dir` idiom `test_written_records.py` uses to keep
    `append_chunk`'s write and `load()`'s glob pointed at the same directory) rather
    than overriding it.
  - Defense in depth: `written_records.append_chunk` now refuses (degrades, does not
    raise) a write that still resolves into the operator's real durable directory
    while `PYTEST_CURRENT_TEST` is set, independent of whether the fixture above took
    effect.
  - New regression test (`test_chunking.py`) exercises `dispatch_plan` with no
    written-records patching of its own and asserts the operator's real directory is
    unchanged.
  - The 413 pre-existing stray files are **not** deleted by this release — cleaning
    an operator's live state directory is proposed separately, not done silently.
- **bug_003 (nit): the two enrichment skills disagreed on whether a `resolvable`
  entry's `resolution_sources` is one value or several.** `RecordSpecError`'s
  `resolvable` payload types `sources` as a tuple, and GATE-03's `name` entry
  (`enrichment.py:427-436`) carries three of the four values at once — but
  `enrich-before-ingest/SKILL.md` instructed "naming **the** `resolution_sources`
  value the entry claims", unambiguously singular, disagreeing with
  `enrich-records/SKILL.md`'s own (ambiguous) phrasing. Both now instruct naming
  **every** value the entry's `sources` tuple carries. New parity test
  (`test_resolution_sources_relay_parity.py`) asserts both skills say the same thing
  and that neither implies a single value.

## [0.28.0] - 2026-08-29

### Fixed

- **D-59-10 gap closure: a written-records bookkeeping failure never stops a
  dispatch.** `written_records.WrittenRecordsError` was not one of the exception
  types `chunking.dispatch_plan`'s loop caught, so it could propagate and abort an
  armed, in-progress dispatch — and on the unattended path it crashed
  `scheduled_arm.py` with an unhandled traceback and no structured outcome, discarding
  whatever a cycle had already accumulated, while that module's own comment asserted
  this could not happen. Operator ruling: catch it in the loop the same way
  `DispatchError` already is, record the failure, and keep sending — this honours
  D-59-06's shipped, operator-facing promise that once enrichment and writing start,
  the run continues until done. **Aborting the dispatch on an unrecordable write was
  considered and rejected**: it is better for auditability in the abstract, but it
  contradicts D-59-06's promise and can strand a batch mid-run — trading a known,
  reportable gap in the record for an unknown, partial write state in HubSpot.
  - `chunking.DispatchOutcome` gains `written_records_failures` (empty-tuple default,
    never `None`) naming every chunk whose bookkeeping went short. One guard covers
    BOTH ways the list can go short: a raised `WrittenRecordsError`, and
    `append_chunk`'s pre-existing falsey return on an `OSError`, which the loop
    ignored before this release — a live silent-short-artifact path of exactly the
    class this ruling names. The chunk's own `ChunkResult` and `failed_batch`
    membership are untouched: a bookkeeping miss is not a dispatch failure, the
    HubSpot write for that chunk may already have landed.
  - **The trade-off, paid loudly rather than swallowed:** a run can now finish with an
    INCOMPLETE written-records list. It is surfaced on all four surfaces this closure
    requires — the new `DispatchOutcome` field; `scheduled_arm.py`'s returned outcome,
    which now also carries the dispatch's `run_id` so the artifact can be found; a
    non-zero process exit code even when the dispatch outcome itself reports
    `dispatched` (a genuine success — the outcome name is never renamed to hide it);
    and both `enrich-records`/`enrich-before-ingest` skills, which now lead with the
    incomplete condition in their reporting instructions before anything else.
  - `scheduled_arm.py`'s stale comment claiming `dispatch_plan` could only raise
    `NotArmedError` from inside the armed window is corrected in this same commit.
  - Lead test drives a multi-chunk `dispatch_plan` with a poisoned response body end
    to end; the unattended path gets a full `run_scheduled_arm_cycle` — unit-level
    coverage alone repeats the mistake that let all four gaps in this phase ship past
    three green suites.

## [0.27.0] - 2026-08-29

### Fixed

- **D-59-09 gap closure: `written_records.json` is now one artifact per `run_id`, not
  one file shared by every dispatch.** Code review and goal verification (gap 2 of
  `59-VERIFICATION.md`) found no protection against two real, concurrent writers — an
  operator's live session and `scheduled_arm.py`'s unattended cron poller — and
  `append_chunk`'s old replace-not-merge rule silently dropped the loser's already-
  flushed chunk history on a race between them. Operator ruling: each run writes its
  own artifact, keyed by `run_id`; a reader globs and unions them.
  - `written_records_path` now takes `run_id` and returns
    `written_records-<run_id>.json` in the plugin's durable state directory, resolved
    fresh on every call as before.
  - `append_chunk`'s run-id-mismatch replace branch is deleted — under per-run files a
    document already on disk at a given path is always this run's own earlier chunks,
    so it is appended to unconditionally. There is nothing foreign left to replace.
  - `load()` with no `path` now globs `written_records*.json` — deliberately NOT
    hyphen-anchored, so an artifact an operator already has under the pre-change shared
    filename is still found — reads every match in sorted order, unions their entries,
    and stamps each with its own document's `run_id`. One unreadable or malformed file
    among several does not suppress the readable ones. `load(path=...)` is unchanged.
  - **An OS-level advisory file lock was considered and rejected**, as was a merged
    index across every run's file: no contention and no stale-lock failure mode on a
    path that must never block a dispatch, and the index is a later addition only if
    operators ask for one combined view. Neither is in this release.
  - Lead test drives TWO interleaved runs through `chunking.dispatch_plan` against one
    shared durable directory — a unit test of `append_chunk` alone would have repeated
    the mistake that let this gap ship.
  - The cost, paid here: every reader of the artifact globs rather than opens one fixed
    path — `write_grant.py`'s grant-consequence text, `README.md`, and
    `enrich-before-ingest/SKILL.md` all reworded to name the per-run shape.

- **D-59-07 gap closure: a single-lane write grant now discloses the written-records
  artifact too, not only a grant spanning both lanes.** The disclosure sentence used to
  live only inside `write_grant._consequence`'s `len(lane_names) > 1` branch — scoped
  there in error, since the artifact is written after every dispatch regardless of lane
  count. It now fires for every grant. `plan_grant`'s authorization control — refusal
  ordering, the empty-record-set refusal, every authority check — is untouched; this is
  a text-only change, and the structural test asserting `write_grant.py` contains no
  HubSpot search call still passes unmodified.

## [0.26.0] - 2026-08-29

### Fixed

- **D-59-08 gap closure: GATE-02 through GATE-05's resolve-and-propose payload now
  actually reaches the operator.** 0.25.0's CHANGELOG entry above claimed these four
  gates were "CONVERTED" — that was true only at the level of
  `enrichment.RecordSpecError` construction. `chunking.dispatch_plan` is the ONE call
  site `enrichment.build_envelope` is invoked from in shipped code, and its
  `except enrichment.RecordSpecError:` clause had no `as e`, discarding both the
  gate's specific message and its `resolvable` tuple and substituting a generic
  placeholder ("this chunk could not be turned into a request") that neither shipped
  skill's dispatch instructions could turn into a proposal. An operator hitting
  exactly GATE-02's own example — a named person with no email, no LinkedIn URL, no
  surname+company — saw that placeholder and nothing to act on, the identical dead
  end D-59-08 was an operator ruling against.
  - `chunking.ChunkResult` gains a `resolvable` field, defaulting to an empty tuple
    never `None`, mirroring `enrichment.RecordSpecError.resolvable` exactly — a
    caller iterates it unconditionally on every result, including successes.
  - `dispatch_plan`'s `RecordSpecError` handler now binds the exception and carries
    `str(e)` and `getattr(e, "resolvable", ())` onto the `ChunkResult`, in place of
    the generic placeholder, which is deleted rather than kept as a fallback — a
    `RecordSpecError` always carries a message the gate wrote, which is strictly
    better than one this module would invent.
  - `ChunkResult`'s docstring is amended, not silently overridden: it still carries
    nothing transport-sourced (T-25-17's rule against echoing a request header
    through a relayed exception), but a `RecordSpecError` message is raised BEFORE
    any request is built and is composed entirely from the operator's own record
    spec — admitting it is not a widening of the original constraint.
  - Both `enrich-records/SKILL.md` (step 9) and `enrich-before-ingest/SKILL.md`
    (the dispatch section) now instruct relaying a non-empty `resolvable` entry as a
    proposal — naming its `detail` and which `resolution_sources` value it claims —
    rather than reporting the chunk as simply refused. Claude proposes, the
    operator confirms; nothing is silently acted on and no value is invented.
  - `59-GATE-INVENTORY.md`'s Owner cells for GATE-02 through GATE-05, and its
    closing paragraph, are corrected: a gate is CONVERTED only once its payload
    reaches the operator, and until this release it did not.
  - Lead test drives the real integration path — `chunking.plan_chunks` into
    `chunking.dispatch_plan` — rather than calling `enrichment.build_envelope`
    directly, which is the exact blind spot that let this ship past three green
    test suites in 0.24.0/0.25.0.
  - GATE-01 and GATE-06 are untouched — both already reached the operator on
    independent code paths unaffected by this defect.

## [0.25.0] - 2026-08-28

### Added

- **D-59-08, second half: the enrichment lane's identity refusals and the grant lane's
  empty-record-set dead end now resolve and propose instead of dead-ending.** Closes out
  `59-GATE-INVENTORY.md` — GATE-02 through GATE-06 are all now **CONVERTED**, alongside
  0.24.0's GATE-01. The inventory has zero `Unplanned items`, and no `CONVERT` row was
  ever reclassified to close the table — every `NOT-APPLICABLE` row was decided that way
  on "no legitimate resolution source", never on difficulty.
  - `enrichment.RecordSpecError` gains the same `resolvable` shape 0.24.0 gave
    `extraction.ExtractionResult`: a tuple of `{"field", "sources", "detail"}` entries,
    validated at construction against the closed resolution vocabulary. Populated at the
    people-branch identity gate and all three companies-branch no-name refusals. Every
    existing refusal MESSAGE is unchanged — including the verbatim-pinned profile-page
    sentence — the payload is additive.
  - **One shared vocabulary, not two.** `RESOLUTION_SOURCES` moved out of
    `extraction.py` into a new `resolution_sources.py` module that both `extraction.py`
    and `enrichment.py` import — `enrichment.py` importing it directly from
    `extraction.py` hits a real circular import
    (`enrichment -> extraction -> preview -> preview_enrichment -> chunking ->
    enrichment`), confirmed live before this release shipped. `extraction.RESOLUTION_SOURCES`
    is unchanged from every existing reader's perspective — it is the same frozenset
    object, re-exported.
  - **FINDING 1 of `53-WALK-RECORD.md` — a create with no HubSpot id and no domain
    could not be granted on any armed path — is now resolvable.** Stated plainly,
    because this is the sentence a security reviewer will look for: **`plan_grant`
    still hard-refuses an empty record set, `_writeSafetyAllows()` is untouched, and no
    resolution ever widens what a grant covers.** `write_grant.py` gained no lookup, no
    transport call and no resolution logic of any kind — pinned by a new structural
    test asserting the module's source carries no HubSpot search call. The refusal's
    detail now names what would resolve it: a read-only HubSpot lookup for the record's
    own id, or for its company's domain. `authorize_ungranted_send` relays the same
    refusal verbatim, so both grant paths agree.
  - `enrich-records/SKILL.md` gains a new step, placed before the grant is ever planned:
    attempt resolution from the closed source vocabulary only (a read-only HubSpot
    search, an earlier operator statement, a provider result already in hand, or a
    same-row derivation), PROPOSE the resolved handle naming its source, and require
    explicit operator confirmation before the confirmed handle reaches `plan_grant`. A
    declined proposal leaves the original refusal standing — nothing is armed. Reuses
    the confirm/correct/decline vocabulary the companies-domain table already
    established, rather than inventing a third.

## [0.24.0] - 2026-08-28

### Added

- **D-59-08: the identity gate resolves and proposes instead of dead-ending.**
  `59-GATE-INVENTORY.md` inventories every operator-facing refuse-and-stop gate
  across the ingest, enrichment, grant and preingest lanes — GATE-01
  (`extraction.py`'s identity gate) is converted by this release; GATE-02
  through GATE-06 (enrichment.py's identity gaps, `write_grant.py`'s
  FINDING-1 empty-record-set refusal) are named as candidates for **59-06**,
  which this release does NOT cover — see the inventory's `Unplanned items`
  note and the gate rows themselves.
  - `extraction.ExtractionResult` gains a `resolvable` group, ADDITIVE to
    `rejected` — every existing reader (`preview.py`, the CLI) sees exactly
    what it saw before. A record that fails the identity pre-flight is still
    rejected exactly as before, AND now also classified with the specific
    fields a legitimate source could supply.
  - A record may carry an optional `resolutions` key naming which fields were
    resolved and from where. `extraction.RESOLUTION_SOURCES` is a CLOSED
    vocabulary of exactly four identifiers (`hubspot_lookup`,
    `operator_statement`, `provider_result`, `same_row_derivation`) — a
    `resolutions` entry naming any other source, or a field the row does not
    actually carry, REJECTS the whole record rather than being accepted
    unlabelled. This is the anti-laundering control (T-59-20).
  - `preview.build_extracted_preview` returns the new `resolvable` key via
    `getattr` with a default, preserving the duck-typing contract for a shim
    caller.
  - **The no-invention rule was NOT relaxed.** *"Never fill a gap to make a
    row satisfy the identity rule"* survives verbatim in both passages of
    `contact-upload/extraction.md`. Only the clause asserting that a bare
    rejection is the correct outcome was rewritten, in both passages, with a
    dated `D-59-08` recorded-edit note stating what it used to say and why —
    nothing was silently deleted. `test_no_invention_structural.py`'s
    structural guarantee (no Python function anywhere in `extraction.py`
    resolves or fills a value into a row) is EXTENDED with four new
    forbidden substrings covering the resolution surface, never relaxed —
    the original four substrings are unchanged. A resolution still requires
    the operator's explicit confirmation before it becomes part of a row;
    the resolution loop is the same one ambiguities already use (Claude
    rewrites the artifact, `validate()` runs again) — no Python function
    ever writes a value in place.

## [0.23.0] - 2026-08-28

### Added

- **D-59-06: a `SessionStart` hook, the plugin's first `hooks/` directory.**
  `hooks/hooks.json` declares a `SessionStart` entry (matcher `startup|resume`)
  invoking `hooks/session-start.sh`, which prints a non-blocking note once per
  session, before any send: once enrichment and writing to HubSpot start for a
  batch, the run continues until it is done; revoking a write grant refuses the
  NEXT send; and a dispatch already running finishes its remaining chunks, so a
  revoke arriving mid-run does not stop it.
  - **This note ships INSTEAD OF making the dispatch loop grant-aware.**
    Revocation semantics are UNCHANGED by this release — a revoke still only
    refuses the next send and still does not stop a running dispatch;
    `dispatch_plan` remains grant-unaware and
    `test_a_revocation_midway_does_not_stop_a_running_dispatch` is byte-identical.
    This release makes that existing behaviour visible to the operator; it does
    not tighten it.
  - The hook script has zero dependencies (no config, no credential, no network,
    no filesystem write) and exits 0 unconditionally, so the note appears even on
    a fresh, unconfigured install.
  - Proven by `tests/test_session_start_hook.py`, which runs the script by
    subprocess and asserts on its stdout — this covers the note's CONTENT only.
    Its DELIVERY (whether the Claude Code host actually fires the hook and
    relays the note to the operator) requires a live session and is recorded as
    an unperformed manual check in `59-VALIDATION.md`.

## [0.22.0] - 2026-08-28

### Changed

- **D-59-07 half (a): the pre-emptive two-lane grant disclosure is retired as
  operator-facing text.** A grant covering both `enrich-before-ingest` lanes used to
  show the operator a long warning at the yes — that the HubSpot write is authorized
  before the enriched preview exists, so held rows and merge conflicts are authorized
  unseen. That warning is retired everywhere an operator reads it: `write_grant.py`'s
  `_consequence` (the one rendering the operator reads at the yes),
  `skills/enrich-before-ingest/SKILL.md` (both the step 1 preamble and the step 5
  disclosure paragraph), and `README.md`'s two-lane grant bullet.
  - **What replaced it:** a plain, non-blocking statement that the grant enables
    enrichment and writes to HubSpot, plus a pointer to the post-run
    `written_records.json` list (0.21.0) the operator can open in HubSpot and amend.
  - **The D-53-05 trade itself is UNCHANGED.** One grant still spans both lanes, the
    record-scoped allowlist is unchanged, and the write is still authorized before the
    enriched preview exists in mechanical terms — only what the operator is told about
    it, in exchange for that trade, moved from a prediction nobody could act on to
    something actionable.
  - Every rewritten passage carries a dated `D-59-07` / 2026-08-28 recorded-edit note.
    The historical `LANES` module comment in `write_grant.py` is left unedited, with a
    dated amendment appended rather than the paragraph being rewritten.
  - Every pinning test is RE-POINTED with a negative assertion (the retired sentence
    is asserted absent), never relaxed:
    `test_a_two_lane_grant_names_both_lanes_and_points_at_the_written_records_list`
    (renamed from `..._and_states_the_preview_trade`) and
    `test_the_ingest_arm_heading_is_strictly_after_the_enriched_preview_heading`. The
    single-lane test and the arm-dispatch-register test are byte-identical.

## [0.21.0] - 2026-08-28

### Added

- **D-59-07: a durable list of the HubSpot records a dispatch run actually wrote.** New
  `scripts/written_records.py` module, plus `chunking.dispatch_plan` now flushes each
  chunk's response into it INLINE, immediately after that chunk is sent — inside the
  same per-chunk loop, never assembled after it. The artifact lives at
  `written_records.written_records_path()` (the same durable home `run_manifest.json`
  and the dashboard-artifact pointer already resolve into), keyed by a `run_id`.
  - **Survives a partial run.** A batch that dies at chunk 7 of 20 still leaves chunks
    1-6 on disk — proven by a test that raises a bare exception out of
    `dispatch_plan`'s loop and asserts the file already holds the earlier chunks.
  - **Survives a revoked run.** Under D-59-06 a dispatch that is revoked mid-run keeps
    writing to HubSpot until its chunks are exhausted; the artifact reflects every
    chunk that run sent, including the ones sent after the revoke — it does not know or
    care about grant state at all.
  - **Never claims a write that did not happen.** A row the backend refused
    (`write_blocked` / `proposed` / `skip` / `needs_match_review` / `held`) is recorded
    as `not_written`, with the backend's own reason. A companies-lane create — whose
    response carries no `hs_object_id` by construction — is recorded as
    `created_id_unknown`, never a fabricated id. The companies-lane create-confirmation
    that WOULD resolve that unknown id is explicitly SCOPED OUT of this release: it
    would mean editing `scripts/build_cloud_workflows.py` and generated n8n workflow
    JSON, both deliberately untouched by this phase.
  - **`email` and every other contact PII field is deliberately excluded from an
    entry.** An operator opens the record by id; this artifact does not need to become
    a second place personal data accumulates.
  - **This release adds the LIST. It does not yet change the grant-time disclosure
    text** — the D-53-05 sentence a grant shows before the yes is untouched here; that
    replacement is a later plugin release (59-03).
  - An artifact write failure (`OSError`) never halts a live dispatch — `append_chunk`
    returns falsey instead of raising, so a bookkeeping miss can never become a mid-run
    stop.

## [0.20.0] - 2026-08-28

### Fixed

- **`enrich-before-ingest` silently discarded every provider answer it paid for.** Step 5
  documented `merge_enriched(unmatched_rows, outcome.responses)`, but
  `chunking.dispatch_plan(...).responses` is ONE RAW BODY PER CHUNK — each body itself
  array-wrapped by n8n's normal `firstIncomingItem` behaviour — never one item per row.
  `merge_enriched` indexes responses by `row_id` and skipped any item that was not a dict,
  so every chunk-list yielded `row_id = None`, the index came out empty, and **every row was
  filed as `unanswered` with no error, no warning and a zero exit.**

  Worse than a crash: `unanswered` is documented as *"a row nothing is known about at all"*
  and exists precisely to distinguish "we could not look" from "we found nothing" (T-38-01).
  A complete, correct, already-billed provider answer was filed under the label meaning its
  opposite, so the operator read "nothing known" and never learned an email had been returned.

  **This was present in every version ever shipped — 0.11.1 through 0.19.0 inclusive.** It
  went unnoticed because Phase 53's operator walk (2026-08-28) was the first end-to-end run of
  this flow anyone had performed; it was that walk's FINDING 2. Measured on one real record,
  same input both ways: as documented, `unanswered: 1` and no email; flattened,
  `unanswered: 0` and the email present.

  Fixed by flattening in step 5, using the idiom `preingest.rerequest_unanswered` already
  applies to this same endpoint. Every other caller of `dispatch_plan` was enumerated and was
  already correct — `rerequest_unanswered` and `fetch_matches`/`match_batch` both flatten, and
  `scheduled_arm` never indexes by `row_id`. This was one wrong call site, not a contract
  mismatch between the two functions.

- **`merge_enriched` now RAISES on a response shape it cannot index, instead of silently
  filing it as `unanswered`.** This is the separable second defect — the shape bug is what lost
  the data, but this silence is what made the loss invisible. A non-dict response item now
  raises `MergeError` naming both the cause and the fix. Precedent: it already raised
  `MergeError` for a duplicated `row_id`. Nothing is merged when it raises.

### Changed

- `chunking.DispatchOutcome.responses` now documents its per-chunk-raw-body contract in its own
  docstring. It was previously inferable only by reading three other modules.

## [0.19.0] - date unrecorded

> **This entry was written retroactively on 2026-08-28 and is INCOMPLETE.** `plugin.json` was
> bumped to `0.19.0` without a matching CHANGELOG entry, which is exactly what this file's own
> release rule forbids ("bumping `.claude-plugin/plugin.json`'s `version` in the SAME commit as
> the CHANGELOG entry"). The gap was found while releasing 0.20.0. The contents below are
> INFERRED from a diff of the installed 0.18.0 and 0.19.0 plugin-cache copies, not recovered
> from a release note — treat them as a pointer, not an authority, and consult the git history
> for what actually shipped.

### Added (inferred from the 0.18.0 → 0.19.0 cache diff)

- `scripts/company_domain.py` — new module, present in 0.19.0 and absent from 0.18.0.
- Changes to `scripts/enrichment.py` and `scripts/extraction.py`, and to the `contact-upload`,
  `enrich-before-ingest` and `enrich-records` skill files. Consistent with Phase 58 ("take what
  the operator actually has" — screenshot, paste, URL, bare name resolving to a company).

## [0.18.0] - 2026-08-25

### Added

- **F2 — a per-send "yes" with no standing grant open can now actually write.** Before
  this, an ungranted send's yes armed the client's own POST only; it never reached
  `n8n_arming`, so the deployed workflow's `ALLOW_HUBSPOT_RECORD_WRITES` stayed `false`
  and every ungranted write returned `write_blocked` regardless of consent (executions
  11934/11935/11937 — every write to date had to be landed by an admin from a terminal).
  The operator's decision (2026-08-25): the per-send yes now opens a per-send armed
  window scoped to that send's records, using the same machinery a standing write grant
  uses; a standing grant remains the wrap-around option that skips the per-send ask.
- Added `write_grant.authorize_ungranted_send()`: composes the existing
  `plan_grant()`/`open_grant()` into a single-lane, single-use grant scoped to exactly
  one send's records, gated on the SAME `allow_write_grants` admin setting a standing
  grant needs (no new key), and getting the SAME Guardrail A dirty-backend refusal for
  free. The grant it returns is used for exactly one `armed_window` call and discarded —
  never remembered, never written to disk. `n8n_arming.arm_for_dispatch`/`_arm_gate`/
  `authorize_send` are untouched; the headless `ALLOW_N8N_ARM` env-var gate
  (`scheduled_arm.py`) is unaffected.
- Updated the dispatch step of `enrich-records`, `contact-upload`, and both lanes of
  `enrich-before-ingest` to open a record-scoped armed window on every send, whichever
  consent authorized it — collapsing "grant open -> skip the ask" / "yes -> window for
  this send" into one shared dispatch pattern.

## [0.17.1] - 2026-08-25

### Fixed

- **F3 — a synchronous body carrying a real refusal was reported as a clean send.** The
  operator walk of 0.17.0 sent one record, the backend answered
  `action: "write_blocked"`, `match.reason: "searched, no hit"`, and the client said
  "Sent. Backend accepted 1 chunk, 1 row. No failures, nothing to re-send" anyway.
  `skills/enrich-records/SKILL.md` step 8 carried a blanket "do not claim per-record
  outcomes" rule, written to stop the client INVENTING an outcome the synchronous body
  never carried — read too broadly, it also suppressed one the body DID carry.
  `scripts/report_enrichment.py`'s `write_blocked` → "blocked" mapping already existed
  and was never reached on this path.
- Added `report_enrichment.build_sync_report(body)`: shapes a chunk's own synchronous
  response into the same created/enriched/blocked/skipped/unknown outcome, reason, and
  match-level/match-reason shape the executions-API report already computes — one
  mapping, not a second copy left to prose. Step 8 now calls it for every response and
  relays what it returns, never inventing beyond it.
- `contact-upload` and `enrich-before-ingest` were checked and do not carry the same
  defect — neither has an equivalent suppression clause.

## [0.17.0] - 2026-08-25

### Changed

- **The arming phrase is gone. The consent it carried is not (VOCAB-05).** Every send used to
  demand a literal string — "arm the enrichment", "arm the upload", "arm review writeback" —
  and the walk showed what that costs: the operator was handed a preview ending "Proceed?",
  answered **"yes"**, and was told a yes does not dispatch, say the exact phrase. A magic
  string demanded at the precise moment they were trying to consent.

  An operator now answers the question they were asked, in their own words. **An affirmative
  answering the send just described — "yes", "go ahead", "do it", "please" — arms that send
  and nothing else.**

  **What made the phrase safe was never its spelling: it was that a casual "ok" could not
  become a write.** That property is preserved by binding the affirmative to *this send's
  shown consequence, in the same turn*. An affirmative answering nothing, answering some
  other question, or arriving before the send has been described arms nothing — the skill
  asks once more, naming what will happen. Ambiguity resolves to not-armed, always. And
  `armed` still has no default in code (`dispatch()` and `dispatch_plan()` raise without it);
  that structural guarantee did not move, and its tests pass byte-identical.

  Scope: `enrich-records`, `contact-upload`, `enrich-before-ingest` (both of its asks) and
  `review-triage`, plus the operator-facing refusal text in `dispatch.py`, `enrichment.py`,
  `review_decision.py` and `preingest.py`, and README/USAGE.

- **`review-triage`'s session arm folded into the per-record confirmation.** That lane already
  read the exact write back and took an explicit yes for each record, never skipped. That yes
  *is* the arm now: it sets `review_armed=True` for that one submit and nothing else. One
  fewer thing to say, and consent moves from session-scoped to per-record — the scope the rest
  of the plugin already uses. A yes on either dispatch lane still authorizes no review write,
  and vice versa.

- **Consent scope narrowed from the conversation to the send.** The skills previously said an
  arm lasted "for this conversation only" while the code passed it per call; the prose now
  matches the code. Arming a send arms nothing else — not the next send on the same lane, not
  another lane.

### Note

- Every phrase pin in the test suite was **rewritten in place with its reason recorded, never
  deleted** — `test_enrich_skill_contract.py`, `test_enrich_before_ingest_skill_contract.py`,
  `test_config_gate.py`, `test_preview_empty_input.py`, `test_preingest_preview.py`. The dead
  spellings are kept as a negative pin so a later edit cannot quietly reintroduce them.

## [0.16.2] - 2026-08-25

### Fixed

- **The `people` form is now documented where the model actually reads it.** 0.16.0 shipped the
  form in `enrichment.py` with 20 passing tests, but the patch that was supposed to add it to
  `enrich-records/SKILL.md` raised partway through and aborted before writing the file. Only
  the second half landed. So the capability existed, every test passed, and an operator asking
  "update John Tsatsimas from Football NSW" was still told there is no search-a-contact-by-name
  path — correctly, because the skill is what the model reads and the skill did not know. A
  contract test now asserts the form, the three identities, and the held-match rule are present
  in the SKILL, because a module test proves the machinery and only this proves the operator
  can reach it.

## [0.16.1] - 2026-08-25

### Changed

- **A company can be named with no domain at all.** 0.16.0 refused a profile URL and asked the
  operator for the company's website — which hands the research back to someone who does not
  want to do it. The guard that survives is *never silently invent a domain* (a LinkedIn host
  is dropped, never passed through as one), not *go and find one yourself*: a company with a
  name is now accepted and looked up by the exact-name search the companies branch gained the
  same day. Creating a NEW company still requires a domain, because domain is the dedupe
  anchor. The superseded test records why it was superseded rather than being deleted.

## [0.16.0] - 2026-08-25

Both entries below came out of the Phase 53 operator walk, from a non-technical operator
saying ordinary sentences. Both are the same shape: the backend could already do the thing,
and the client stood in the way.

### Added

- **Name a person the way you would name them.** `{"people": [{"firstname", "lastname",
  "company"}]}` — or a name with an email or a LinkedIn URL. The backend has resolved
  contacts by name since Phase 36; no client form emitted it, so the skill asked for a
  HubSpot record id, which no operator carries in their head. Any ONE of email, LinkedIn URL,
  or surname + company is enough; less than that is refused by name, saying which of the three
  would fix it, rather than spending three provider calls on a row that can only return
  nothing. Match safety is inherited rather than reinvented: an exact identity enriches that
  record, while a same-surname, same-company match with no exact identity is **held for the
  operator to confirm** — a second John Tsatsimas is surfaced, never silently overwritten.
  This is NOT the `rows` form, which describes people who are not in HubSpot and stays pinned
  to `mode: propose`.

### Fixed

- **A LinkedIn URL is no longer mistaken for a company domain.** Naive host extraction turned
  `linkedin.com/company/futsal-australia` into the domain `linkedin.com`, which would search
  HubSpot for that host, find nothing, and create a company whose domain IS linkedin.com —
  after which every later LinkedIn-sourced company would MATCH that one poisoned record. One
  bad row swallowing every future company, with no error at any point. Profile hosts
  (LinkedIn, Facebook, X, Crunchbase and the rest) now normalise to no domain: the companies
  form refuses them by name and asks for the company's own website, and the ingest lane's
  resolver falls through to its exact-name match instead of associating a contact to whatever
  record happens to hold `linkedin.com`. The two engines' host tables are pinned equal by
  test, because a host one accepts and the other rejects is a silent divergence.

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
