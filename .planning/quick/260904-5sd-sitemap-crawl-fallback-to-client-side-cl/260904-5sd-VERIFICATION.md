---
quick_id: 260904-5sd
verified: 2026-09-03T19:30:02Z
status: passed
score: 11/11 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Quick Task 260904-5sd: web-search fallback — Verification Report

**Goal:** when the sitemap-based website crawl cannot find persons for suggest-contacts, fall
back to client-side Claude web search results, with priority given to authoritative and
industry websites and LinkedIn.

**Verified:** 2026-09-03T19:30:02Z (UTC) · **Status:** passed · **Re-verification:** No — initial

Method: every truth was probed by **executing the real module in-process**, not by reading the
SUMMARY or by trusting the executor's own tests. The executor's tests were then read to confirm
they assert the same thing and drive real code rather than mocks.

## Goal Achievement

### Observable Truths

| # | Truth (from `must_haves.truths`) | Status | Evidence |
|---|---|---|---|
| 1 | A `refused` disposition anywhere never reaches the search path (D-5sd-04) | ✓ VERIFIED | Direct probe of `eligible_after_ladder`: `[empty, refused]`, `[refused, empty]`, `[refused]` and `[empty, unknown, refused]` all return `eligible=False`. Order-free — the refusal check (`search_fallback.py:212`) precedes the eligible-vocabulary check and runs on every entry. |
| 2 | Clean-but-empty AND cap-exhausted both reach it (D-5sd-06) | ✓ VERIFIED | `[empty]` → True; `[cap_exhausted]` → True; `[empty, empty, cap_exhausted]` → True. `ELIGIBLE_DISPOSITIONS = ("empty", "cap_exhausted")` at `:74`. |
| 3 | Unknown / absent / unreadable disposition is INELIGIBLE — fail-closed, never a raise (D-5sd-06) | ✓ VERIFIED | `[{"url": …}]` (no key) → `eligible=False`, reason `"carries no readable disposition (None)"`, **no exception**. `disposition: "wat"` → False. Non-list `attempts` → False. An entry that is not a dict → False. All eleven malformed inputs probed; zero raises. |
| 4 | An empty `attempts` list is INELIGIBLE, saying nothing establishes the crawl completed | ✓ VERIFIED | `[]` and `None` → `"no ladder attempt was recorded, so nothing establishes that the crawl completed"` (`:192-199`). |
| 5 | Only rank 1/2 sendable; a rank-3 row is collected, ranked, shown, but ALWAYS held with its source URL in the reason (D-5sd-05) | ✓ VERIFIED | `hold_weak_sources` probe: tier-3 record in `sendable` moved to `held` with `reason_code: "search_source_not_strong"` and the locator quoted verbatim in the reason. Tier 1 and tier 2 stayed sendable. No path exists to promote a tier-3 row — the `continue` at `:405-406` is gated on `tier in STRONG_TIERS = (1, 2)`. |
| 6 | The tier gate and the waterfall gate are independent and BOTH must hold | ✓ VERIFIED | `test_the_tier_gate_and_the_waterfall_gate_are_independent_and_both_must_hold` and the composition round both assert `partition_for_dispatch` alone sends BOTH people (identical successful merge, identical related-domain email, `held == []`), then `hold_weak_sources` holds only the rank-3 one. Two separate functions, neither aware of the other; `partition_for_dispatch` is byte-unchanged (0 deletions in its source region). |
| 7 | A host on no tier is REJECTED with a reason naming it — not ranked last (D-5sd-02 tier 4) | ✓ VERIFIED | Probe: `https://randomsite.tld/x` → `rejected`, reason `"randomsite.tld is on no tier of the committed source allowlist — an unlisted source is rejected outright, never ranked last (D-5sd-02)."` Never appears in `accepted`. |
| 8 | `linkedin.com.attacker.tld` and `example.com.attacker.tld` rejected; a real subdomain of a listed host accepted | ✓ VERIFIED | Both traps → REJECT (host on no tier). `board.example.com` → tier 1; `au.linkedin.com` → tier 2; `sub.racingaustralia.horse` → tier 3. Apex↔`www` accepted in **both** directions. Matcher is `host == listed or host.endswith("." + listed)` (`:251`) over `url_fallback._canonical_authority` (netloc, casefolded, one `www.` label). Extra probes: `linkedin.com@evil.tld` and `linkedin.com:443` both REJECT (over-rejects — fails safe). |
| 9 | A ladder-sourced record's send-vs-hold behaviour is byte-identical to before | ✓ VERIFIED | `synthesise_rows(...)` with no `source_tier` returns provenance `{"input": "suggest_contacts_ladder", "locator": …}` — two keys, no extra. `hold_weak_sources` `continue`s on any record whose `provenance.input != SEARCH_INPUT` before reading anything else (`:390-391`); probe confirms `after_sendable == sendable`, `after_held == held`. `test_suggest_contacts.py` diff is **+133 / −0** — no pre-existing assertion was edited. |
| 10 | `partition_for_dispatch` keeps its required `company_domains` argument and its suffix-trap refusal | ✓ VERIFIED | Live: signature is `(rows, company_domains)`; calling with one arg raises `TypeError`; `x@example.com.attacker.tld` against `example.com` is held `email_domain_mismatch`. Source diff for `suggest_contacts.py` touches only `synthesise_rows` and the `no_candidates` docstring — zero lines inside `partition_for_dispatch`. |
| 11 | Plugin suite ≥ 2365/5 baseline; root and node suites unchanged; `n8n/` zero diff | ✓ VERIFIED | Plugin suite run here: **2430 passed, 5 skipped**. `git diff --numstat 385ced4..245a327 -- tests/ n8n/ src/ scripts/ config/` is **empty** — no root-repo source or test file changed, so the root and node suites are unchanged by construction (stronger than a re-run). `git diff --stat … -- n8n/` empty. |

