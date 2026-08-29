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
