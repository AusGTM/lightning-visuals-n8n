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

Nothing below is a per-record claim. Reading a run's outcome per record is a separate
capability; claiming it here would be a guess dressed as a report.

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

2. **Resolve which records.** Three forms, and only two of them are supported:

   - **Record IDs** — the operator pastes HubSpot record IDs. Spec:
     `{"record_ids": ["101","102"], "object_type": "companies"}` (or `"contacts"`).
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

5. **Ask for approval.** If the operator declines, STOP here. Nothing is sent. The only
   thing that has happened is one read of the status endpoint, which costs nothing.

6. **Check arming.** Disarmed is the default and the state of every new conversation. Say
   plainly that sending is off, and that the operator can turn it on **for this
   conversation only** by saying: **"arm the enrichment"**. This state is never written to
   disk — it exists only as the `armed` argument passed to the dispatch call below, for
   this turn only. Arming this lane does not arm the contact-upload lane, or the review
   lane, in either direction.

7. **Dispatch the plan the operator approved — only after they have said the arming phrase
   this turn.** `scripts/chunking.py` is a library here (the same way `scripts/report.py`
   already is, not a CLI): rebuild the plan from the same spec and the same configured
   ceiling — it is deterministic, so it is the same plan that was previewed — and send it:

   ```python
   import chunking, config_gate, enrichment
   cfg = config_gate.load_config()
   providers = enrichment.resolve_providers(<override or None>, cfg)
   plan = chunking.plan_chunks(<spec>, chunking.chunk_ceiling(cfg))
   outcome = chunking.dispatch_plan(plan, providers, True, cfg)
   ```

   Chunks go one at a time, in plan order. A chunk that fails is skipped and the rest
   continue — one bad chunk does not abandon the batch. `armed` has no default: if the
   operator has not said the arming phrase this turn, pass nothing and do not call this at
   all.

8. **Report what was sent, and no more than that.** From `outcome.results`, say how many
   chunks the backend accepted and how many rows were in them. For any chunk that failed,
   give its short reason as recorded — a non-2xx, an unreachable webhook, or a response
   that could not be read. A timeout counts as a failure here even though the backend may
   still be working; say so rather than implying the records were rejected.

   If `outcome.failed_batch` is present, say that the failed records have been collected as
   **a batch that can be re-sent** — one well-formed enrichment request, not a list of
   errors — and that re-sending it goes through this same arming gate, because a re-send is
   a send. Name it as the thing to hand to a retry.

   **Do not claim per-record outcomes.** The synchronous response does not carry them, and
   inventing them from an accepted chunk would report success for records nothing has
   confirmed. If the operator asks what happened to a specific record, say plainly that
   this lane reports at chunk granularity and point them at the record in HubSpot.
