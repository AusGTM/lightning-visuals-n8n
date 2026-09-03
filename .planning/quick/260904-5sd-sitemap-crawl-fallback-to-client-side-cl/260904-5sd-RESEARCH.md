# Quick Task 260904-5sd — Web-search fallback for suggest-contacts — Research

**Researched:** 2026-09-04
**Domain:** operator-claude-plugin (client-side skill + pure Python modules), plugin→n8n enrichment seam
**Confidence:** HIGH on the repo facts (all `file:line` verified by reading this session); MEDIUM on the tier-3 domain proposals (curation input, tagged `[ASSUMED]`)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-5sd-01 — Disposition: sendable if a strong source agrees AND enrichment validates**

> a search-sourced person MAY become sendable — it is not unconditionally held — but only when **both** hold:
> 1. the result comes from a **strong source** per the D-5sd-02 ranking, and
> 2. it is **validated through the existing enrichment machinery** (the Lusha search-and-enrich waterfall), which is the operator's stated mechanism: *"can be validated using the enrichment machinery e.g. Lusha"*.
>
> A weaker source, or a person the waterfall cannot confirm, is **held**, not sent.
>
> **How to apply:** the existing G-62-7 email-domain relatedness rule and the emailless hold still apply on top — this decision ADDS a gate, it never removes one. Do not weaken `partition_for_dispatch`'s required `company_domains` argument or its suffix-trap refusal. Note the standing gating boundary from quick task 260904-5a8: `match.tier` is what `preingest.py` → `confidence.py` → `held_queue.py` gate on, so anything this task writes into a match verdict changes send-vs-hold behaviour and must be deliberate.

**D-5sd-02 — Source priority: an explicit ranked allowlist, curated and committed**

> the priority rule is an **explicit ranked allowlist in committed config**, following the `FREEMAIL_DOMAINS` precedent (a committed list, mirrored where needed, pinned by a parity test). Ranking, highest first:
> 1. the company's own host
> 2. LinkedIn
> 3. a named list of racing/sport industry bodies and known industry media
> 4. everything else — **rejected, not merely ranked last**
>
> **How to apply:** rejection of an unlisted source is part of the rule, not an oversight — an unknown domain contributes nothing. Keep the list in config, not hard-coded in a function.

**D-5sd-03 — Cost: not priced into the SUGGEST-05 ceiling, but still bounded**

> client-side Claude web search spends no provider credit and no separately-billed API tokens, so it is **not priced into the per-company ceiling**. It is still **bounded by a named cap on the number of searches**, mirroring `MAX_FOLLOWUP_FETCHES`.
>
> **How to apply:** SUGGEST-05's invariant ("a round may spend LESS than the priced cap; it may never spend more") continues to hold for everything it currently covers — this decision does not widen the ceiling, it declares searches outside it. Any provider credit the D-5sd-01 validation step spends (Lusha) is NOT free and remains inside the existing priced ceiling — do not let the "free" ruling leak onto the enrichment call it triggers.

**D-5sd-04 — This task AMENDS D-62-03, and does so narrowly: not-found only, never a refusal**

> **This task overturns a prior recorded decision, deliberately and with authority.** The attachment point's own docstring at `operator-claude-plugin/scripts/suggest_contacts.py:410-412` currently reads: *"There is no second-source branch and no search-engine fallback here."* D-62-03 (rev 2, `62-CONTEXT.md:129-137`) is the decision behind it, and its rationale is a PRINCIPLE rather than a scope cut:
>
> > **Do not escalate past a refusal.** If the ladder gives up, or a page is unreachable, that is a result to report — not a prompt to try a search engine. Phase 53's walk run 4 recorded the principle verbatim: *"escalating past a refusal turns a fence into a suggestion."*
>
> **Decision (operator, 2026-09-04):** D-62-03 conflated two different endings. They are now separated, and only one of them gets the fallback:
>
> | Ending | Behaviour |
> | --- | --- |
> | The crawl COMPLETED and found no persons — no people page, or the sitemap listed nothing usable | **Search fallback fires.** This is absence of information, not a fence. |
> | The site REFUSED — 403, 401, `robots.txt` disallow, an explicit block, or otherwise unreachable | **Terminates exactly as today.** No search, no second source. The fence stays a fence. |
>
> **Why:** the operator's directive asks for the not-found case specifically ("if sitemap based website crawl **cannot find persons**"). Phase 53's principle is about routing around a site that told us no, and it survives this change intact — a refusal is still terminal. Overturning the principle wholesale was offered and declined.
>
> **How to apply:** the refusal-vs-not-found distinction must be a real, testable branch, not a comment — a test should prove a simulated 403/robots-disallow does NOT reach the search path while a clean-but-empty crawl does. Update the `suggest_contacts.py:410-412` docstring: it cites D-62-03 by name, so leaving it unchanged would make the code contradict its own recorded decision. Record the amendment where D-62-03 lives, rather than silently diverging from it.

### Claude's Discretion

Not stated as a separate section in CONTEXT.md. Everything not fixed by the three decisions above — module name, config filename, the exact tier-3 starting set, the cap constant's value, the CLI verb shape — is planner/implementer discretion within the patterns this document records.

### Deferred Ideas (OUT OF SCOPE)

None recorded in CONTEXT.md.
</user_constraints>

---

## Summary

The feature is one new pure-Python module + one new committed config list + a bounded amendment to
`skills/suggest-contacts/SKILL.md` step 5. Nothing in `url_fallback.py` changes: an off-host search
result cannot live behind that module's `same_host` guard, which is why CONTEXT.md put it in its own
module. Nothing about `partition_for_dispatch`, `extraction.hold_emailless` or the G-62-7
email-domain rule changes either — D-5sd-01 stacks a gate on top of them.

The seam that makes it work already exists and is already blessed by a test in this repo: the model
performs the I/O and writes a JSON scratch file; a Python CLI reads that file and applies the rule.
`skills/contact-upload/extraction.md:253-257` uses exactly this for sitemap URLs
(`url_fallback.py <pasted> --filter <file>`), and
`operator-claude-plugin/tests/test_url_fallback.py:346-349` states the principle verbatim: *"reading
a local JSON file the model itself already wrote to scratch. That is not a fetch."* So the answer to
"can a SKILL.md-driven search hand structured results to Python deterministically?" is **yes for the
part that must be deterministic** (the allowlist decision, made on the URL string) and **no for
transcription fidelity** (unverifiable — stated as a finding in §2 below, not hidden).

