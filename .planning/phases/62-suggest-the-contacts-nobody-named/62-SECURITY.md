---
phase: "62"
slug: "suggest-the-contacts-nobody-named"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-02"
---

# Phase 62 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register authored at plan time (all six PLAN files carried a `<threat_model>` block), so this
audit verified declared mitigations rather than building a register retroactively.

**The ASVS L1 short-circuit was deliberately NOT taken.** With `threats_open: 0` at grep level
and a plan-time register, the workflow permits skipping the auditor. This phase had already
produced one mitigation that was described in a plan and existed **only as SKILL.md prose** —
see the CR-01 note below — which a grep-level pass would have counted as closed. The auditor was
spawned and every `mitigate` threat was verified against enforcing code or a test, with live
execution used wherever a mitigation had a broken history.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| fetched page content → row synthesis | Page HTML and sitemap XML are attacker-influenceable | Names, titles, URLs entering a row that may become a HubSpot write |
| sitemap-derived URL → `web_fetch` | A page can list any URL it likes | Candidate URLs, gated scheme → host → budget |
| live HubSpot portal → `scripts/role_vocabulary.py` | Credentialled bulk read of every contact `jobtitle` | Employment data (read-only) |
| clustered titles → Anthropic Haiku | Portal job titles leave the portal for one clustering call | Distinct title strings + counts only |
| committed vocabulary cache → operator menu | The YAML decides what an operator believes recurs in their CRM | Role families + evidence status |
| operator config → grant arithmetic | `per_company_cap` and batch company count decide how much credit a yes authorises | Operator-supplied integers |
| n8n executions list → sampled headroom | Remaining monthly allowance sampled from a list the plugin does not own | Execution counts |
| ingest webhook envelope → `Merge Contacts` | Round-level source map decides written provenance | Provenance labels (header-authenticated) |
| HubSpot company search → row → response projection | Portal data crossing into a spend decision | `num_associated_contacts` (read-only rollup) |
| operator → LLM orchestrator → `synthesise_rows` | The per-company cap is spoken by a human and threaded by an LLM | An integer that becomes real Lusha credit |
| round → provider waterfall | Every emitted row becomes a stage-2 provider credit | ~1 Lusha credit per contact |

---

## Threat Register

**⚠ ID collision — threat IDs are phase-local and 62-06 reuses 62-01's.** `T-62-01`–`T-62-04`
name *different* threats in `62-01-PLAN.md` and `62-06-PLAN.md`. Every row below is disambiguated
`{plan}:{id}`. A bare grep for `T-62-01` returns the wrong threat half the time. **Recommendation:
adopt a plan-scoped scheme (`T-62.06-01`) for future phases.**

