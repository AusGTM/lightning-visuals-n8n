---
phase: 59-frictionless-write-path
reviewed: 2026-08-28T14:15:47Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/extraction.py
  - operator-claude-plugin/scripts/resolution_sources.py
  - operator-claude-plugin/scripts/enrichment.py
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/scripts/preview.py
  - operator-claude-plugin/scripts/preview_enrichment.py
  - operator-claude-plugin/scripts/scheduled_arm.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/durable_paths.py
  - operator-claude-plugin/hooks/session-start.sh
  - operator-claude-plugin/hooks/hooks.json
  - tests/conftest.py
  - tests/_credential_guard_probe.py
  - operator-claude-plugin/tests/test_written_records.py
  - operator-claude-plugin/tests/test_write_grant.py
  - operator-claude-plugin/tests/test_extraction_resolvable.py
  - operator-claude-plugin/tests/test_no_invention_structural.py
  - operator-claude-plugin/tests/test_enrichment_envelope.py
  - operator-claude-plugin/skills/contact-upload/extraction.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
findings:
  critical: 3
  warning: 1
  info: 0
  total: 4
status: issues_found
---

# Phase 59: Code Review Report

**Reviewed:** 2026-08-28T14:15:47Z
**Depth:** standard
**Files Reviewed:** 21 (plus docs cross-referenced for contract consistency)
**Status:** issues_found

## Summary

Phase 59 shipped four things: (1) a durable `written_records.py` artifact flushed
per-chunk inside `chunking.dispatch_plan` (D-59-07), (2) a `SessionStart` hook
disclosing run-to-completion behaviour (D-59-06), (3) a closed `resolvable`
vocabulary that lets `extraction.py` and `enrichment.py` propose a resolution
instead of dead-ending a row (D-59-08, GATE-01 through GATE-06), and (4) a
root `tests/conftest.py` credential-stripping fixture (D-59-04).

Two of the four pieces have real, demonstrable defects. The `resolvable` payload
GATE-02 through GATE-05 were built to carry (`enrichment.RecordSpecError.resolvable`)
is discarded by the exact function (`chunking.dispatch_plan`) both shipped skills
(`enrich-records/SKILL.md`, `enrich-before-ingest/SKILL.md`) use to dispatch —
meaning the operator-facing improvement these four gates exist to deliver never
reaches the operator through the documented flow, and no test exercises that
integration path (every existing test drives `enrichment.build_envelope` directly).
Separately, `written_records.json` — the artifact `write_grant.py`'s own consequence
text promises the operator as "the records this run actually wrote" — has no lock
and a "different run_id replaces rather than merges" rule; two dispatches racing
against the single shared path (an operator's live session and `scheduled_arm.py`'s
unattended cron tick, which is exactly the concurrency this repo's own unattended
design invites) silently drop each other's already-recorded chunk history, which is
precisely the failure D-59-07 exists to prevent. A third defect sits at the boundary
between the two: `written_records.append_chunk`'s own content-shape refusal
(`WrittenRecordsError`, on a `reason` string matching a forbidden-name substring) is
not one of the three exception types `dispatch_plan`'s loop catches, so it propagates
uncaught and aborts every remaining chunk of an armed, in-progress dispatch — with
zero test coverage and a stale contradicting comment in `scheduled_arm.py`, the one
unattended caller this guarantee matters most for.

The credential-stripping fixture (D-59-04), the `write_grant.py` control itself
(D-59-08/GATE-06), the closed `RESOLUTION_SOURCES` vocabulary's construction-time
validation, and `session-start.sh` all held up under scrutiny — no issues found
there.

## Critical Issues

### CR-01: GATE-02 through GATE-05's `resolvable` payload is discarded by the only dispatch path the shipped skills use

**File:** `operator-claude-plugin/scripts/chunking.py:311-317` (the catch site);
`operator-claude-plugin/scripts/enrichment.py:344-478` (where GATE-02..05 raise
`RecordSpecError(msg, resolvable=(...))`)

