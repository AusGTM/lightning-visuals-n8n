---
name: enrich-before-ingest
description: Load a contact spreadsheet, match it against HubSpot, enrich anything HubSpot does not already have, and only then create it — so no new contact lands in HubSpot incomplete. Use when the operator asks to enrich contacts before uploading them, wants new contacts as complete as possible before they hit HubSpot, or says something like "load these and enrich them first" — or invoke it directly as /operator-claude-plugin:enrich-before-ingest.
---

# Enrich Before Ingest

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.

This skill turns a spreadsheet of contacts into HubSpot records that are as complete as
possible before they exist. A row that already matches something in HubSpot is left
alone — this flow never writes the spreadsheet's own columns onto a record HubSpot
already has, because the only property-write path this plugin has is the email-keyed
`contact-upload` lane, and that lane's mechanics are reused here unmodified, not
duplicated. A row that matches nothing goes through the enrichment waterfall first, so
what gets created is the fullest version of that contact this plugin can build, not
whatever seven columns happened to be in the source file.

## Steps

1. **State the target, and how many times this flow will ask.** One write grant covers
   this whole batch and this flow asks once; with no grant open it asks twice. Say which
   of the two applies before any other work. Run:

   ```
   python3 scripts/config_gate.py
   ```

   If the JSON reports `"ok": false`, relay its `"error"` message to the operator
   exactly as given, then STOP. Never show, echo, or ask for a secret, and never
   surface a raw socket or parser error — the script has already translated it.

   If it reports `"ok": true`, tell the operator this flow touches the n8n instance
   named in `"target"` three ways: an unarmed search that just looks up whether a row
   already exists in HubSpot, a provider waterfall call that spends money once armed,
   and the ingest write itself — the same endpoint `"target"` names — once armed too
   (under a batch grant that is the same authorization; with no grant open it is a
   second, separate ask). Then read `"can_send"` exactly as `contact-upload/SKILL.md` step 1
   does: when it is `false`, say so with the relayed `"send_blocked_reason"`, and carry
   on building previews (they cost nothing), but do not ask for either send for the
   rest of this conversation.

   **With no write grant open**, say up front, before any other work, that this flow
   will ask for permission **twice, at two different moments** — once before any
   provider credit is spent, and again before anything is written to HubSpot — with a
   full preview of the enriched
   result landing in between. The second ask is not a formality and it is not a repeat
   of the first: it is the operator's answer to that preview, which does not exist yet
   when the first grant is given. Say this plainly here so it is not a surprise five
   turns later — an operator surprised by the second ask learns to pre-grant both,
   which is exactly the shortcut this design exists to prevent.

   **The batch path, and say it here rather than at step 5:** if a write grant covering
   both of this flow's lanes is open, the operator is asked once instead of twice — that is
   D-53-05, their own decision of 2026-08-25. Name which lanes the open grant covers and say
   what the single ask covers: the grant enables enrichment and writes to HubSpot; after the
   run, the records it actually wrote are listed in a `written_records-<run_id>.json` file
   (one per run, matching `written_records*.json`) — see step 5's recorded edits, D-59-07
   (2026-08-28) and D-59-09 (2026-08-29), for what this line used to say and why it changed
   twice. With no grant open, this flow asks twice, exactly as described above.

   **One grant, the whole batch — including what it creates (Phase 61 Plan 06 Task 3,
   REVIEW-11).** The machinery is real code, not prose: `write_grant.plan_grant(config,
   lanes=[...], ...)` opens a grant spanning both of this flow's lanes in one call,
   `open_grant`'s `_consequence()` branch states the two-lane consequence at the yes, and
   `authorize_send`/`authorize_ungranted_send` route every send through the SAME grant —
   including a company or contact THIS BATCH creates partway through. `write_grant.covers()`
   only ever admits a value present in the grant's own `record_ids`/`record_domains` at the
   moment it was opened, so a same-run create's brand-new HubSpot id (unknowable before the
   write that mints it) is never, by itself, inside the grant — what covers it instead is the
   DOMAIN this step's own confirmation table names before the grant is ever opened (step 2,
   below: every company gets a proposed website confirmed in the batch table first). Express
   a same-run create's send by that domain, never by its own new id, and it is covered with
   no widening (verified against the real functions in `test_write_grant.py` and
   `test_unattended_pair_composition.py` — no change to `covers()` was needed, because the
   scope question was already answered by the domain the operator confirmed at step 2).

   **A resumed run gets a FRESH grant, always.** A grant exists only as a value in this
   conversation (GRANT-06) — it is never persisted and never rehydrated from
   `run_manifest.py` or `held_queue.py`. Resuming a broken batch (step 8, below) brings back
   which rows still need work; it never brings back the authority to write them. If no grant
   is open when a resumed batch reaches a send, that send asks again (or refuses, per steps 5
   and 7), exactly as if it were the first attempt.

   **The end-of-run account is scoped to THIS run (REVIEW-C16).** Read it from
   `written_records.load(path=written_records.written_records_path(run_id))` — never the
   path-less `written_records.load()`, which aggregates every historical run's artifact and
   would inflate the one number an operator checks a batch grant against with a previous
   batch's writes. The fuller end-of-run report, per-run ceilings, and the post-run allowlist
   proof are Phase 57's work (RUN-05, AFTER-01, AFTER-03) and are deliberately not built here.

