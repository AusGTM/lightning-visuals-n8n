# WALK RUN 4 — 2026-08-30, operator chair, Claude Desktop — **FAILED**

**Operator verdict, 2026-08-30:** *"I do not need to complete walk, I consider it failed at this
point."*

**Prereqs, both met for the first time:** `origin/master` pushed (`a624499`), installed plugin
updated Desktop-side to **0.28.6**. This is the first walk ever run from the operator's own
chair, against the installed plugin rather than the repo — the two limitations recorded on run
3's verdict.

**Record under test:** `https://www.linkedin.com/in/robert-cavallucci-14698741/` — a fresh
profile, deliberately not run 3's `joshua-fusco-481309247` (reusing that would have been an
update, which carries an `hsObjectId` and sails through the write-safety gate on the id
allowlist, skipping the create path).

---

## Where it stopped

**Halted before step 3.** The grant was never opened, so **steps 3–7 were never exercised.**
Nothing in this run tests the grant, the one-yes property, revocation, out-of-scope refusal, or
the unset-key message.

Sequence as it actually went:

1. **Step 2 — setup check: PASS.** The plugin reported setup complete and listed
   `allow_write_grants` as on. Settings file named and correctly described as living outside the
   plugin folder so it survives updates.
2. **Operator asked to "enrich and ingest" the URL.** No grant open (fresh conversation; grants
   are in-conversation only), so the plugin correctly announced the **ungranted** two-gate path
   — one gate before spending provider credit, one before writing. *This is correct behaviour on
   that path, not a violation of "one grant, one yes"; that property only binds once a grant is
   open.*
3. **URL adapter attempted the fetch and LinkedIn returned HTTP 999** (its standard anti-bot
   response).
4. **The plugin stopped and asked the operator for the company.** It proposed
   `firstname=Robert / lastname=Cavallucci` from the vanity slug **as a proposal**, put company
   and email into ambiguities, and declined to escalate — citing that the escalation ladder does
   not run on a tool error because "escalating past a refusal turns a fence into a suggestion".

The operator declined to supply the company and ended the walk.

---

## What went RIGHT, and should not be lost in the failure

Recording these because a failed walk is still evidence, and these are the parts that held:

- **No terminal was needed at any point.** Every step ran from Desktop.
- **The installed plugin at 0.28.6 loaded and behaved.** Limitation 2 from run 3's verdict is
  genuinely closed.
- **The no-invention boundary held under pressure.** It refused to scrape a page the licensed
  waterfall already covers (D-58-03), refused to state a cause the tool had not given it, and
  proposed the slug-derived name as a *proposal* rather than writing it on its own authority.
- **The ungranted-path disclosure was correct and legible** — two gates, named, with an enriched
  preview promised in between.

---

## FINDING D — the plugin demands a field its own backend does not need

**Severity: this is why the walk failed, and it is not a grant defect.**

The plugin refused to proceed without a company, on the rule that a contact needs either an email
or all three of firstname + lastname + company to have an identity. **That front-end rule does
not reflect what the backend can actually do with a LinkedIn URL.** Verified in source:

| Capability | Evidence | Needs a company? |
| --- | --- | --- |
| HubSpot match by `linkedin_url` | `n8n/code/resolveIdentity.js:76-78` — `linkedin_url` is a **strong** match key, same tier as email | **No** |
| Lusha v3 contact enrich by LinkedIn URL | `n8n/code/lushaRequest.js:79-91` — `lushaContactBody` accepts **any subset** of the identity keys; `linkedin_url` maps to `contact.linkedinUrl` (line 83). Only a wholly empty set returns the skip form | **No** |

So both operations the plugin said it could not perform — match, then enrich — are keyed on
something the operator had already supplied. The blocker is entirely in the ingest/extraction
front-end contract.

**This does not require loosening the no-invention rule.** Nothing would be invented: the
operator supplies the URL, the licensed provider returns sourced fields, the operator confirms.
A searched-and-sourced value is not an invented one — those two have been collapsed into one
rule, and separating them is the fix. The verbatim no-invention sentence in `extraction.md` can
stay exactly as it is.

**It is NOT a regression.** No recorded operator ruling about best-effort identity resolution
exists anywhere in `.planning/` (searched 2026-08-30), and the extraction adapter's escalation
ladder has only ever been **same-host URL fetching** (`url_fallback.py`, host-bound in code, not
by judgement). There has never been a web-search or waterfall rung in it. The capability was
never built rather than built and lost.

**The actual root cause is process, not code.** The operator states this rule was given verbally
before ("this was a rule I stated earlier"). It was never written into requirements, so nothing
implemented it and nothing guarded it. That is the third documented-vs-actual gap to cost
something in two days — see also P5's two wrong observations and the handover's false claim about
`written_records.json`.

**One design correction for whoever plans the fix:** the operator asked for *web search*. For a
**person**, that is the weaker instrument — `claude_web` research is company-oriented
(`object_type: companies` throughout `src/web_research.py`). The right mechanism is the licensed
waterfall keyed on `linkedin_url`, which is already built and already paid for.

---

## Consequences for GRANT-01

**GRANT-01 stays ticked** — run 3 earned it and this run does not retract it. But:

- **Limitation 1 is NOT closed.** The grant surface was never reached from the operator's chair,
  so *"a Claude-Desktop walk remains the only thing that proves G-2 is truly gone"* still stands.
