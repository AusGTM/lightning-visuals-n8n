---
phase: "62"
slug: "suggest-the-contacts-nobody-named"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-02"
updated: "2026-09-04"
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

**Extended 2026-09-04** to cover plans 62-11 and 62-12, which landed after the 2026-09-02
audit and were not yet in this artifact. Same discipline: every `mitigate` threat checked
against a cited `file:line`, several live-reproduced rather than trusted from the SUMMARYs
alone (the required `company_domains` parameter was independently confirmed to raise
`TypeError` when omitted; the suffix-trap and subdomain fixtures were hand-traced against
`email_domain_relation`'s actual branches, not just read). Prior findings (62-01..62-10) are
untouched below.

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
| n8n executions API — the diagnosis artifact / the client's verdict list (62-11) | Stored execution payloads carry real contact data; a reader that silently returns a subset makes the client under-report what n8n actually produced | Row verdicts, run/item counts, provider `billing` blocks |
| repo `.env` — the diagnostic invocation (62-11) | `N8N_API_KEY` read into a short-lived process for a read-only executions-API walk | Bearer/API-key header, never echoed |
| provider response — a sendable row (62-12) | A provider resolving a weak `firstname+lastname+company` key can return a different person's contact details | Enriched email vs. the company's recorded domain |
| CRM `website`/`domain` property — the send-direction comparison baseline (62-12) | The company's recorded website decides who is sendable; a profile-host or absent value must fail closed | Domain strings only, no credential |
| JS freemail set (`n8n/code/companyLink.js`) — Python mirror (62-12) | Two engines classifying the same domain differently is a silent divergence | `FREEMAIL_DOMAINS` membership |

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
| 62-11:T-62-11-01 | Information Disclosure | `62-11-DIAGNOSIS.md` | high | mitigate | Read in full: rows named by `row_id`, only run/item counts and `Lusha Enrich` `billing` blocks quoted — no email/phone pasted (grep for `@`/phone patterns in the artifact confirms none). Regression fixture in `test_watch_settle_reporting.py:227-245` is explicitly SYNTHETIC (`row-a`/`row-b`), never a fetched payload | closed |
| 62-11:T-62-11-02 | Information Disclosure | API key in the inline invocation | high | mitigate | `executions_client.py:52-58` — every transport exception caught by bare `except Exception:` and re-raised as `ExecutionsClientError(...) from None`, discarding the original text (which can carry request headers); zero `N8N_API_KEY`/`Authorization`/`Bearer` string anywhere in the committed artifact (grep-confirmed) | closed |
| 62-11:T-62-11-03 | Tampering | the executions API | high | mitigate | `executions_client.get_execution` (`:108-114`) issues `requests.get` only, `includeData=true`; live-verified `git status --porcelain n8n/ scripts/build_cloud_workflows.py` silent | closed |
| 62-11:T-62-11-04 | Repudiation | under-reported async verdicts (the gap itself) | high | mitigate | `report.all_node_items` (`report.py:81-105`) concatenates every run; wired into `watch._build_response_rows` (`watch.py:415`) and `report_enrichment.enrichment_row_ledger` (`report_enrichment.py:144`); RED-before/GREEN-after tests quoted in `62-11-SUMMARY.md` and independently re-run green in this audit. **Synchronous-path instance of the same class is an explicit, named residual — see R-04** | closed with residual |
| 62-11:T-62-11-05 | Denial of Service | `all_node_items` | low | accept | See Accepted Risks Log AR-07 | closed (accepted) |
| 62-11:T-62-11-SC | Tampering | npm/pip/cargo installs | low | accept | See Accepted Risks Log AR-08 | closed (accepted) |
| 62-12:T-62-12-01 | Spoofing | `email_domain_relation` | high | mitigate | `suggest_contacts.py:427-486`; suffix-trap fixture (`x@romaturfclub.com.au.attacker.tld` vs `romaturfclub.com.au` → `mismatch`) hand-traced by this audit (`ed.endswith("." + cd)` correctly refuses — the string ends in `.attacker.tld`, not `.romaturfclub.com.au`) and pinned in `test_suggest_contacts.py:451`; subdomain-plus-`www` sendable case (`staff@mail.romaturfclub.com.au` vs `www.romaturfclub.com.au`) at `:449` | closed |
| 62-12:T-62-12-02 | Spoofing | hostile/profile-host CRM `website` value | medium | mitigate | `enrichment._clean_domain` (`enrichment.py:239-254`) returns `None` for any `NOT_A_COMPANY_DOMAIN` host; `email_domain_relation` (`suggest_contacts.py:478-480`) turns that into `company_domain_unknown` → held, never compared; pinned by `test_email_domain_relation_company_domain_unknown` (linkedin.com case) | closed |
| 62-12:T-62-12-03 | Elevation of Privilege | required `company_domains` parameter | high | mitigate | `def partition_for_dispatch(rows, company_domains):` (`suggest_contacts.py:519`), no default; **live-executed by this audit**: calling it with the second argument omitted raises `TypeError: partition_for_dispatch() missing 1 required positional argument: 'company_domains'` — not merely asserted, reproduced | closed |
| 62-12:T-62-12-04 | Information Disclosure | held-row reasons in the report | low | accept | See Accepted Risks Log AR-09 | closed (accepted) |
| 62-12:T-62-12-05 | Tampering | scope creep into `extraction.hold_emailless` | medium | mitigate | `extraction.py` absent from every commit this plan made (`git log` on the five 62-11/62-12 commits confirmed); `test_partition_for_dispatch_holds_the_stranger_hold_emailless_alone_would_send` (`test_suggest_contacts.py:417-439`) pins `hold_emailless` alone still returns the stranger sendable | closed |
| 62-12:T-62-12-06 | Denial of Service | `email_domain_relation` | low | accept | See Accepted Risks Log AR-10 | closed (accepted) |
| 62-12:T-62-12-SC | Tampering | npm/pip/cargo installs | low | accept | See Accepted Risks Log AR-11 | closed (accepted) |

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
| AR-07 | 62-11:T-62-11-05 | `all_node_items` (`report.py:81-105`) only concatenates items already present in an already-fetched execution payload's own `run_data[node_name]` list — no loop over anything caller-controlled, no I/O of its own, bounded by whatever the executions API already returned. | Plan author (62-11), confirmed by audit 2026-09-04 | 2026-09-04 |
| AR-08 | 62-11:T-62-11-SC | No package installed or considered; `requirements.txt`/`package.json` absent from every commit this plan made (git-log-confirmed). | Plan author (62-11), confirmed by audit 2026-09-04 | 2026-09-04 |
| AR-09 | 62-12:T-62-12-04 | A held-row reason names only the email's domain and the company's recorded domain, both already visible to the operator on the row and in HubSpot; the local part of the address is never included by `_relation_reason` (`suggest_contacts.py:489-516`). | Plan author (62-12), confirmed by audit 2026-09-04 | 2026-09-04 |
| AR-10 | 62-12:T-62-12-06 | `email_domain_relation` is pure string work: one `rsplit`, one frozenset membership test, two `_clean_domain` calls whose regexes are anchored prefix substitutions (`^https?://`, `^www\.`) with no backtracking risk. No I/O. | Plan author (62-12), confirmed by audit 2026-09-04 | 2026-09-04 |
| AR-11 | 62-12:T-62-12-SC | No package installed or considered — a public-suffix dependency was explicitly rejected (Decision 1). `requirements.txt`/`package.json` absent from every commit this plan made. | Plan author (62-12), confirmed by audit 2026-09-04 | 2026-09-04 |

*Accepted risks do not resurface in future audit runs.*

**All eleven are `low`/`medium` against `block_on: high`** — none would count toward `threats_open`
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
| R-04 | 62-11:T-62-11-04 | The under-reported-verdicts fix is scoped to the ASYNC recovery channel only, by explicit plan decision (62-11-PLAN.md Decision 4). `Respond to Webhook` still takes one run's items on the SYNCHRONOUS path; `preingest.rerequest_unanswered`, `enrich-records`, and `contact-upload`'s enrich pass all call `chunking.dispatch_plan` with `async_ack` defaulted `False` and are exposed to the identical row loss if a chunk splits at `Merge Winners`/`Merge Company`. Quantified live in `62-11-DIAGNOSIS.md` Q4 (`Respond to Webhook`'s own 3-run trace on `12096`/`12098`, first-arrival-wins). Fix needs a workflow-topology change through `scripts/build_cloud_workflows.py` plus an operator deploy — named as a standing UAT item, not attempted, per this phase's offline-only constraint. |
| R-05 | 62-11:T-62-11-04 | Same-class readers `62-11-DIAGNOSIS.md`'s `## Remaining exposure` names but does not fix: `report.contact_row_ledger`/`report._write_node_items` on `LV Contact Ingest (Cloud template)` (same `runs[0]`-only idiom, not walked with the same rigor as the enrichment workflow); `Merge Company` in the companies lane (structural mirror of `Merge Winners`, 3 inbound edges, no company row in the live batch so no live evidence it ever splits — `enrichment_row_ledger`'s fix benefits it automatically since the fix reads by node name); `Enrichment Gate` (5 inbound edges, upstream of `Merge Winners`, `runs=1` in all three examined executions, no current reader takes only `runs[0]` of it). None fixed, none live-evidenced as currently exploitable; named rather than silently left. |

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
| 2026-09-04 | 42 (29 + 13) | 42 (31 mitigate + 11 accepted) | 0 | gsd-security-auditor (ASVS L1, block_on: high) — extended for 62-11, 62-12 |

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

**2026-09-04 extension — verification method for 62-11/62-12.** Re-run independently by this
audit rather than trusted from the SUMMARYs: root suite `.venv/bin/python -m pytest -q` → 4112
passed / 154 skipped / 0 failed; plugin suite `python -m pytest operator-claude-plugin/tests/ -q`
→ 2365 passed / 5 skipped / 0 failed (matches 62-12-SUMMARY.md exactly); node suite
`node --test tests/n8n/*.test.mjs` → 867 pass / 0 fail (untouched, confirming zero backend
change); `git status --porcelain n8n/ scripts/build_cloud_workflows.py` silent. Two claims were
independently reproduced rather than read off the SUMMARY: (1) `partition_for_dispatch(rows)`
called with `company_domains` omitted raises `TypeError` (live-executed by this audit, not just
grepped for a missing default); (2) the suffix-trap and subdomain fixtures were hand-traced
through `email_domain_relation`'s actual `ed`/`cd` comparison, confirming the label-boundary
direction is correct (`ed.endswith("." + cd)`, not a bare substring test). The JS/Python
`FREEMAIL_DOMAINS` mirror was read on both sides (`n8n/code/companyLink.js:25-34`,
`enrichment.py:227-236`) and found byte-identical, and the comment-stripping parser fix
(`_js_set_members`, `test_people_and_url_normalisation.py:103-115`) was read and confirmed to
strip each line's `//` tail before joining, closing the gotcha the plan named. The quick-task
260904-447 bounded `html.unescape` fix (outside these two plans, landed the same day) was
checked per the dispatch's scope note: both `role_classify.py::_tokenize` and
`role_vocabulary.py::_normalize_title` bound the fixed-point loop at `MAX_UNESCAPE_PASSES = 5`
identically, a parity test (`test_both_trees_unescape_to_the_same_bounded_fixed_point`) pins the
two constants and their output equal, and the bound was confirmed to terminate in constant time
against a pathologically nested 20-generation input rather than spinning to a true fixed point —
not re-fixed, per the dispatch's instruction.

**Unregistered threat flags:** none. No SUMMARY carried a `## Threat Flags` section. The two
genuinely new pieces of attack surface — the `source_by_field` multipart part on
`dispatch.dispatch()` and the `num_associated_contacts` read — both map to registered threats
(T-62-16/17 and T-62-18/19). `62-11-SUMMARY.md` and `62-12-SUMMARY.md` both carry a
`## Threat Flags` section reading `None`; this audit independently checked for undocumented new
attack surface in both plans' diffs and found none beyond what the two plans' own threat
registers already name — `all_node_items` (T-62-11-05), `email_domain_relation`'s reason strings
(T-62-12-04), and the required-parameter change (T-62-12-03) are the only genuinely new
surfaces, and all three are registered.

**Implementation deviation noted outside the register:** 62-04 Task 2 widened `preingest.py`'s
`_KNOWN_OUTCOME_CONTRACT_VERSIONS` to `{1, 2}` — a file not in that plan's `<files>` list. This is
a compatibility widening on a response-parsing path (the client accepts two known-good wire
contract versions, not arbitrary input), not new attack surface, but it is the one deviation that
touched an unplanned file.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (AR-01 … AR-11)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
- [x] ASVS L1 short-circuit deliberately declined; auditor spawned and every mitigation verified against code
- [x] Residuals R-01 … R-03 named and scoped rather than absorbed into "closed"
- [x] 2026-09-04 extension: 62-11 and 62-12 threat registers verified against enforcing code,
  not documentation; required-parameter enforcement and suffix-trap direction independently
  live-reproduced by this audit
- [x] Residual R-04 (synchronous-path row loss, named not fixed, scoped by 62-11 Decision 4) and
  R-05 (sibling readers named in `62-11-DIAGNOSIS.md`'s Remaining exposure, not live-evidenced)
  recorded rather than silently dropped
- [x] `threats_open: 0` reconfirmed after the extension

**Approval:** verified 2026-09-02; extended 2026-09-04 (62-11, 62-12)