2. **Resolve rows, then match them against HubSpot — unarmed.** For a spreadsheet
   (CSV/XLSX), read it with:

   ```python
   import preingest
   result = preingest.rows_from_table(path)
   rows = result["rows"]
   ```

   naming any `dropped_headers` the way `contact-upload` step 3 names dropped
   columns. For anything that is not already tabular — pasted text, a JSON blob, a
   URL, one or more images — follow `contact-upload/SKILL.md`'s own `extraction.md`
   contract exactly as that skill does, then take its accepted rows in place of
   `rows_from_table`'s.

   **A row carrying just one strong identity key — a non-blank `email`, or a non-blank
   `linkedin_url` — proceeds to the match search below exactly like any row that also
   carries a company.** The backend needs no company name to look a row up or later
   enrich it (D-61-01, the operator's own words: "relying on the plugin to propose
   best effort completion using the services n8n gives it"), so this flow never asks
   the operator to supply one just to get such a row moving — that is the unnecessary
   exception D-61-01 rejects. The weaker `firstname`+`lastname`+`company` group is
   unaffected and still needs all three fields present.

   **When that extraction pass also yields company rows** (`record_type: companies` —
   one artifact validates both lanes in one pass, companies first), confirm every
   proposed website in one table before those rows join this batch. When a company
   arrives with no domain — a bare name, a screenshot, a LinkedIn or directory page —
   propose one from whatever you can already see; research it only when you cannot
   confidently propose one, or the operator says to check it. Render one table, one
   row per company, showing exactly three things: the company, the proposed website,
   and where that came from with a one-line reason — an evidence link only on a row
   something actually researched. Before the batch yes, three moves are open on any
   row: accept as shown, type the right website instead, or say this one is wrong.
   Say what happens to that last case in the operator's own terms: the company still
   goes through, looked up by its name instead, and the run's report says so — never
   dropped.

   State the profile-page rule where the operator meets it: a LinkedIn or directory
   page is read for who the company is, and that page's own address is never recorded
   as their website, because a company filed under a social site's address becomes
   the record every later company from that source is mistaken for.

   **An affirmative answering this shown table, in the same turn, covers the batch,
   and anything that is not clearly an answer to this table leaves the batch
   unsent.** Only once every row is decided — a yes, a correction, or a decline —
   does `company_domain.to_envelope_spec` turn the table into the spec this batch is
   built from; an undecided row stops the whole batch rather than defaulting either
   way.

   Mint one `row_id` per row, once, for the whole batch — never per chunk, which would
   mint the same id twice:

   ```python
   spec = preingest.build_rows_spec(rows)
   ```

   Then look each row up against HubSpot, in chunks, sending an explicit empty
   provider list:

   ```python
   import chunking, config_gate, preingest

   cfg = config_gate.load_config()
   plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg, key="max_rows_per_match_request"))
   outcome = preingest.match_batch(plan, cfg)
   classified = preingest.classify_matches(
       spec["rows"], outcome.responses, unchecked_row_ids=outcome.unchecked_row_ids,
   )
   ```

   **This search needs no arming.** It writes nothing to HubSpot and spends no
   provider credit — it is a read wearing a search's clothes, not a step this flow's
   two grants protect. Widening what this search can look up — including the
   `linkedin_url` key above — does not change that: `fetch_matches` takes no `armed`
   parameter and sends an explicit empty provider list. The consent gate that guards
   spending is step 5's, below, unchanged — and every new call this widening enables
   still goes through the existing `preingest.match_batch` and `chunking.dispatch_plan`
   functions, never a new transport.

   Report exactly four groups, by name:

   - **auto-matched** — an exact email match. Count only here; nothing to decide.
   - **proposed** — a same-lastname, same-company match with no email match. Held for
     the operator to confirm, one at a time, in the next step.
   - **unmatched** — no hit at all. These are the rows that go on to enrichment.
   - **unchecked** — a chunk the search itself could not complete. Offer a retry for
     this group specifically, and say plainly that "we could not look" is a different
     answer from "we did not find one" — an unchecked row has not been ruled out of
     anything.

3. **Confirm the proposed matches — one numbered table, one line per decision.**
   (Amended 2026-08-05 at this skill's own read-through — 37-CONTEXT.md §13's
   confirmation-format amendment supersedes one-proposal-per-turn. The invariant
   that survives is the real one: each decision is still individually expressed,
   with the candidate's evidence and the row's own values side by side.)

   Render every proposed row from this chunk as **one numbered markdown table**: row
   label, then the row's own firstname/lastname/company/email, then the candidate's
   six fields — the HubSpot object id, first name, last name, email, job title, and
   company (this endpoint ships exactly those six; there is no record-modification
   timestamp on it at all, and none should be asked for, implied, or invented). A row
   with two or more candidates is ambiguous: give it one table line per candidate,
   sub-labelled `3a`, `3b`, and so on under its own row number.

   Answers are per-item and the vocabulary is fixed — nothing outside these four
   forms is accepted:

   - `<label>. approve` — confirm this row against its one candidate.
   - `<label>. deny` — decline this row; it moves to the unmatched, enrich-first path.
   - `<label>. pick <sub-label>` — for an ambiguous row only, e.g. `3. pick 3b`. An
     ambiguous row takes **only** `pick`; `approve`/`deny` on its own row label is
     refused, because there is no single candidate for a bare approve to mean.
   - `<label>. email: <address>` — a row-data correction, not a match decision: give
     this row the email it is missing, right here, so it does not fall to the ingest
     gate as a held row for no email later.

   Denying the whole table is fine as a blanket action — `deny all` is accepted, and
   the cost of getting it wrong is one row re-checked. Approving is different: a
   bare blanket approval, with no scope named, is refused outright — guessing what
   "all" means and approving the wrong candidate against it silently evaporates the
   true row (treated as already in HubSpot, never created — this is the original
   nine-directors failure, one row at a time). Bulk approval must name its scope
   explicitly every time: `approve 1-4, 7`, or, to approve literally every row in the
   table, `approve all 6` — restating the count is what proves the scope was seen,
   not assumed.

   Any row nobody answered this turn stays **pending** and is **restated** in full
   next turn — never defaulted either way, in either direction. A single malformed
   answer line refuses the **whole** table before anything is applied (the same
   all-or-nothing guard `apply_match_decisions` already runs), and the refusal names
   the offending line so the operator knows exactly what to fix and resend — not the
   whole table blind.

   Turn the answered lines into decisions and apply them in one call:

   ```python
   resolved = {"row-4": "101452", "row-9": preingest.DECLINE_MATCH}
   classified = preingest.apply_match_decisions(classified, resolved)
   ```

   A confirmed row moves into the auto-matched group, carrying the chosen candidate's
   object id. A declined row moves into the unmatched group and is enriched like any
   other no-match row. A row still pending stays proposed and is shown again.

   Copy/edit/reupload of the whole table — so an operator could answer it outside
   the chat turn and paste the result back — is a named upgrade path, not built here;
   the chunk ceiling already caps a proposal batch at roughly twenty rows, which is
   what keeps one table readable in a single turn.

4. **Preview the cost of enriching everything still unmatched.** Resolve providers
   the same way `enrich-records` step 3 does — the admin default is the full
   waterfall, and the operator may override it for this batch only, nothing written to
   config. Build the spec from the rows still sitting in `unmatched` after step 3:

   ```python
   unmatched_rows = [entry["row"] for entry in classified["unmatched"]]
   spec = {"rows": unmatched_rows, "object_type": "contacts"}
   ```

   Then render the same four blocks `enrich-records` renders:

   ```
   python3 scripts/preview_enrichment.py '<spec-json>' '<providers-json-or-omit>'
   ```

   For a batch too large for one argv string, write the spec to a scratch file first
   and pass its path — `preview_enrichment.py` reads a spec from a file when its first
   argument names one that exists. The records block for a rows spec says these rows
   are **not** in HubSpot yet, the opposite of what the ids/list form of this same
   preview says — do not summarise that away. Print the `"preview"."markdown"` block
   as a markdown table in chat by default.

5. **Ask for this waterfall run, then run it — or, under a grant, just run it.**

   **If a write grant covering this lane and these rows is open, ask for nothing here.**
   The operator approved this send when they opened the grant, and for a two-lane grant
   they were told at that moment that the HubSpot write was being authorized before this
   preview existed (D-53-05). Re-asking now would restore the stop-and-ask the grant
   exists to remove while giving back none of the protection that was traded (D-53-06,
   operator 2026-08-25). Name the grant the send runs under and continue.

   With no grant open, everything below is exactly as it was. Disarmed is the default and
   the state of every new conversation. Say plainly that sending is off, then ask for this
   run by naming what it will do — how many rows, which providers, and that it spends
   provider credit. **An affirmative answering that question — "yes", "go ahead", "do it",
   "please" — arms this run and nothing else.** There is no phrase to learn: an operator
   saying yes must never have to produce the system's wording to be heard (VOCAB-05). An
   affirmative that answers nothing, answers some other question, or arrives before this
   run has been described does **not** arm it — ask once more, naming what will happen, and
   take that answer; anything ambiguous is not consent. This state is never written to disk
   — it exists only as the `armed` argument passed to the dispatch call below, for this run
   only.

   **If a write grant covering this lane and these records is already open, do not ask at
   all.** Under D-53-05 (the operator's own decision, 2026-08-25) one grant may
   cover **both lanes of this flow — the enrichment lane and the contacts lane**. Say which
   lanes the open grant covers, in those words, rather than leaving the operator to infer
   it: when it covers both, neither of this flow's two asks is made and step 7 does
   not ask a second time. With no grant open, everything above is exactly as it is today,
   and step 7 asks again on its own.

   **Say what the operator accepted when they opened a grant covering both lanes, and say it
   at the yes rather than after it:** the grant **enables enrichment and writes to
   HubSpot** across both lanes. After the run, the records it actually wrote are listed in a
   `written_records-<run_id>.json` file (one per run, matching `written_records*.json`), in
   the plugin's durable state directory, so the operator can open them in HubSpot and amend
   them. This same disclosure applies to a single-lane grant too — say it there as well, not
   only when a grant spans both lanes.

   > **RECORDED EDIT — D-59-07, operator, 2026-08-28.** This paragraph used to carry a
   > longer pre-emptive warning, at the yes, describing the ordering of the write relative
   > to the enriched preview and what that ordering left unseen ahead of a write. That
   > warning is retired as operator-facing text — it was compensation nobody could act on
   > until after the fact anyway. The D-53-05 trade itself (one grant spans both lanes, the
   > allowlist stays record-scoped) is UNCHANGED; only what the operator receives in
   > exchange for it changed, from a prediction to the actionable post-run list above.
   >
   > **RECORDED EDIT — D-59-09, operator, 2026-08-29.** The artifact named above used to be
   > one file shared across every run (`written_records.json`); it is now one file per run,
   > and the disclosure sentence itself used to fire only for a grant spanning both lanes —
   > scoped there in error, since the artifact is written after every dispatch regardless of
   > lane count. Both corrections land here in the same edit.

   They can still stop the run by revoking the grant, and revoking
   **refuses the next send** — it **does not stop a dispatch already running**, so a revoke
   arriving mid-dispatch still lets every remaining chunk of that send go out.

   **A grant removes the question, not the safety.** The previews still run and are still
   shown, the rows are still named individually, each send still arms and disarms its own
   window bounded to that send's records, and a failed disarm is still reported loudly as
   its own state.

   **Every send opens its own record-scoped armed window — never a bare dispatch with the
   backend still disarmed (F2, 2026-08-25).** Under a grant, `write_grant.authorize_send`
   builds the decision from it. With no grant open, this run's own yes is what authorizes
   it: `write_grant.authorize_ungranted_send` builds a single-use grant scoped to exactly
   this send's records — using the SAME `allow_write_grants` authority and the SAME
   Guardrail A dirty-backend refusal a standing grant gets — and discards it once this
   dispatch finishes; it is never remembered as a standing grant, never written to disk.
   Once said this turn, mint the run handle, dispatch **asynchronously**, and recover the
   proposed values from the execution rather than the wire.

   **This dispatch submits async and reads progress via `run_state` (gap-closure,
   2026-08-31, operator decision "Option B" — see `scripts/watch.py`'s "Async recovery"
   section for the full mechanism).** A `mode: "propose"` row's proposed field values
   never travel by any channel `run_state.py` reads (CLAUDE.md §13.0.2: progress is
   read by the client, never by n8n) — `async_ack=True` makes the synchronous response
   an ack only (`Build Async Ack` wins the race against the full chain, deterministically,
   every time). The values are not lost, though: `Build Response` still runs to
   completion and its own output — read off the settled execution by the SAME `run_id`
   this run minted, an exact match, never a timing guess — is byte-identical to what the
   synchronous body would have carried. `watch.recover_async_dispatch` is the one place
   that reads it; nothing here re-implements that walk.

   ```python
   import chunking, config_gate, enrichment, n8n_arming, preingest, run_state, watch, write_grant

   run_id = run_state.new_run_id()  # minted before any HTTP call (REVIEW-C14)
   run_state.start_run(run_id, [row["row_id"] for row in unmatched_rows])

   cfg = config_gate.load_config()
   providers = enrichment.resolve_providers(<override or None>, cfg)
   plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg))
   decision = (
       write_grant.authorize_send(
           grant, lane="enrichment",
           record_ids=<this send's ids>, record_domains=<this send's domains>)
       if grant is not None else
       write_grant.authorize_ungranted_send(
           cfg, lane="enrichment", object_type=<object_type>,
           record_ids=<this send's ids>, record_domains=<this send's domains>,
           allow_create=<allow_create>, label="this run")
   )
   if not decision["armed"]:
       # revoked, closed, outside the grant, the admin has not enabled write grants, or
       # the backend is not in a known-disarmed state — STOP and report decision["detail"]
       ...
   with n8n_arming.armed_window(decision["workflow_id"],
                                <this send's ids>, <this send's domains>,
                                <allow_create>, cfg, grant=decision["grant"]):
       outcome = chunking.dispatch_plan(plan, providers, True, cfg, run_id=run_id, async_ack=True)
   run_state.mark_dispatched(run_id, [row["row_id"] for row in unmatched_rows])
   progress = run_state.read_progress(run_id)  # tell the operator N submitted, still running

   recovery = watch.recover_async_dispatch(cfg, run_id, plan.chunk_count)
   if not recovery["recovered"]:
       # The bound elapsed before every chunk settled. Tell the operator this run is
       # still going and offer to check again — by calling watch.recover_async_dispatch
       # with this SAME run_id, never by re-dispatching (that sends the same rows twice).
       ...
   else:
       merge_report = preingest.merge_enriched(unmatched_rows, recovery["responses"])
   ```

   **`recovery["responses"]` is already flat** — one `Build Response` item per row,
   because that is what one settled execution's own output already is (unlike a
   synchronous `outcome.responses`, which is one raw body PER CHUNK and needs flattening
   before `merge_enriched` — see `preingest.rerequest_unanswered`'s own re-request pass
   for that same flatten, and FINDING 2, 53-WALK-RECORD.md, for what skipping it does).
   Passing `recovery["responses"]` straight to `merge_enriched` is correct as written.

   The allowlist handed to `armed_window` is **this send's records, never the grant's whole
   record set** — that narrowing is what keeps every window strictly smaller than the grant
   it runs under, and it is the only structural protection left on this path once D-53-05
   collapsed the two asks into one.

   Chunks go one at a time, in plan order; a chunk that fails is skipped and the rest
   continue. The consent itself has no default — if the operator has not said yes this
   turn and no grant is open, do not call `dispatch_plan` at all.

   **A failed chunk's `outcome.results[i].resolvable` (D-59-08, gap closure
   2026-08-29) is a proposal to offer, not a dead end to report.** When it is
   non-empty, walk its entries and tell the operator what each `detail` says would
   resolve the row, naming every `resolution_sources` value the entry's `sources`
   tuple carries — an entry can claim more than one of the four
   (`hubspot_lookup`, `operator_statement`, `provider_result`, `same_row_derivation`).
   Nothing here acts on the operator's behalf — Claude proposes, the operator
   confirms, and no field is filled in to make the row pass. Refuse-to-propose, not
   refuse-to-guess, same as everywhere else this phase touches.

   **A linkedin-only row's waterfall miss is a HOLD, never a fallback to research
   (D-61-04).** Per D-61-04, only Lusha reads a bare `linkedin_url` at all — Apollo's
   match body and ZoomInfo's `hasZoomKey` never read the key, so neither can ever
   return anything for a row that carries nothing else. When Lusha itself finds no
   match for such a row, hold it with that reason recorded rather than escalating to
   `claude_web` research: that adapter is company-oriented (`object_type: companies`
   throughout `src/web_research.py`) and would be answering a different question
   about a different kind of subject entirely.

   **A HIT is proposed through the same `resolutions` / `provider_result` loop
   `extraction.md`'s own adapters already use — never a second proposal surface.**
   A value Lusha returns for a field this row did not already have is provenance, not
   invention (D-61-02's distinction): show it to the operator, and once confirmed,
   record it as a `resolutions` entry and validate the corrected record again, the
   same rewrite-and-revalidate loop the extraction lane already runs:

   ```python
   import chunking, config_gate, extraction, preingest

   cfg = config_gate.load_config()
   spec = preingest.build_rows_spec(preingest.rows_from_table(path)["rows"])
   plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg, key="max_rows_per_match_request"))
   outcome = preingest.match_batch(plan, cfg)
   classified = preingest.classify_matches(
       spec["rows"], outcome.responses, unchecked_row_ids=outcome.unchecked_row_ids,
   )
   # A linkedin-only row that lands in `unmatched` goes through the waterfall like any
   # other unmatched row (steps 4-5 above). Once Lusha returns a value this row did not
   # already carry, propose it; a confirmed value becomes a `resolutions` entry and the
   # corrected record is validated again — never written on Claude's own authority.
   unmatched_row = classified["unmatched"][0]
   record = {
       "row": unmatched_row["row"],
       "provenance": {"input": "lusha_waterfall", "locator": unmatched_row["row_id"]},
       "resolutions": [
           {"field": "company", "source": "provider_result", "detail": "Lusha contact enrich"}
       ],
   }
   result = extraction.validate({"records": [record]})
   ```

   `RESOLUTION_SOURCES`'s closed vocabulary is the same anti-laundering control here as
   everywhere else it applies (T-59-20): a `resolutions` entry naming a source outside
   the four legitimate identifiers rejects the whole record rather than being accepted
   unlabelled — there is no linkedin-specific exception to that rule.

   **When `outcome.written_records_failures` is non-empty (D-59-10, gap closure
   2026-08-29), say so plainly and lead with it, before the preview in the next
   step.** The `written_records-<run_id>.json` file this run flushes into (named at
   step 1 above) is **INCOMPLETE** — name which chunk indices are missing from it —
   and say the records those chunks wrote are **not** in that file even though the
   writes may have landed: a bookkeeping miss is not a dispatch failure, so the
   chunk's own send may well have succeeded. This list must never be read, by the
   operator or by Claude, as a complete account of what was written when this field
   is non-empty — the trade-off D-59-10 names explicitly for never stopping the
   dispatch over a bookkeeping failure.

   **Assess confidence, and hold — don't block (D-61-07).** Once the waterfall's own
   responses land, three properties hold for the rest of this run, stated in the
   operator's own terms because they are the promise this phase is measured against:
   nothing here is guessed, nothing is written that was held, and nothing waits for a
   held row mid-run. For each row's own response item (or its absence, for a row whose
   chunk failed outright — see above), turn it into a typed outcome and a verdict:

   ```python
   import confidence, held_queue, preingest, run_manifest, run_state

   # `responses` here is `recovery["responses"]` from the dispatch step above — already
   # flat (one item per row; see that step's own note on why no second flatten belongs
   # here).
   responses_by_id = {item["row_id"]: item for item in responses}
   held_entries = held_queue.load()
   verdicts = run_manifest.load()

   for row in unmatched_rows:
       row_id = row["row_id"]
       item = responses_by_id.get(row_id)
       parsed = preingest.parse_outcome(item) if item is not None else preingest.UNPARSEABLE_OUTCOME
       verdict = confidence.assess(parsed)

       if verdict.verdict == confidence.CONFIDENT:
           continue  # no per-row gate — proceeds to ingest like any other sendable row

       entry = held_queue.build_entry(row, verdict.hold_code, verdict.reason, parsed)
       held_entries[row_id] = entry
       held_queue.save(run_id, held_entries)
       verdicts[row_id] = run_manifest.CONFIDENCE_HELD
       # Shared path (unchanged) — step 8's resume reads this SAME file across turns.
       run_manifest.save(run_id, verdicts)
       # Run-scoped path (new) — the ONLY thing that makes run_state.read_progress able
       # to see this run's held rows; step 8's resume never reads this second copy.
       run_manifest.save(run_id, verdicts, path=run_manifest.run_manifest_path(run_id))

   progress = run_state.read_progress(run_id)  # done/held/failed, now that verdicts exist
   ```

   **The queue entry is written before the manifest verdict, in that order, every
   time** — a crash between the two leaves an unmentioned row that simply gets
   re-checked on the next resume (a duplicate provider call, never a dropped contact),
   never a row marked held with nothing recorded to review. The two `run_manifest.save`
   calls are a deliberate dual-write, not a redundancy: the shared path is what step 8's
   resume already reads across separate invocations of this skill (unchanged by this
   gap-closure), and the run-scoped path is what `run_state.read_progress` reads within
   THIS run. A confident row (the `continue` above) still gets no manifest entry at all
   — unchanged from before this gap-closure — so `read_progress`'s `done` bucket
   under-counts for this flow; `held`/`failed` are the buckets this call is for.

   A row this table cannot confirm is HELD, not guessed and not asked about here — the
   run moves straight to the next row regardless of what this one did, and reaches its
   last row whatever any single row's chunk or verdict was. Held rows do not join the
   `sendable`/`send` set below; they are collected, and shown ONCE, in the end-of-run
   review pass described after step 7's report.

   **The end-of-run review reuses step 3's own numbered-table vocabulary — `approve` /
   `deny` / `pick <sub-label>` / `email: <address>` — never a second decision
   vocabulary.** Its two safety rules carry over unchanged: a bare blanket approval
   with no named scope is refused, and one malformed line refuses the whole table
   before anything is applied. `approve` on a held row means proceed with it despite
   the hold; `pick` selects among a `HOLD_AMBIGUOUS_CANDIDATES` row's own real
   candidates, the same as an ordinary ambiguous, multi-candidate proposal.

   **What stays exactly as it is, said here so it is not mistaken for relaxed:** the
   non-clobber merge policy, the write-safety gate nodes, `plan_grant`'s empty-record-
   set refusal, the material-conflict judge gate, the per-send armed window, and the
   post-run written-records account. This step only decides who gets asked before a
   write — the write itself is exactly as gated as it always was.