**Score:** 11/11 truths verified (0 present-behaviour-unverified, 0 overrides).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `operator-claude-plugin/scripts/search_fallback.py` | 3 pure decisions + 2-verb CLI | ✓ VERIFIED | 490 lines. `eligible_after_ladder`, `rank_results`, `hold_weak_sources`, `load_sources`, `SourceAllowlistError`, `MAX_FALLBACK_SEARCHES = 3`, `for/enumerate` argv scan (no `while`). Imported and exercised by both SKILL.md's block and two test modules. |
| `operator-claude-plugin/config/source_allowlist.yaml` | committed ranked list | ✓ VERIFIED | Header states operator-curated / `[ASSUMED]` / tier-4-is-rejection. `linkedin.com` **alone** at tier 2; 17 tier-3 hosts each with a one-line justification. RESEARCH.md's two *(placeholder — do not ship)* rows (`austrac…`, `commbank…`) are absent. Parses through `load_sources()`. |
| `operator-claude-plugin/tests/test_search_fallback.py` | full behaviour coverage | ✓ VERIFIED | 53 tests, all passing. Covers every bullet of the plan's behaviour block, both suffix traps, the fail-closed disposition, the shipped-config contract, both CLI verbs in subprocess, and the AST purity + no-`while` guards. |
| `.planning/todos/pending/2026-09-04-website-less-company-search-fallback.md` | deferred case filed | ✓ VERIFIED | 61 lines; names `suggest_contacts.py:143-152` as the terminal, records the case as deliberately scoped out. |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| SKILL.md step 5 | `search_fallback.py --eligible` / `--rank` | documented CLI verbs, fetch only `accepted[]` in rank order | ✓ WIRED — both verbs present in SKILL.md and both work in subprocess (`test_the_cli_agrees_with_the_in_process_function`) |
| accepted URL | existing `select_people` / `synthesise_rows` path | step 8's single python block; no second dispatch path | ✓ WIRED — the block reuses the round's one sink `suggest_contacts.round_artifact`; the registry proves exactly ONE `suggest-contacts` python block exists |
| `synthesise_rows(..., source_tier=N)` | `provenance.source_tier` → `hold_weak_sources` | record key, never a row key | ✓ WIRED — probed live; `extraction.validate` accepts the extra key (composition test asserts `provenance["input"] == "suggest_contacts_web_search"` on the accepted record) |
| SKILL.md block's call tuple | `COVERED` key in `test_skill_sequence_coverage.py` | shrink-only ratchet, zero grandfather budget | ✓ WIRED — derived tuple matches the registry exactly; `GRANDFATHERED_UNCOVERED == {}` and `MAX_GRANDFATHERED == 0` unchanged |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|---|---|---|---|
| Full plugin suite | `../.venv/bin/python -m pytest tests/ -q` | 2430 passed, 5 skipped in 11.28s | ✓ PASS |
| Plan Task 2 `<verify>` one-liner | signature + amendment + todo assertions | `Task2 verify OK` | ✓ PASS |
| Plan Task 3 `<verify>` one-liner | one block, three `search_fallback` calls, sink, ratchet, tokens | `Task3 verify OK` | ✓ PASS |
| `eligible_after_ladder` × 13 inputs | in-process probe | matches the truth table, zero raises | ✓ PASS |
| `rank_results` × 15 URLs | in-process probe | traps rejected, tiers correct, check order correct | ✓ PASS |
| `hold_weak_sources` × 6 records | in-process probe | rank-3 held, rank-1/2 sendable, ladder untouched, `held` re-sorted by index, no duplicate hold | ✓ PASS |
| `partition_for_dispatch` suffix trap | in-process probe | `email_domain_mismatch` on `example.com.attacker.tld` | ✓ PASS |
| `synthesise_rows` bad tiers | `1.0`, `True`, `"2"`, `0`, `4`, `[2]` | all six refused with `ValueError` naming the value | ✓ PASS |

### Requirements Coverage

