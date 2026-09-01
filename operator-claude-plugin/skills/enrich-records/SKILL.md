---
name: enrich-records
description: Enrich companies or contacts that already exist in HubSpot, by record ID or by naming a HubSpot list. Use when the operator asks to enrich, research, or fill in data on records already in HubSpot — "enrich these companies", "run the waterfall on this list", "research these accounts" — or invoke it directly as /operator-claude-plugin:enrich-records.
---

# Enrich Records Already in HubSpot

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.


This skill turns "enrich these records" into a `hubspot/enrichment/event` request. It
structures nothing and uploads nothing: the records already exist in HubSpot, and the
provider waterfall, web research, judge escalation, merge policy and scoring all live in
n8n. This skill's whole job is: work out **which** records, **which** providers, **what
it will cost** and **how it will be split** — show all four — and then, only when
explicitly armed, send exactly that plan.

Per-record outcomes are relayed only from what the backend's own response body carries —
never inferred, never invented (step 9, and the F3 recorded edit there). A chunk the
transport accepted can still hold a gated row inside it, and where the body genuinely
says nothing per record, this lane reports at chunk granularity and says so.

## Steps

1. **State the target up front, before any other work.** Run:

   ```
   python3 scripts/config_gate.py
   ```

   If the JSON reports `"ok": false`, relay its `"error"` message to the operator exactly
   as given, then STOP. Never show, echo, or ask for a secret, and never surface a raw
   socket or parser error — the script has already translated it.

   If it reports `"ok": true`, tell the operator that this lane POSTs to
   **`hubspot/enrichment/event`** on the n8n instance named in `"target"` (same instance,
   different path from the contact-upload lane), and that dispatch is currently
   **disarmed** for this conversation. Say this even if the operator only asked a
   question, before doing anything else.

