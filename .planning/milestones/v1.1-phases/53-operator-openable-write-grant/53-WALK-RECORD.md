# Phase 53 — Operator walk record

**Run:** 2026-08-28, autonomously by Claude at the operator's instruction.
**Record under test:** https://www.linkedin.com/in/joshua-fusco-481309247/ (create + enrich + land)

## Caveat on what this run can prove

53-04 wanted an OPERATOR walk from Claude Desktop. This run is Claude Code with terminal
access, so it tests the COMPOSITION but not the operator's constraint set. Any step where a
terminal-only capability was used is marked TERMINAL-ASSISTED and does not count as evidence
that an operator could do it unaided.

## Steps

(filled in as the walk proceeds)

### Step 2 — is the plugin set up? **PASS**

`init_check.py` (plugin root, v0.18.0): "Setup is complete — nothing to do." Every capability
`ready`. Critically:

```
Optional settings your n8n admin controls:
  - letting an operator open a write grant (live HubSpot writes for a named batch): on  (allow_write_grants)
```

The setting is reported as **on**, in operator-readable words, naming the key. Step 2 of
53-04's script is satisfied.

**Negative check (string `"true"` reads as NOT enabled) — NOT performed.** It requires editing
`operator.local.json`, and a same-version reinstall is known to delete that file. Deferred
rather than risked; the boolean-vs-string discrimination is separately unit-tested.

### VERSION FINDING — the walk runs 0.18.0, not the repo

Surfaced before any live action, because walking stale code and reporting a broken composition
would be a false finding.

- The Skill tool served `0.18.0/skills/initialize/SKILL.md`, so **0.18.0 is the ACTIVE version**.
  The cache also holds `0.19.0` (and eight older builds).
- **0.18.0 vs 0.19.0 source diff:** `enrichment.py`, `extraction.py`, 4 skill files, plus
  `company_domain.py` which exists ONLY in 0.19.0. That is Phase 58's company-domain work.
- **Does it matter for THIS walk?** No. The record under test is a CONTACT sourced from a
  LinkedIn *person* URL. `linkedin_url` is an accepted person identity key in 0.18.0 —
  6 references in `enrichment.py`, the same count as 0.19.0 (`{people: [{firstname,lastname,
  company|email|linkedin_url}]}`, and the identity gate at :298/:308). The version gap is in
  the company-domain path, which this record does not exercise.
- **The repo differs from BOTH installed versions.** `diff` of repo `write_grant.py` against
  0.19.0's shows only Phase 54's changes: `anthropic_usd` relabelled `MEASURED` -> `PROJECTED`,
  and WR-04's "worst case"/"floor" sentence rewritten. Label and wording, not behaviour.
- **Consequence for this record, stated plainly:** the walk exercises the grant path as an
  operator would actually meet it (installed plugin), and for this input 0.18.0 is functionally
  equivalent to 0.19.0. Findings are valid for the grant composition. They are NOT evidence
  about Phase 58's company-domain path, which is 0.19.0-only and unexercised here.

### Step 3 (skill step 1) — config gate **PASS**

`config_gate.py` -> `ok: true`, `can_send: true`, `send_blocked_reason: null`,
target `https://alexherman.app.n8n.cloud/webhook/hubspot/contact-upload`.

### Step 4 (skill step 2) — resolve the row — **HALTED: the input cannot produce a row**

The walk stopped here, before any grant was opened, any credit spent, or anything armed.

**What happened.** The input is a URL, so `contact-upload/extraction.md` applies. That contract
is explicit that Claude is the extractor, that no HTTP client may be used, and — the governing
rule — *"Never fill a gap to make a row satisfy the identity rule. A row that gets rejected with
a stated reason is the correct outcome."*

The LinkedIn profile itself was NOT fetched (forbidden by the contract; also auth-walled). The
URL string supplies a `linkedin_url` and, from the vanity slug `joshua-fusco`, a plausible
first and last name. It supplies **no company and no email**. Those two were written into
`ambiguities`, not guessed into the row.

`scripts/extraction.py` ruled:

