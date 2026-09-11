---
name: review-triage
description: Work the queue of HubSpot records the enrichment pipeline flagged for a human decision — see each conflict in plain language, approve or reject it, and have the result confirmed by re-reading the record. Use when the operator asks what needs review, what is waiting on them, to work or clear the review queue, to look at flagged or held records, or to approve or reject a specific record — or invoke it directly as /operator-claude-plugin:review-triage.
---

# Review Triage

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.


The pipeline holds a decision back when it is not sure enough to write it. This skill shows
those held decisions, lets the operator adjudicate one, and reports what actually landed.

**Two things this skill never does.** It never decides for the operator which way a record
should go, and it never claims a write landed because the request was accepted. The verdict
always comes from re-reading the record afterwards.

**The backend owns the policy, not this skill.** The protected-field labels below are a
*display* lookup so the operator knows before they invest in a decision. This client never
refuses a decision on policy grounds — the endpoint is the one authority on what may be
written, and a second opinion here would be a second authority that drifts from it.

## Steps

1. **Check configuration and state the arming position, before any other work.**

   `scripts/review_queue.py` and `scripts/review_decision.py` are libraries, not CLIs —
   the same way `scripts/report.py` is. Import them (`python3` with
   `operator-claude-plugin/scripts` on the path, as `conftest.py` does for the tests) and
   call `config_gate.load_config()` first.

   If loading raises `ConfigError`, relay its message to the operator **exactly as given**
   — it already names the missing key, where to fix it, and what still works — and STOP.
   Never show, echo, or ask for a secret.

   Then say, before answering anything else, the **accurate two-part position** (D-60-01,
   D-60-04, Phase 60): nothing reaches HubSpot until the operator says yes to a specific
   record's exact write, **and** a write grant covering that record must be open. The
   operator can open that grant right here in this conversation — no shell, no deploy —
   once an n8n admin has set `allow_write_grants` in `operator.local.json`. Say it even if
   the operator only asked a question.

2. **Fetch the queue.**

   ```
   review_queue.fetch_queue(config, object_type)      # "companies" or "contacts"
   ```

   It returns `{available, reason, object_type, total, returned, rows}`.

   **If `available` is `false`, the queue was not read — say so and stop.** Do not describe
   an unavailable queue as an empty one. `hubspot_search_did_not_run` in particular means
   HubSpot refused the search, not that the backlog is clear; telling the operator nothing
   needs review when nothing was read is the worst answer this skill can give. Name the
   reason in plain language and say who can fix it.

   If `available` is `true`, render with:

   ```
   review_queue.render_queue(rows, total, policy_lookup, link_lookup)
   ```

   The two lookups are **exactly** these — `link_lookup` takes the whole **row** and must
   extract `hs_object_id` itself, because `render_record` passes it the row, while
   `record_link` takes an **id**. Composing them any other way renders a broken URL with
   the entire row dict in it (found live, RB-9 step 5):

   ```python
   policy_lookup = lambda field: review_queue.policy_class(object_type, field)
   link_lookup = lambda row: review_queue.record_link(
       object_type, row.get("hs_object_id"), config.get("hubspot_portal_id"))
   ```

   `total` greater than `returned` means this is a page, not the whole backlog — the
   rendering already says so. Companies and contacts are separate fetches; if the operator
   asks "what needs review" without saying which, show both.

