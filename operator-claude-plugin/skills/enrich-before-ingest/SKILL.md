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

1. **State the target, and that this flow arms twice.** Run:

   ```
   python3 scripts/config_gate.py
   ```

   If the JSON reports `"ok": false`, relay its `"error"` message to the operator
   exactly as given, then STOP. Never show, echo, or ask for a secret, and never
   surface a raw socket or parser error — the script has already translated it.

   If it reports `"ok": true`, tell the operator this flow touches the n8n instance
   named in `"target"` three ways: an unarmed search that just looks up whether a row
   already exists in HubSpot, a provider waterfall call that spends money once armed,
   and the ingest write itself — the same endpoint `"target"` names — once armed a
   second time. Then read `"can_send"` exactly as `contact-upload/SKILL.md` step 1
   does: when it is `false`, say so with the relayed `"send_blocked_reason"`, and carry
   on building previews (they cost nothing), but do not ask for either send for the
   rest of this conversation.

   Say up front, before any other work, that this flow will ask for permission
   **twice, at two different moments** — once before any provider credit is spent, and
   again before anything is written to HubSpot — with a full preview of the enriched
   result landing in between. The second ask is not a formality and it is not a repeat
   of the first: it is the operator's answer to that preview, which does not exist yet
   when the first grant is given. Say this plainly here so it is not a surprise five
   turns later — an operator surprised by the second ask learns to pre-grant both,
   which is exactly the shortcut this design exists to prevent.

   **The one exception, and say it here rather than at step 5:** if a write grant covering
   both of this flow's lanes is open, the operator is asked once instead of twice — that is
   D-53-05, their own decision of 2026-08-25. Name which lanes the open grant covers and say
   what the single ask costs them: the HubSpot write is authorized before the enriched
   preview exists. With no grant open, this flow asks twice, exactly as described above.

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
   two grants protect.

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
   at the yes rather than after it:** the HubSpot write is **authorized before the enriched
   preview exists**. Every row held for review, and every merge conflict where the source
   file's own value was kept over a differing provider value, is authorized before they have
   seen it — the enriched preview at step 6 is the only place those become visible ahead of a
   write. It is still rendered and still worth reading; under a two-lane grant it is a report
   rather than a gate. They can still stop the run by revoking the grant, and revoking
   **refuses the next send** — it **does not stop a dispatch already running**, so a revoke
   arriving mid-dispatch still lets every remaining chunk of that send go out.

   **A grant removes the question, not the safety.** The previews still run and are still
   shown, the rows are still named individually, each send still arms and disarms its own
   window bounded to that send's records, and a failed disarm is still reported loudly as
   its own state.

   Under a grant, this step's dispatch is wrapped in this send's own window:

   ```python
   import n8n_arming, write_grant

   decision = write_grant.authorize_send(
       grant, lane="enrichment",
       record_ids=<this send's ids>, record_domains=<this send's domains>)
   if not decision["armed"]:
       # revoked, closed, or outside the grant — STOP and report decision["detail"]
       ...
   with n8n_arming.armed_window(decision["workflow_id"],
                                <this send's ids>, <this send's domains>,
                                <allow_create>, cfg, grant=decision["grant"]):
       outcome = chunking.dispatch_plan(plan, providers, True, cfg)
   ```

   The allowlist handed to `armed_window` is **this send's records, never the grant's whole
   record set** — that narrowing is what keeps every window strictly smaller than the grant
   it runs under, and it is the only structural protection left on this path once D-53-05
   collapsed the two asks into one.

   Once said this turn, dispatch and merge:

   ```python
   import chunking, config_gate, enrichment, preingest

   cfg = config_gate.load_config()
   providers = enrichment.resolve_providers(<override or None>, cfg)
   plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg))
   outcome = chunking.dispatch_plan(plan, providers, True, cfg)
   merge_report = preingest.merge_enriched(unmatched_rows, outcome.responses)
   ```

   Chunks go one at a time, in plan order; a chunk that fails is skipped and the rest
   continue. `armed` has no default — if the operator has not said the phrase this
   turn, do not call `dispatch_plan` at all.

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
   protection and leave the cost. Run the dispatch below inside this send's own window:

   ```python
   import n8n_arming, write_grant

   decision = write_grant.authorize_send(
       grant, lane="contacts",
       record_ids=<this send's ids>, record_domains=<this send's domains>)
   if not decision["armed"]:
       # revoked, closed, or outside the grant — STOP and report decision["detail"]
       ...
   with n8n_arming.armed_window(decision["workflow_id"],
                                <this send's ids>, <this send's domains>,
                                <allow_create>, cfg, grant=decision["grant"]):
       result = dispatch.dispatch(out_path, True, cfg)
   ```

   Same rule as step 5: the allowlist is **this send's records, never the grant's whole
   record set**. And the same honesty about stopping it — revoking the grant **refuses the
   next send** and **does not stop a dispatch already running**.

   Build and send a CSV of exactly the rows the preview marked SEND — never the
   operator's original file, which is what makes holding a row back possible at all:

   ```python
   import extraction

   sendable_rows, held = extraction.hold_emailless(merge_report.rows)
   extraction.write_dispatch_csv(sendable_rows, out_path)
   ```

   `write_dispatch_csv` raises, and writes nothing, if a held row ever slipped through
   this far — treat that raise as a bug to stop and report, not something to retry
   around.

   ```
   python3 scripts/dispatch.py <out_path> armed
   ```

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

8. **Resuming a broken batch.** If a chunk failure, a dropped connection, or an
   operator stopping mid-batch leaves rows unfinished, this flow does not have to
   re-spend provider credit on rows it already settled. Persist what each row's run
   actually reached — `matched`, `enriched`, `held`, or `unchecked` — as this batch
   proceeds:

   ```python
   import run_manifest
   run_manifest.save(run_id, verdicts)
   ```

   The next time this skill runs against the same source, load it back and ask only
   about what still needs an answer:

   ```python
   manifest = run_manifest.load()
   resume = run_manifest.rows_to_resume(rows, manifest)
   ```

   Tell the operator what was **skipped** because it already finished, by name or
   count, rather than silently starting a smaller batch — a resume that looks like a
   fresh, smaller run is indistinguishable from one that lost rows. Rows still `held`
   are re-included the moment they gain an email and reported as still held
   otherwise; rows `unchecked` are always re-requested, because "we could not look" is
   a reason to look again, not an answer about the row.