```json
{"ok": true, "accepted": [],
 "rejected": [{"index": 0, "reason": "no identity present: needs a non-blank 'email', or all three of 'firstname'/'lastname'/'company' non-blank"}]}
```

`accepted: []`. There is no row to match, enrich, or write.

**This is the contract working, not a defect.** The rejection is the outcome extraction.md
prescribes. Recorded as a walk finding rather than worked around: supplying an employer from
outside knowledge to get this row past the gate is precisely what the no-invention rule exists
to prevent.

**The finding worth carrying forward — an inconsistency between two identity rules:**

- `config/column_mapping.yaml` `required_identity.any_of` = `[email]` OR
  `[firstname, lastname, company]`. **`linkedin_url` is not an identity here.**
- `scripts/enrichment.py:205` documents the enrichment spec form as
  `{"people": [{firstname,lastname,company|email|linkedin_url}]}`, and its own gate (:302, :308)
  treats a row with a `linkedin_url` as sendable.

So the ENRICHMENT lane accepts a LinkedIn URL as identity and the INGEST lane does not. A person
known only by their LinkedIn URL can be enriched but can never be created. Whether that is
intended is a real question for a planner; it is not something this walk should decide.

**Not a Phase 58 regression.** Phase 58's "take what the operator actually has (screenshot,
paste, URL, bare name)" is scoped to COMPANIES resolving to a company the backend can act on.
Person-URL -> contact was never in its scope.

**Cost so far: zero.** No grant opened, no arming, no provider credit, no n8n executions, no
HubSpot writes. The halt is upstream of all of it.

---

## Walk resumed 2026-08-28 — operator supplied the missing identity

Operator statement: *"Joshua Fusco, League Commissioner & Director of Media and Communications
of Series Futsal Victoria"*, plus a design ruling (recorded separately) that Claude should
RESOLVE AND PROPOSE rather than refuse outright.

### Step 4 (retry) — extraction **PASS**
`accepted: 1`, `rejected: []`, `dropped_keys: []`. firstname/lastname/company satisfy
`required_identity`; jobtitle and linkedin_url ride along as attributes.

### Step 4b — unarmed HubSpot match **PASS**
`auto_matched: 0, proposed: 0, unmatched: 1, unchecked: 0`. No existing contact — a CREATE.

### Step 5 — cost preview **PASS**
Honest: rates dated (2026-07-30, 29 days old), "at most" framing, Lusha priced at first-time
rate deliberately over-stating. Apollo reported `unknown — could not be read` with the reason
(rate limits, not a credit pool) rather than a guessed number.

### FINDING 1 — a create with no email cannot be granted at all **(prediction confirmed)**
`plan_grant(record_ids=[], record_domains=[])` REFUSES:
> "refusing to plan a grant over an empty record set. The deployed `_writeSafetyAllows()`
> returns false when both allowlists are empty, so a grant over nothing would report as a
> grant while granting nothing at all — worse than refusing, because it reads as success."

`authorize_ungranted_send` (the F2 no-grant path) refuses identically on BOTH lanes. So a
contact with neither a HubSpot id nor an email domain is unreachable on every armed path.
**The refusal is correct and well-reasoned** — it fails loudly rather than silently.

Resolved by looking the company up read-only: Series Futsal Victoria = HubSpot `283816805830`,
domain `seriesfutsal.com`, AU, tier C, `lv_anti_icp_flag: false` (58-06's fix held — the
execution-`11983` false veto is gone). Scoping by that domain arms writes for ANY contact at
that domain; a create has no id, so domain is the narrowest scope expressible. Disclosed, not
slipped in.

### Step 6 — grant opened **PASS**, and the D-53-05 disclosure LANDS
Answers 53-04's walk question directly. Verbatim from `consequence`:
> "This grant covers both lanes at once, which means the HubSpot write is authorized BEFORE the
> enriched preview exists — held rows and merge conflicts that the enriched preview is the only
> place to see ahead of a write are authorized unseen. The preview is still rendered, and the
> record set is unchanged; what moved is WHEN you approved it, not WHAT it covers."