2b. **Read the held queue too (F2-3, 2026-09-11 ruling).** The pipeline also holds rows
   that never reached HubSpot at all — a contact-ingest row `held_queue.json` parked on a
   `no_match` hold. Those never show up in step 2's HubSpot fetch because there is no
   HubSpot record to search for. Reading this file is local and costs nothing — no network,
   no provider credit:

   ```python
   import held_queue

   held_state = held_queue.classify_read()
   held_entries = held_queue.load()
   still_open = held_queue.open_entries(held_entries)          # drops create/skip/drop
   undecided = {rid: e for rid, e in still_open.items()
                if held_queue.entry_verb(e) is None}             # also drops retry

   known_company_domains = set()  # grows during this sitting -- see 2c below
   by_facet = {}
   for rid, entry in undecided.items():
       by_facet.setdefault(
           held_queue.classify_facet(entry, known_company_domains), []).append(rid)
   ```

   **If `held_state` is `held_queue.ANOMALOUS`, the held queue was NOT read** — the same
   rule step 2's `available: false` branch already carries: say so plainly and do not
   render it as empty. `held_queue.ABSENT` (no file) IS legitimately empty — say that
   instead, never the same sentence as `ANOMALOUS`.

   **A `retry`-marked entry is not in `undecided` and is not lost — it is `held_queue.
   open_entries`'s own "still open" but has already been looked at once this backlog's
   life.** It belongs to the next enrichment run's own resume (`run_manifest.
   rows_to_resume` reads it there), not to this table. Count it in the parked line (2c)
   so no open entry is both unlisted and uncounted.

   **`known_company_domains` is conversation knowledge, never a lookup this step
   performs.** `held_queue.classify_facet` discriminates on whether the entry's OWN email
   domain is already known to exist as a HubSpot company — never on whether the entry's
   `row["company"]` column happens to be filled in (a row can carry a company name and
   still read `needs_company`, because the classifier never reads that field at all). With
   nothing yet confirmed this sitting, every entry reads `needs_company` — the function's
   own documented safe, review-first default. Add a domain only from a legitimate source —
   the same closed vocabulary `enrich-records/SKILL.md` step 7 already names
   (`hubspot_lookup`, `operator_statement`, `provider_result`, `same_row_derivation`):
   an enrich-records or contact-upload batch that already ran earlier in this sitting, an
   operator statement naming a company already in HubSpot, or 2c's own company-verb
   handoff landing. Never Claude's own recall, never a domain inferred from a company's
   name. This step performs no HubSpot search of its own to populate it — that would be
   exactly the widening `write_grant.py`'s own docstring already refuses to take on
   (`plan_grant`'s resolution happens in a skill, never inside the authorization
   boundary), and giving THIS read a lookup of its own would be the identical widening one
   step earlier.

2c. **Render one table, continuously numbered from 1 — HubSpot conflicts first, then the
   held rows.** Number every row from step 2's HubSpot render onward without resetting,
   then continue the same sequence for `by_facet[held_queue.FACET_NEW_PERSON]` and
   `by_facet[held_queue.FACET_NEEDS_COMPANY]`, in that order. Each held row shows the
   person (first name, last name), the company, the enriched email the waterfall found, and
   the hold's own reason. Say plainly that the email shown is what the run recovered, not a
   guess, and name its source (`entry["row"]`, the merged row `held_queue.build_entry`
   persisted — see `260911-w6o-SUMMARY.md`).

   - **A `held_queue.FACET_NEW_PERSON` row offers `create`** — this row's own domain is
     already known to exist in HubSpot, so its create is expected to land.
   - **A `held_queue.FACET_NEEDS_COMPANY` row offers `company`, not `create`** — see step
     4c for what that verb does and why the label does not change once the company lands.

   **Pre-suggest the create, under the table, as a ready answer the operator can send back
   verbatim.** One line offering the bulk create for the new-person facet, restating its
   count in the same shape `enrich-before-ingest/SKILL.md` step 3's own bulk example uses.
   This is an OFFER, never an action, and the count in it is the count of new-person rows
   actually shown — never a total that folds in a parked or a conflict row.

   **Print exactly one parked line under the table.** `parked_ids` is every entry in
   `still_open` that the table did not list — `held_queue.FACET_NOTHING_FOUND` rows (no
   usable email to create by), every entry whose `classify_facet` reads `None` (a hold code
   other than `no_match` — five others: `unparseable`, `unadjudicated_conflict`, an
   unrecognized match signal, `ambiguous_candidates`, `no_table_row_matched`), and every
   `retry`-marked entry. Give the count and the words that show them, each with its own
   hold reason when the operator asks. Say in one sentence why they are parked rather than
   dropped: an unread or unshown queue presented as an empty one is the worst answer this
   skill can give.

3. **Let the operator pick which records to work this sitting.** Do not pick for them. They
   may name one record, several, or say to work the whole page shown — either way, the
   records named here are what step 4 scopes the sitting's authority to.

   **The answer vocabulary for the numbered table is ONE vocabulary, ported by heading from
   `enrich-before-ingest/SKILL.md` step 3** ("Confirm the proposed matches — one numbered
   markdown table, one line per decision") — never a second one invented here: per-item
   answers keyed by the row's own label; a blanket decline is accepted; a bare blanket
   approval with no named scope is refused outright; a bulk affirmative must restate its
   count, in the same shape that step's own example uses, because restating the count is
   what proves the scope was seen rather than assumed; an unanswered row stays pending and
   is restated in full next turn, never defaulted in either direction; and one malformed
   answer line refuses the WHOLE table before anything is applied, naming the offending
   line. **On a HubSpot-flagged conflict, `approve`/`reject` remain the only decision
   words — that vocabulary is not widened by this table.** A held row answers with its own
   facet's verb instead: `create` (new-person), `company` (needs-company; step 4c), or the
   backlog's own `skip`/`drop` (`held_queue.VERB_SKIP`/`held_queue.VERB_DROP`) to close a
   row out with no further action.

4. **Open the sitting — one grant, one batch window, for the whole sitting (D-60-06).**

   Mint the run id before any HTTP call — the same run this sitting's `written_records`
   artifact and step 8's account are both keyed by:

   ```python
   import n8n_arming, run_state, write_grant

   run_id = run_state.new_run_id()
   ```

   **If a grant already open from an earlier enrichment or contact-ingest batch in this
   conversation covers the records step 3 named, reuse it (D-60-02) — do not open a
   second one.** One grant opened for any of the three lanes covers all three together, so
   a record already enriched or ingested under an open grant can be triaged here with no
   second deliberate yes.

   **Otherwise, plan and open a grant over exactly the records step 3 named,** naming
   `providers=[]` always — a review batch spends no provider credit, and a create spends
   none either (the enrichment already happened; this is the ingest write only), so naming
   the configured provider selection here would price the envelope against credits this
   sitting never touches. **`lanes` and `allow_create` widen only when this sitting
   includes at least one held-row create** (2c/3): `lanes=["review", "contacts"]` and
   `allow_create=True` in that case; otherwise `lanes=["review"]` and `allow_create=False`,
   exactly as before:

   ```python
   proposal = write_grant.plan_grant(
       config, lanes=["review", "contacts"] if any_create_chosen else ["review"],
       object_type=object_type, record_ids=record_ids, record_domains=record_domains,
       allow_create=any_create_chosen, providers=[])
   ```

   Present the proposal exactly as any other grant offer is presented, and only once the
   operator confirms:

   ```python
   grant = write_grant.open_grant(proposal, confirmation, config)
   ```

   Then open **one** batch window over the grant's own record scope and hold it for the
   **whole sitting** — every record picked in step 3, not one window per decision:

   ```python
   batch = write_grant.authorize_review_batch(grant)
   if not batch["armed"]:
       # relay batch["detail"] and stop — nothing to open, nothing armed
       ...
   ```

   ```python
   with n8n_arming.armed_review_window(
           batch["workflow_id"], batch["record_ids"], batch["record_domains"],
           config, grant=grant) as window:
       ...  # steps 5-8 run inside this block, once per record the operator picked
   # window.disarm_result is available once the block exits — on the happy path,
   # on a mid-sitting exception, and on a mid-sitting revocation alike (the context
   # manager's own guarantee, unchanged from the per-send window dispatch already uses).
   ```

   **Read the LITERAL allowlist back from `window.arm_result["observed"]` and state it to
   the operator, id by id, before the first decision of the sitting.** Why in one clause:
   the NUMBER of ids the grant covers is not evidence of WHICH ids actually landed on the
   live backend, and a window whose allowlist does not hold the record about to be decided
   will refuse it (the 49-W2 lesson — a count check is not a membership check). An
   administrator with a repository checkout has an independent second-process cross-check
   available for this: the scoped form of `scripts/verify_live_write_safety.py`, which can
   pin allowlist MEMBERSHIP on this one workflow while every other stays asserted fully
   disarmed. This skill does not ask the operator to run it — the plugin does not ship that
   script, and this skill's own closing section forbids a step that shells out — but it is
   quoted here in full so an administrator can use it without reconstructing the invocation:

   ```
   python scripts/verify_live_write_safety.py --expectation armed \
       --allowlist <the id(s) or domain(s) window.arm_result["observed"] shows> \
       --expect-armed ALLOW_HUBSPOT_REVIEW_WRITES \
       --armed-workflow "LV Review Decision (Cloud)"
   ```

   **Say plainly that the window is grant-wide but every decision inside it is still
   checked per record** (D-60-03): a record the grant does not name is refused even
   mid-sitting, exactly as if no window were open at all — the batch window widens WHEN
   the backend accepts a review write, never WHAT it may write.

   **This window covers the review workflow only — a held-row create (4a-4c below) opens
   its own, separate window on the ingest workflow, and the two never collide.** An
   ingest send's own pre-flight (`write_grant.preflight_before_send`) scopes its liveness
   read to that one lane's workflow id, never to every workflow a grant happens to cover
   (`n8n_arming.arm_for_dispatch`/`arm_for_review` each target exactly one `workflow_id`'s
   own declaring nodes — confirmed on disk, not merely assumed). So the review window's own
   arm is never mistaken for a dirty ingest backend, and an ingest create can run before,
   after, or between conflict decisions, in whatever order the operator's picks make
   natural — 4a-4c do not need to nest inside the `with` block above.

4a. **Held rows: build the CSV for the creates this sitting chose (2c's `create` verb).**
   A rewritten CSV of exactly the chosen rows is the only shape allowed to reach the
   backend — a held row nobody chose must be unable to travel with one that was:

   ```python
   import extraction, preingest

   create_rows = [held_entries[rid]["row"] for rid in chosen_row_ids]
   created_by_row_id = {rid: held_entries[rid]["row"].get("email") for rid in chosen_row_ids}
   create_rows = preingest.strip_enrichment_extras(create_rows)
   create_rows = extraction.strip_row_id(create_rows)
   extraction.write_dispatch_csv(create_rows, send_path)
   send_row_count = len(create_rows)
   ```

   `chosen_row_ids` and `send_path` bind by name from the operator's answered table lines
   and this sitting's scratch directory. `strip_enrichment_extras` runs before
   `strip_row_id` for the same reason `enrich-before-ingest/SKILL.md` step 7 already
   orders them — a held row's stored fields (`mobilephone`, `lv_linkedin_url`) are not in
   `extraction.canonical_props()`, and skipping this strip raises `non_canonical_key_in_row`
   at the write, not here where it could still be fixed.

   `created_by_row_id[rid]` is never `None` for a row reached this way: `chosen_row_ids`
   only ever names rows 2c offered `create` for, and `held_queue.classify_facet` only
   ever returns `FACET_NEW_PERSON` for an entry it has already proven carries a usable
   email (its own decision table, step 1) — so a row with no email can never be `create`d
   here, and 4c's `if email` filter is a defensive read of that guarantee, not a silent
   drop of a row the operator actually chose.

4b. **Send it — contact-upload's own dispatch, by heading, never a second copy of it
   here.** From here the create follows `contact-upload/SKILL.md`'s own steps, unmodified,
   naming them exactly: **"Dispatch under an open grant, or otherwise only once the
   operator has said yes to this send."**, **"Report the outcome — per record, not a bare
   acceptance."**, **"Re-check, only when the operator asks."**, **"Retry a transport
   failure — same dispatch, same arming gate."**, and **"Clean up."** Two reasons, one
   clause each: there is exactly ONE ingest dispatch implementation in this plugin and a
   second copy here would drift from it; and because 4's grant already covers the
   `contacts` lane when a create is chosen, that step's `grant is not None` branch asks the
   operator nothing further — no export, no second skill invocation, no extra prompt. Hand
   it `send_path`, `send_row_count`, `send_ids=[]` (a create names no existing record),
   `send_domains` — the domain of each chosen row's own enriched email, the same shape
   `suggestion_declines.py`'s own precedent already binds it (`row["email"].rpartition
   ("@")[2]`, verified on disk) — and `allow_create=True`, plus the open `grant`.

4c. **Confirm by re-reading, then mark — ONE call for the whole create batch, never one
   per row** (the F1 lesson: each of these costs an n8n execution):

   ```python
   import chunking, config_gate, preingest

   cfg = config_gate.load_config()
   confirm_spec = preingest.build_rows_spec(
       [{"email": email} for email in created_by_row_id.values() if email])
   confirm_plan = chunking.plan_chunks(
       confirm_spec, chunking.chunk_ceiling(cfg, key="max_rows_per_match_request"))
   confirm_outcome = preingest.match_batch(confirm_plan, cfg)
   confirmed = preingest.classify_matches(
       confirm_spec["rows"], confirm_outcome.responses,
       unchecked_row_ids=confirm_outcome.unchecked_row_ids)
   landed = {entry["row"]["email"]: entry["hs_object_id"]
             for entry in confirmed["auto_matched"]}
   ```

   The verdict comes from this independent re-read, never from 4b's own dispatch report —
   this skill's standing rule (step 8) applies here too. The join is on email, not
   `row_id`: `build_rows_spec` mints fresh ids and refuses a row that already carries one,
   so the held row's id does not survive this confirm pass. An `unchecked` or `unmatched`
   confirm row is **"sent, not yet confirmed"** with an offer to re-read — never inverted
   into "the create failed": a HubSpot search index can genuinely lag a fresh create by
   seconds to about a minute, and `unmatched` here means "not yet visible", not "not
   there".

   Then mark, only for a row the re-read actually found — `held_queue.record_verb` loads
   and saves itself, so there is nothing to `load()` or `save()` separately:

   ```python
   import held_queue

   for row_id, email in created_by_row_id.items():
       if email and email in landed:
           held_queue.record_verb(row_id, held_queue.VERB_CREATE, run_id)
   ```

   A row not in `landed` keeps its open status and is shown again next sitting — never
   marked on a hope.

   **A `held_queue.FACET_NEEDS_COMPANY` row's `company` verb (2c) hands off BY HEADING to
   `enrich-records/SKILL.md`'s "Companies that may not be in HubSpot yet" form** —
   unmodified, its own website-confirm table and mandatory-domain rule included. What this
   skill supplies is the domain, derived from the held row's own email address; the
   company's NAME comes from the operator, never guessed from a domain. Per CLAUDE.md
   §13.0.1 the ingest lane resolves a row's company by manual id, then the email's own
   domain, then an exact name — and a create that resolves none is downgraded to review
   **server-side**. This plugin does not and will not reproduce that downgrade
   client-side: the backend is the one authority on it.

   **The facet does not flip on its own.** `held_queue.classify_facet` is pure over the
   entry plus whatever `known_company_domains` the caller supplies — nothing writes a
   confirmed company back into the held entry, and nothing re-derives the facet from disk.
   Once the company create/confirm lands, add that domain to this sitting's own
   `known_company_domains` and re-facet **that one row**
   (`held_queue.classify_facet(entry, known_company_domains)`) — it now reads
   `FACET_NEW_PERSON`. Offer that row's create in the **same sitting**, immediately after
   the company lands, through 4a-4c above.

5. **Elicit the decision and a reason.**

   **On a HubSpot-flagged conflict**, the two decisions are **approve** and **reject**, and
   nothing else is a decision word — the held-queue rows step 2c/3 added have their own
   verbs, named where their facet is (2c), and do not widen this pair.

   - **Approve** promotes the record's own held candidate through the backend's existing
     non-clobber merge.
   - **Reject records the operator's reason and leaves the record in the queue.** Say it in
     those words. A rejection does not clear, dismiss, remove, resolve or close anything —
     the record is still flagged afterwards and will still appear in this queue. A review
     flag is never cleared without a recorded decision.

   **Ask for a reason every time**, in the operator's own words, and say why: the reason is
   what makes this decision legible to whoever reads the record in six months. If they
   decline to give one, **accept the decision anyway** — a decision without a reason is
   still a decision. Do not block on it and do not invent one.

6. **Show the exact write, from the backend, before anything is sent.**

   ```
   review_decision.preview_decision(config, object_type, record_id, decision, reason)
   ```

   The `would_write` map it returns is **the backend's own computed patch**, not a
   reconstruction made here. Show every key and value in it. On an approval it is a
   multi-key patch and includes a provenance blob that can run to kilobytes — summarise the
   blob as "the audit trail entry for this decision" rather than pasting it.

   Preview works whether or not a grant is open and whether or not the batch window from
   step 4 is armed. That is deliberate: the operator cannot approve what they cannot see.

   If the preview comes back with `available: false`, or with a non-writing outcome
   (`stale`, `no_candidate`, `not_flagged`, `refused`), report it now in the operator's
   terms — what happened, that **nothing was written**, and what to do next — and do not
   offer to submit. In particular:
   - `stale` — the record changed since the pipeline froze this candidate. Nothing written,
     still queued. Re-run enrichment or reject with a reason.
   - `no_candidate` — the record is in the queue but holds nothing to promote. Every
     record flagged as a possible duplicate is in this position: there is a reason to
     record, but nothing to approve. A contacts approve does not land here today, because
     no contact currently in the review queue holds a candidate — approving a contact is
     a real write: its enriched value was already saved to HubSpot at the moment the
     record was flagged, so approving promotes nothing new; it takes the record out of
     the queue and records who decided and when.
   - `not_flagged` — the record is not in the queue. Nothing to decide.

7. **Confirm this record's exact write, then submit it.**

   Read the exact write back to the operator and get an explicit yes for **this record**.
   **That yes is the arm.** An affirmative answering the exact write just shown — "yes",
   "go ahead", "do it", "please" — arms `review_armed=True` for that one submit and nothing
   else. There is no phrase to learn: an operator saying yes must never have to produce the
   system's wording to be heard (VOCAB-05). **This per-record ritual is unchanged by the
   grant** — what changed underneath it is only the authority, never the act.

   Disarmed is the default and the state of every new conversation, and it is the state
   again after every submit: consent here is per record, never per session, however many
   records have already been worked. An affirmative that answers nothing, answers some
   other question, or arrives before the exact write has been read back does **not** arm
   anything — read the write back and ask again. Anything ambiguous is not consent.

   **A yes here authorizes this record's write and nothing else.** It does not arm the
   contact-upload lane or the enrichment lane, and a yes given on either of those does not
   authorize a review write. Say so plainly if the operator seems to expect otherwise — the
   per-record consent stays lane-specific even though, since Phase 60, one grant now spans
   all three lanes: the grant is the authority, the yes is still the act.

   ```
   review_decision.submit_decision(config, object_type, record_id, decision, reason,
                                   reviewed_by, review_armed=True, grant=grant,
                                   run_id=run_id, preview=preview)
   ```

   **If it refuses with `reason: "grant_not_authorized"`, relay the message as given and
   offer to open a grant covering this record — the same offer step 4 makes at the start of
   a sitting, scoped to just this one record if that is all the operator wants right now.**
   That refusal replaces the old shell-environment-variable refusal this skill used to
   produce, which no longer exists: opening a grant is something the operator can do from
   this conversation, so route them there rather than to an administrator.

   **One true sentence about what a reject achieves with no grant open, said plainly and
   not softened (cross-AI review MEDIUM-3, D-60-07 amendment):** a reject is always
   *sent*, even with no grant open — that carve-out survives — but the deployed backend
   checks its own record allowlist before it looks at the decision word, so a reject on a
   record no open grant covers still comes back `not_allowlisted` and the record **stays
   flagged**. Do not promise the operator that rejecting always clears the queue entry.
   Relay whichever outcome came back, and if it is `not_allowlisted`, offer the same remedy
   an approve gets: open a grant covering the record.

8. **Report verified or failed — from the re-read, never from the response.**

   ```
   review_decision.verify_decision(preview["would_write"], response)
   ```

   The approved business fields are checked TWICE — once against what the backend reported
   writing, once against the independent post-write re-read — while a handful of properties
   the preview cannot pin (the review timestamp, the provenance blob's embedded timestamp,
   and the reviewed-by label) are checked against the backend's own report of what it wrote
   rather than against the preview's guess. That is why a successful approve now reports
   `verified` even though those few properties always differ between preview and submit.

   Report its `status` and `message`:

   - **`verified`** — the record was read back after the write and holds the approved
     values. This is the only wording that means the change landed.
   - **`failed`** — say plainly that the change is **not confirmed** and the operator should
     check the record in HubSpot. This covers a mismatch (the named fields are in the
     message), a record that could not be read back, and an empty or unreachable response.
     An empty response usually means this record is not on the backend's allowlist — a real
     "nothing was written", not a broken tool. Never soften a `failed` into "probably fine".
   - **`not_written`** — the endpoint's own non-writing outcome. Relay its message; nothing
     changed and the record is still queued.

   Then offer the next record — still inside the same batch window from step 4, until the
   operator is done with this sitting.

   **When the sitting ends, give the end-of-run account (D-60-08).** Read this run's own
   artifact through
   `written_records.load(path=written_records.written_records_path(run_id))` — never the
   path-less `written_records.load()`, which would fold in every previous run's writes too.

   Tell the operator which records this sitting actually wrote to HubSpot, from that
   file's own entries — not from what was asked for, and not from the response body of any
   one submit. **A decision whose bookkeeping failed still landed** — the write always wins
   over the log (D-59-10) — and is reported as such from the `written_records` key on that
   decision's own submit envelope (`True` on a clean append, or the exception's type name
   when the append itself failed); a bookkeeping failure never means the write did not
   happen, only that this file may be missing that one entry.

## What this skill never asks the operator to do

Run a command, edit a file, or paste a secret. If something cannot be done from this
conversation — a missing config key, or the admin's `allow_write_grants` settings key that
turns on grant-opening in the first place — name it, say who can do it, and stop there.
