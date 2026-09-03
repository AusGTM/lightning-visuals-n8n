---
phase: 62-suggest-the-contacts-nobody-named
plan: 10
subsystem: api
tags: [operator-claude-plugin, suggest-contacts, contact-upload, url_fallback, same_host, release]

requires:
  - phase: 62-suggest-the-contacts-nobody-named
    provides: "url_fallback.same_host/filter_candidates (Phase 35), suggest_contacts.next_candidates routing through it unmodified (62-07), mint_row_ids/rejoin_enriched (62-08), the contiguous-token role matcher + expanded governance vocabulary (62-09)"
provides:
  - "url_fallback._canonical_authority + same_host treating apex and a single leading www. label as one host (G-62-2), while still refusing a suffix host, a real subdomain, a differing port, and a double www label"
  - "The same fix reaching contact-upload's URL adapter for free, since both callers route through the one shared same_host"
  - "SKILL.md/extraction.md prose stating the apex/www equivalence and the redirect-scope rule (D-62-03) where the operator's agent reads it"
  - "operator-claude-plugin 0.38.2, released with a CHANGELOG section naming all three gaps closed this round (G-62-2, G-62-3, G-62-4)"
affects: [suggest-contacts, contact-upload, url_fallback]

actuals:
  tokens: 6527
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Canonical-authority helper ahead of a host-equality guard: one small pure function computing the comparison key, the guard unchanged in shape (compare two values), so the security property (still no I/O, still no suffix match) is provable by reading the helper alone"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/url_fallback.py
    - operator-claude-plugin/tests/test_url_fallback.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/skills/contact-upload/extraction.md
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - .planning/phases/62-suggest-the-contacts-nobody-named/62-UAT.md
  deleted:
    - scripts/uat62_eligibility_read.py
    - scripts/uat62_website_survey.py
    - scripts/uat62_cluster_probe.py

key-decisions:
  - "Decision 1 (the equivalence rule): implemented exactly as specified — _canonical_authority drops a single leading www. label from a casefolded netloc only when the remainder still contains a dot; same_host now compares two canonical authorities. Lands in same_host itself, so contact-upload's URL adapter is fixed by the same guard with no second copy (D-62-01)."
  - "Decision 2 (one replaced test): test_same_host_rejects_a_www_variant was the only pre-existing test changed, replaced by two directional acceptance tests (test_same_host_treats_apex_and_www_as_the_same_host_recorded_www_direction / _reverse_direction) plus a docstring rewrite. Every other pre-existing test in the file passed unmodified."
  - "Decision 3 (redirect scope): documented in prose only (SKILL.md step 5) — a redirect target is offered back through next_candidates like any other candidate; no chain-follower or redirect-following mechanism was built."
  - "Decision 4 (UAT scratch removed): scripts/uat62_eligibility_read.py and scripts/uat62_website_survey.py were git rm'd. scripts/uat62_cluster_probe.py turned out to have been an UNTRACKED working-tree file, never committed (the plan's premise that 'all three [were] confirmed tracked at planning time' did not hold for this one) — removed with plain rm, and this discrepancy is called out below rather than silently absorbed."

patterns-established:
  - "A security-relevant equivalence widening gets its own pure helper with the boundary cases spelled out in its own docstring, one line per boundary, citing the ruling that authorized the widening — so the authority for the loosening sits beside the loosening."

requirements-completed: [SUGGEST-01, SUGGEST-02, SUGGEST-04, SUGGEST-05]

coverage:
  - id: D1
    description: "same_host treats a recorded www host and its own apex sitemap (and the reverse) as one host, while an attacker suffix host, a real subdomain, a differing port, a dotless remainder, and a double www label are all still refused"
    requirement: "SUGGEST-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py#test_same_host_treats_apex_and_www_as_the_same_host_recorded_www_direction"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py#test_same_host_still_refuses_the_attacker_suffix_host"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_url_fallback.py#test_filter_candidates_accepts_the_measured_apex_sitemap_and_still_refuses_the_attacker_host"
        status: pass
    human_judgment: false
  - id: D2
    description: "next_candidates accepts the measured Gladstone case in both directions, at the real seam, and still refuses the attacker host naming both hosts"
    requirement: "SUGGEST-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_next_candidates_accepts_the_recorded_www_companys_own_apex_sitemap"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_next_candidates_accepts_the_reverse_direction_recorded_apex_site_serves_www"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_next_candidates_still_refuses_the_attacker_host_naming_both_hosts"
        status: pass
    human_judgment: false
  - id: D3
    description: "The redirect scope and apex/www equivalence are documented where the operator's agent reads them, without a new mechanism"
    requirement: "SUGGEST-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "0.38.2 released with plugin.json and CHANGELOG.md bumped in the same commit, naming G-62-2/G-62-3/G-62-4, with zero n8n change"
    requirement: "SUGGEST-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py"
        status: pass
      - kind: other
        ref: "git status --porcelain n8n/ scripts/build_cloud_workflows.py (silent)"
        status: pass
      - kind: other
        ref: "node --test tests/n8n/*.test.mjs (867 passed, 0 failed)"
        status: pass
    human_judgment: false

