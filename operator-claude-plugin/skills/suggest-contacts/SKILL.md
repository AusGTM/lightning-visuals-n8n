---
name: suggest-contacts
description: After a batch of companies has been ingested or enriched, offer to find and propose people at the companies that have nobody named at them — this skill is auto-offered by the assistant right after such a batch finishes, not only invoked on request, and it is also directly invocable. Use when a company batch just completed, when the operator asks to find contacts, suggest people, or fill in who works at a company, or says something like "who's at these companies" — or invoke it directly as /operator-claude-plugin:suggest-contacts.
---

# Suggest the Contacts Nobody Named

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory`.

This skill is different in kind from every other skill in this plugin: it is **raised by
the assistant itself**, right after a company batch finishes, rather than waiting to be
asked (D-62-15, SUGGEST-01). It is also directly invocable — the operator can start a
round on their own, at any point, over the batch just processed.

The sitting reaches a company's own people page through the sitemap ladder already built
for `contact-upload`'s URL adapter, filters what it finds to the roles the operator picked
once for the whole batch, enriches the people it named through the same waterfall every
other lane uses, and lands them as proposals through the same match, held-row and
association gates a spreadsheet upload goes through. Nothing here is a second
implementation of any of that — it composes what plans 62-01 through 62-04 already built
and what `enrich-before-ingest/SKILL.md` already calls.

## Steps

1. **What this will and will not do, and how many times it asks.** Run:

   ```
   python3 scripts/config_gate.py
   ```

   If the JSON reports `"ok": false`, relay its `"error"` message to the operator exactly
   as given, then STOP. Never show, echo, or ask for a secret.

   Then say plainly, before anything else:

   - Nobody is created without going through the same match, held-row and association
     gates a spreadsheet upload already goes through (SUGGEST-04) — this round proposes,
     it never writes directly.
   - No person is confirmed one at a time, and no company is confirmed one at a time
     either (D-62-10). The operator's only two decisions this round are the roles and the
     cap, both chosen once for the whole batch.
   - The round is covered by the session grant already open — it asks for nothing extra
     (D-62-11, SUGGEST-05). Name the lanes **individually**, never as a collective
     phrase: on the **enrichment** lane, this round spends provider credit finding contact
     details for the people stage 1 names; on the **contacts** lane, it writes proposals
     into the ingest lane exactly like a spreadsheet upload would.

2. **The company set.** The batch just processed, and nothing else (D-62-04) — never
   every company in the portal with no contacts, and never an operator-supplied list.
   Call `suggest_contacts.eligibility(company_rows)` on that batch's own response rows
   and render the tri-state result: **eligible** (zero associated contacts, this round
   will try it), **has contacts** (already has someone, skipped), and **unknown** (the
   count could not be read). An `unknown` company is reported as unknown and offered as
   an operator choice — try it anyway, or leave it out — never silently included and
   never silently dropped.

3. **Roles and the cap, chosen once for the whole batch.** Render
   `role_classify.offer_block(role_classify.load_families())`. When the vocabulary is
   un-evidenced (the portal was too sparse to derive one), that block's own disclosure
   sentence is shown exactly as it renders — never trimmed, never softened (D-62-07).

   Ask once for the role selection — `role_classify.chosen_families(vocabulary, labels)`
   validates it against the vocabulary's own labels — and once for the per-company cap,
   default 2 (D-62-12). Both are **round-level**: the same role list and the same cap
   apply to every eligible company in this batch. Never re-ask either one per company.

   **A cap above the grant's priced cap is refused, in code, not just here in prose.**
   The chosen cap is passed through `suggest_contacts.agreed_cap(chosen_cap, figures)` —
   whatever it returns is the ONLY number the rest of this round spends against. It reads
   the open grant's own `figures["suggestion_allowance"]["priced_cap"]` (3 — the top of
   D-62-12's 2-to-3 band, what the grant was actually priced against at the moment it
   opened) and raises `suggest_contacts.CapRefused` naming both numbers — "the grant
   priced this round at a cap of 3; a cap of 5 was not what was agreed to" — when the
   chosen cap exceeds it, or when the grant never priced a suggestion allowance at all.
   Relay a `CapRefused` to the operator exactly as it reads (the same "relay the error
   verbatim" discipline step 1 already uses for `config_gate.py`), and stop the round.
   The round may spend LESS than the priced cap; it may never spend more.

4. **The price, before the spend.** Show the suggestion allowance already sitting in the
   open grant's envelope — `figures["suggestion_allowance"]["line"]` — naming both
   components in the one sentence it already renders: stage-1 page fetches and stage-2
   provider credits. State plainly that this is a worst-case ceiling and that actuals land
   at or under it, never over (D-62-14, SUGGEST-05).

   **If no grant is open**, follow `enrich-before-ingest/SKILL.md` step 5's two-phase ask
   verbatim: disarmed is the default, say so plainly, then ask for this round by naming
   what it will do. An affirmative answering that question — "yes", "go ahead", "do it" —
   arms this run and nothing else; anything ambiguous is not consent.

5. **Stage 1 — read the company's own pages.** For each eligible company in turn: the
   operator supplies or approves the starting page URL, and
   `suggest_contacts.discovery_plan(company_row)` builds the ladder — the same sitemap
   escalation `url_fallback.py` already builds for `contact-upload`'s URL adapter, called
   as a library and never rebuilt (D-62-01). Fetch with the native `web_fetch` tool and
   nothing else — the same INGEST-05 contract `contact-upload/SKILL.md`'s own URL adapter
   already follows: candidates are fetched only in the order the ladder shows, only after
   the operator has approved them, stopping at the first one that yields people.

   Thread the fetch budget per company through `suggest_contacts.company_budget(attempts)`
   and `suggest_contacts.next_candidates(company_row, attempts, sitemap_urls)` — the
   budget resets for the next company, it is never carried over from the last one.

   When nothing is found, report `suggest_contacts.no_candidates(company_row, pasted_url,
   attempts)`'s reason **verbatim** — it is `url_fallback.give_up_message`'s own text, and
   this skill adds no explanation of its own for why a page was empty — then move to the
   next company (D-62-03).

   **Do not escalate past a TOOL-LEVEL REFUSAL.** When a fetch comes back as an error
   code, or the page's content is itself an access-denied or error notice, that is a
   fence and it stays a fence — no search engine, no other host, no second attempt at the
   same content somewhere else. Escalating past a refusal turns a fence into a
   suggestion.

   A crawl that **completed and simply found nobody**, or that **ran out of its own fetch
   budget**, is a different ending: that is absence of information, not a fence, and the
   search fallback below may fire for it (D-5sd-04, D-5sd-06). The two are told apart by
   a recorded disposition, never by re-reading the prose `outcome`.

   **The disposition transcription contract.** Record a `disposition` on each `attempts`
   entry, alongside the existing free-prose `outcome` (which is unchanged and still
   rendered verbatim):

   | What `web_fetch` did | `disposition` |
   | --- | --- |
   | Returned an error code rather than page content | `refused` |
   | Fetched, but the page's content is an access-denied, blocked, or error notice | `refused` |
   | Fetched fine, and the page had no people on it | `empty` |

   An error code is recorded as `refused` **without naming a cause**. `web_fetch` cannot
   report `robots.txt` distinctly from a site declining or an admin's domain filter, and
   `contact-upload/extraction.md`'s own contract forbids claiming one — say the fetch was
   refused, never why. A missing or unrecognised disposition means the fallback will not
   fire at all (it is fail-closed), so the round simply reports and moves on.

   **Cap exhaustion needs its own entry.** When `next_candidates` refuses the remaining
   candidates for budget, append ONE final `attempts` entry carrying `disposition:
   "cap_exhausted"`. Cap exhaustion is a property of the ladder, not of any one URL —
   every per-URL entry is honestly `empty` — so without this entry the signal has no
   source and the fallback never fires in exactly the case D-5sd-06 opened it for.

   **The fallback, when it is eligible.** Run your own web search for the company's
   people, write the results to a scratch file of your own choosing (the same idiom
   `contact-upload/extraction.md` already uses for `url_fallback.py --filter`), then:

   ```
   python3 scripts/search_fallback.py --eligible <attempts.json>
   python3 scripts/search_fallback.py --rank <results.json> --company-url <the ladder's pasted URL>
   ```

   Run `--rank` only when `--eligible` reported `"eligible": true`. Then `web_fetch`
   **only** the URLs in `accepted[]`, in rank order, and nothing else. Each accepted
   entry carries its own rank: **1** the company's own host, **2** LinkedIn, **3** a
   named industry body or trade outlet. Call that value `source_rank` below. The whole fallback
   for one company is bounded by `MAX_FALLBACK_SEARCHES` — at most that many searches and
   at most that many accepted URLs.

   - **A search snippet is never a source for a row field.** The ranker reads the URL host
     and nothing else; a person comes from the fetched page, never from search result text
     or a title. If a URL was mis-transcribed it simply fails to fetch or yields nobody.
   - **A rejected host contributes nothing at all** — not a lower rank, not a caveat, not
     a mention in the report as a person (D-5sd-02, rank 4).
   - **A rank-3 result is collected, ranked and shown, but can never be sent** (D-5sd-05).
     Pass the accepted entry's rank through to `synthesise_rows`'s fifth argument (`source_rank` in the block
     below) so step 8's gate can see it.
   - The search itself spends no provider credit and no separately-billed tokens, so it is
     outside the priced ceiling shown at step 4 (D-5sd-03). The Lusha credit that a
     promoted person triggers at stage 2 is **not** free and stays inside it.

   The ladder is bound to the host built from the company's own recorded website — a
   scheme is added when the record has none, but `www.`, case, path and query are kept
   exactly as recorded, never rewritten (G-62-1). A company whose recorded value cannot
   be its own site (a social/profile link, or a value with no dot in it) yields no
   candidates at all, with a reason naming that value — never a guessed URL. Apex and
   `www.` on that same host are treated as one host (operator ruling 2026-09-03, G-62-2):
   a site that serves its sitemap from the other of the two is followed normally. A
   refusal still naming two genuinely different hosts is a different site, and is
   reported as such — never as "no people page".

   **Redirects.** `web_fetch` hands a cross-host redirect back to you rather than
   following it, so a redirect target is offered back through `next_candidates` like any
   other candidate: an apex/`www` redirect on the same host passes and may be fetched;
   any other redirect target is refused and reported, never chased somewhere else
   (D-62-03); and each accepted redirect fetch spends one of that company's five.

6. **Filter, then synthesise.** `suggest_contacts.select_people(people, family_list,
   chosen_families, known_contacts)` drops a person already associated with that company
   before the role filter even runs, and applies the chosen roles to whoever is left
   (D-62-18) — a person the round already knows about at that company is never spent on.
   `suggest_contacts.synthesise_rows(company, selected, fetched_url, per_company_cap)`
   then emits at most `per_company_cap` rows, each carrying the URL actually fetched as
   its provenance locator — never the company's homepage, and never the page the
   operator originally pasted if the ladder had to escalate past it.

   Each company's synthesised records are **accumulated** into the round's own list, not
   dispatched one company at a time — the round dispatches once, for the whole batch,
   only after every eligible company has gone through steps 5-6 (G-62-4).

7. **Stage 2 — enrich the people stage 1 named.** No confirmation between the stages
   (D-62-02) — the round moves straight from named people to enriching their contact
   details.

   **The mint, first.** After every eligible company's stage 1 has finished and before
   the first stage-2 call, `suggest_contacts.mint_row_ids(records)` gives the WHOLE batch
   its join keys in one call, by calling `preingest.build_rows_spec` once. This cannot
   happen per company: `build_rows_spec` mints `row-1`, `row-2`, ... by position over the
   list it is given, and refuses a row that already carries one — a per-company call
   would mint `row-1` at every company and join two different people onto one id with no
   error. `mint_row_ids`'s returned `spec` is the exact chunking spec the round's chunk
   plan is built from.

   Stage 2 itself uses the SAME machinery `enrich-before-ingest/SKILL.md` step 5 already
   calls for its own enrich pass — `enrichment.resolve_providers`,
   `chunking.dispatch_plan(..., async_ack=True, execution_ceiling=...)`,
   `watch.recover_async_dispatch`, `preingest.merge_enriched` — and builds no second
   dispatch path; that reuse is load-bearing, not incidental, since this skill hands that
   block a plan rather than re-documenting its grant/arming/ceiling machinery. The
   stage-1 rows (firstname, lastname, company, jobtitle, no email) are exactly what the
   waterfall needs to resolve a person by identity group 2.

   **The re-join, after.** `preingest.merge_enriched` returns FRESH rows and never
   mutates the ones it was given, so `suggest_contacts.rejoin_enriched(records,
   merge_report.rows)` gives each record its own merged row back — joined on `row_id`,
   never on position — before anything is partitioned. Without it, a row the waterfall
   just filled with an email would be reported to the operator as held, because the
   round's own records would still be pointing at their pre-merge rows.

8. **Land as proposals.** `suggest_contacts.partition_for_dispatch(rows, company_domains)`
   splits the sendable rows from the held ones. A row still missing an email after
   stage 2 is held exactly like a CSV row (`extraction.hold_emailless`, unchanged) —
   but a row that DOES have an email is no longer automatically sendable: **the
   enriched email's domain must be on the company's own domain, or a subdomain of it,
   or the row is held too** (operator ruling, 2026-09-04: "the email domain should be
   related to the company"). A personal-mailbox address (Gmail, Hotmail, an AU
   consumer ISP...) is held as well, but labelled distinctly from a stranger's domain,
   so the held pile reads as "strangers" vs "people with Gmail" at a glance. Both holds
   say why in words: `email domain thehartford.com does not match
   romaturfclub.com.au`, never a bare flag.

   This is a deliberate precision-for-recall trade, taken with the cost measured and
   in view before the ruling: the case that prompted it was Roma Turf Club's committee
   page naming Craig Smith, Vice President, while the waterfall's own resolution
   returned `craig.smith@thehartford.com` — a US insurer, a different Craig Smith
   entirely. Applied back to that sitting's own six rows, the rule holds BOTH of the
   two rows that had emails, yielding zero sendable rows instead of two. Do not soften
   the rule to recover yield; the operator accepted this cost, in view, on purpose.

   `company_domains` maps each round company's NAME to its recorded `website`/`domain`
   — build it from the same `eligible_companies` this round already collected. A
   company absent from the map, or whose recorded value is not a usable domain (a
   LinkedIn URL, for example), holds every one of its rows with
   `reason_code: "company_domain_unknown"` rather than being measured against nothing.
   The scope is this round only: `extraction.hold_emailless` itself is untouched, so
   `contact-upload` and `enrich-before-ingest` — where the operator supplied the email
   themselves — are unaffected.

   `extraction.validate()` runs **once per sendable row**, after stage 2 has merged its
   fields on — never before, and never twice for the same row. This ordering is correct
   and unchanged: `validate()` never minted `row_id`
   and never will — the mint is `build_rows_spec`'s, done once at the batch level in step
   7, before stage 2 runs — so by the time `validate()` sees a row, its identity/
   provenance check is exactly what it should be: a check on the row as it finally
   stands, not a decision point. `row_id` is a plugin-internal join key, not a canonical
   prop, so `validate()` reports it among each record's `dropped_keys` and still accepts
   the record; `extraction.strip_row_id` is the boundary strip before a dispatch CSV,
   exactly where `enrich-before-ingest/SKILL.md` step 7 already places it. The held half
   is handled exactly as `enrich-before-ingest/SKILL.md`'s own held-row path:
   `confidence.assess()`, then `held_queue.build_entry()`, then `run_manifest.save()`.

   Send the round's per-field source map with the final dispatch — `dispatch.dispatch(...,
   source_by_field=...)` — so the written contacts carry mixed provenance: `claude_web`
   for the name and job-title fields stage 1 named, and the provider's own name for the
   email and phone fields stage 2 filled in (plan 62-04, D-62-17). As with step 1: no
   per-person confirmation and no per-company confirmation happen here either — a row
   either clears the gates a spreadsheet upload clears, or it is held, named individually,
   for the operator to see in the report.

   The whole documented sequence, in one pass, over the batch:

   ```python
   import chunking
   import extraction
   import role_classify
   import search_fallback
   import suggest_contacts

   verdicts = suggest_contacts.eligibility(company_rows)
   # Round-level (D-62-12, SUGGEST-02): the vocabulary and the cap are resolved ONCE,
   # before the per-company loop -- never re-asked per company.
   vocabulary = role_classify.load_families()
   per_company_cap = suggest_contacts.agreed_cap(chosen_cap, figures)

   records = []
   for eligible_company in eligible_companies:
       plan = suggest_contacts.discovery_plan(eligible_company)
       # The operator approves candidates from `plan`, in the order shown, stopping at
       # the first that yields people (the INGEST-05 contract, inherited unchanged).
       # `people` below is whatever that approved fetch actually returned, and
       # `attempts` is this company's own record, each entry carrying a `disposition`
       # per step 5's table.
       verdict = search_fallback.eligible_after_ladder(attempts)
       if not people and verdict["eligible"]:
           # Absence of information, not a fence (D-5sd-04, D-5sd-06). `results` is what
           # your own web search returned, written to a scratch file and read back; the
           # ranker reads the URL host ONLY, so a snippet is never a source for a field.
           ranked = search_fallback.rank_results(results, plan["pasted_url"])
           # web_fetch ONLY ranked["accepted"], in rank order. `people`, `fetched_url`
           # and `source_rank` below then come from the page actually fetched -- a
           # rank-3 accept still yields people, and step 8's gate is what holds them.
       selection = suggest_contacts.select_people(
           people, vocabulary["families"], chosen_families, known_contacts)
       # The accepted entry's own rank is the FIFTH argument; a ladder-found person
       # passes None there, which keeps that record's provenance byte-identical.
       records.extend(suggest_contacts.synthesise_rows(
           eligible_company, selection["selected"], fetched_url, per_company_cap,
           source_rank))

   # The mint -- ONCE, over the whole accumulated batch, never per company.
   minted = suggest_contacts.mint_row_ids(records)
   plan = chunking.plan_chunks(minted["spec"], chunking.chunk_ceiling(cfg))
   # Stage 2 -- hand `plan` and `minted["spec"]["rows"]` to `enrich-before-ingest/
   # SKILL.md` step 5's dispatch block verbatim: `enrichment.resolve_providers`,
   # `chunking.dispatch_plan(..., async_ack=True, execution_ceiling=...)`,
   # `watch.recover_async_dispatch`, `preingest.merge_enriched` -- no second dispatch
   # path here. `merge_report` below is that block's own `preingest.merge_enriched`
   # result.
   records = suggest_contacts.rejoin_enriched(minted["records"], merge_report.rows)
   # company_domains is REQUIRED (no default) -- the email-domain-relatedness rule
   # (operator ruling, 2026-09-04) applies to every sendable row.
   company_domains = {c.get("name"): (c.get("website") or c.get("domain"))
                      for c in eligible_companies}
   sendable, held = suggest_contacts.partition_for_dispatch(
       [record["row"] for record in records], company_domains)
   # The SECOND, records-level gate (D-5sd-01 + D-5sd-05): a search-sourced person is
   # sendable only from the company's own host or LinkedIn. A rank-3 row is held however
   # confidently the waterfall validated it. Independent of the pass above; both hold.
   sendable, held = search_fallback.hold_weak_sources(records, sendable, held)
   for record in records:
       if record["row"] not in sendable:
           continue  # a held row never reaches extraction.validate()
       result = extraction.validate(suggest_contacts.round_artifact([record]))
   ```

9. **Report.** Per company: eligible / skipped / unknown, people named, people already
   known and dropped before the cap, fetches spent against the per-company bound, people
   proposed, and people held with why. Quote the ceiling shown at step 4 alongside the
   actuals, so the operator can see the actuals landed at or under it.

   Group the held rows by `reason_code` — "held: 4" must never appear on its own.
   Report the five codes separately: `no_email` (no usable email at all),
   `email_domain_freemail` (a personal mailbox — Gmail, Hotmail, an AU consumer ISP),
   `email_domain_mismatch` (a stranger's domain — the row that started this rule),
   `company_domain_unknown` (nothing on record to compare against), and
   `search_source_not_strong` (found by the step-5 search fallback on a rank-3 industry
   source rather than the company's own site or LinkedIn — D-5sd-05). Quote each held
   row's own prose `reason` under its group, so the operator can act on it without
   opening HubSpot first; a `search_source_not_strong` reason quotes the **source URL**
   specifically, so the operator can judge a third-party claim themselves rather than
   taking the hold on trust.
