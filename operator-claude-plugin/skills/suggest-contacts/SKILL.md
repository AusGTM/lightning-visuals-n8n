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

   **Do not escalate past a refusal.** No search engine, no other host, no second attempt
   at the same content somewhere else. When the ladder gives up on a company, that is a
   result to report, not a prompt to go looking elsewhere for it.

   The ladder is bound to the host built from the company's own recorded website — a
   scheme is added when the record has none, but `www.`, case, path and query are kept
   exactly as recorded, never rewritten (G-62-1). A company whose recorded value cannot
   be its own site (a social/profile link, or a value with no dot in it) yields no
   candidates at all, with a reason naming that value — never a guessed URL. When
   `next_candidates` refuses a same-page sitemap link and names two DIFFERENT hosts in
   its reason, that means the site itself serves a different host variant than the one
   recorded in HubSpot — not that the page is missing; report it as a host mismatch, not
   as "no people page".

6. **Filter, then synthesise.** `suggest_contacts.select_people(people, family_list,
   chosen_families, known_contacts)` drops a person already associated with that company
   before the role filter even runs, and applies the chosen roles to whoever is left
   (D-62-18) — a person the round already knows about at that company is never spent on.
   `suggest_contacts.synthesise_rows(company, selected, fetched_url, per_company_cap)`
   then emits at most `per_company_cap` rows, each carrying the URL actually fetched as
   its provenance locator — never the company's homepage, and never the page the
   operator originally pasted if the ladder had to escalate past it.

7. **Stage 2 — enrich the people stage 1 named.** No confirmation between the stages
   (D-62-02) — the round moves straight from a named person to enriching their contact
   details. This uses the SAME machinery `enrich-before-ingest/SKILL.md` step 5 already
   calls for its own enrich pass — `enrichment.resolve_providers`,
   `chunking.dispatch_plan(..., async_ack=True, execution_ceiling=...)`,
   `watch.recover_async_dispatch`, `preingest.merge_enriched` — and builds no second
   dispatch path. The stage-1 rows (firstname, lastname, company, jobtitle, no email)
   are exactly what the waterfall needs to resolve a person by identity group 2.

8. **Land as proposals.** `suggest_contacts.partition_for_dispatch(rows)` splits the
   sendable rows from the held ones, unchanged from any other lane — a suggested row
   still missing an email after stage 2 is held exactly like a CSV row, no special case
   anywhere for a suggestion's origin. `extraction.validate()` runs **once per sendable
   row**, after stage 2 has merged its fields on — never before, and never twice for the
   same row. The held half is handled exactly as `enrich-before-ingest/SKILL.md`'s own
   held-row path: `confidence.assess()`, then `held_queue.build_entry()`, then
   `run_manifest.save()`.

   Send the round's per-field source map with the final dispatch — `dispatch.dispatch(...,
   source_by_field=...)` — so the written contacts carry mixed provenance: `claude_web`
   for the name and job-title fields stage 1 named, and the provider's own name for the
   email and phone fields stage 2 filled in (plan 62-04, D-62-17). As with step 1: no
   per-person confirmation and no per-company confirmation happen here either — a row
   either clears the gates a spreadsheet upload clears, or it is held, named individually,
   for the operator to see in the report.

   The whole documented sequence, in one pass, over one eligible company:

   ```python
   import extraction
   import role_classify
   import suggest_contacts

   verdicts = suggest_contacts.eligibility(company_rows)
   plan = suggest_contacts.discovery_plan(eligible_company)
   # The operator approves candidates from `plan`, in the order shown, stopping at the
   # first that yields people (the INGEST-05 contract, inherited unchanged). `people`
   # below is whatever that approved fetch actually returned.
   vocabulary = role_classify.load_families()
   selection = suggest_contacts.select_people(
       people, vocabulary["families"], chosen_families, known_contacts)
   # figures is the open grant's own envelope (step 4); chosen_cap is what the operator
   # picked in step 3. agreed_cap() is the ONLY number the rest of this round spends
   # against -- it raises CapRefused rather than letting a too-high or malformed cap
   # reach synthesise_rows.
   per_company_cap = suggest_contacts.agreed_cap(chosen_cap, figures)
   records = suggest_contacts.synthesise_rows(
       eligible_company, selection["selected"], fetched_url, per_company_cap)
   # Stage 2 -- the SAME dispatch machinery `enrich-before-ingest` already uses
   # (`enrichment.resolve_providers`, `chunking.dispatch_plan(..., async_ack=True,
   # execution_ceiling=...)`, `watch.recover_async_dispatch`, `preingest.merge_enriched`)
   # -- merges each named person's email/phone onto their own record's "row" dict here,
   # never a second dispatch path.
   sendable, held = suggest_contacts.partition_for_dispatch(
       [record["row"] for record in records])
   for record in records:
       if record["row"] not in sendable:
           continue  # a held row never reaches extraction.validate()
       result = extraction.validate(suggest_contacts.round_artifact([record]))
   ```

9. **Report.** Per company: eligible / skipped / unknown, people named, people already
   known and dropped before the cap, fetches spent against the per-company bound, people
   proposed, and people held with why. Quote the ceiling shown at step 4 alongside the
   actuals, so the operator can see the actuals landed at or under it.
