# Phase 66: Rich enrichment, not minimum enrichment - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning

<domain>
## Phase Boundary

The waterfall asks for every field it can confidently reach, instead of the minimum that makes
a record usable. Today `ENRICH_GATE`'s `REQUIRED = ["email", "jobtitle", "mobilephone"]`
chases 3 of the 12 fields the contacts merge policy can promote — and because that same list
drives Lusha's selective reveal (`lushaContactBody(id, missingFields)`), a minimum became a
ceiling for one provider and the intent for all three.

**In scope:** widening the chased-field set on BOTH the contacts and companies lanes, writing
the one contact field that has no producer at all (`lv_linkedin_url`), making phone+email
completeness visible in the operator's report, and a producer/consumer matrix per field for
both lanes.

**Out of scope:** every threshold and every drop path — see D-66-08. This is entirely an n8n
lane change; it touches no plugin skill and no `suggest_contacts.py`, which is why it is the
one v1.2 phase that can run as a parallel stream.

</domain>

<decisions>
## What gets chased

- **D-66-01: `REQUIRED` becomes the full policy-promotable set, on both lanes.** For contacts
  that is all 12 keys in `config/field_policy.yaml`'s `contacts` block: `city`, `country`,
  `email`, `hs_country_region_code`, `hs_state_code`, `jobtitle`, `lv_linkedin_url`,
  `lv_persona_group`, `mobilephone`, `phone`, `seniority`, `state`. The companies lane gets
  the same treatment against its own policy block.
  **Cost is the mapping work, not credits:** Lusha v3 bills flat per contact and reveal-field
  count does not change the bill (`REQ-lusha-selective-reveal` §6); ZoomInfo's extra fields
  ride a request already paid for. Verify the ZoomInfo assumption before relying on it —
  `phone` and `mobilePhone` are already in `ZOOM_OUTPUT_FIELDS`, so it is probably moot.
  — **Reversibility:** reversible — `REQUIRED` is a list in the builder wrapper.

- **D-66-02: `lv_linkedin_url` gets a producer.** Measured: `normalizeProviders.js` contains
  no `linkedin` reference at all, while Apollo and ZoomInfo both return a LinkedIn URL, so
  the data is arriving and being discarded at normalize. Add a `_push` in each provider's
  contacts branch with a small URL normalizer — force https, lowercase host, strip query and
  trailing slash, refuse a non-`linkedin.com` host. This is the **only** field of the 12 that
  needs new normalize code; the other 11 already have producers in the Apollo branch alone.
  Filling it also makes future rows matchable on a key the system already privileges
  (`required_identity.any_of` includes the LinkedIn group).

- **D-66-03: Watch the `lv_linkedin_url` / `linkedin_url` naming seam.** The merge policy key
  is `lv_linkedin_url`; `required_identity.any_of` and `columnMap` use `linkedin_url`. A
  candidate pushed under the wrong key is silently dropped at merge — no error, no log. The
  plan must state which key the candidate carries and prove the merge consumes it.