**Issue:** `enrichment.build_envelope` is called from exactly one place in the
shipped code: inside `chunking.dispatch_plan`'s per-chunk loop
(`chunking.py:301`). When it raises `enrichment.RecordSpecError` — which is
precisely what GATE-02 (person with no email/linkedin_url/lastname+company),
GATE-03 (profile-page URL with no name), GATE-04 (blank name, no domain), and
GATE-05 (no `name` key, no domain) do, each carrying a `resolvable` tuple built
specifically so the operator can be offered a path forward instead of a dead
end — `dispatch_plan` catches it and replaces BOTH the specific message (e.g.
*"There is not enough to find John in HubSpot or at any provider. Add their
company, or an email address, or a LinkedIn profile URL — any one of the three
is enough."* plus its three-entry `resolvable` list) AND the `.resolvable`
attribute itself with a single generic, non-actionable string:

```python
except enrichment.RecordSpecError:
    results.append(ChunkResult(
        index=index, rows=rows, ok=False,
        reason="this chunk could not be turned into a request",
    ))
    failed_chunks.append(chunk)
    continue
```

Both `enrich-records/SKILL.md` (§8, the exact snippet at lines 281-305) and
`enrich-before-ingest/SKILL.md` (§ dispatch, lines ~302-315) document this
`plan_chunks` → `dispatch_plan` call as the ONE way a "people"/"companies" spec
is sent, and neither file mentions `resolvable`, `build_envelope`, or
`RecordSpecError` anywhere (`grep -rln resolvable operator-claude-plugin/skills/`
finds only `contact-upload/SKILL.md`, which covers GATE-01 — a different code
path, `extraction.py`, that is never routed through `dispatch_plan`). Step 9 of
`enrich-records/SKILL.md` even instructs Claude to relay the chunk's reason "as
recorded" — which, for these four gates, is the generic string above, not the
resolve-and-propose guidance 59-06 built.

Confirmed by the test suite's own shape: every test exercising `.resolvable`
(`test_enrichment_envelope.py:354-421`) calls `enrichment.build_envelope(...)`
directly and inspects the raised exception in isolation. `test_chunking.py` has
zero references to `RecordSpecError` or the generic fallback string, so nothing
in the suite ever drives a spec through `plan_chunks` → `dispatch_plan` far
enough to notice the payload is dropped at the one integration point that
matters.

**Failure scenario:** An operator runs `enrich-records` naming "John at Football
NSW" with no email — exactly GATE-02's example. `plan_chunks` builds a chunk;
`dispatch_plan` calls `build_envelope`, which raises `RecordSpecError` with a
three-option `resolvable` list. Claude, following the documented flow, sees only
`outcome.results[i].reason == "this chunk could not be turned into a request"`
and has nothing to offer the operator — the exact "immediate refusal" dead end
D-59-08 was a direct operator ruling against, on the exact gate the operator's
own ruling was made about (GATE-02 through GATE-05 share the ruling's origin
story, GATE-01). `59-GATE-INVENTORY.md`'s claim that these four gates are
"CONVERTED" is false for the flow an operator actually uses.

**Fix:** `dispatch_plan`'s `except enrichment.RecordSpecError as e:` should carry
`str(e)` and `getattr(e, "resolvable", ())` onto the `ChunkResult` (adding a
`resolvable` field to that dataclass, or embedding it in `reason`), so a caller —
and the skill instructions relaying `outcome.results` — can surface it. At
minimum, propagate the specific message instead of the generic placeholder;
better, thread the structured `resolvable` tuple through so the skill can render
the same "add X, Y, or Z" guidance `test_enrichment_envelope.py` already proves
`build_envelope` produces.

---

### CR-02: Concurrent dispatch runs silently clobber each other's `written_records.json` chunk history

**File:** `operator-claude-plugin/scripts/written_records.py:183-228` (`append_chunk`)

**Issue:** `written_records_path()` always resolves to one single shared path
(`durable_paths.resolve_state_path().parent / "written_records.json"`) — there
is no per-run file, no lock file, and no advisory locking anywhere in
`written_records.py`, `durable_paths.py`, or `chunking.py` (confirmed by
grepping for `lock`/`Lock`/`flock`/`filelock` across all three — zero hits
outside unrelated prose). `append_chunk`'s own merge rule is:

```python
existing = _load_document(target)
if (isinstance(existing, dict) and existing.get(RUN_ID_FIELD) == run_id
        and isinstance(existing.get(ENTRIES_FIELD), list)):
    entries = existing[ENTRIES_FIELD] + new_entries
else:
    entries = new_entries          # <-- discards everything already on disk
```

This is correct for the intended case — a brand-new run finding a *stale
previous* run's leftover file — but nothing distinguishes that from two runs
racing concurrently against the same path. `scheduled_arm.py` is an
unattended, cron-triggered caller of the identical `chunking.dispatch_plan`
(`scheduled_arm.py:226`), designed to run on its own schedule independent of
whether an operator has a live session open — i.e. the two processes this repo
ships (an operator's interactive dispatch and the unattended poller) are
exactly the pair capable of racing against one shared file with no
coordination between them.

**Failure scenario:** Operator run A (`run_id="A"`) is mid-dispatch, having
already flushed chunks 0-4 to `written_records.json`. `scheduled_arm.py`'s cron
tick fires concurrently as run B (`run_id="B"`, generated fresh via
`uuid.uuid4().hex` — collision-proof, so B is guaranteed a different id) and
calls `append_chunk("B", 0, ...)`. It reads the file, sees `run_id="A" != "B"`,
and — correctly, from B's own point of view — replaces the whole document with
just B's first chunk. Run A then flushes chunk 5: it reads the file, now sees
`run_id="B" != "A"`, and — by the SAME logic, now incorrectly from A's point of
view — replaces the document with only chunk 5's entries. Chunks 0-4, each of
which already carries real HubSpot writes made by run A, silently vanish from
the one artifact `write_grant.py`'s own consequence text (`write_grant.py:385-389`)
tells the operator to open in HubSpot and amend. The artifact ends up
*understating* what was actually written — the exact failure category D-59-07
exists to prevent ("a design that only emits on clean completion fails exactly
the cases the operator most needs it for" — 59-CONTEXT.md D-59-07 — a
concurrent-run clobber is the same shape of failure, just triggered by a second
writer instead of a crash).

Nothing in `59-01-PLAN.md`/`59-01-SUMMARY.md` or the module's own docstring
acknowledges this as an accepted limitation; the crash-survival tracer test
(`test_written_records.py`'s `test_a_dispatch_that_crashes_mid_loop_...`) proves
single-writer crash durability but there is no equivalent concurrent-writer
test anywhere in the suite.

**Fix:** Either (a) scope the artifact path per run-id (e.g.
`written_records-{run_id}.json`, with a separate "latest run" pointer or a
listing convention), or (b) take an OS-level advisory lock
(`fcntl.flock`/`msvcrt.locking`) around the read-modify-write in `append_chunk`
so a second writer blocks rather than clobbers. Given `scheduled_arm.py` and an
operator's live session are both real, independent processes already shipped in
this repo, this is not a hypothetical multi-process design — it needs one of
the two.

---

### CR-03: `WrittenRecordsError` propagates uncaught through `dispatch_plan`, and can abort an armed run mid-dispatch on ordinary backend content

**File:** `operator-claude-plugin/scripts/written_records.py:91-93,152-166`
(`_looks_forbidden`, the forbidden-marker check inside `classify_item`);
`operator-claude-plugin/scripts/chunking.py:297-334` (the loop that calls
`append_chunk` without catching it); `operator-claude-plugin/scripts/scheduled_arm.py:218-226`

**Issue:** `classify_item` checks every entry value (including the backend's
free-text `reason` field, sourced from live n8n response bodies —
`BUILD_INGEST_RESPONSE`'s `reason: row.reason || null` at
`scripts/build_cloud_workflows.py:516`, itself drawn from `id.reason`,
`row.reject_reason`, or `company_hold_reason`, all human-authored English
sentences) against `_FORBIDDEN_NAME_MARKERS = ("arm", "secret", "api_key",
"apikey", "token", "credential", "password", "grant", "permission", "webhook")`
via a bare substring test (`marker in lowered`). A match raises
`WrittenRecordsError`, and `written_records.py`'s own module docstring states
this is deliberate: *"A `WrittenRecordsError` ... DOES propagate — ... this
function does not decide whether the caller should continue."*

But `chunking.dispatch_plan`'s per-chunk loop (`chunking.py:297-334`) only
catches three exception types — `NotArmedError`, `DispatchError`,
`enrichment.RecordSpecError` — deliberately, per D-11b/D-12, so that "a failing
chunk is recorded and the run continues." `WrittenRecordsError` is none of
those three, so it propagates straight out of `dispatch_plan`, aborting the
loop before the remaining, not-yet-sent chunks are ever dispatched — even
though nothing about those chunks or the HubSpot writes already made is
actually broken. `test_written_records.py`'s own crash test
(`test_a_dispatch_that_crashes_mid_loop_...`) proves this propagation is
intentional for a genuine process kill (a bare `RuntimeError` injected at the
transport boundary) — but the SAME uncaught-propagation path also fires for a
content-shape refusal raised entirely inside this module's own bookkeeping
logic, on data the backend sent successfully. Nothing in the test suite
exercises that second case: `test_chunking.py` has zero references to
`WrittenRecordsError`, and there is no test asserting that `dispatch_plan`
either survives it or is expected not to.

The consequence is sharpest in `scheduled_arm.py`, the plugin's one genuinely
unattended caller. Its own comment (`scheduled_arm.py:222-224`) says: *"`dispatch_plan`
never raises for a single failed chunk (D-12: recorded, the run continues); it
only raises `NotArmedError`, which cannot fire here since `armed=True` is
passed literally."* That statement is no longer accurate after 59-01 —
`WrittenRecordsError` is a second, real way `dispatch_plan` can raise, and
`run_scheduled_arm_cycle`'s only exception handlers around the dispatch call
are `except n8n_arming.ArmingRefused` and `except n8n_arming.DisarmFailed`
(`scheduled_arm.py:218-230`); `_cli_main` catches only
`config_gate.ConfigError` (`scheduled_arm.py:265-277`). A `WrittenRecordsError`
here propagates all the way to `if __name__ == "__main__":`, crashing the cron
script with an unhandled Python traceback instead of the JSON `_outcome(...)`
dict the docstring promises ("Returns an outcome dict; never raises..."),
discarding the already-accumulated `results`/`responses`/`run_id` entirely
(they only get assembled into `DispatchOutcome` after the loop completes
normally), and leaving a cron log/monitor with nothing structured to page on
for a batch that may have already written several real HubSpot records.

The armed window is still guaranteed to disarm on this path (`armed_window.__exit__`),
so this is not a live-writes-left-open risk — it is a silent-abort-plus-crash
risk on the exact unattended path D-59-06/D-59-07 were built to make safe to
leave running.

**Failure scenario:** No current hardcoded `reason` string in the codebase
happens to contain one of the ten markers (checked directly against every
`reason`/`gate.reason`/`company_hold_reason` string this review could find in
`scripts/build_cloud_workflows.py` and `n8n/code/*.js`), so this is not
observed failing in the current test run. It is, however, a proven, reachable
code path with zero test coverage and a demonstrably stale contract comment in
its most safety-critical caller — a future addition of a `reason` string
containing any of "arm" (matches "alarm", "warm", "disarm", "pharma", …),
"grant" (matches "granted" — plausible verbatim in a passed-through HubSpot
403 scope error), "token", "credential", or "permission" (all plausible in
auth-error passthrough text) would silently truncate a live, armed,
multi-chunk HubSpot write run with no operator-visible explanation.

**Fix:** Catch `written_records.WrittenRecordsError` in `dispatch_plan`'s loop
alongside the other three types, log/record it as a bookkeeping failure on that
chunk's `ChunkResult` (distinct from a dispatch failure, since the HubSpot write
for that chunk may have already happened), and continue to the next chunk —
consistent with the OSError-degrades-gracefully guarantee this same module
already gives `append_chunk`. At minimum, update `scheduled_arm.py`'s
docstring/comment so it stops asserting a guarantee the code does not have, and
add the corresponding `except` there too.

## Warnings

### WR-01: A single-lane grant's consequence text never mentions `written_records.json`

**File:** `operator-claude-plugin/scripts/write_grant.py:347-390` (`_consequence`)

**Issue:** The sentence disclosing that a post-run list of actually-written
records exists (D-59-07's stated replacement for the retired pre-emptive
warning) is appended only inside `if len(lane_names) > 1:` (`write_grant.py:373-389`).
A grant spanning exactly one lane — plausible via `enrich-records` used on its
own, or `contact-upload` without `enrich-before-ingest` — never reaches that
branch, so its consequence text tells the operator live writes are enabled but
never that `written_records.json` exists to review afterward. `write_grant.py`
still flushes to that artifact regardless of how many lanes the grant covers
(`chunking.dispatch_plan` has no lane-count branch), so the artifact exists for
every grant; only the disclosure is scoped to multi-lane grants.
`test_write_grant.py`'s only test asserting the `written_records.json` mention
is named `test_a_two_lane_grant_names_both_lanes_and_points_at_the_written_records_list`
— there is no corresponding single-lane assertion, matching the code gap.

**Fix:** Move the `written_records.json` sentence out of the `len(lane_names) > 1`
branch so every grant's consequence text mentions it, regardless of lane count.

---

_Reviewed: 2026-08-28T14:15:47Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