2. **Resolve which records.** Five forms, and only four of them are supported:

   - **Record IDs** — the operator pastes HubSpot record IDs. Spec:
     `{"record_ids": ["101","102"], "object_type": "companies"}` (or `"contacts"`).
   - **People, named the way you would name them** — "John Tsatsimas at Football NSW", or a
     name with an email address or a LinkedIn profile URL. Spec:
     `{"people": [{"firstname": "John", "lastname": "Tsatsimas", "company": "Football NSW"}]}`.
     **Prefer this over asking for a record id.** An operator does not carry HubSpot ids in
     their head, and the backend has resolved contacts by name since Phase 36 — asking for an
     id when a name was given is the client refusing what the backend already supports. Any ONE
     of: an email, a LinkedIn URL, or surname + company. Less than that is refused by name,
     saying which of the three would fix it.

     Say how the match is decided, because it governs what gets written: an exact identity
     (email or LinkedIn URL) enriches that record; a same-surname, same-company match with no
     exact identity is **held for the operator to confirm**, never written over — so a second
     John Tsatsimas is surfaced rather than silently overwritten. Say the cost of confirming
     it too: confirming a held match and sending it again re-runs the whole lookup for that
     person, and costs the same as this run did.

   - **Companies that may not be in HubSpot yet** — the operator names companies by name
     and website domain. Spec: `{"companies": [{"name": "Perth Racing", "domain":
     "perthracing.com.au"}]}`. A LinkedIn or Facebook page is **not** a domain — the client
     refuses one by name and asks for the company's own website, because searching HubSpot
     for `linkedin.com` matches nothing and would create a company whose domain IS the
     social network, after which every later LinkedIn-sourced company matches that one
     poisoned record. **Domain is mandatory** and the client refuses a company
     without one, by name: domain is what the backend searches HubSpot on, so a
     domainless company could only ever be created, never matched — the duplicate-company
     shape this form exists to avoid. Each company is matched on its domain first: an
     existing record is enriched in place and never duplicated; one with no match is
     created, and only if creation is armed on the backend. Say that distinction plainly
     before the preview — the operator is deciding whether new records may appear in
     their CRM, which no other form of this skill can do.

     **Confirm every proposed website in one table before any of this reaches the
     preview.** When a company arrives with no domain — a bare name, a screenshot, a
     LinkedIn or directory page — propose one from whatever you can already see;
     research it only when you cannot confidently propose one, or the operator says to
     check it. Render one table, one row per company, showing exactly three things:
     the company, the proposed website, and where that came from with a one-line
     reason — an evidence link only on a row something actually researched. Before the
     batch yes, three moves are open on any row: accept as shown, type the right
     website instead, or say this one is wrong. Say what happens to that last case in
     the operator's own terms: the company still goes through, looked up by its name
     instead, and the run's report says so — never dropped.

     State the profile-page rule where the operator meets it: a LinkedIn or directory
     page is read for who the company is, and that page's own address is never
     recorded as their website, because a company filed under a social site's address
     becomes the record every later company from that source is mistaken for.

     **An affirmative answering this shown table, in the same turn, covers the batch,
     and anything that is not clearly an answer to this table leaves the batch
     unsent.** Only once every row is decided — a yes, a correction, or a decline —
     does `company_domain.to_envelope_spec` turn the table into the spec this step's
     preview is built from; an undecided row stops the whole batch rather than
     defaulting either way.

     **Below that table, one more line: domain research.** `company_domain.needs_research`
     names every row you could not confidently propose a website for, plus any row the
     operator asked to have checked. Show how many companies that is, which ones, and
     what `cost_guard.research_line` says it would cost — a dollar figure when the rate
     is measured, or plainly that the cost is not measured when it is not; never a
     figure for zero rows, and never a "$0" standing in for either. Say, in your own
     words, that saying nothing about this line means it goes ahead as part of the same
     batch yes, and that they can strike it with one sentence instead. State what
     striking it costs them plainly: those companies are matched by name instead of by
     website, which is less certain. A struck line moves those rows onto the exact same
     name-only path a declined row already takes — `company_domain.decline_research`
     feeds them into `apply_domain_decisions` as declines, never a second path.
   - **A HubSpot list** — the operator names a saved list. Spec:
     `{"list": "<the list name>", "object_type": "contacts"}`. **Do not resolve or count
     the list yourself.** The backend resolves it with the one HubSpot credential that
     exists, and it refuses a list too large to finish inside one response rather than
     enriching an arbitrary part of it.
   - **A saved view** — **refused.** Say exactly:

     > "I can't resolve a HubSpot *view* — HubSpot doesn't expose views through its API.
     > Save that view as a **list** in HubSpot and give me the list name, or paste the
     > record IDs directly."

     Then stop and wait. Do not try the list endpoint with the view's name: a view name
     that happens to match an unrelated list name would enrich the wrong records with no
     error at all.

   If the object type is anything other than contacts or companies, ask — do not guess.

   **A contact is never created by this skill.** The backend holds any contact it cannot
   associate to a company (2026-08-25 ruling), so the order that works is companies first,
   contacts second: enrich or create the company, confirm it is searchable by its domain,
   then ingest the contacts that belong to it.

3. **Resolve the provider selection.** The admin default lives in
   `operator.local.json` as `enrichment_providers` and ships as the **full
   waterfall**, so saying nothing enables every provider. The operator can override it for
   this batch only: a list of provider names, `"all"`, or `"none"`. Nothing is written to
   the config file — an override applies to this batch and no other.

4. **Build the preview — one command, four blocks.**

   ```
   python3 scripts/preview_enrichment.py '<spec-json>' '<providers-json-or-omit>'
   ```

   This reads the operator config, plans the chunks, loads the dated rate table, reads
   remaining balances from `hubspot/backend-status`, and renders. It sends no enrichment
   request and changes nothing. Print the `"preview"."markdown"` block as a markdown table
   in chat by default; publish it as an Artifact only if the operator asks.

   Four things the operator must see before deciding, and the rendered block already
   carries all four — do not summarise them away:

   - **What is being enriched.** For record IDs, the exact count. For a list, the list
     name and the word **`unknown`** — the count is resolved by the backend, and no number
     is shown rather than a fabricated one. `unknown` there does not mean zero, does not
     mean empty, and does not mean there is nothing to do.
   - **Which providers.** Stated every time, whatever it resolved to, including the full
     waterfall and none.
   - **What it will cost.** Per provider in credits plus the Anthropic dollar figure, with
     the date the rates were measured and how old they are. The figures say **at most**:
     Lusha is priced at its first-time rate rather than its measured-zero re-enrich rate,
     so the estimate over-states on purpose.
   - **How it will be split.** The chunk count and the rows in each chunk — and dispatch
     sends exactly that plan.

   **On the balance line, say what the block says and no more.** A balance below the
   estimate is a warning naming that provider. A balance of exactly zero is the same
   warning — zero is a real balance. A balance that could not be read is **neither**: say
   headroom could not be *confirmed*, never that there is enough. If the status endpoint is
   unreachable every balance reads unknown and the preview still renders in full; report
   that as "I could not read any balance", not as "there is no cost".

   **Apollo's `unknown` is the normal answer, not a fault.** Apollo exposes per-endpoint
   rate limits rather than a depleting credit pool, so no per-match credit price exists for
   it and a better API key would not produce one. Do not present it as broken, and do not
   suggest anyone fix it.