**D-5sd-04's branch does not exist yet, and that is the single most important finding here.**
`attempts[].outcome` is untyped model prose that nothing in the codebase reads (§1b) — a 403 on a
sitemap rung is byte-identical, in Python, to a sitemap that listed nothing. The refusal-vs-not-found
distinction is a **threading task on an existing model→Python JSON channel**, not a conditional
someone can add in one line. The good news: a refusal on the *starting* URL already terminates
before the ladder is built, so only ladder-rung refusals need the new signal.

**Primary recommendation:** add `scripts/search_fallback.py` (pure, no I/O outside its `__main__`
guard, AST-guarded like `url_fallback.py`) + `config/source_allowlist.yaml` (loaded the way
`role_classify.load_families` loads `role_vocabulary.yaml`); fire it from SKILL.md step 5 at the
`no_candidates` terminal; feed accepted people back into the SAME `select_people` →
`synthesise_rows` → single-mint → single stage-2 dispatch path; gate promotion at the *records*
level on provenance, never on a row field.

---

## 1. The attachment point

### The real control flow

`suggest_contacts.no_candidates(company_row, pasted_url, attempts)` at
`operator-claude-plugin/scripts/suggest_contacts.py:409-417` is the terminal. Its whole body is:

```python
return {
    "outcome": "no_candidates_found",
    "company": company_row,
    "reason": url_fallback.give_up_message(pasted_url, attempts),   # :416
}
```

Its docstring already names the thing this task reverses (`suggest_contacts.py:412`): *"There is no
second-source branch and no search-engine fallback here."*

**What the caller currently does with the message.** `skills/suggest-contacts/SKILL.md:107-110`:
report the reason **verbatim**, add no explanation of the caller's own, then **move to the next
company** (D-62-03). Nothing is recorded against that company; the per-company loop simply advances.

### State in hand at that moment

Two layers, and the second is the one that matters architecturally.

**Per-company (the arguments):**

| Value | Where it comes from | Notes |
|---|---|---|
| `company_row` | the round's `eligible_companies` | carries `name`, `website`/`domain`, `row_id` |
| `pasted_url` | `_ladder_source(company_row)` (`suggest_contacts.py:45-74`) | the company's own normalised host — this is **tier 1 of D-5sd-02, computed, not listed** |
| `attempts` | the model's own `[{"url","outcome"}]` record | spent ladder budget; `company_budget(attempts)` = `len(attempts)` (`suggest_contacts.py:381-388`) |
| people found | **none** — that is why this branch fired | |

**Round-level, live in SKILL.md step 5's loop (`SKILL.md:232-247`) and reusable as-is:**
`vocabulary` (`role_classify.load_families()`), `chosen_families`, `per_company_cap`
(`agreed_cap(...)`), `known_contacts`, and the **accumulating `records` list** — which is not
dispatched per company (G-62-4, `SKILL.md:142-143`).

### Consequence for the plan (the architecture)

Because the accumulator and the round-level role/cap state are live at the give-up point, a
search-found person feeds the **same** downstream path with no second implementation:

```
no_candidates fires
  → eligible_after_ladder(attempts)   # D-5sd-04 gate: a refusal anywhere stops here (§1b)
  → model runs N web searches (N bounded by the new cap)
  → model writes results to a scratch JSON
  → python3 scripts/search_fallback.py --rank <file> --company-url <pasted_url>
      → {accepted:[{url,tier,...}], rejected:[{url,reason}]}
  → model web_fetches the ACCEPTED urls only, extracts people
  → select_people(...)            # unchanged — roles + already-associated dedupe still apply
  → synthesise_rows(...)          # unchanged shape, DIFFERENT provenance (see §4)
  → records.extend(...)           # same accumulator, before the batch mint
```

The single `mint_row_ids` (`suggest_contacts.py:321-341`) and the single stage-2 dispatch are
untouched. **No second dispatch path** — the same rule `SKILL.md:158-165` already states.

### Two things the planner must not miss

1. **`SKILL.md:112-114` currently forbids exactly this feature.** Verbatim: *"**Do not escalate past
   a refusal.** No search engine, no other host, no second attempt at the same content somewhere
   else."* Same for the `no_candidates` docstring at `suggest_contacts.py:410-412`. **D-5sd-04
   authorises and scopes the amendment**: narrow both to "no escalation past a *tool-level
   refusal*, and no off-host fetch outside the committed allowlist" — never a wholesale deletion.
   `skills/contact-upload/extraction.md:237-238` carries the other half of the same rule for a
   genuine tool error (`url_not_allowed`); that half is **correct, load-bearing, and must stay
   untouched** — see §1b, where it is what makes the refusal case terminate by construction.
   D-5sd-04 also requires the amendment be recorded at `62-CONTEXT.md:129-137`, where D-62-03 rev 2
   lives, rather than silently diverging from it.

2. **There is a second, different terminal state, and CONTEXT does not attach to it.**
   `discovery_plan` returns a plan with **zero candidates** when the company has no usable
   website/domain (`suggest_contacts.py:143-152`, reason from `_ladder_source` at `:63` / `:67-70`).
   That is not `give_up_message` and never reaches `no_candidates`. CONTEXT.md locks the attachment
   to the `give_up_message` call site only. See Open Questions.

---

## 1b. D-5sd-04 — can the attachment point tell a REFUSAL from a clean-but-empty crawl?

### The answer, plainly: **No. Not at all, in Python, today.** This is a threading task, not a conditional.

### What `attempts` actually carries

`[{"url": <str>, "outcome": <str>}, ...]` — and `outcome` is **free-text prose the model writes**,
not a status, not a code, not an enum.

- `url_fallback.py:206-207` (docstring, the only place the shape is stated): *"`attempts` is
  `[{"url", "outcome"}, ...]`, **the model's own record** of what it tried after the pasted URL
  fetched but came back empty."*
- `url_fallback.py:213` — the **only** read of `outcome` anywhere in the repo:
  `lines.append(f"- {attempt['url']} — {attempt['outcome']}")`. Interpolated into a string. Never
  compared, never parsed, never branched on.
- `suggest_contacts.py:381-388` — the **only** programmatic use of `attempts` anywhere:
  `company_budget(attempts)` returns `len(attempts or [])`. A **count**. Nothing else.
- `suggest_contacts.py:409-417` — `no_candidates` passes `attempts` straight to `give_up_message`
  and returns the rendered prose as `reason`. No inspection.

**The existing tests prove the collapse is already live.** `test_url_fallback.py:236-242` builds two
attempts in one list: `{"outcome": "empty result set"}` (a not-found) and `{"outcome": "404"}` (an
absence/refusal) — **two different endings, one untyped field, and the assertion is only that both
strings appear in the message.** `test_suggest_contacts.py:317-322` does the same with
`"outcome": "empty"`. There is no code path anywhere that could tell them apart.