| Threat ID | Category | Component | Severity | Disposition | Mitigation (verified) | Status |
|-----------|----------|-----------|----------|-------------|------------------------|--------|
| 62-01:T-62-01 | Tampering | `synthesise_rows` | high | mitigate | `suggest_contacts.py:255-256` asserts row keys ⊆ `canonical_props()`; second stop `extraction.py:901` STRUCT-01 `raise` | closed |
| 62-01:T-62-02 | Elevation of Privilege | `next_candidates` / sitemap URLs | high | mitigate | `url_fallback.py:105-155` scheme→host→budget, called unmodified at `suggest_contacts.py:287-295`; off-host refusal test passes | closed |
| 62-01:T-62-03 | Denial of Service (budget) | per-company ladder walk | medium | mitigate | `MAX_FOLLOWUP_FETCHES` bound; per-company reset proven by `test_company_budget_resets_between_two_companies_in_one_round` | closed |
| 62-01:T-62-04 | Information Disclosure | test fixtures | low | mitigate | All phase-62 fixtures use `example`-suffixed hosts and synthetic names (grep-confirmed, no exception) | closed |
| 62-01:T-62-05 | Spoofing | a page claiming a person | medium | accept | See Accepted Risks Log AR-01 | closed (accepted) |
| 62-02:T-62-06 | Elevation of Privilege | `role_vocabulary.py` writing to portal | high | mitigate | `scripts/role_vocabulary.py:84-93` sole HTTP call is a search read; zero `.patch(`/`.put(` in file; `_portal_ok()` (`:80-81`) exits 1 with no API call on mismatch | closed |
| 62-02:T-62-07 | Information Disclosure | titles sent to Anthropic | medium | mitigate | `role_vocabulary.py:126` payload is `{"titles": distinct_titles}`; no name/email/record-id field exists in the module | closed |
| 62-02:T-62-08 | Tampering | un-evidenced list rendered as portal-derived | high | mitigate | `role_classify.py:43-68` returns `evidenced` alongside `families`, never the list alone; `offer_block()` (`:71-88`) emits the disclosure sentence; shipped YAML reads `evidenced: false` at document and every family level | closed |
| 62-02:T-62-09 | Spoofing | model inventing a family | medium | mitigate | System prompt (`:65-73`) forbids unseen members; `rank_top_families` (`:139`) drops any member absent from sampled counts — a backstop independent of the prompt | closed |
| 62-02:T-62-10 | Denial of Service (budget) | unbounded portal sweep | low | accept | See Accepted Risks Log AR-02 | closed (accepted) |
| 62-03:T-62-11 | Denial of Service (budget) | round spending past monthly allowance | high | mitigate | `write_grant.py:500-523` adds suggestion weight to `executions` **before** `ceiling_verdict` at `:536`, so Phase 57's `CEILING_OVER` refusal-before-start fires on it | closed |
| 62-03:T-62-12 | Tampering | unmeasured stage-1 rate rendered as $0 | high | mitigate | `cost_guard.py:280-293` — null rate → `unmeasured`, `cost_usd` None, text "dollar cost not measured"; no `$0` substring in the function; `cost_rates.json` value confirmed `null` | closed |
| 62-03:T-62-13 | Repudiation | figure key collision | medium | mitigate | `write_grant.py:475-499`, `:564` — `suggestion_allowance` a distinct third key; tests pin `chunk_ceiling` int and `ceiling` dict | closed |
| 62-03:T-62-14 | Elevation of Privilege | allowance silently widening a yes | high | mitigate | Blocking `checkpoint:decision` answered `one-envelope` by the human operator (`62-03-SUMMARY.md:129`); disclosure at `write_grant.py:633-636` states worst-case and "Unspent allowance is simply not spent" | closed |
| 62-03:T-62-15 | Information Disclosure | provider balances in fixtures | low | accept | See Accepted Risks Log AR-03 | closed (accepted) |
| 62-04:T-62-16 | Spoofing | caller mislabelling provider data | medium | mitigate | Ingest `Webhook Trigger` confirmed `authentication: headerAuth`; `mergeContacts.js:205` writes `resolvedSource` only into the provenance entry — `_gate()` (`:207`) never receives it, so the map cannot change which fields promote | closed |
| 62-04:T-62-17 | Tampering | source map leaking onto ordinary CSV uploads | high | mitigate | `build_cloud_workflows.py:292-304` try/catch returns `{}` on any failure; node tests assert the absent case is byte-identical to today's CSV behaviour and that a missing `Set Config` fails closed | closed |
| 62-04:T-62-18 | Repudiation | unread contact count read as a real zero | high | mitigate | `build_cloud_workflows.py:2188`, `:4760` stamp `null` explicitly; `suggest_contacts.py:50-56` branches `count is None` → UNKNOWN **before** magnitude | closed |
| 62-04:T-62-19 | Elevation of Privilege | a read-field addition becoming a write | high | mitigate | `num_associated_contacts` appears only in search bodies (`:2160`, `:5016`) and a response projection (`:4760`); the three carrying nodes confirmed named `Search`/`Fetch`, not update nodes | closed |
| 62-04:T-62-20 | Denial of Service | regenerated workflow deployed unreviewed | medium | accept | See Accepted Risks Log AR-04. *Register text said `mitigate`; its rationale is an accept and is recorded as one.* | closed (accepted) |
| 62-05:T-62-21 | Elevation of Privilege | fetching a URL nobody approved | high | mitigate | Candidate-generation bound is code (`url_fallback.py:105-155`). **Partly prose — see Residual R-01.** | closed with residual |
| 62-05:T-62-22 | Tampering | proposed person becoming a silent write | high | mitigate | `suggest_contacts.py` holds no HTTP client (grep-confirmed); composition test proves a held row is never validated and never reaches dispatch | closed |
| 62-05:T-62-23 | Denial of Service (budget) | round spending past what was agreed | high | mitigate | Cap and fetch bound both code-enforced and live-probed. **Step 9 reporting is prose — see Residual R-03.** | closed with residual |
| 62-05:T-62-24 | Information Disclosure | real person in a fixture | medium | mitigate | Composition fixtures use `example-club.example` and invented names (grep-confirmed) | closed |
| 62-05:T-62-25 | Spoofing | page misattributing a person | medium | accept | See Accepted Risks Log AR-05 | closed (accepted) |
| 62-06:T-62-01 | Denial of Service (resource) | `synthesise_rows` cap slice | high | mitigate | **Live-executed probe:** refuses `None`/`-1`/`"2"`/`True`/float/list/dict/`inf`; accepts `0`→`[]` and positive ints. Independently reproduced, not inherited from the review transcript | closed |
| 62-06:T-62-02 | Elevation of Privilege | chosen cap vs `priced_cap` | high | mitigate | **Live-executed probe:** `agreed_cap` refuses over-priced naming both numbers, refuses unpriced/malformed. `SKILL.md:170-172` binds the **return value**, not a literal. **See Residual R-02.** | closed with residual |
| 62-06:T-62-03 | Tampering | grant figures with no `suggestion_allowance` | medium | mitigate | Live probe: `agreed_cap(2, {})`, `(2, {"suggestion_allowance": None})`, `(2, None)` all refuse "never priced" — never falls back to `PRICED_CAP` at spend time | closed |
| 62-06:T-62-04 | Information Disclosure | refusal messages | low | accept | See Accepted Risks Log AR-06 | closed (accepted) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale (verified against code) | Accepted By | Date |
|---------|------------|-----------------------------------|-------------|------|
| AR-01 | 62-01:T-62-05 | A page claiming a person who does not work there is out of this module's reach. The row lands as a **proposal** through the existing match/held gates, never a silent write; `suggest_contacts.py` has no HTTP client, and every row passes `partition_for_dispatch` → `extraction.validate()`. The fetched URL travels as the row's provenance locator so the operator can check the claim's source. | Plan author (62-01), confirmed by audit 2026-09-02 | 2026-09-02 |
| AR-02 | 62-02:T-62-10 | The portal sweep is paged, read-only and manually invoked — no cron or scheduler wiring for `role_vocabulary.py` exists anywhere in the phase. HubSpot search reads are free, and this repo already runs the identical idiom for `lv_org_type`. | Plan author (62-02), confirmed by audit 2026-09-02 | 2026-09-02 |
| AR-03 | 62-03:T-62-15 | No new balance surface: `suggestion_line()` never calls `cost_guard.fetch_balances`. Balances are the pre-existing envelope mechanism, untouched by this phase. | Plan author (62-03), confirmed by audit 2026-09-02 | 2026-09-02 |
| AR-04 | 62-04:T-62-20 | This phase regenerates and **commits** workflow JSON only; deployment and arming are explicitly out of scope and remain an operator action, matching Phase 61's disarmed-only close. `git status` on `n8n/wf_*.json` is clean and no SUMMARY names a deploy or arm. **Consequence to carry: the committed JSON is now ahead of the live n8n instance** (missing `num_associated_contacts` and `sourceByField`). Recorded in CLAUDE.md §13.0.2. | Plan author (62-04), confirmed by audit 2026-09-02 | 2026-09-02 |
| AR-05 | 62-05:T-62-25 | A page misattributing a person is out of the system's reach. Mitigated by the proposal-not-creation guarantee and by the fetched URL travelling as the row's provenance locator (`suggest_contacts.py:262-266` sets `provenance.locator = fetched_url` on every row). | Plan author (62-05), confirmed by audit 2026-09-02 | 2026-09-02 |
| AR-06 | 62-06:T-62-04 | `CapRefused` messages name only two integers (chosen and priced) and no secret. Confirmed by live probe of every refusal string. The plugin holds no HubSpot credential and this phase adds none. | Plan author (62-06), confirmed by audit 2026-09-02 | 2026-09-02 |