5. **Ask for approval — unless a grant already carries it.** With no grant open: if the
   operator declines, STOP here. Nothing is sent. The only thing that has happened is one
   read of the status endpoint, which costs nothing.

   **Under an open grant covering this lane and these records, do not ask again.** The
   operator already approved this send when they opened the grant: the envelope's
   arithmetic and the consequence sentence were what they said yes to, and that yes was
   given *before* the run rather than during it (D-53-06, operator 2026-08-25). Asking
   "shall I proceed?" here would restore the very stop-and-ask the grant exists to remove —
   half the friction, none of the protection. Say which grant the send runs under, then go
   straight on. The preview above is still rendered and still shown; under a grant it
   informs rather than gates, because the gate moved earlier.

6. **Ask for this send, in the operator's own words.** Disarmed is the default and the
   state of every new conversation. Say plainly that sending is off, then ask for this send
   by naming what it will do — how many records, and that it writes them to HubSpot. **An
   affirmative answering that question — "yes", "go ahead", "do it", "please" — arms this
   send and nothing else.** There is no phrase to learn: an operator saying yes must never
   have to produce the system's wording to be heard (VOCAB-05).

   **Consent counts only where it is attached to what was shown.** An affirmative that
   answers nothing, or answers some other question, or arrives before this send has been
   described, does **not** arm anything — ask once more, naming what will happen, and take
   that answer. Anything ambiguous is not consent: treat it as not armed, and ask. This
   state is never written to disk — it exists only as the `armed` argument passed to the
   dispatch call below, for this send only. Arming this send arms nothing else: not the
   next send on this lane, not the contact-upload lane, not the review lane.

   **If a write grant covering this lane and these records is already open, do not ask at
   all.** Say which grant the send is running under and dispatch under it —
   not asking twice is the whole point of a grant. With no grant open, everything above is
   exactly as it is today.

   **A grant removes the question, not the safety.** The preview still runs and is still
   shown, the records are still named, each send still arms and disarms its own window
   bounded to that send's records, and a failed disarm is still reported loudly as its own
   state. Revoking a grant **refuses the next send** — it **does not stop a dispatch already
   running**, so a revoke arriving mid-dispatch still lets every remaining chunk of that
   send go out.

   Whichever consent applies — a standing grant, or this send's own yes — step 8's dispatch
   opens the same kind of record-scoped armed window; see there for the code (F2,
   2026-08-25: the yes now arms a window for this send, where it used to arm the client's
   own POST only, and nothing on the backend).