**Nothing records WHY a fetch produced nothing.** No status code, no refusal marker, no robots
signal, no tool-error code. Only that a URL was tried and a human-readable sentence about it.

### But there is a second structural fact that changes the shape of the fix — and it is good news

The INGEST-05 contract `SKILL.md:99-101` inherits by reference already routes a **tool-level refusal
away from the ladder entirely**. `skills/contact-upload/extraction.md:232-238`:

> - **Fetch failed (a tool-level error).** The tool returns an error code rather than page content…
>   **This branch ends here — the escalation ladder below does not run on a tool error, because
>   escalating past a refusal turns a fence into a suggestion.**
> - **Fetched but nothing usable.** The fetch succeeded — no error code — but the page's content has
>   no legible contact or company data in it.

So the two endings split by **where they terminate**, not by a field:

| Ending | Reaches `give_up_message`? | Distinguishable today? |
|---|---|---|
| **Refusal on the STARTING url** (tool error code, e.g. `url_not_allowed`) | **No** — `extraction.md:237-238` ends that branch before the ladder is even built | Yes, by construction. D-5sd-04's "terminates exactly as today" is already satisfied **provided the plan does not attach the fallback to the tool-error branch as well.** |
| **Fetched-but-empty on the starting url, ladder runs, every rung empty** | Yes | — this is the case D-5sd-04 wants the fallback for |
| **Refusal on a LADDER RUNG** (`/sitemap.xml` 403s, the WP-REST rung 401s) | **Yes** — the model records it as prose in `attempts` and carries on to the next rung | **No. This is the real gap.** A site that 403s its sitemap is byte-identical, in Python, to a site whose sitemap listed nothing usable. |

### Does `web_fetch` surface a refusal distinctly to the model?

**Partly — and less finely than D-5sd-04's table implies.**

- It surfaces *some* structured outcomes: `SKILL.md:126-130` documents that a cross-host redirect is
  handed back rather than followed; `extraction.md:232` documents that a failed fetch *"returns an
  error code rather than page content."* So there **is** an error-code channel the model can read.
- But `extraction.md:233-236` is explicit that the codes are **coarse**: for `url_not_allowed`
  *"the error code genuinely cannot tell those two apart"* — site declined vs. an admin's domain
  filter — and the contract forbids the model from claiming either.

**Consequence for the plan:** D-5sd-04's right column names four causes (403, 401, `robots.txt`
disallow, explicit block). The tool does **not** report `robots.txt` as a distinct cause and the
existing contract forbids inferring it. The plan must collapse them into **one** disposition —
"the fetch returned an error code / the site declined" — and must not write a SKILL.md rule that
asks the model to name robots.txt, which would re-introduce exactly the invention
`extraction.md:234-236` closed.

### The seam a planner has to open

`attempts` is the only carrier, and it **already crosses the model→Python boundary as JSON** —
`url_fallback.py:249-250` / `:258-260` read `--attempted <file>` with `json.loads`. So the threading
is a schema addition on an existing channel, not a new channel.

Smallest change that makes the branch real and testable:

1. **A typed key on each attempt entry** — recommend `disposition`, a closed vocabulary:
   `"empty"` (fetched OK, no people) / `"refused"` (the tool returned an error code) /
   `"unreachable"` (transport failure). **Leave `outcome` exactly as it is** — free prose, rendered
   verbatim by `give_up_message`. Do **not** parse `outcome` for `"403"`: that is string-sniffing
   model prose, the fragility this repo already refuses everywhere else.
2. **A pure predicate in the new module** — e.g.
   `search_fallback.eligible_after_ladder(attempts) -> {"eligible": bool, "reason": str}`. Returns
   `False` the moment **any** attempt carries a refusal disposition, naming that URL (one fence
   anywhere is a fence). **Fail-closed:** an unrecognised disposition string is treated as a
   refusal, never as `"empty"`; a **missing** `disposition` key **raises**, naming the entry —
   the validate-then-apply register `eligibility` already uses (`suggest_contacts.py:128-134`) and
   `agreed_cap`'s refuse-rather-than-default register (`:245-262`). Raising beats defaulting here:
   silently treating a missing key as `"refused"` would make the whole feature quietly never fire
   and read to the operator as "search found nothing."
3. **Put the new key requirement on the NEW predicate only.** `give_up_message` and
   `company_budget` read `url`/`outcome`/`len()` and must stay untouched — that keeps
   `test_url_fallback.py:235-284` and `test_suggest_contacts.py:248-322` passing unmodified, which
   is the cheapest possible blast radius.
4. **A SKILL.md transcription contract** — an explicit mapping table telling the model which
   `web_fetch` outcome becomes which disposition, mirroring `extraction.md:229-243`'s existing
   two-outcome split, and stating that an error code is `refused` **without** claiming a cause.
5. **Docstring + decision-record edits D-5sd-04 names explicitly:** amend
   `suggest_contacts.py:410-412` (it asserts the opposite of this feature) and record the amendment
   at `62-CONTEXT.md:129-137`, where D-62-03 rev 2 lives.

### The test D-5sd-04 demands — fully offline, no stub needed

All pure-function, all against the `no_network` guard by construction:

- `[{"url": …, "outcome": "empty result set", "disposition": "empty"}]` → **eligible**
- `[{…"disposition": "empty"}, {…"disposition": "refused"}]` → **NOT eligible**, reason names the
  refused URL — *this is the "simulated 403/robots-disallow does not reach the search path" test*