6. **The enriched preview — the last look before anything reaches HubSpot.** Render
   it:

   ```python
   preview = preingest.render_enriched_preview(unmatched_rows, merge_report)
   ```

   State explicitly, in your own words, that nothing here has reached HubSpot yet —
   this is the last look before the next grant lets anything reach it. Name **every**
   held row individually, by the person, with the reason it is held, regardless of
   batch size — a count is not enough for a row that names an actual contact. For
   every row that will be sent, show what the source file supplied, what the
   enrichment waterfall added, and its SEND verdict. Show any merge conflicts the
   report carries — a case where the source's own value and a provider's differing
   value both exist, and the source's value was kept. This is the moment the operator
   is actually deciding something, not a status update on the way to a decision
   already made.

7. **Ask for the HubSpot write, then ingest.** Skip this step entirely if step 1 reported
   `can_send: false`. Otherwise: disarmed is the default here too. Say plainly that sending
   is off, then ask for this write by naming what it will do — how many rows, and that they
   are written to HubSpot. **An affirmative answering that question — "yes", "go ahead",
   "do it", "please" — arms this write and nothing else.** An affirmative that answers
   nothing, answers some other question, or arrives before this write has been described
   does **not** arm it; anything ambiguous is not consent. This state is never written to
   disk, it exists only as the `armed` flag on the one dispatch call below, for this write
   only, and it does not carry over from anything said earlier in the conversation — with
   no write grant open, an operator who already said yes to the waterfall at step 5 is
   still asked for this one, because it is a different consequence.

   **If the write grant opened at step 5 covers this lane too, do not ask
   again** — that is the single ask D-53-05 bought, and asking again here would take the
   protection and leave the cost.

   **Every send opens its own record-scoped armed window — never a bare dispatch with the
   backend still disarmed (F2, 2026-08-25).** Under a grant that covers this lane,
   `write_grant.authorize_send` builds the decision from it. Otherwise — no grant, or a
   grant that covers only the enrichment lane — this write's own yes is what authorizes
   it: `write_grant.authorize_ungranted_send` builds a single-use grant scoped to exactly
   this send's records — using the SAME `allow_write_grants` authority and the SAME
   Guardrail A dirty-backend refusal a standing grant gets — and discards it once this
   dispatch finishes; it is never remembered as a standing grant, never written to disk.
   Run the dispatch below inside this send's own window either way:

   ```python
   import config_gate, dispatch, n8n_arming, write_grant

   cfg = config_gate.load_config()
   decision = (
       write_grant.authorize_send(
           grant, lane="contacts",
           record_ids=<this send's ids>, record_domains=<this send's domains>)
       if grant is not None else
       write_grant.authorize_ungranted_send(
           cfg, lane="contacts", object_type="contacts",
           record_ids=<this send's ids>, record_domains=<this send's domains>,
           allow_create=<allow_create>, label="this write")
   )
   if not decision["armed"]:
       # revoked, closed, outside the grant, the admin has not enabled write grants, or
       # the backend is not in a known-disarmed state — STOP and report decision["detail"]
       ...
   with n8n_arming.armed_window(decision["workflow_id"],
                                <this send's ids>, <this send's domains>,
                                <allow_create>, cfg, grant=decision["grant"]):
       result = dispatch.dispatch(out_path, True, cfg, run_id=outcome.run_id)
   ```

   `run_id=outcome.run_id` is what makes D-59-09's "one file per run" promise (step 1, step
   5) true across BOTH of this flow's dispatches: `outcome` is step 5's own
   `chunking.dispatch_plan` result, and passing its `run_id` through here is what keeps
   this write's entry in the SAME `written_records-<run_id>.json` file as the enrichment
   lane's chunks rather than starting a second file — omitting it would still work
   (`dispatch.dispatch` generates its own `run_id` when none is given), just into the wrong
   file. `result` is `{"body": <the raw JSON body>, "run_id": <str>,
   "written_records_failures": [...]}`, not a bare body — `body = result["body"]` below,
   same as `contact-upload/SKILL.md`'s own step 7.

   Same rule as step 5: the allowlist is **this send's records, never the grant's whole
   record set**. And the same honesty about stopping it — revoking the grant **refuses the
   next send** and **does not stop a dispatch already running**.

   **When `result["written_records_failures"]` is non-empty, say so plainly before the
   report** — the same D-59-10 relay step 5 already gives the enrichment lane's own
   bookkeeping misses: this write's outcome could not be recorded in the artifact even
   though the write itself may have landed; a bookkeeping miss is never a dispatch failure.

   Build and send a CSV of exactly the rows the preview marked SEND — never the
   operator's original file, which is what makes holding a row back possible at all:

   ```python
   import extraction

   sendable_rows, held = extraction.hold_emailless(merge_report.rows)
   sendable_rows = extraction.strip_row_id(sendable_rows)
   extraction.write_dispatch_csv(sendable_rows, out_path)
   ```

   `strip_row_id` drops the `row_id` join key `build_rows_spec` minted in step 2 — every
   stage since has carried it forward on purpose, but it is not a HubSpot property, and
   `write_dispatch_csv` refuses any row that still carries it (STRUCT-01). This is the
   only place in this flow that call belongs — every earlier stage still needs `row_id`
   to join by.

   `write_dispatch_csv` raises, and writes nothing, if a held row ever slipped through
   this far — treat that raise as a bug to stop and report, not something to retry
   around.

   From here, follow `contact-upload/SKILL.md`'s own steps **by heading, unmodified**
   — their mechanics are untouched by this flow and a second copy of them here is
   exactly the drift risk this plugin avoids everywhere else:

   - "Dispatch under an open grant, or otherwise only once the operator has said yes to
     this send." — the call above.
   - "Report the outcome — per record, not a bare acceptance." — summary counts,
     failing rows in full, successful rows only for a small batch.
   - "Re-check, only when the operator asks."
   - "Retry a transport failure — same dispatch, same arming gate."
   - "Clean up." — delete this flow's own scratch artifacts the same way, whether the
     batch was sent or the operator declined.

   **After** the backend's own report, restate the held rows from step 6 — they never
   entered this dispatch at all, so nothing in the backend's report mentions them, and
   a person named once several turns earlier is a person nobody is acting on unless
   they are said again here.

   Then hand the confirmed-match object ids onward — every row in `classified`'s
   auto-matched group, whether it matched by email or was confirmed in step 3 —
   to `enrich-records`:

   ```python
   confirmed_ids = [entry["hs_object_id"] for entry in classified["auto_matched"]]
   ```

   A confirmed match with no email is the clearest case this matters for: it is not
   ingested (there is no email to ingest it by) and this flow does not enrich its
   attributes either — but it now has a HubSpot object id, which is exactly what
   `enrich-records` needs to work with a record by id rather than by email.

   Three things worth saying plainly, here or earlier, however the conversation
   reaches them: this flow always sends a **rewritten** CSV of exactly the approved
   rows, never the operator's own file, because holding a row back is impossible any
   other way; a confirmed match with no email keeps its id and nothing else, as just
   described; and the two consents are per-call arguments that never outlive the
   turn that gave them, while a write grant, where one is open, lasts the conversation,
   is **never written to disk**, and ends on completion, revocation, session end, error
   or a ceiling breach.

   **Arming one lane does not arm any other lane**, in either direction — and that stays
   true under a grant, which is worth saying because a grant spanning two lanes reads as
   if it contradicted it. It does not. D-53-05 collapsed the two asks at the level of the
   **grant**, the authorization; it changed nothing at the level of the **arm**. A grant
   may authorize both lanes, but **each individual arm still opens its own window over one
   lane's workflow and only that send's records**. Saying a phrase early still does not
   carry it forward to a moment that has not happened yet.

