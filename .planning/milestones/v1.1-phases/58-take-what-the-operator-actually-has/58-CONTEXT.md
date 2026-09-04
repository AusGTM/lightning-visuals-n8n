# Phase 58: Take What the Operator Actually Has - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Every input an operator holds for a **company** — a screenshot (website or search-results
page), a pasted block of text, a URL of any kind, a bare name with no domain — resolves to
something the backend can act on. When no usable domain is present, the system finds one and
**confirms it before writing** (a wrong domain poisons the dedupe anchor). A refusal is the
last resort and always names what would make it work. Closes INPUT-01..04
(`.planning/milestones/v1.1-REQUIREMENTS.md`).

Out of this phase: contact review-flag clearing (deferred to Phase 54), suggested contacts
(Phase 59), single-pass dispatch (Phase 54).

</domain>

<decisions>
## Implementation Decisions

### Who researches the domain
- **D-58-01:** **Claude proposes, backend verifies selectively.** Claude in-conversation
  proposes a domain from what it already knows/sees (free, instant, marked unverified). The
  backend's companies-branch `Claude Web Research` node runs **only** for rows Claude cannot
  confidently propose, or where the operator says "not sure, check it".
- **D-58-02:** **Operator confirmation substitutes for backend verification.** A domain the
  operator confirms in the table is written without a research call — consent is the gate,
  not a second model pass.
- **D-58-03:** A LinkedIn/profile URL may **seed research as input only** (company name,
  industry off the page). It is never passed through as a domain — the
  `NOT_A_COMPANY_DOMAIN` guard (mirrored Python↔JS) is unchanged. — **Reversibility:**
  one-way in spirit — weakening this guard re-opens the LinkedIn domain-poisoning defect the
  2026-08-25 walk found; any change needs an operator ruling.

### Confirm-before-write shape
- **D-58-04:** **Batch table with per-row control.** One table: company name, proposed
  domain, where it came from. One scoped approve covers the batch; the operator can
  pick/deny/correct individual rows first. Matches the existing pre-ingest
  match-proposal-confirm pattern and the bulk-approve-with-scope-restated rule. VOCAB-05
  consent binding applies: the affirmative answers this shown table, ambiguity = not armed.