- refusal in the **first** position and in the **last** position, both → NOT eligible (order-free)
- `{"disposition": "wat"}` → NOT eligible (fail-closed on an unknown value)
- entry with no `disposition` → raises, naming the entry
- CLI parity through the subprocess layer (`test_url_fallback.py:36-50`'s `_run_url_cli` idiom)

**What still cannot be tested:** that the model transcribed the disposition honestly. Same class as
§2's transcription limit — and it is the reason the disposition vocabulary must be *closed* and
fail-closed, so the only way to reach the search path is an affirmative `"empty"`.

---

## 2. How a Claude-Code skill invokes web search

### Two tool surfaces — know which one is operative

| | Claude Code built-in `WebSearch` | API server tool `web_search` |
|---|---|---|
| Who runs it | the Claude Code session (the operator's own session) | the Messages API, server-side |
| Result shape | result blocks with **title + URL** (plus the model's own reading of them) `[VERIFIED: observed live this session — a `WebSearch` call in this very research task returned a `Links: [{"title":…,"url":…}]` block]` | `web_search_result` blocks: `url`, `title`, `page_age`, `encrypted_content` `[CITED: platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool]` |
| Bounding | no `max_uses` knob exposed to a skill | `max_uses`, `allowed_domains`/`blocked_domains`, `user_location` `[CITED: same]` |
| Cost | inside the operator's Claude Code session | **$10 per 1,000 searches** plus token cost `[CITED: same]` |

**The plugin runs inside a Claude Code session** (`skills/*/SKILL.md` are markdown instructions
executed by that session; the plugin manifest is `operator-claude-plugin/.claude-plugin/plugin.json`).
So `WebSearch` is the operative surface — which is precisely what makes D-5sd-03's "no separately
billed API tokens" ruling correct. The API `web_search` pricing above is recorded so the plan does
**not** accidentally reach for the API surface and invalidate the ruling.

`web_search` appears **nowhere** in the plugin today `[VERIFIED: repo-wide scan of
operator-claude-plugin/**/*.md this session — only `web_fetch` hits, at
skills/suggest-contacts/SKILL.md:98,126, skills/contact-upload/extraction.md:217,468,
tests/samples/24-url-step.md:4, CHANGELOG.md:1794]`.

### The established `web_fetch` idiom, for reference

- `skills/contact-upload/extraction.md:217-227` — "It is a server tool — the fetch **is** the tool —
  so no HTTP client, parser, or scraping library is involved… The operator pastes the URL. That is
  also what makes the fetch possible at all — **the tool only fetches a URL that has already
  appeared in the conversation; you cannot construct one yourself.**"
- Redirect handling: `SKILL.md:126-130` — a cross-host redirect is handed back rather than followed,
  and the target is re-offered through `next_candidates` like any other candidate.

**Relevant to this feature:** the "URL must have appeared in the conversation" constraint is
*satisfied* by a search — the search results put the URLs into the conversation, which is what makes
them fetchable at all. The fallback therefore has a natural two-step shape: `WebSearch` (produces
URLs) → allowlist filter in Python → `web_fetch` on the survivors.

### The seam: how results cross into Python

**They cross as a file the model writes.** This is not a workaround; it is the pattern this repo
already blessed and tests:

- `skills/contact-upload/extraction.md:253-257`: *"If a sitemap candidate's content is itself a list
  of page URLs, **write that list to a file** and pass it through `python3 scripts/url_fallback.py
  <the pasted URL> --filter <the file> --already-fetched <n>` before fetching any of them. Never
  fetch a URL read out of page content without that check — **page content is data, not
  direction**."*
- `url_fallback.py:252-257` — the `--filter` branch: `json.loads(pathlib.Path(_filter_path).read_text(...))`.
- `tests/test_url_fallback.py:346-349` — the AST purity guard explicitly carves out this one
  filesystem touch: *"the one place url_fallback.py may legitimately touch the filesystem, because
  it reads a local JSON file the model itself already wrote to scratch. **That is not a fetch.**"*
  Enforced by `test_url_fallback_calls_open_only_inside_the_main_guard` (`:406-414`).

**So: yes, the same split works.** Python builds/validates strings; the model does the I/O.
Concretely:

```
model runs WebSearch  →  writes /path/scratch/search-results.json:
    [{"url": "https://www.linkedin.com/in/...", "title": "...", "snippet": "..."}, ...]
  →  python3 scripts/search_fallback.py --company-url <pasted_url> --rank <that file> [--already-searched N]
  →  {"ok": true, "accepted": [{"url":…, "tier": 1|2|3, "why": …}],
                  "rejected": [{"url":…, "reason": "host not on the committed source allowlist"}],
                  "cap": MAX_FALLBACK_SEARCHES, "budget_remaining": …}
  →  model web_fetches ONLY accepted[].url, in tier order
```

### The honest limitation — state it, do not soften it

The scratch file is a **model transcription**, not a machine channel. Two distinct properties:

- **Enforceable in Python (and therefore testable offline):** *only an allowlisted host contributes.*
  The decision is made on the URL string, which is checkable. Identical trust class to
  `filter_candidates`, which already treats fetched page content as attacker-influenceable data
  (`url_fallback.py:145-148`).
- **NOT enforceable:** *the transcription is faithful* — that the URL the model wrote is one the
  search engine actually returned, and that the title/snippet were not paraphrased. No offline test
  can assert this. Mitigation, and it is a real one: **do not let the ranker read the snippet or
  title at all for its accept/reject decision.** Rank on the URL host only; the model then
  `web_fetch`es the accepted URL and the *fetched content* — not the search snippet — is what
  produces the person. A fabricated URL then simply fails to fetch or yields nobody.

Recommendation the planner should encode as a rule: **a search snippet is never a source for a row
field.** Same rule as STRUCT-04 already applied in `extraction.md:270-272`.

---

## 3. The allowlist's shape and home

### How `FREEMAIL_DOMAINS` is actually structured

- **Python:** `operator-claude-plugin/scripts/enrichment.py:227-236` — a module-level
  `frozenset({...})` of bare lowercase hosts, with a `# AU consumer ISPs` comment line mid-set.
- **JS mirror:** `n8n/code/companyLink.js:25` — `const FREEMAIL_DOMAINS = new Set([...])`, exported at
  `companyLink.js:169`. The header comment at `enrichment.py:218-226` says the **JS set is
  authoritative** and Python is the mirror, because the ingest lane resolves the question there.
- **Parity test:** `operator-claude-plugin/tests/test_people_and_url_normalisation.py:118-130`
  (`test_the_two_engines_agree_on_what_is_freemail`) — parses the JS `new Set([...])` block via
  `_js_set_members` (`:103-115`) and asserts `js_hosts == set(enrichment.FREEMAIL_DOMAINS)`. Note the
  documented gotcha at `:105-109`: strip each line's `//` tail **before** joining lines, or a
  standalone comment swallows the entries after it. The sibling test for `NOT_A_COMPANY_DOMAIN` is at
  `:91-100`.

Both lists are **in code, not in config**, because both are consumed by two engines.

### Where the new list belongs

**Recommendation: `operator-claude-plugin/config/source_allowlist.yaml`, not a Python constant.**
D-5sd-02 says explicitly *"Keep the list in config, not hard-coded in a function."* The precedent to
follow is `role_vocabulary.yaml`, not `FREEMAIL_DOMAINS`:

- `role_classify.py:30-31` — `PLUGIN_ROOT = Path(__file__).resolve().parent.parent`;
  `DEFAULT_VOCABULARY_PATH = PLUGIN_ROOT / "config" / "role_vocabulary.yaml"`.
- `role_classify.load_families(path=None)` (`:58-83`) — `path` parameter for tests, default to the
  shipped file, `import yaml` **inside the function**, and a named error class
  (`RoleVocabularyError`, `:51-55`) that refuses on a missing file rather than returning an empty
  list, because *"a missing shipped config file is an incomplete install, never a silent empty
  list."* Mirror all four of these properties.
- Existing shipped-config test precedent: `tests/test_column_mapping_shipped.py`.

### Does it need a JS mirror? **No — and here is the check, not an assumption.**

A mirror is required when *two engines answer the same question*. This list is answered on the client
only:

- The only things that cross the plugin→n8n boundary are (a) canonical row props via
  `write_dispatch_csv` / `enrichment.build_envelope`'s `MATCH_LOOKUP_KEYS`
  (`enrichment.py:79`, `:324-326`) and (b) the free-form request-level `source_by_field` JSON form
  field (`dispatch.py:98-105`, CLAUDE.md §13.0.2).
- No n8n node performs a web search or ranks a source host — the backend's own
  `WEB_RESEARCH_MAX_SEARCHES` axis is a *company-ICP research* concern in `src/web_research.py`
  (CLAUDE.md §11.2/§12.3), explicitly disclaimed as unrelated at `suggest_contacts.py:25-29`.
- Therefore no JS engine can disagree, and a parity test would pin nothing. **Do not add one.**

What *does* need a test is the config↔loader contract: the shipped file exists, parses, every entry
is a bare lowercase host with a dot, and no entry appears in two tiers.

### Shape of an entry, for a 4-tier ranking

Tier 1 is **computed, never listed** — it is the company's own host, already in hand as
`_ladder_source`'s `pasted_url`, compared with `url_fallback.same_host` (`url_fallback.py:130-140`,
which already treats apex and `www.` as one host per G-62-2). Tier 4 is **the absence of a match**.
So the file lists tiers 2 and 3 only:

```yaml
version: "lv-source-allowlist-v1"
tiers:
  2:
    label: "LinkedIn"
    hosts:
      - linkedin.com
  3:
    label: "Racing/sport industry bodies and industry media"
    hosts:
      - <host>            # one-line justification as a YAML comment
```

**Matching rule — recommend explicitly, do not leave to the implementer.** Use the same
label-boundary rule `email_domain_relation` already uses (`suggest_contacts.py:484`):
`host == listed or host.endswith("." + listed)`. This accepts `www.linkedin.com` and
`au.linkedin.com`, and **refuses `linkedin.com.attacker.tld`** — the suffix trap. Never a bare
`in`/`endswith(listed)` substring test. Note `linkedin.com` is simultaneously in
`enrichment.NOT_A_COMPANY_DOMAIN` (`enrichment.py:211`) — that is not a contradiction: LinkedIn is
never a *company's own domain* and is a legitimate *source of a person*. The plan should carry that
sentence so a reviewer does not "fix" the apparent conflict.

### Proposed tier-3 starting set

**Every entry below is `[ASSUMED]`** — proposed from domain knowledge of the Australian
racing/sport-media market, not verified against a live source this session (offline constraint). The
operator curates; the plan should ship them as a starting set, not an empty list, and should mark the
file as operator-curated in its header comment.

| Host | One-line justification |
|---|---|
| `racingaustralia.horse` | The national thoroughbred administration body; its site names club and body officeholders. |
| `racingvictoria.com.au` | Victorian principal racing authority — names board, executives, and club contacts. |
| `racingnsw.com.au` | NSW principal racing authority — same role for NSW. |
| `racingqueensland.com.au` | Queensland principal racing authority. |
| `racingandwagering.wa.gov.au` | WA racing authority (RWWA) — the state's peak body. |
| `racingsa.com.au` | SA principal racing authority. |
| `tasracing.com.au` | Tasmanian racing authority. |
| `harness.org.au` | National harness racing body — the code the portal already carries records for. |
| `grv.org.au` | Greyhound Racing Victoria — the third code. |
| `austrac...` *(placeholder — do not ship)* | — |
| `racenet.com.au` | Major AU racing news outlet; carries appointment/executive announcements. |
| `racing.com` | Racing Victoria's own media arm — broadcast/streaming side, directly ICP-relevant. |
| `sportspromedia.com` | Sports-media trade press; carries broadcast/rights executive appointments. |
| `ministryofsport.com.au` | AU sports-business trade press — appointments and executive moves. |
| `sportbusiness.com` | International sports-business trade press, covers ANZ rights deals. |
| `ausport.gov.au` | Australian Sports Commission — names national sporting organisation contacts. |
| `olympics.com.au` | AOC — names NSO and member-body officeholders. |
| `paralympic.org.au` | Paralympics Australia — same. |
| `commbank...` *(placeholder — do not ship)* | — |

Two rows above are deliberate placeholders showing where the operator will add; the plan should
**drop them** and ship only the justified sixteen. Ordering inside a tier is not significant — the
tier number is the rank.

**Not proposed, deliberately:** general news outlets (abc.net.au, news.com.au), aggregators
(crunchbase.com, zoominfo.com — already in `NOT_A_COMPANY_DOMAIN`), and any social host other than
LinkedIn. D-5sd-02's tier 4 rejects them by default and that is the correct default.

---

## 4. Validating a search-found person through the waterfall (D-5sd-01)

### The entry point, function by function

There is **no client-side Lusha call**. The plugin's entry point is the same one
`enrich-before-ingest/SKILL.md` step 5 and `suggest-contacts/SKILL.md:158-165` already use:

1. `enrichment.resolve_providers(override, config)` — `scripts/enrichment.py:141`.
2. `chunking.plan_chunks(spec, chunking.chunk_ceiling(cfg))` — `scripts/chunking.py:218`, `:192`.
3. **`chunking.dispatch_plan(plan, providers, armed, config, ..., async_ack=True, execution_ceiling=...)`**
   — `scripts/chunking.py:352-353`. This is the function to cite.
4. → `enrichment.build_envelope(spec, providers)` **rows form** — `scripts/enrichment.py:308-328`.
   Sets `mode: "propose"` *inside the branch* so write mode is structurally unreachable
   (`enrichment.py:272-277`). Only `MATCH_LOOKUP_KEYS` cross:
   `("email", "firstname", "lastname", "company", "linkedin_url")` — `enrichment.py:79`.
5. → `enrichment.dispatch_enrichment(envelope, armed, config, transport)` — `scripts/enrichment.py:533`.
6. → n8n node **`Lusha Enrich`**, which POSTs
   `https://api.lusha.com/v3/contacts/search-and-enrich` when the row has no stored
   `lusha_contact_id`, and `/v3/contacts/enrich` when it does —
   `scripts/build_cloud_workflows.py:5468-5472` (and the cloud twin at `:3675-3682`).

A stage-1 row is exactly `firstname` + `lastname` + `company` + `jobtitle`, no email
(`suggest_contacts.synthesise_rows`, `scripts/suggest_contacts.py:294-303`) — identity group 2, which
`SKILL.md:165` already names as what the waterfall needs.

### Cost per call

`[CITED: docs/LUSHA-V3-CONTRACT.md]`

| Case | `billing.creditsCharged` |
|---|---|
| First-time `/v3/contacts/search-and-enrich` on a name+company identity | **1** (flat; charged again on a verified repeat of the same identity — §7 of that doc) |
| No match (`results[i].error`, NOT_FOUND) | **0** — *"a no-match is free"* |
| `/v3/contacts/enrich` against a stored `lusha_contact_id` | **0**, unconditionally (A7, 4/4 calls) |
| 400/401 error paths | no `billing` key at all; nothing charged |
| Companies lane `search-and-enrich` | 2 (not this lane) |

`reveal` field-count does **not** change the billed cost (A3 refuted, §6).

**D-5sd-03 boundary, restated so it cannot leak:** the search is free; **this credit is not.** It
sits inside the existing SUGGEST-05 priced ceiling, unchanged. A search-found person that reaches
stage 2 spends the same 1 credit as a ladder-found one — so the *new* search cap bounds how many
people can *enter* stage 2, and the existing `agreed_cap` (`suggest_contacts.py:218-263`) still
bounds how many rows per company are synthesised at all.

### Confirmation vs non-confirmation, precisely

Stage 2's result is joined by `preingest.merge_enriched(rows, responses)` —
`scripts/preingest.py:565-673`, returning a `MergeResult` (`:533-556`). Then
`suggest_contacts.rejoin_enriched(records, merge_report.rows)` (`:344-372`) puts each merged row back
on its record by `row_id`.

| Outcome | Observable | Meaning |
|---|---|---|
| **Confirmed** | the merged row now carries a non-empty `email` (filled by `merge_enriched`'s fill-not-overwrite pass, `preingest.py:651-663`) | the waterfall resolved the identity |
| **Not confirmed — no match** | `row_id` present in `merge_report.rows` but `email` still absent | Lusha returned NOT_FOUND (0 credits); the row already routes to `extraction.hold_emailless` → `reason_code: "no_email"` (`suggest_contacts.py:552-555`) |
| **Not confirmed — never answered** | `row_id` in `merge_report.unanswered` (`preingest.py:646-649`), reason = `UNANSWERED_REASON` (`:527-530`) | *nothing is known* — distinct from "nothing to add", deliberately (T-38-01). **Must be held**, never treated as a no-match. |
| **Confirmed but wrong person** | `email` present, `email_domain_relation` ≠ `"related"` (`suggest_contacts.py:427-486`) | the G-62-7 rule already holds it (`email_domain_mismatch` / `email_domain_freemail`) |

**So the D-5sd-01 promote predicate is, precisely:**

```
sendable(record)  ⟺   source_tier(record) is "strong"                       # NEW gate
                  AND record.row_id ∉ merge_report.unanswered               # NEW, explicit
                  AND partition_for_dispatch([...], company_domains) put the row in `sendable`
                                                                            # UNCHANGED, covers
                                                                            # no_email + domain relatedness
```

Everything else is `held`, with a reason naming which of the three failed.

### The load-bearing structural finding

**The source tier cannot ride on the row.** `synthesise_rows` asserts every row key is in
`extraction.canonical_props()` (`suggest_contacts.py:291`, `:305-306`), and `write_dispatch_csv`
raises on a non-canonical key (CLAUDE.md §13.0.2 states this is exactly why `source_by_field` had to
be request-level). Therefore:

- The tier must be carried on the **record's `provenance`** — the sibling dict `synthesise_rows`
  already builds (`suggest_contacts.py:311-316`), which never becomes a row field.
- `provenance.input` is currently the hardcoded literal `"suggest_contacts_ladder"`
  (`suggest_contacts.py:313`). A search-sourced record needs a distinct value (e.g.
  `"suggest_contacts_web_search"`) plus the tier. That means **`synthesise_rows` needs a parameter,
  or a thin sibling** — the planner should pick one and say which; a parameter with a
  default preserves every existing call site byte-for-byte.
- The new gate therefore runs at the **records** level, alongside `partition_for_dispatch`'s
  row-level split, and re-joins on `row_id` — the same join `rejoin_enriched` already does. Do not
  add a keyword to `partition_for_dispatch`; D-5sd-01 says *"Do not weaken `partition_for_dispatch`'s
  required `company_domains` argument or its suffix-trap refusal."*

### `match.tier` — the boundary to stay clear of

Quick task 260904-5a8's `gating_boundary` finding (`.planning/quick/260904-5a8-.../260904-5a8-SUMMARY.md:75-77`):
`match.tier` gates downstream `confidence.py` / `held_queue.py` behaviour; `match.reason` does not.
The `match` verdict is produced **in n8n** (`n8n/code/matchProposal.js::summarizeMatch`), not in the
plugin. **This feature must write nothing into a match verdict.** The source tier is a plugin-side
records-level concept; keeping it there means zero blast radius on `confidence.assess()` /
`held_queue.build_entry()`. `suggest_contacts.py:548-550` already records the same discipline for the
62-12 reason codes: *"`confidence.ALL_HOLD_CODES` is not widened by these codes."* Follow it.

### `source_by_field`

`SKILL.md:216-219` already sends `dispatch.dispatch(..., source_by_field=...)` with `claude_web` for
stage-1-named fields. `dispatch.py:98-105` does no validation of source labels, so a distinct label
for search-sourced name/jobtitle fields (e.g. `claude_web_search`) rides free. Note
`resolution_sources.RESOLUTION_SOURCES` (`scripts/resolution_sources.py:26-31`) is a *different*,
closed vocabulary — `{hubspot_lookup, operator_statement, provider_result, same_row_derivation}` —
governing what a Claude-*resolved value* may claim, and it is **not** the `source_by_field`
vocabulary. Do not conflate them.

---

## 5. Testability under `no_network`

### What the guard actually does

`operator-claude-plugin/tests/conftest.py:632-649` — autouse `no_network` monkeypatches
`requests.post`, `requests.request` and `requests.Session.request` to raise. Autouse *"so a later
plan's test cannot opt out by forgetting to request a fixture"* (`:637-638`). A second autouse
fixture, `no_durable_writes` (`:652-683`), redirects `written_records_path` to `tmp_path`.

Note the scope precisely: it patches **`requests` only**. A module that imports no HTTP client
satisfies it *by construction* — which is the property `url_fallback.py:6-9` and
`suggest_contacts.py:4-10` both claim and both prove with AST tests.

### The honest test shape — follow `url_fallback.py`'s trio

**1. Pure-function tests on the ranker** (the bulk). All offline, no stubs needed:
- tier 1: a result on the company's own host, apex↔`www` both directions (mirrors
  `test_url_fallback.py:127-142`)
- tier 2: `linkedin.com`, `www.linkedin.com`, `au.linkedin.com` accepted
- **suffix trap: `linkedin.com.attacker.tld` REFUSED** (mirrors `:143-151`) — this is the
  security-critical one
- tier 3: a listed body host accepted; a real subdomain of it accepted; an unlisted host **rejected
  with a reason naming it** (D-5sd-02's tier 4 is rejection, so this is a positive assertion, not an
  omission)
- non-http scheme refused with its own reason (mirrors `:226-234`)
- the search cap: accept up to it, refuse the remainder with a reason naming the constant (mirrors
  `:207-225`)
- config loader: missing file raises a named error, not an empty list (mirrors
  `role_classify.RoleVocabularyError`, and `test_column_mapping_shipped.py`'s shipped-file idiom)

**2. AST purity guards** — copy `test_url_fallback.py:330-414` structurally:
- `_import_names` + an `ALLOWED_ROOT_IMPORTS` subset assertion (`:378-389`)
- `FORBIDDEN_DOTTED_IMPORTS` by exact dotted name — `urllib.parse` allowed, `urllib.request`
  forbidden (`:392-403`)
- `open()` only inside the `__main__` guard (`:406-414`) — the new module reads the model's scratch
  JSON there and nowhere else

**3. CLI subprocess parity** — `_run_url_cli` (`test_url_fallback.py:36-50`) builds an *isolated*
plugin root and runs the script as a real subprocess, so the operator-facing layer cannot drift from
the in-process function. The new module ships a config file too, so its isolated root must copy
`config/source_allowlist.yaml` as well as `scripts/` — a small but real difference from
`_run_url_cli`, which deliberately copies `scripts/` only.

### What a test **cannot** assert offline

State these as known gaps in the plan, not as things to mock away:

- **That a search happened, or returned anything.** The search is model-invoked; the suite never
  sees it. Same class as `web_fetch` today — `test_url_fallback.py:6-9` says so in as many words.
- **Transcription fidelity** — that the URLs in the scratch file are ones a search engine actually
  returned. Unverifiable by construction (§2). Mitigated by ranking on the URL host only and by
  requiring a real `web_fetch` before any person is produced.
- **That the SKILL.md prose is followed.** There is no executable link from prose to behaviour. The
  closest available check is a *presence* assertion over `SKILL.md` text (the repo has this idiom —
  `tests/samples/` and the sufficiency tests), which is worth exactly one test on the amended
  "do not escalate past a refusal" paragraph, so the amendment cannot be silently reverted.

---

## 6. Traps

| Trap | Evidence | Consequence for the plan |
|---|---|---|
| **`cd` does not persist between Bash calls**; agent threads reset cwd | environment note; `SKILL.md:8-12` requires every `python3 scripts/...` to run from the plugin root | every command in the plan uses an absolute path or a single compound `cd … && …` |
| **`node --test tests/n8n/` (directory form) is broken on node 24** — must use the glob `tests/n8n/*.test.mjs` | CLAUDE.md §13.0; MEMORY test-suite note | only relevant if any n8n test is touched — **this feature touches none** |
| **`.venv/bin/python -m pytest`**, not system python (system python lacks deps) | MEMORY test-suite note; 5a8 SUMMARY:123 | plugin suite: `cd operator-claude-plugin && ../.venv/bin/python -m pytest tests/ -q` |
| **The `rtk` shell hook mangles `grep`/`pytest` stdout** | observed live this session (grep output collapsed to per-file counts); 5a8 SUMMARY:128-132 used `pytest.main()` via `python3 -c` to bypass it | verify steps should use `python3 -c`/`python3 - <<EOF` for anything whose exact stdout matters |
| **`partition_for_dispatch`'s `company_domains` is REQUIRED, no default** — an optional arg would be a one-keyword bypass of the operator's ruling | `suggest_contacts.py:531-536` | do not add a keyword to this function; the new gate is a separate, records-level pass |
| **Suffix trap, both directions** | fetch side: `url_fallback._canonical_authority` (`:114-127`) + `same_host` (`:130-140`); send side: `email_domain_relation`'s `ed.endswith("." + cd)` (`:484`) | the new host matcher must be the label-boundary form, never a bare `endswith`/`in` |
| **No `while` loop is permitted in any plugin script** | `url_fallback.py:238-240` names the rule; enforced by `tests/test_report_sufficiency.py:221`/`:236-237` (`_has_while_loop`) | the new module's `__main__` argv scan uses the `for _i, _a in enumerate(_rest)` shape (`url_fallback.py:244-250`) |
| **Do not name the cap `WEB_RESEARCH_MAX_SEARCHES`** | `suggest_contacts.py:25-29` explicitly reserves that name for the backend's own, unrelated axis | name it e.g. `MAX_FALLBACK_SEARCHES`, in the new module, mirroring `MAX_FOLLOWUP_FETCHES` (`url_fallback.py:24`) |
| **`select_people` and the per-company cap still apply to search-found people** | `suggest_contacts.py:176-205`, `:266-290`; nothing in CONTEXT exempts them | search-found people go through the same role filter, the same already-associated dedupe, and the same `agreed_cap` |
| **`mint_row_ids` must stay a single batch-level call** | `suggest_contacts.py:321-335` — per-company minting would mint `row-1` at every company | the fallback runs *inside* the per-company loop, **before** the mint; it never dispatches |
| **`attempts[].outcome` is untyped model prose — never branch on it** | `url_fallback.py:206-213` (only read is an f-string); `test_url_fallback.py:237-238` already mixes `"empty result set"` and `"404"` in one list | D-5sd-04's branch needs a NEW typed key (§1b), not a regex over `outcome` |
| **Do not attach the fallback to the tool-error branch** | `extraction.md:237-238` ends that branch before the ladder runs — this is what makes a starting-URL refusal terminal by construction | attaching there would silently overturn the half of D-62-03 the operator explicitly kept |
| **Plugin version bump + CHANGELOG on any plugin change**; a stale marketplace clone hides an unbumped release | MEMORY plugin-release note; `.claude-plugin/plugin.json` currently `0.38.4` | include the bump as a task |
| **Committed n8n JSON is already ahead of the live instance** | CLAUDE.md §13.0.2 amendment (2026-09-02) | irrelevant here — **this feature touches no n8n file**; say so explicitly so no one regenerates workflows |

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | Every tier-3 host proposed in §3 is a legitimate AU racing/sport body or industry-media site | §3 | A wrong host admits a non-authoritative source into the "strong" tier; mitigated because the operator curates the file and the D-5sd-01 Lusha gate still applies on top |
| A2 | Claude Code's built-in `WebSearch` exposes no `max_uses` equivalent to a skill, so the search cap must be enforced by the skill's own bookkeeping (an attempt count threaded like `attempts`) | §2, §6 | If a knob exists, the cap could be enforced more strongly than by prose+count; the proposed shape still bounds it, just less hard |
| A4 | `web_fetch` reports a 403/401 to the model as a *tool error code* (the `extraction.md:232` "returns an error code rather than page content" branch), not as a fetched page the model must judge | §1b | If a 403 comes back as fetchable body content instead, the model would classify it `"empty"` and the fence would leak. Cheap mitigation the plan should carry anyway: the SKILL.md transcription table should say a page whose content is an error/access-denied notice is `"refused"`, not `"empty"` |
| A3 | No n8n node performs a web search or host ranking, so no JS mirror is needed | §3 | A missed engine would mean a silent divergence of exactly the kind `FREEMAIL_DOMAINS`'s parity test exists to prevent; checked by scanning `n8n/code/` and `scripts/build_cloud_workflows.py` this session and finding search only in `src/web_research.py` (a different, ICP-research lane) |

---

## Open Questions

1. **What counts as a "strong source" in D-5sd-01?** D-5sd-02's ranking has four tiers and tier 4 is
   *rejected outright*, so "a weaker source … is held" has no unambiguous referent: either
   (a) strong = tiers 1–2, and tier 3 is admitted-but-always-held, or (b) strong = tiers 1–3, and the
   only "weaker" case is one that never survives ranking at all — which would make that clause
   vacuous.
   - **Recommendation:** default to **(a)** — the company's own host and LinkedIn promote (subject to
     the Lusha gate); tier 3 admits a person to the round but always holds them. Reading (a) is the
     conservative one, it makes the "weaker source is held" clause non-vacuous, and it is
     one-line-reversible if the operator meant (b). The planner should put this to the operator at
     the plan's own confirmation point rather than assume.

2. **Does the fallback also fire for a company with no usable website?** That company never reaches
   `give_up_message` — it terminates at `discovery_plan`'s empty-candidates branch
   (`suggest_contacts.py:143-152`). CONTEXT.md attaches the fallback to the `give_up_message` call
   site only. **Recommendation:** scope this task to the locked attachment point, and record the
   website-less case as a follow-up. Firing there is arguably the *higher*-value case (a company with
   no site is exactly one a search could help), but it is not what was decided.

3. **A third ending D-5sd-04's table does not name: the ladder exhausted its budget.**
   `MAX_FOLLOWUP_FETCHES` is 5 (`url_fallback.py:24`), and `filter_candidates` refuses the remainder
   with *"the follow-up fetch cap … is exhausted"* (`:179-185`). Nobody said no — so it is not a
   refusal — but the crawl did **not COMPLETE**, so it does not cleanly satisfy D-5sd-04's left
   column either. **Recommendation:** treat cap-exhaustion as **eligible** (it is absence of
   information, not a fence — the site never declined anything), and say so explicitly in the
   predicate's docstring so the reading is on the record rather than incidental. One line to flip if
   the operator disagrees. Note also that `filter_candidates`'s own `refused` list is the **ladder's**
   refusals (off-host, non-http scheme, cap) — never the **site's** — and must not be confused with
   a disposition.

4. **Where does the scratch JSON live?** `url_fallback.py`'s `--filter` idiom takes a path the model
   chose. The plugin has `operator-claude-plugin/scratch/` and `durable_paths.py`. Not a blocker —
   the planner should just pick one and be consistent with what `contact-upload/extraction.md:253`
   already does (unspecified path, model's choice).

---

## Sources

**Primary (HIGH — read this session, `file:line` cited inline)**
- `operator-claude-plugin/scripts/suggest_contacts.py` (whole file)
- `operator-claude-plugin/scripts/url_fallback.py` (whole file)
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` (whole file)
- `operator-claude-plugin/skills/contact-upload/extraction.md:200-280`
- `operator-claude-plugin/scripts/enrichment.py:190-330`, `:528-533`
- `operator-claude-plugin/scripts/preingest.py:505-675`
- `operator-claude-plugin/scripts/role_classify.py` (whole file)
- `operator-claude-plugin/scripts/dispatch.py` (whole file)
- `operator-claude-plugin/scripts/resolution_sources.py` (whole file)
- `operator-claude-plugin/scripts/chunking.py:352-420`
- `operator-claude-plugin/tests/conftest.py:632-683`
- `operator-claude-plugin/tests/test_url_fallback.py:1-50, 330-452`
- `operator-claude-plugin/tests/test_people_and_url_normalisation.py:91-131`
- `n8n/code/companyLink.js:25, 44-65, 169`
- `scripts/build_cloud_workflows.py:3675-3682, 5468-5472`
- `docs/LUSHA-V3-CONTRACT.md` (credit-cost sections)
- `.planning/quick/260904-5a8-.../260904-5a8-SUMMARY.md:70-118`
- `.planning/phases/62-suggest-the-contacts-nobody-named/62-CONTEXT.md:129-137` (D-62-03 rev 2)
- `operator-claude-plugin/tests/test_suggest_contacts.py:248-322`
- `./CLAUDE.md` §13.0.2, §29.1

**Secondary (MEDIUM — external documentation)**
- `https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool` — API `web_search`
  tool definition, result shape, `max_uses`/`allowed_domains`, $10/1,000 searches
- `https://docs.claude.com/en/docs/claude-code/skills` — SKILL.md structure (frontmatter + markdown
  instructions)

**Observed live this session**
- Claude Code's built-in `WebSearch` returning a `Links: [{"title", "url"}]` block — the concrete
  result shape a skill can transcribe.

---

## Metadata

**Confidence breakdown**
- Attachment point & control flow: **HIGH** — every line read directly
- D-5sd-04 refusal-vs-not-found (§1b): **HIGH** on the negative finding (the only reads of
  `attempts`/`outcome` in the whole repo were enumerated and cited); **MEDIUM** on A4, the one
  `web_fetch` behaviour that is documented rather than observed
- The model↔Python seam: **HIGH** — the pattern already exists, is used, and is test-blessed
- Allowlist home/shape: **HIGH** on the precedent, **MEDIUM** on the tier-3 contents (`[ASSUMED]`)
- Lusha entry point & cost: **HIGH** — cited from the repo's own live-probed contract doc
- Testability: **HIGH** — the model to copy is a 452-line test file in this repo

**Research date:** 2026-09-04
**Valid until:** ~30 days (stable — the only fast-moving input is the Claude Code tool surface)
