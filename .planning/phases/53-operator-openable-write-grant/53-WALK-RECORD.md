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