7. **Before planning a grant or authorizing a send, resolve a record set that would
   otherwise be empty (D-59-08, 2026-08-28).** This is FINDING 1 of
   `53-WALK-RECORD.md`: a `people` form naming someone the operator believes exists in
   HubSpot, or a `companies` create, can name a record with **neither a HubSpot object
   id nor a usable domain** — the exact handle `plan_grant`/`write_grant.py` needs to
   scope a grant to. `plan_grant` still hard-refuses that empty record set; its own
   refusal now names what would resolve it. **The resolution happens here, in this
   skill, before `plan_grant` or `authorize_ungranted_send` is ever called** —
   `write_grant.py` gains no lookup, no HubSpot call, and no resolution logic of its
   own; giving the authorization boundary a lookup that can change what it grants is
   exactly the widening this phase leaves untouched.

   - **Recognise the case.** The record the operator named has no id and no domain to
     scope a grant to — `plan_grant`'s refusal (or the ungranted per-send path's
     identical one) says so by name.
   - **Attempt resolution from the legitimate sources ONLY**, named by the same
     identifiers `extraction.RESOLUTION_SOURCES`/`resolution_sources.RESOLUTION_SOURCES`
     use: a read-only HubSpot search (`hubspot_lookup`) for the company the record
     belongs to, the operator's own earlier statements in this conversation
     (`operator_statement`), a provider result already in hand from this run
     (`provider_result`), or a stated derivation from another field of the same row
     (`same_row_derivation`) — e.g. a company name from a profile-page slug already on
     the row.
   - **What is still forbidden, said explicitly to the operator when this step
     applies:** Claude's own recall about the company, an inferred domain from a
     company name, a plausible corporate email pattern, and anything the operator has
     no way to check. This step changes refusing into **proposing** — never into
     guessing.
   - **PROPOSE the resolved handle and the scope it produces, naming which source it
     came from, and wait for the operator to confirm.** Reuse the same confirm/
     correct/decline vocabulary step 2's company-domain table already established —
     accept as shown, correct it, or decline it — rather than inventing a third set of
     words for the same interaction. **A declined proposal leaves the original refusal
     standing** — no grant is planned, nothing is armed.
   - **Only once confirmed**, call `plan_grant` (or `authorize_ungranted_send`) with the
     confirmed handle. The resulting grant is **narrower than or equal to** what the
     operator named — never wider; this is the same per-send narrowing rule step 8
     (dispatch) already applies, unchanged by this step.

   **When `plan_grant` refuses because the batch would exceed the sampled monthly
   execution allowance (`ceiling["verdict"] == write_grant.CEILING_OVER`), the refusal
   carries a `split_offer` (D-57-04, RUN-05's "offers a smaller batch") — present it
   rather than only the bare shortfall.** `split_offer["affordable_spec"]` being
   present means a smaller batch fits now; relay `record_ceiling_per_run` (how many
   records this run could carry) against the total, and that the rest — the same
   count as `split_offer["remainder_spec"]`'s own records — would be **queued for a
   future run the operator will separately authorise, never a schedule that runs
   itself**: each subsequent run opens its OWN grant (GRANT-06), so accepting the
   smaller batch now is not standing permission to spend later. When
   `split_offer["affordable_spec"]` is `None`, relay `split_offer["reason"]` instead —
   no split can be offered (an unsampleable allowance, or a remainder too small for
   even one record), and the operator's only path is to name a smaller batch by hand
   or override.

   **The state transition an ACCEPTED offer follows, in order — never out of order**
   (REVIEW-57-H5: `plan_grant` itself writes nothing durable on a refusal the operator
   has not acted on):

   1. `plan_grant()`'s refusal carries the pure `split_offer`. Nothing is written yet.
   2. The operator accepts the affordable subset (or names a different one, or
      declines outright — a decline leaves no file, exactly like any other refusal).
   3. Call `plan_grant`/`open_grant` again over `split_offer["affordable"]` (the
      resolved scope) and `split_offer["affordable_spec"]` (the plan to dispatch) — a
      FRESH grant, unchanged by D-57-04: this is the same open-a-grant step this skill
      already runs, just over the smaller batch.
   4. **Only once that fresh grant is open**, persist the remainder so it survives past
      this conversation:

      ```python
      import remainder_queue

      entry = remainder_queue.build_entry(
          split_offer["remainder_spec"], remainder_queue.REASON_ALLOWANCE_SPLIT)
      remainder_queue.save(run_id, [entry])
      ```

      A `RemainderQueueError` or a falsey `save()` here must not stop the run that just
      got its fresh grant — report the save failure alongside everything else, the
      same never-raise guard step 8's ceiling-stop path already follows.
   5. A declined offer never reaches step 3 or 4 — nothing is queued for work the
      operator never agreed to.

8. **Dispatch the plan the operator approved — under an open grant, or otherwise only
   after they have said yes to this send.** `scripts/chunking.py` is a library here (the same way `scripts/report.py`
   already is, not a CLI): rebuild the plan from the same spec and the same configured
   ceiling — it is deterministic, so it is the same plan that was previewed — and send it.

   **Every send opens its own record-scoped armed window — never a bare dispatch with the
   backend still disarmed.** Under a grant, `write_grant.authorize_send` builds the
   decision from it. With no grant open, this send's own yes is what authorizes it:
   `write_grant.authorize_ungranted_send` builds a single-use grant scoped to exactly this
   send's records — using the SAME `allow_write_grants` authority and the SAME Guardrail A
   dirty-backend refusal a standing grant gets — and discards it once this dispatch
   finishes; it is never remembered as a standing grant, never written to disk. Both
   functions return the identical `{armed, workflow_id, grant, refusal, detail}` shape, so
   the dispatch is the same call either way:

   `send_ids`/`send_domains`/`allow_create`/`object_type`/`providers_override` below are
   whatever step 2/3 already resolved for this send — bound to real names here, not left
   as angle-bracket placeholders, because this block is executable Python and an AST test
   (`test_write_grant.py`) `compile()`s it (REVIEW-57-M4):

   ```python
   import chunking, config_gate, enrichment, n8n_arming, run_report, run_state, write_grant

   run_id = run_state.new_run_id()  # minted before any HTTP call (REVIEW-C14) — the SAME
   # id this run's written-records file, audit record, and end-of-run report (step 10)
   # are all keyed by.

   cfg = config_gate.load_config()
   providers = enrichment.resolve_providers(providers_override, cfg)
   plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg))
   # D-60-02 (Phase 60, 2026-09-01): the grant behind this call, if opened via
   # write_grant.plan_grant(config, lanes=["enrichment", "contacts", "review"], ...),
   # covers all three lanes together — so a record enriched under this grant can also be
   # triaged in review-triage's SKILL.md in the same sitting, with no second deliberate
   # yes, bounded as always to the grant's own records.
   decision = (
       write_grant.authorize_send(
           grant, lane="enrichment",
           record_ids=send_ids, record_domains=send_domains)
       if grant is not None else
       write_grant.authorize_ungranted_send(
           cfg, lane="enrichment", object_type=object_type,
           record_ids=send_ids, record_domains=send_domains,
           allow_create=allow_create, label="this send")
   )
   if not decision["armed"]:
       # revoked, closed, outside the grant, the admin has not enabled write grants, or
       # the backend is not in a known-disarmed state — STOP and report decision["detail"]
       ...

   # Phase 57 / D-57-01 / RUN-05: bound this dispatch to the grant's own sampled ceiling,
   # never left unbounded. `ok` — the sampled monthly remainder; `unknown` — the monthly
   # allowance could not be sampled, so this run is self-bound to its OWN quote of N
   # executions instead of running unchecked (REVIEW-57-H6); `over` is reached here only
   # when the operator OVERRIDDEN the preflight refusal (an override never travels — it
   # comes only from the operator's own answer in this conversation, never from stored
   # state or a config value), and is bounded by that same self-quote so the override
   # cannot silently become "spend without limit".
   ceiling = decision["grant"]["ceiling"]
   if ceiling["verdict"] == write_grant.CEILING_OK:
       execution_ceiling = ceiling["remaining_sampled"]
   elif ceiling["verdict"] == write_grant.CEILING_UNKNOWN:
       execution_ceiling = ceiling["projected_executions"]
   else:
       execution_ceiling = ceiling["projected_executions"]

   # 57-05 Task 1: record the ceiling verdict and this grant's balance readability the
   # MOMENT they are observed — before dispatch, not at the end — so a run that dies
   # mid-dispatch still leaves this on disk for the end-of-run report to reconstruct
   # from (crash-recovery is the entire reason this record exists). `record_audit`
   # raises only on a grant-shaped value, which nothing here supplies; it is still
   # wrapped so a bookkeeping defect can never halt a live dispatch (D-59-10's same
   # posture).
   balances_at_grant = decision["grant"].get("envelope", {}).get("verdicts")
   try:
       run_report.record_audit(run_id, ceiling=ceiling, balances=balances_at_grant)
   except run_report.RunReportError:
       pass

   # Grant closure on every exit (REVIEW-57-H8/M5): `outcome`/`disarm` start None so an
   # exception raised BEFORE `dispatch_plan()` returns — inside `enrichment.build_envelope`
   # or the transport itself — cannot leave either name unbound when the closure below
   # runs. A crash closes with the pre-existing `unhandled_error` reason and re-raises; a
   # normal return (including a ceiling stop, which is not an exception) closes through the
   # same adapter with no override, deriving `ceiling_breach` only when `outcome.
   # ceiling_stop` is actually present.
   outcome = None
   disarm = None
   crashed = False
   try:
       with n8n_arming.armed_window(decision["workflow_id"], send_ids, send_domains,
                                    allow_create, cfg, grant=decision["grant"]) as window:
           outcome = chunking.dispatch_plan(plan, providers, True, cfg, run_id=run_id,
                                            execution_ceiling=execution_ceiling)
       disarm = window.disarm_result
   except Exception:
       crashed = True
       raise
   finally:
       close_reason = write_grant.CLOSED_UNHANDLED_ERROR if crashed else None
       grant = write_grant.record_dispatch_outcome(
           decision["grant"], outcome, cfg, disarm=disarm, reason=close_reason)
       # 57-05 Task 1: the disarm result and any ceiling-stop metadata, observed at the
       # END of the run — the second of this run's two audit observations, merged into
       # the same record rather than replacing the first (REVIEW-57-M11).
       import dataclasses
       stop = outcome.ceiling_stop if outcome is not None else None
       try:
           run_report.record_audit(
               run_id, disarm=disarm,
               ceiling_stop=(dataclasses.asdict(stop) if stop is not None else None))
       except run_report.RunReportError:
           pass
   ```

   The allowlist handed to `armed_window` is **this send's records, never the grant's whole
   record set**. That narrowing is what keeps every window strictly smaller than the grant
   it runs under; a skill that passed the grant's full list would widen every window to the
   whole batch and every test would still pass.

   Chunks go one at a time, in plan order. A chunk that fails is skipped and the rest
   continue — one bad chunk does not abandon the batch. The consent itself has no default:
   if the operator has not said yes to this send and no grant is open, pass nothing and do
   not call this at all.

   **When `outcome.ceiling_stop` is present, this is a budget stop, not a chunk
   failure** (D-57-01) — it never appears in `outcome.failed_batch` and every attempted
   chunk's `ok` is still True. Tell the operator four things: spending stopped BEFORE the
   named chunk was sent, the run completed rather than aborting, the unsent rows
   (`outcome.ceiling_stop.remainder`) are named individually and are not lost, and the
   grant is now closed for `ceiling_breach` — `grant["state"]` is `write_grant.CLOSED`
   after the `finally` above runs — so a further send needs a fresh grant.

9. **Report what was sent, and relay what the backend actually said about it.** From
   `outcome.results`, say how many chunks the backend accepted and how many rows were in
   them. For any chunk that failed, give its short reason as recorded — a non-2xx, an
   unreachable webhook, or a response that could not be read. A timeout counts as a
   failure here even though the backend may still be working; say so rather than implying
   the records were rejected.

   **When a failed chunk's `resolvable` tuple is non-empty (D-59-08, gap closure
   2026-08-29), offer the resolution instead of reporting a dead end.** This is the
   same identity gate GATE-01 already relays through the ingest preview — GATE-02
   through GATE-05 refuse a `people`/`companies` chunk the same way, and their
   `resolvable` payload now survives the trip through `dispatch_plan` rather than being
   replaced by a placeholder. For each entry, relay its `detail` as a proposal of what
   would resolve that row, and name every `resolution_sources` value its `sources`
   tuple carries — an entry can claim more than one of the four
   (`hubspot_lookup`, `operator_statement`, `provider_result`, `same_row_derivation`),
   and every value it claims belongs in the relay, not just the first. **Claude
   proposes and the operator confirms — a resolvable entry is never
   silently acted on, and no value is invented to satisfy the gate.** D-59-08's own line
   applies here exactly as it does at every other gate this phase converted: the change
   is refuse-to-propose, never refuse-to-guess.

   **When `outcome.written_records_failures` is non-empty (D-59-10, gap closure
   2026-08-29), say so plainly and lead with it.** The post-run written-records list
   for this run is **INCOMPLETE** — name which chunk indices are missing from it — and
   say that the records those chunks wrote are **not** in the artifact even though the
   writes may have landed: a bookkeeping miss is not a dispatch failure, so the chunk's
   own send may well have succeeded. The list must never be read, by the operator or by
   Claude, as a complete account of what was written when this field is non-empty —
   that is the exact failure D-59-10 exists to prevent (aborting the dispatch over a
   bookkeeping failure was considered and rejected, so this loud disclosure is what was
   chosen instead).

   **For every response in `outcome.responses`, read what it actually says before calling
   that chunk sent.** Import `scripts/report_enrichment.py` (a library here, the same way
   `scripts/report.py` already is, not a CLI) and call `build_sync_report(response)` on
   each one. It returns `(rows, reason)`: one row per record the body itself decided on,
   each carrying `outcome` — one of `written_records`'s eight words (D-57-03/57-02):
   `written`, `write_attempted`, `created_id_unknown`, `written_id_unknown`, `gated`,
   `held`, `failed`, `no_action` — `reason` (present for `gated`/`held`/`failed`), and
   `match_level`/`match_reason` (how the record was found — high / medium / none /
   unknown, and why). Relay every one of them by name: a chunk the transport accepted
   can still carry a `gated`, `held`, or `failed` row inside it, and "the backend
   accepted 1 chunk, 1 row" must never stand in for that when the row itself says
   otherwise.

   **`gated` is AFTER-03's case (57-05): the row would have been written and is
   RECOVERABLE, never a failure.** Say plainly that opening a grant and re-sending it
   writes it — never describe it as a dead end, and never let its wording read like a
   `written` row's.

   RECORDED EDIT (F3, 2026-08-25) — never invent what the body does not carry; always
   relay what it does. This step used to carry a blanket rule against stating any
   per-record outcome at all, written to stop the client INVENTING an outcome the
   synchronous body never carried. A live walk hit the old rule read too broadly: a body
   reading `action: "write_blocked"`, `match.reason: "searched, no hit"` was received and
   reported as "no failures, nothing to re-send" anyway. The property was never "withhold
   per-record detail" — it is "never guess beyond what the body says". When
   `build_sync_report` returns a `reason` instead of rows (the body was not shaped like a
   decision response at all — the `{status_code, text}` fallback, or an empty or malformed
   body), say plainly that this lane reports at chunk granularity for that chunk and point
   the operator at the record in HubSpot — that is the one case where a real gap in the
   body limits what can be said, not a habit of withholding what it does carry.

   If `outcome.failed_batch` is present, say that the failed records have been collected as
   **a batch that can be re-sent** — one well-formed enrichment request, not a list of
   errors — and that re-sending it goes through this same arming gate, because a re-send is
   a send. Name it as the thing to hand to a retry.

10. **Read the end-of-run report — this is what the operator reads INSTEAD of watching the
   run (AFTER-01, 57-05).** Step 9 relays what happened DURING the run — this step is the
   after. One call joins every durable store this run touched into one block: per-record
   outcome, association outcome, held rows named individually with reasons, spend against
   the ceiling, and the disarm verdict.

   ```python
   import run_report

   report = run_report.build_run_report(
       run_id, cfg, outcomes=[outcome], disarm=disarm,
       balances=balances_at_grant, ceiling=ceiling)
   ```

   Render `report["block"]` to the operator verbatim — it already carries the
   `REPORT INCOMPLETE` banner when any store could not be read cleanly, and it already
   states which provider balances were readable and which were not, and which part of
   the spend was therefore actually bounded (D-57-02): a ceiling cannot guard what it
   cannot read.

   **A `gated` row on this surface must never read as a completed one (AFTER-03).** It
   says the row would have been written and is recoverable by opening a grant and
   re-sending it — never a failure, and never worded like a `written` row.

   `contact-upload/SKILL.md`'s own step 7 report is a single-shot upload the operator
   watches in real time; it is deliberately NOT a call site for this report (REVIEW-57-L5)
   — AFTER-01 exists for the run nobody is watching, and that lane keeps its existing
   report unchanged.