| Decision | Status | Evidence |
|---|---|---|
| D-5sd-01 both gates | ✓ SATISFIED | Truth 6; `partition_for_dispatch` untouched, `hold_weak_sources` is a second independent pass |
| D-5sd-02 ranked allowlist, tier 4 = rejection | ✓ SATISFIED | Truths 7, 8; committed YAML; `_tier_of` returns `(None, None)` → reject |
| D-5sd-03 bounded, not priced in | ✓ SATISFIED | `MAX_FALLBACK_SEARCHES = 3` with the pricing ruling in its comment; SKILL.md step 5 states it and that the Lusha credit stays inside the ceiling |
| D-5sd-04 refusal terminal, not-found opens | ✓ SATISFIED | Truth 1; `no_candidates` docstring corrected; SKILL.md's "Do not escalate past a TOOL-LEVEL REFUSAL" paragraph retained and narrowed |
| D-5sd-05 strong stops at rank 2 | ✓ SATISFIED | Truths 5, 6; see the deviation judgement below |
| D-5sd-06 cap exhaustion eligible, fail-closed | ✓ SATISFIED | Truths 2, 3; SKILL.md carries the `cap_exhausted` append instruction, without which the signal has no source |
| Amendment recorded where D-62-03 lives | ✓ SATISFIED | 26-line blockquote directly beneath D-62-03 rev 2 in `62-CONTEXT.md`; states the principle survives and that wholesale overturn was offered and declined |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | none | — | No `TBD` / `FIXME` / `XXX` / `HACK` / stub marker in any of the eight touched files. (`_PLACEHOLDER_RE` in `test_skill_sequence_coverage.py:36` is pre-existing regex machinery, not a debt marker — that file's diff is +20/−0 and touches only the `COVERED` entry.) |
| `search_fallback.py` | 321, 345 | `rank_results` output strings say "tier" | ℹ️ INFO | These are ranker-internal JSON fields (`accepted[].why`, `rejected[].reason`). SKILL.md never instructs surfacing them to the operator — step 9's report quotes the **held row's** prose reason, which says "rank". The D-10b guard scans `skills/` only and passes. Not a gap. |
| `url_fallback._canonical_authority` | 124 | uses `netloc`, so a port or userinfo travels with the authority | ℹ️ INFO | Probed: `linkedin.com:443` and `linkedin.com@evil.tld` both REJECT. Over-rejection, i.e. fails safe. Pre-existing behaviour, deliberately reused rather than re-derived. |

## Deviation Judgement — the `tier` / `rank` vocabulary split

**Verdict: the split satisfies D-5sd-05. Not a gap, not a warning.**

D-5sd-05's operational requirement is substantive, not lexical: *"the hold pile is where they
belong, **with the source URL in the reason so the operator can judge**."* The shipped hold
reason (`search_fallback.py:420-426`) reads:

> named by https://racenet.com.au/2019/committee — a third-party source (source rank 3), not
> this company's own site or LinkedIn, so this person is held for you to judge rather than
> sent. An industry site can name someone historically: the person can be real and the
> enrichment confirmation genuine, and the role still stale (D-5sd-05).

That gives the operator the URL, the source class, why it is weak, and the failure mode to
judge against. Every element D-5sd-05 asked for is present. The noun changed; nothing the
decision required did.

Three further points make this the right resolution rather than a tolerated one:

1. **The guard is pre-existing, shipped, and correct.** `test_report_enrichment.py::test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder` bans `icp`/`tier` from every file under `skills/` because in this system "tier" means the **ICP** tier (D-10b). Its docstring states its single exemption is by name and *"not a general allowance for any future skill."* Widening it would have been the wrong fix.
2. **"Rank" is arguably clearer, not merely compliant.** Showing an operator "source tier 3" in a portal where `lv_icp_tier` exists invites exactly the confusion D-10b was written to prevent.
3. **The split is documented at both ends**, so a reviewer cannot "fix" it: `search_fallback.py:414-419` explains why the operator-visible string differs from the internal name, and SKILL.md names the fifth argument `source_rank` in prose while passing it positionally into `source_tier`.

Internal naming (`source_tier`, `STRONG_TIERS`, `provenance.source_tier`, `SEARCH_SOURCE_TIERS`)
is unchanged, exactly as the plan specified, and none of it is operator-facing.

## Gaps Summary

None. All eleven must-have truths hold under direct execution of the shipped code, not merely
under the executor's own tests. The two limits the plan accepted in advance — transcription
fidelity is unverifiable offline, and a mis-stamped provenance fails OPEN — are stated in the
docstrings that carry them (`rank_results`, `hold_weak_sources`) and in the plan's threat
register with disposition `accept`; they are known ceilings, not gaps, and are not routed to
human verification because no must-have claims otherwise.

Working tree carries one unrelated modified file
(`.planning/todos/pending/2026-09-04-provenance-aware-manual-protected.md`), correctly left
uncommitted and outside this task's scope, as the SUMMARY records.

---

_Verified: 2026-09-03T19:30:02Z (UTC)_
_Verifier: Claude (gsd-verifier)_