It also names the disarm guardrail 53-04 only PROPOSED ("a second consecutive failure closes
the grant") — so that shipped. Cost figures live under `envelope`, with Apollo `known: false`
carrying a full citation instead of a number.

Send authorization narrowed correctly:
> "bounded to this send's 0 record id(s) and 1 domain(s) — narrower than the grant, never wider."

### Step 7 — enrichment ran **PASS** (arm -> dispatch -> disarm verified live)
The waterfall found real data: `email josh@seriesfutsal.com` (confidence 85,
`human_review_required`), `jobtitle League Commissioner`, seniority, `city South Morang`,
`state Victoria`, `country Australia / AU`, `lusha_contact_id`. Returned
`action: proposed / mode: propose / needs_review: true`, reason *"email: promoted into a blank
field at confidence 85 — verify before relying on it"*. Nothing written to HubSpot.

### FINDING 2 — **THE COMPOSITION BREAK. Silent, total loss of enrichment.**

`enrich-before-ingest/SKILL.md` step 5 documents:

```python
outcome = chunking.dispatch_plan(plan, providers, True, cfg)
merge_report = preingest.merge_enriched(unmatched_rows, outcome.responses)
```

`dispatch_plan` returns **a list of PER-CHUNK LISTS**. `merge_enriched` indexes responses by
`row_id` and skips any item that is not a dict — so every item (a list) yields `row_id = None`
and is skipped. The index ends empty and every row falls through as `unanswered`.

Measured on this record, same data both ways:

| Call | `unanswered` | merged email |
|---|---|---|
| **As documented (nested)** | **1** | **`None`** |
| Flattened `[i for chunk in raw for i in chunk]` | 0 | `josh@seriesfutsal.com` |

**Why this is worse than a crash.** It fails into the `unanswered` group, which
`merge_enriched`'s own docstring defines as *"a row nothing is known about at all"* and which
exists precisely to distinguish "we could not look" from "we found nothing" (T-38-01). A
correct, complete provider answer is filed under the one label that means the opposite. The
operator reads "nothing known", concludes the providers found nothing, and never learns an
email was returned — after paying the credit for it.

Under a two-lane grant this is compounded: the write was already authorized, the enriched
preview is a report rather than a gate, and the report says the row is empty.

With the flatten applied, the rest behaved correctly — the operator's longer jobtitle was KEPT
over the provider's shorter one and recorded in `conflicts` (fill-not-overwrite working), and
11 non-canonical keys were dropped and REPORTED rather than silently widened onto the row.

### Walk HALTED here deliberately — no HubSpot write attempted
Pushing the create through a hand-flattened workaround would manufacture a success that
misrepresents the shipped flow, and would route around the exact defect the walk exists to
find. The composition is broken; that is the finding.

### FINDING 3 — `close_grant` enforces its reason vocabulary **PASS**
A free-text close reason was REFUSED, naming the seven reportable reasons (GRANT-04). Closed
with `session_end`.

### Post-walk state — clean
`verify_live_write_safety.py --expectation disarmed` -> **`VERDICT: disarmed PASS`** across all
5 workflows / 15 declaring nodes. `armed_window` disarmed correctly on context exit. Grant
`closed`. Scratch artifacts deleted.

**Cost:** 1 n8n execution, ~1 Lusha credit + ~1.08 ZoomInfo credit, ~$0.07 Anthropic.
**HubSpot writes: ZERO.** Joshua Fusco was NOT created.

## Verdict

53-04 predicted *"every component correct, the composition broken."* That is exactly what this
walk found, twice over — once benignly (the empty-allowlist refusal, which fails loudly and
correctly) and once seriously (FINDING 2, which fails silently and discards paid-for data).

**GRANT-01 is NOT ticked.** The grant machinery itself works: authority, envelope, disclosure,
narrowing, arm/disarm, revocation vocabulary. The FLOW it exists to serve does not — an
enrich-before-ingest batch cannot carry enrichment to the write, and does not say so.