*Accepted risks do not resurface in future audit runs.*

**All six are `low`/`medium` against `block_on: high`** — none would count toward `threats_open`
even under the strictest reading where an unlogged accept counts as open.

---

## Residuals

Named rather than hidden. **None blocks** — each matches its declared mitigation's own stated
scope and none contradicts what was promised.

| ID | Threat | What is actually enforced, and what is not |
|----|--------|---------------------------------------------|
| R-01 | 62-05:T-62-21 | Candidate **generation** is code-bound (`url_fallback.py:105-155`, scheme→host→budget, live-verified). Operator approval, fetch-in-shown-order, and the no-search-engine-escalation rule are SKILL.md text pinned only by a text-presence grep. No code fix exists without giving `suggest_contacts.py` an HTTP client — which is itself the control this module's purity is built on. `62-VERIFICATION.md`'s human-verification items 1–2 are the correct acceptance test. |
| R-02 | 62-06:T-62-02 | `agreed_cap` → `synthesise_rows` is bound in the documented SKILL.md sequence and driven by a composition test, but nothing at the Python call boundary forces a caller through `agreed_cap` first — `synthesise_rows(cap=10**9)` still accepts (live-confirmed). The sequence-coverage ratchet checks call **order**, not dataflow identity. Rated informational by two prior independent reviews (`62-REVIEW-GAP.md` IN-01, `62-VERIFICATION.md`); this audit concurs on independently reproduced evidence. |
| R-03 | 62-05:T-62-23 | The caps themselves are code-enforced and live-probed. Step 9's "report actuals against the quoted ceiling" is prose — it relies on the orchestrating assistant actually doing the reporting. |