status: complete
---

# Phase 62 Plan 10: Apex/www equivalence closes G-62-2, plus release 0.38.2 Summary

**`same_host` now treats a single leading `www.` label as the same host as its apex — narrowly, in one shared helper, with the attacker-suffix/subdomain/port/dotless boundaries each pinned by their own test — and the round ships as 0.38.2 alongside 62-08's and 62-09's fixes.**

## Observed RED (Task 1, before the fix)

```
FAILED test_url_fallback.py::test_same_host_treats_apex_and_www_as_the_same_host_recorded_www_direction
  AssertionError: assert False is True
   +  where False = same_host('https://www.gladstoneturfclub.com.au/x', 'https://gladstoneturfclub.com.au/dt_staff-sitemap.xml')

FAILED test_url_fallback.py::test_same_host_treats_apex_and_www_as_the_same_host_reverse_direction
FAILED test_url_fallback.py::test_same_host_port_travels_with_the_authority
FAILED test_url_fallback.py::test_filter_candidates_accepts_the_measured_apex_sitemap_and_still_refuses_the_attacker_host
  AssertionError: assert [] == ['https://gladstoneturfclub.com.au/dt_staff-sitemap.xml']

FAILED test_suggest_contacts.py::test_next_candidates_accepts_the_recorded_www_companys_own_apex_sitemap
FAILED test_suggest_contacts.py::test_next_candidates_accepts_the_reverse_direction_recorded_apex_site_serves_www

6 failed, 89 passed in 0.52s
```

The 6 failures are exactly the positive-direction and seam cases the fix was meant to change. Every negative/refusal fixture (attacker suffix, real subdomain, dotless remainder, double `www`) already passed under the pre-fix raw-netloc-equality code — expected, since those pairs are refused whether the comparison is raw or canonical. Each still has its own test post-fix, so a future widening that starts admitting one of them fails the suite rather than shipping quietly.

## The one replaced test (Decision 2)

**Old** — `test_same_host_rejects_a_www_variant`:
```python
def test_same_host_rejects_a_www_variant():
    assert same_host("https://gctc.com.au/x", "https://www.gctc.com.au/y") is False
```

**New** — split into two directional acceptance tests over the measured Gladstone hosts:
```python
def test_same_host_treats_apex_and_www_as_the_same_host_recorded_www_direction():
    assert same_host(
        "https://www.gladstoneturfclub.com.au/x",
        "https://gladstoneturfclub.com.au/dt_staff-sitemap.xml",
    ) is True

def test_same_host_treats_apex_and_www_as_the_same_host_reverse_direction():
    assert same_host(
        "https://gladstoneturfclub.com.au/dt_staff-sitemap.xml",
        "https://www.gladstoneturfclub.com.au/x",
    ) is True
```
This is the sole pre-existing test this plan changed. Every other test in `test_url_fallback.py` — the off-host refusal, the cap, the locked four-rung order, the acceptance case, the 62-07 host-less refusals — passed unmodified before and after.

## The canonical-authority rule as implemented

```python
def _canonical_authority(url):
    netloc = urlsplit(url).netloc.casefold()
    if netloc.startswith("www.") and "." in netloc[len("www."):]:
        return netloc[len("www."):]
    return netloc
```
`same_host` compares two `_canonical_authority` values instead of two raw casefolded netlocs. Boundary cases, each with its own test:

| Pair | Verdict |
|---|---|
| `www.gladstoneturfclub.com.au` vs `gladstoneturfclub.com.au` (both directions) | SAME |
| `www.gladstoneturfclub.com.au` vs `evil.gladstoneturfclub.com.au.attacker.tld` | DIFFERENT |
| `gladstoneturfclub.com.au` vs `board.gladstoneturfclub.com.au` | DIFFERENT |
| `www.x.example:8080` vs `x.example:8080` | SAME |
| `www.x.example:8080` vs `x.example` | DIFFERENT (port) |
| `www.com` vs `com` | DIFFERENT (dotless remainder) |
| `www.www.x.example` vs `www.x.example` | DIFFERENT (exactly one label stripped) |