- **D-58-05:** Evidence per row = **source + one-line reason** (e.g. "official site linked
  from their LinkedIn"). Evidence URL shown when the backend researched it. No full
  ProviderResult evidence block in the table.
- **D-58-06:** A **denied** proposal falls back to the 0.16.0 accept-by-name path: row
  proceeds with blank domain via name lookup / exact-name company search, disclosed in the
  report. The operator may instead type the correct domain in place. Denied never means
  dropped (INPUT-04).
- **D-58-07:** An **operator-typed** domain passes the existing syntax /
  `NOT_A_COMPANY_DOMAIN` / freemail guards only — no research pass. Operator is the
  highest-trust source (trust_rank 100, same as the review lane). The guard still refuses
  linkedin.com, gmail.com, etc. even from the operator.

### Research cost consent
- **D-58-08:** Backend domain research is **its own envelope line** — "domain research:
  N companies × ~$Y" — and names WHICH rows need it. Fits D-53-02 disclosure discipline and
  cost_guard's per-provider breakdown.
- **D-58-09:** Research is **default-on, declinable**: rows needing it are priced into the
  envelope automatically and the single batch yes covers it, unless the operator strikes the
  line (INPUT-02: the system finds one rather than asking the operator to).
- **D-58-10:** Declining the research line gives those rows the **same name-only fallback**
  as a denied proposal (D-58-06) — one consistent degradation path for every no-domain
  outcome.

### Company extraction contract
- **D-58-11:** Minimum identity for an extracted company row is **name alone**. Domain is
  desirable and researched when absent. Refuse only when there is literally nothing to act
  on.
- **D-58-12:** Extraction captures **enrichment seeds only** beyond name + domain: country,
  industry, website URL when the source shows them. The no-invention rule (Phase 35,
  `extraction.md`) applies verbatim: a field the source does not supply is left out; the
  waterfall fills the rest. No employee counts / revenue capture.
- **D-58-13:** **Mixed input runs one extraction pass, both lanes.** A paste/screenshot
  holding people AND companies is read once; contact rows flow the existing contact lane,
  company rows the new company lane, companies-first ordering (operator ruling 2026-08-25)
  preserved.
- **D-58-14:** Source types at parity with the contact lane: pasted text, foreign JSON,
  public URL, screenshots — plus two named explicitly: a **bare name list** (one per line /
  comma-separated) and a **search-results-page screenshot** (multiple candidate companies
  per image, each its own row with provenance).

### Claude's Discretion
- Exact table rendering, wording of the confirm question, and how "check it" requests are
  phrased — bound by VOCAB-01..03 (consequence language, no system vocabulary).
- Confidence heuristic for when Claude declines to propose and routes to backend research.
- Handling of an ambiguous company name matching two portal records (existing rule: two
  matches = ambiguity, not a match — extend, don't reinvent).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/milestones/v1.1-REQUIREMENTS.md` — INPUT-01..04 (this phase's closes), VOCAB-01..05 (wording constraints on every operator-facing turn)
- `.planning/milestones/v1.1-ROADMAP.md` § Phase 58 — goal, risk note (research priced + declinable), execution order ruling

### Extraction machinery (the template being extended)
- `operator-claude-plugin/skills/contact-upload/extraction.md` — Claude-as-extractor contract, no-invention rule, handoff-file protocol (D-01/D-02: no API calls, no OCR)
- `operator-claude-plugin/scripts/extraction.py` — structural validator (provenance, ambiguity-excludes-value)
- `operator-claude-plugin/tests/test_extraction_contract.py`, `test_extraction_handoff.py` — pins to extend, never delete

### Company lane as it exists
- `CLAUDE.md` §13.0.1 — contact→company association, company resolution order (domain, then name; two name matches = ambiguity), company creation lives only in `wf_enrichment_cloud` companies branch, domain-mandatory spec form
- `scripts/build_cloud_workflows.py` — sole author of n8n flows (never hand-edit `n8n/wf_*.json`); companies branch carries the `Claude Web Research` node and exact-name fallback (2026-08-25)
- `n8n/code/companyLink.js` — `NOT_A_COMPANY_DOMAIN` guard (JS half; Python mirror in plugin scripts)

### Consent, envelope, cost
- `.planning/phases/53-operator-openable-write-grant/53-CONTEXT.md` — D-53-01..05 (grant authority, envelope-as-disclosure D-53-02, client-held lifetime)
- `operator-claude-plugin` cost_guard / envelope modules — per-provider rate table, tri-state balance; intro Anthropic pricing expires 2026-08-31

### Walk evidence motivating this phase
- `.planning/quick/260825-contact-company-association/UAT.md` — the four walk gaps; two were input-shape defects (person named by name had nowhere to go; LinkedIn URL became a domain)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Contact-lane extraction adapters (`extraction.md` + `extraction.py`): the four source
  adapters, provenance schema, ambiguity list, handoff-file protocol — extend to company
  rows rather than writing a parallel system.
- Pre-ingest match-proposal-confirm lane: auto-matched / unmatched / confirmed states and
  the approve/deny/pick confirmation vocabulary — the confirm table reuses this pattern.
- `Claude Web Research` node (companies branch) + judge escalation: already returns
  evidence URLs; domain research is the same call shape.
- 0.16.0 accept-by-name path: name-only lookup + exact-name company search — the fallback
  target for denied/declined rows.

### Established Patterns
- Claude IS the extractor; scripts validate structure only (D-01/D-02).
- No-invention rule governs every adapter; a rejected row with a stated reason is a correct
  outcome.
- Workflows are generated by `build_cloud_workflows.py` and deployed+bounced; stored
  read-backs prove nothing (project memory).
- VOCAB-05: consent is an affirmative answering the shown proposal in the same turn;
  ambiguity resolves to not-armed; `dispatch()` raises without `armed`.

### Integration Points
- Company envelope spec form `{"companies": [{"name", "domain"}]}` — domain currently
  mandatory in the create path; name-only rows ride the accept-by-name lookup instead.
- Envelope/cost preview blocks (records / providers / cost / chunks) — the research line
  lands in the cost block.
- `wf_enrichment_cloud` companies branch — creation + dedupe stays there; this phase feeds
  it better-resolved inputs, it does not move creation.

</code_context>

<specifics>
## Specific Ideas

- Operator ruling (2026-08-25): "A blanket refusal is not useful because the operator does
  not want to research that" — refusals must name what would make the input work.
- The walk's LinkedIn-URL-became-a-domain defect is the concrete failure D-58-03 exists to
  keep closed.
- One consistent degradation path everywhere: any no-domain outcome (denied, declined,
  unresearchable) lands on accept-by-name with a blank domain, disclosed in the report.

</specifics>

<deferred>
## Deferred Ideas

- **Contact review-flag clearing lane** — contacts get flagged `lv_enrichment_needs_review`
  but no lane clears a contact flag. Operator ruled 2026-08-26: defer to **Phase 54**
  (rides with single-pass dispatch work). Recorded in STATE.md's open items.

</deferred>

---

*Phase: 58-take-what-the-operator-actually-has*
*Context gathered: 2026-08-26*