- **D-66-04: Both lanes ship in this phase.** Contacts and companies widened together as one
  coherent "rich enrichment" change, with the producer/consumer matrix covering both. Accepted
  cost: a larger blast radius in one phase, and the company lane also carries the judge/
  conflict guard (58-06's `MATERIAL_CONFLICT_GROUPS` suppression), which the plan must not
  disturb.
  — **Reversibility:** costly — two gates and two merges move together.

## What the operator sees

- **D-66-05: A phone-less row is FLAGGED as partial, not held.** Still sendable; the report
  distinguishes phone+email from email-only. Holding would hold most rows — direct dials are
  far scarcer than emails, and ZoomInfo's `directPhone`/`hasDirectPhone` are **400 on this
  account** (not entitled), so a verified direct dial is not purchasable here at all. The
  ceiling this account can buy is `phone` (often a switchboard) plus `mobilePhone`.
  Rejected: holding phone-less rows — a much larger behaviour change, and it would have made
  Phase 69's decline store a dependency of this phase.

- **D-66-06: Completeness is visible in the report.** A row with phone AND email must be
  distinguishable from an email-only row. Today nothing expresses the operator's stated target
  ("a phone number AND email are preferable ... with email only as fallback") and a phone-less
  contact is indistinguishable from a complete one.

- **D-66-07: Deliverable includes a producer/consumer matrix per field, both lanes.** For each
  policy-promotable field: which provider branches emit a candidate, what the policy does with
  it, and whether any field has no producer. That matrix is how a second `lv_linkedin_url`
  gets caught rather than discovered live.

## What must NOT move

- **D-66-08: The thresholds ARE the confidence mechanism and they stay.** This phase asks for
  MORE fields; it never lowers the bar a value clears to be written.
  - No `min_confidence` lowered anywhere.
  - No `fill_blank_only` weakened — a populated human value still wins.
  - The three phone drop paths stay exactly as they are, each deliberate:
    1. `doNotCall` (Lusha) / `dnc_status` (Apollo) → `continue`. A suppression, not a
       downscore.
    2. `normalizePhone(...)` returning null → `continue` ("null-drop: un-normalizable phone
       never reaches HubSpot"). Never written raw.
    3. ZoomInfo `directPhone` / `hasDirectPhone` → unentitled on this account. Not a bug to
       route around.
  - The merge policy is NOT the blocker and a fix must not start there: `phone` is already
    `fill_blank_only` / `min_confidence: 80` in both `config/field_policy.yaml` and
    `mergeContacts.js`'s `DEFAULT_CONTACT_POLICY`, so a returned phone promotes into a blank
    today. Nothing needs loosening.

- **D-66-09: `phone` gets NO `stale_after_days`, and the reason is recorded.** Measured:
  `stale_after_days` is read only by `mergeContacts.js`'s `stale_refreshable` branch. `phone`
  and `mobilephone` are both `fill_blank_only`, whose branch is blank→promote /
  non-blank→`stage_only` and never consults a TTL. A TTL on `phone` today is inert, and the
  only way to activate it is to change the class — which weakens `fill_blank_only` and is
  forbidden by D-66-08. Substantively it is also the wrong signal: a switchboard number is
  org-scoped and outlives staff turnover, and for a senior leader at an AU sporting club
  (annual AGM committee turnover) the field that actually goes stale is `jobtitle`, which is
  already `stale_refreshable` at 180 days.

- **D-66-10: Never hand-edit `n8n/wf_*.json`.** `ENRICH_GATE`'s `REQUIRED` lives in the
  WRAPPER built by `scripts/build_cloud_workflows.py`, not in the frozen `enrichmentGate.js`
  module. Regenerate via the builder. Check whether `src/` carries an equivalent required-field
  list that must move in the SAME commit (Phase 46 parity rule).

### Claude's Discretion

- The URL normalizer's exact strictness for `lv_linkedin_url` beyond the named rules.
- How completeness is rendered in the report (a count, a per-row marker, or both).
- The matrix's format and where it lives (a doc, a generated artifact, or a test).
- Whether the companies-lane widening is one task or split by provider branch.

### Folded Todos

- **`2026-09-04-phone-is-never-chased-only-accepted.md`** — this phase in full, including its
  "general defect the phone case is one instance of" section, which is what makes this a
  12-field change rather than a one-field one.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief
- `.planning/todos/pending/2026-09-04-phone-is-never-chased-only-accepted.md` — read the three
  drop paths, the two operator decisions, the parity note, and the measured 12-vs-3 counts.
- `.planning/ROADMAP.md` § "Phase 66" and § "Binding on all six" (SAFE-01..05).
- `.planning/milestones/v1.2-REQUIREMENTS.md`

### The code this phase changes
- `scripts/build_cloud_workflows.py` — `ENRICH_GATE`'s `REQUIRED` list lives in the wrapper
  here, and `lushaContactBody(id, missingFields)` derives Lusha's reveal list from it. The
  single most important file in this phase.
- `n8n/code/enrichmentGate.js` — the frozen module. `REQUIRED` is NOT in it.
- `n8n/code/normalizeProviders.js` — `apolloCandidates` (already emits 11 of 12 contact
  fields), `zoominfoCandidates`, `lushaCandidates`, `_push`, `normalizePhone`, `_personaGroup`,
  `_codeShaped`. D-66-02's new LinkedIn push lands here.
- `config/field_policy.yaml` — the `contacts` and `companies` blocks; the 12 promotable
  contact keys are its `contacts` keys.
- `n8n/code/mergeContacts.js` — `DEFAULT_CONTACT_POLICY`, the `fill_blank_only` and
  `stale_refreshable` branches (D-66-09's evidence), `_statusFor`.

### Must not be disturbed
- `n8n/code/mergeCompanies.js` and `n8n/code/providerConflict.js` — 58-06's material-conflict
  suppression on the companies lane. Widening the companies gate must not change which
  conflicts are judged. See CLAUDE.md §15.0.
- CLAUDE.md §29 and §29.1 — the never-write-automatically list and the ONE scoped
  `numberofemployees` exception (company enrichment lane, `fill_blank_only`, numeric provider
  values only). Widening the companies lane must not quietly extend that exception.
- CLAUDE.md §9.2 — the field-governance classes.

### Provider contracts
- `docs/LUSHA-V3-CONTRACT.md` and `REQ-lusha-selective-reveal` §6 — flat per-contact billing
  regardless of reveal-field count. D-66-01's cost claim rests on this.
- `ZOOM_OUTPUT_FIELDS` (in the builder) — already includes `phone`/`mobilePhone`; records
  `directPhone`/`hasDirectPhone` as 400/unentitled on this account.
- CLAUDE.md §8.1 — the contact staging table naming `apollo_linkedin_url` /
  `zoominfo_linkedin_url`, evidence the LinkedIn data arrives.

### Identity seam
- `config/column_mapping.yaml` `required_identity.any_of` and `n8n/code/columnMap.js`
  `requiredIdentity` — the `linkedin_url` spelling, pinned by
  `tests/n8n/columnMapIdentityParity.test.mjs`. D-66-03's seam.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `normalizeProviders._push(out, field, source, value, normalizedValue, accuracy, recencyDate)`
  — the one candidate-emitting helper. D-66-02's LinkedIn candidate is one more call, not new
  machinery.
- `apolloCandidates`'s contacts branch already emits email, phone, mobilephone, jobtitle,
  seniority, persona_group, city, state, country, hs_country_region_code, hs_state_code —
  11 of 12. Widening `REQUIRED` mostly turns on producers that already exist.
- `_codeShaped(value, minLen, maxLen)` — the existing guard for emitting a code candidate only
  when the raw value is already code-shaped. The precedent for a conservative normalizer.
- `mergeContacts`'s `fill_blank_only` branch — already promotes into a blank at threshold.
  A chased phone lands with no policy change at all.

### Established Patterns
- **The wrapper holds the list; the module is frozen.** `REQUIRED` in the builder, not in
  `enrichmentGate.js`. Same shape as `CONFLICT_WATCH` (58-06).
- **Parity in one commit.** A shared predicate that exists in both engines moves in a single
  commit (Phase 46 rule). Check `src/` for an equivalent required-field list.
- **Regenerate, never hand-edit.** `scripts/build_cloud_workflows.py` → `n8n/wf_*.json`.
- **Deliberate drops are commented as such.** The null-drop comment is the model: a drop that
  looks like a bug carries the sentence explaining it is not.
- **Committed JSON is currently AHEAD of the running instance** (CLAUDE.md §13.0.2, standing
  fact). An in-repo node is not evidence of what n8n is executing.

### Integration Points
- `ENRICH_GATE` → `missingFields` → `lushaContactBody` — the coupling that makes `REQUIRED` a
  reveal list and not merely a checklist. This is the mechanism the whole phase turns on.
- The operator report gains completeness (D-66-06); Phase 68's rule applies — a report reports,
  it does not halt.
- **No plugin skill and no `suggest_contacts.py` are touched.** This is why Phase 66 is the
  only v1.2 phase with no file overlap against 64/65/67/68/69, and can be planned and executed
  as a parallel stream.

</code_context>

<specifics>
## Specific Ideas

- The operator's target, verbatim (2026-09-04, during the 260904-5sd UAT): *"A phone number
  AND email are preferable — that is the target goal, with email only as fallback."*
- And the general form: *"Enrichment appears sparse. I want enrichment to fill as many
  available fields that are confident as it can from the waterfall. Rich enrichment is the
  goal, not minimum enrichment."*
- The live instance that makes it concrete: a CREATE row with every field blank, where the
  round discovered `Head of Marketing and Content` and `seniority: Director` and kept neither.
- The cost argument inverts the usual one: asking for more fields is free on this provider
  mix. The expense is mapping work.

</specifics>

<deferred>
## Deferred Ideas

- **Making `phone` genuinely stale-refreshable** — needs a class change that D-66-08 forbids.
  If the operator later wants phone refresh, it is a governance decision of its own.
- **Buying verified direct dials** — `directPhone` is 400/unentitled on this account. An
  entitlement question, not an engineering one.
- **Extending the §29.1 `numberofemployees`-style exception to other native company fields** —
  explicitly not done here; each such exception is an operator ruling.

### Reviewed Todos (not folded)
- `2026-09-04-company-domain-has-no-candidate-source.md` — the companies merge lane's own
  producer gap (`domain` has no candidate source, so 260904-pav's correction mechanism has
  nothing to correct with). Adjacent to D-66-07's companies matrix and likely to be SURFACED
  by it, but not folded: it is a merge-correction question, not a chased-field question.
- `2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md` — Phases 64/65.
- `2026-09-04-skill-step8-routes-holds-into-a-queue-that-refuses-them.md` — Phase 69.

</deferred>

---

*Phase: 66-rich-enrichment-not-minimum-enrichment*
*Context gathered: 2026-09-05*