`url_fallback.py` gained no import, no `open()` outside the `__main__` guard, and no new module-level capability — the existing `test_url_fallback_import_set_is_a_subset_of_the_pure_stdlib_allowlist` / `test_url_fallback_never_imports_a_named_forbidden_capability` / `test_url_fallback_calls_open_only_inside_the_main_guard` guards all still pass, confirming the no-I/O property `62-VALIDATION.md`'s manual verification rests on is unchanged.

## Decisions — implemented or amended

- **Decision 1 (equivalence rule):** implemented verbatim. `same_host` alone changed; `filter_candidates`'s check order, refusal message, and `plan_ladder` are byte-identical to before.
- **Decision 2 (one replaced test):** implemented exactly — see above.
- **Decision 3 (redirect scope):** implemented as prose only, in `SKILL.md` step 5 — no redirect-following code exists or was added.
- **Decision 4 (UAT scratch removal):** implemented, **amended in one respect**. `scripts/uat62_eligibility_read.py` and `scripts/uat62_website_survey.py` were tracked and were `git rm`'d cleanly. `scripts/uat62_cluster_probe.py` was checked and found to be an **untracked working-tree file that had never been committed** — the plan's premise ("all three confirmed tracked at planning time") did not hold for this one file. It was removed with a plain `rm` instead of `git rm` (there was nothing to stage a deletion for), and this is recorded here per this executor's deviation-reporting rule rather than silently treated as identical to the other two. The net effect the plan asked for — the file gone from the repo, its finding preserved in `62-UAT.md` — is achieved either way.

## Housekeeping outcome

Confirmed via repo-wide grep before deletion: no committed `.py`/`.md`/`.json`/`.mjs`/`.js` file imports or invokes any of the three `uat62_*` scripts. `62-UAT.md`'s "Tooling written for this UAT" section now carries a paragraph recording the removal, naming where each script's findings live (the quoted 83.5%/78-scheme-bearing figures for the two tracked scripts; G-62-5 for the cluster probe).

## Deviations from Plan

### Auto-fixed / noted issues

**1. [Deviation, documented per plan instruction] `scripts/uat62_cluster_probe.py` was untracked, not tracked, at execution time.**
- **Found during:** Task 2, before running `git rm`.
- **Issue:** the plan's `must_haves.truths` and `<verification>` §4 state all three UAT scripts were "confirmed tracked at planning time"; `git log --all` and `git show HEAD~1:scripts/uat62_cluster_probe.py` show it was never committed.
- **Fix:** removed with plain `rm` (no tracked deletion to stage); the plan's Task 2 `<verify>` command `git status --porcelain scripts/uat62_eligibility_read.py scripts/uat62_website_survey.py scripts/uat62_cluster_probe.py` therefore shows no line for the third path (it was never tracked, so there is nothing for git to report deleted) — the other two show `D`.
- **Files modified:** scripts/uat62_cluster_probe.py (deleted, untracked).
- **Commit:** N/A (untracked file; nothing to commit for its removal, only the working-tree state changed).

No other deviations — plan executed as written otherwise.

## Verification

1. `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` — `2339 passed, 5 skipped`.
2. `node --test tests/n8n/*.test.mjs` — `867 passed, 0 failed`, backend suite untouched.
3. `git status --porcelain n8n/ scripts/build_cloud_workflows.py` — silent.
4. `git ls-files` confirms every path in `files_modified` except the untracked `uat62_cluster_probe.py` (see Deviations).
5. RED-first evidence quoted above.
6. The one replaced test quoted above, old and new.

## Task Commits

- `a7db81f` — `fix(62-10): treat apex and www as one host in same_host (G-62-2)`
- `c5c6752` — `docs(62-10): document apex/www equivalence + redirect scope, remove UAT scratch`
- `ce9e1fe` — `chore(62-10): release 0.38.2 -- G-62-2, G-62-3, G-62-4`

## Self-Check: PASSED

- `operator-claude-plugin/scripts/url_fallback.py` — FOUND, modified.
- `operator-claude-plugin/.claude-plugin/plugin.json` reads `0.38.2` — confirmed by direct read.
- `operator-claude-plugin/CHANGELOG.md` carries `## [0.38.2]` with G-62-2/G-62-3/G-62-4 — confirmed by direct read.
- Commits `a7db81f`, `c5c6752`, `ce9e1fe` — FOUND in `git log --oneline -5`.
- `scripts/uat62_eligibility_read.py`, `scripts/uat62_website_survey.py` — MISSING (deleted, as intended).
- `scripts/uat62_cluster_probe.py` — MISSING (deleted, as intended; see Deviations for its untracked status).