8. **Resuming a broken batch (Phase 61 Plan 05 Task 3, REVIEW-C13/08/C15).** If a chunk
   failure, a dropped connection, or an operator stopping mid-batch leaves rows
   unfinished, this flow does not have to re-spend provider credit on rows it already
   settled. Persist what each row's run actually reached — `matched`, `enriched`,
   `held`, or `unchecked` — **per chunk, as this batch proceeds, through
   `chunking.merge_chunk_verdicts`, never a bare `run_manifest.save`:**

   ```python
   import chunking

   chunking.merge_chunk_verdicts(run_id, chunk_verdicts)
   ```

   **Never call `run_manifest.save(run_id, verdicts)` directly from this step.**
   `save()` writes the map it is given as the COMPLETE document — a call that saved
   only the current chunk's own rows would ERASE every earlier chunk's verdicts, which
   is exactly backwards from what "persist per chunk" is for. `merge_chunk_verdicts`
   loads whatever this run has already accumulated, folds this chunk's verdicts on top,
   and saves the whole thing — the crash window this bounds is exactly one chunk wide.

   The next time this skill runs against the same source, do not read `run_manifest.load()`
   and `rows_to_resume` directly — classify the file first, through `watch.resume_or_disclose`,
   and say its disclosure sentence out loud, VERBATIM, before anything else in this step:

   ```python
   import watch

   resume_report = watch.resume_or_disclose(rows)
   # Say resume_report.disclosure out loud, verbatim, before proceeding.
   rows = resume_report.rows
   ```

   This is the report-path half of a deliberate split: the RESUME rule underneath
   (`run_manifest.rows_to_resume`) is unchanged and still degrades a missing or corrupt
   manifest to "resume everything" — that trade is correct and stays. What
   `resume_or_disclose` adds is telling the operator WHICH of four things actually
   happened, rather than letting a corrupted or foreign-run manifest read as a fresh
   first run:

   - **`"no previous state — running all N rows"`** — nothing has run here before.
   - **`"resuming — K of N already done, M to go"`** — an ordinary resume; K/M come
     straight from `resume_report.skipped`/`resume_report.rows`.
   - **`"previous state unreadable — rerunning all N rows, nothing was skipped"`** — the
     manifest file exists but could not be trusted (missing, malformed, or carrying a
     verdict word that is not one of the six allowed).
   - **`"previous state belongs to a different run — rerunning all N rows, nothing was
     skipped"`** — the file is perfectly readable, but its own recorded run id does not
     match this run's (pass `expected_run_id=` to get this fourth classification).

   The last two are both a **full rerun, disclosed loudly** — never a partial trust and
   never presented as a fresh first run (REVIEW-C15). Rows still `held` are re-included
   the moment they gain an email and reported as still held otherwise; rows `unchecked`
   are always re-requested, because "we could not look" is a reason to look again, not
   an answer about the row — both of those are `rows_to_resume`'s own unchanged rules,
   inherited through `resume_or_disclose`.

   Once this pass's own rows settle, distinguish what THIS pass finished from what was
   already done before it started — never one merged count, which reads exactly like a
   fresh run that got lucky:

   ```python
   completion = watch.build_resume_completion_report(resume_report, this_pass_verdicts)
   ```