### Why this phase's residuals are stated so precisely

Phase 62 shipped a mitigation that its own plan described as enforced and that existed **only as
SKILL.md prose**: "a cap above the grant's priced cap is refused, naming the number." No code
compared the two, and `synthesise_rows` sliced with a bare `people[:per_company_cap]`, so
`per_company_cap=None` silently uncapped the round. It passed a green 3,929-test suite and was
caught by adversarial code review (CR-01) and independently reproduced by the verifier. Plan
62-06 exists solely to close it.

The lesson is recorded here because it is the reason this audit refused the L1 short-circuit:
**a mitigation described in a plan is not evidence.** R-01 and R-03 are prose-dependent by
necessity, not by oversight — and they are labelled as such rather than counted as code.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-02 | 29 | 29 (23 mitigate + 6 accepted) | 0 | gsd-security-auditor (ASVS L1, block_on: high) |

**Verification method.** Every `mitigate` threat checked against a `grep`/`Read` match at a cited
`file:line`; threats with a documented history of a broken mitigation (the whole 62-06 register
plus T-62-14's disclosure sentence) were **re-executed live** rather than trusted from the earlier
review transcripts. Suites re-run independently by the auditor: `.venv/bin/python -m pytest -q` →
3929 passed / 154 skipped / 0 failed; `node --test tests/n8n/*.test.mjs` → 862 pass / 0 fail;
targeted phase-62 files → 101 passed (66 Python + 35 Node).

**Domain invariants re-confirmed independently:** no plugin script holds a HubSpot credential
(`scripts/role_vocabulary.py` sits at repo root, outside `operator-claude-plugin/`); no
Lusha-Prospecting call anywhere in phase-62 files; no `web_fetch` in any backend n8n code;
`git status` on `n8n/wf_*.json` clean — nothing pending, nothing armed.

**Unregistered threat flags:** none. No SUMMARY carried a `## Threat Flags` section. The two
genuinely new pieces of attack surface — the `source_by_field` multipart part on
`dispatch.dispatch()` and the `num_associated_contacts` read — both map to registered threats
(T-62-16/17 and T-62-18/19).

**Implementation deviation noted outside the register:** 62-04 Task 2 widened `preingest.py`'s
`_KNOWN_OUTCOME_CONTRACT_VERSIONS` to `{1, 2}` — a file not in that plan's `<files>` list. This is
a compatibility widening on a response-parsing path (the client accepts two known-good wire
contract versions, not arbitrary input), not new attack surface, but it is the one deviation that
touched an unplanned file.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (AR-01 … AR-06)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
- [x] ASVS L1 short-circuit deliberately declined; auditor spawned and every mitigation verified against code
- [x] Residuals R-01 … R-03 named and scoped rather than absorbed into "closed"

**Approval:** verified 2026-09-02