- **Limitation 2 IS closed.** The installed plugin ran.
- **A new operator-blocking friction is recorded.** The original G-2 was specifically about
  `ALLOW_N8N_ARM` needing a shell variable, and that blocker was never reached. But the broader
  G-2 question — *can the operator do this unaided?* — got a fresh negative answer today, from a
  different cause. The operator sat down, supplied the only thing they had, and could not
  proceed.

**A re-walk should not be attempted until FINDING D is fixed**, or it will halt in the same place.

---

## Cost

Effectively nil: one refused fetch, zero provider credits, zero n8n executions, zero HubSpot
writes, zero Anthropic research calls. Nothing was armed and no grant was opened.

---

# WALK CONCLUDED — 2026-08-30, operator verdict: **all steps passed as per walk requirement**

The operator resumed and completed the walk after the halt above. Revised outcome: **steps 1–6
reached their gates and step 7 PASSED outright.** The run is no longer "failed at step 2" — it is
a completed walk whose value is a diagnosis rather than a write.

## Step 7 — **PASS**, on all four criteria

With `allow_write_grants` unset in `operator.local.json`, the refusal read:

> Grant authority is OFF. `allow_write_grants` is not true in `operator.local.json`.
> `plan_grant`/`open_grant` hard-refuse at the authority gate — no grant opens from this
> conversation until your n8n admin sets that key.

| Criterion | Result |
| --- | --- |
| Names the key | **PASS** — `allow_write_grants` |
| Names the file | **PASS** — `operator.local.json` |
| Names who sets it | **PASS** — "your n8n admin" |
| Does NOT tell the operator to set a shell environment variable | **PASS** — no env var mentioned |

This is the **direct G-2 probe, and G-2's original shape is genuinely gone on this lane.** The
refusal points at a settings key an admin edits in a file, not at a shell export an operator in
Claude Desktop cannot perform. Cited live from the operator's chair: `write_grant.py:436`,
`config_gate.py:107`.

## Steps 3–6 — reached, and each refusal was correct in isolation

- **The empty-record-set refusal fired and explained itself well**: *"refusing to plan a grant
  over an empty record set… This is resolvable: a read-only HubSpot lookup for the record's own
  object id, or — for a record that does not exist yet and therefore has no id — for its
  company's domain."* That is `plan_grant`'s operator-confirmed load-bearing refusal working as
  designed, and naming its own resolution.
- **The grant-handle boundary held**: a LinkedIn URL is not a grant handle; a grant scopes by
  HubSpot record id or company domain, never a profile URL.
- **The no-invention rule held again**: it declined to guess Football Queensland's domain from
  memory, and offered the two legitimate routes (operator statement, or a read-only lookup).

## FINDING E — the Desktop session has no HubSpot read path

New, and it matters more than it looks. From step 7 verbatim:

> This session has no HubSpot read path: n8n-mcp returned 401, HubSpot MCP connector is
> unauthorized. So I can't resolve the URL from here, and I won't invent an id.

Every "this is resolvable — just do a read-only lookup" escape hatch the refusals offer
**depends on a read path that does not exist in the operator's chair.** The refusals are
therefore well-worded but unactionable from where the operator actually sits: they name a
remedy the session cannot perform. A read-only HubSpot lookup costs nothing, writes nothing, and
is the single unblocking capability for most of steps 3–6.

## FINDING F — no confidence self-assessment, therefore no autonomy (operator's diagnosis)

**Operator, 2026-08-30, verbatim:**

> *"Again Steps 1-6 show how incredibly halting this process is, that there is no self assessment
> of confidence, and therefore no autonomy in workflow, it requires an operator to walk through
> each step every single time, if an operator has hundreds of contacts to ingest, this means they
> will need to go through hundreds of research steps, and approval gates. That gets away from the
> point of doing this altogether. The point is that this plugin is supposed to take all the
> research, enrichment, and ingestion off the operator's hands in a non-clobbering way (as using
> the 3 separate backend services, which DO DO the research enrichment and ingestion ALREADY, but
> they clobber each other - if we keep the non-clobbering aspect while removing the autonomous
> research, enrichment and ingestion parts then this makes a worse system - again, guidance is
> speed, efficiency autonomy is MORE IMPORTANT than gating, permissions, security - this is a GTM
> function, not a core product or security function)"*

**This is the sharpest statement of the problem in the project's history, and it reframes the
milestone.** The load-bearing argument: the three backend services **already perform** research,
enrichment and ingestion. The plugin's entire reason to exist is that they clobber each other.
**Keep the non-clobbering and remove the autonomy, and the result is worse than the raw
services** — which is what the walk just demonstrated at n=1.

Note what is NOT being asked for, because a careless reading would destroy the value:
**non-clobbering is explicitly kept** ("in a non-clobbering way"). The target is *approval
friction and per-row research halts*, not the merge policy.

Every individual refusal in steps 3–6 was correct. **The composition of correct refusals is the
defect** — the same shape as the five composition defects of 2026-08-29, one level up.

## Verdict

**GRANT-01 stays ticked. Limitation 1 is now CLOSED for the authority surface** — step 7 proved
the grant refusal is operator-actionable from Claude Desktop with no terminal. What remains
unproven is a grant actually *opening and carrying a batch* from that chair, which steps 3–6
could not reach.

**Cost:** zero. No credits, no executions, no writes, nothing armed.
