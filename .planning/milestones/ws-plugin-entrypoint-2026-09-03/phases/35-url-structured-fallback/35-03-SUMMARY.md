---
phase: 35-url-structured-fallback
plan: 03
status: complete
completed: 2026-08-05
requirements: [INGEST-05, INGEST-06]
---

# 35-03 Summary — the acceptance case walked live, and `0.10.0`

## Task 1: the live walk against `gctc.com.au` — PASS, 9 rows

Walked by following `extraction.md`'s rewritten URL adapter as written, not improvising past it.

### Observed, step by step

1. **Pasted URL fetched** — `https://gctc.com.au/board-of-directors/`. No tool error. The content
   received ended at `"Board of Directors - Aquis Gold Coast Turf Club [Content truncated due to
   length...]"` — **0 people**.
2. **Reported as the named empty outcome with no cause stated.** No claim about JavaScript, no claim
   about what the tool can or cannot execute. This is the behaviour change that motivated the phase:
   the walk that *produced* this phase told the operator "likely a client-rendered page", and that
   was wrong — the content was server-side available the whole time.
3. **No same-URL retry offered.** The adapter now says not to, and the walk did not.
4. **Candidates printed before any was fetched**, in the locked order, with the cap named — 4
   candidates, all on `gctc.com.au`, "at most 5 follow-up fetches across the whole ladder":

   | # | URL |
   |---|---|
   | 1 | `https://gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors` |
   | 2 | `https://gctc.com.au/wp-json/wp/v2/posts?slug=board-of-directors` |
   | 3 | `https://gctc.com.au/sitemap.xml` |
   | 4 | `https://gctc.com.au/wp-sitemap.xml` |

5. **Rung 1 fetched, returned the roster, ladder stopped there.** Rungs 2–4 were never fetched.
6. **9 rows accepted, 0 rejected:** Brett Cook (Chairman), Trent Watson (Deputy Chairman, Finance),
   Jarrad Young (Honorary Treasurer, Finance), Peter Ward (Development), Luke Henderson (Racing and
   Training), Greg Leeson (Marketing, Sponsorship & Event), Royce Ahrens (Beaudesert Racing Club),
   Tara Hastings (Corporate Governance & Compliance), Sandy Cowell (Membership and Wagering).
7. **No email, no phone on any row** — machine-checked, `any(email or phone) is False`. The
   representation carries none; a row carrying one would have been invention.
8. **Provenance names the URL that actually served the row**, e.g.
   `https://gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors → [0].content.rendered, board
   entry 1` — not the pasted page URL.

### The negative case

`https://gctc.invalid-tld-for-uat-probe.example/board/` → tool-level error
(`getaddrinfo ENOTFOUND`). **The named refusal was given and the ladder was NOT run** —
`url_fallback.py` was not invoked at all on that branch. The fence stayed a fence.

### Acceptance criteria

| Criterion | Result |
|---|---|
| All 9 directors appear by name | ✅ |
| Candidate list shown before any fetch, first candidate exact, cap named | ✅ |
| No same-URL retry offered | ✅ |
| No claim about how the page renders | ✅ |
| Provenance names the wp-json URL on every row | ✅ |
| No row carries an email or a phone | ✅ (machine-checked) |
| Tool-error case → named refusal, no ladder | ✅ |
| Observations written here before Task 2 | ✅ |

## Findings from the walk (worth more than a green suite)

1. **"Verbatim" is not reliably verbatim through the summarising model.** An earlier
   verbatim-prompted fetch of this exact endpoint returned the names in ALL CAPS; this walk's
   equally verbatim-prompted fetch returned them title-cased. `web_fetch` answers a prompt with a
   small fast model rather than returning raw content, so casing — and by extension any exact-string
   claim — is not stable across fetches. **Not invention** (no field was fabricated), but it means
   an operator cannot treat extracted strings as byte-faithful to the page. Recorded as an
   ambiguity on the batch. Worth a todo: either say so plainly in the adapter, or stop promising
   "verbatim" in prompts it cannot guarantee.

2. **A login wall lands in the nothing-usable branch, and the ladder would fire on it.**
   `https://www.linkedin.com/company/melbourne-racing-club/people/` fetched with **no tool error**
   and returned a login screen — so by the adapter's own definition that is "fetched, nothing
   usable", and the ladder would offer `linkedin.com/wp-json/...` candidates. Harmless (they would
   404, same-host, capped, operator-approved) but pointless noise, and it sits awkwardly next to the
   authenticated-page exclusion — no authentication is attempted, but the ladder is being pointed at
   a page that requires it. Not a defect against this phase's criteria; logged as a todo rather than
   fixed here, since narrowing it means detecting a login wall, which is a judgement call the
   adapter currently and deliberately avoids.

## Task 2: suites, CHANGELOG cut and version bump — one commit

See the release commit. All four gates green before the cut.

## Task 3: push to master and refresh the marketplace clone

Master is the branch the marketplace reads. `0.9.0` shipped with a correct bump sitting on a feature
branch and the Update button stayed grey until master had it — that is why this is its own task.
