# Phase 35: URL Structured-Representation Fallback — Context & Handover

**Written:** 2026-08-05, from a live UAT 2.4 walk. **Read this first; it is self-contained.**
**Workstream:** `plugin-entrypoint` · **Target release:** plugin `0.10.0` · **No backend change.**

---

## 1. Where things stand

- **Phase 34 SEALED** 2026-08-05. Plugin `0.9.0` published, on master, marketplace clone refreshed.
  UAT 2.2 walked **PASS** by the operator.
- Suites (baselines to beat): plugin **1022 passed / 5 skipped** · full python **1903 / 6** ·
  node **553** · disarmed-artifact gate **0**.
- Tenant disarmed. Backend deployed and bounced in Phase 34; **this phase touches no backend file.**
- Branch `feat/v0.6-plugin-entrypoint`, in sync with `origin/master`.

---

## 2. The problem, measured live

UAT 2.4 reads: *"Give it a public URL → contact/company data extracted from the page."*

The operator supplied `https://gctc.com.au/board-of-directors/` (Gold Coast Turf Club board).
Walked in Claude Desktop on the installed plugin, and again here. Both produced the same thing:

| Probe | Result |
|---|---|
| `gctc.com.au/board-of-directors/` (HTML) | `[Content truncated due to length...]` immediately after `<title>`, **0 people** |
| `gctc.com.au/` (HTML) | same — truncated after title, before any body |
| `gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors` | **all 9 directors, with role strings** |

**The limitation is NOT a length ceiling.** The homepage truncates at the same point as the board
page — before the body starts. A roster too long for a budget would cut off *mid-list*. This host's
HTML converts to almost nothing (page-builder WordPress theme). `web_fetch` takes only `url` and
`prompt` — there is no length, offset, or pagination knob to widen. "Expand the limit" was never
available.

**The plugin behaved exactly as specified.** `skills/contact-upload/extraction.md`'s URL adapter
defines two outcomes and the second one TERMINATES:

> **Fetched but nothing usable.** … report it as a named result, with the reason ("the page fetched,
> but its content had nothing extractable — likely a client-rendered page this tool cannot execute").

Grep confirms: no mention of `wp-json`, a REST endpoint, a sitemap, a print view, a sub-page, or any
alternate representation anywhere in that file. Desktop hit the second outcome, reported it, and
handed back. Correct behaviour against an incomplete contract — the **same shape as UAT 2.2**, where
the plugin correctly predicted the header drop and the alias table was the gap.

**Two aggravating details, both worth fixing:**

1. **The contract supplies a wrong explanation and the run repeated it back.** It hands the model
   the phrase *"likely a client-rendered page"*. wp-json returned the full roster, so the content
   IS server-side available — the page is not client-rendered in the way the operator was told. The
   contract primes a conclusion instead of a probe.
2. **Retrying the same URL cannot help.** `web_fetch` caches 15 minutes per URL, so the Desktop
   run's "retry with a tighter prompt" re-read byte-identical content. The adapter should not
   suggest a same-URL retry at all.

---

## 3. The decision (operator, 2026-08-05)

Add a **bounded escalation ladder** to the URL adapter. On "fetched, nothing usable" — never on a
tool error — try the site's own structured representation before giving up:

1. `/wp-json/wp/v2/pages?slug=<slug>` then `/wp-json/wp/v2/posts?slug=<slug>`
   (WordPress covers a large share of club/association/league sites — this milestone's ICP exactly)
2. same-host sitemap (`/sitemap.xml`, `/wp-sitemap.xml`) → individual profile pages
3. only then report "nothing usable", **without** the client-rendered guess unless something
   actually evidences it

### Bounds — these are the phase, not decoration

- **Same host only.** A fallback that wanders off-host is a different page, not the operator's page.
- **A hard cap on follow-up fetches** (propose 5, name it in config or a constant). A sitemap can
  list thousands of URLs; an uncapped ladder is a crawler, and a crawler is out of scope.
- **The operator sees which URLs it will try, before it tries them.** Same shape as Phase 34's
  per-header confirmation: propose, human sees, then act.
- **Provenance names the URL actually fetched**, not the pretty one the operator pasted. A row that
  came from `wp-json` must say so, or the audit trail is a lie by omission.
- **STRUCT-04 unchanged.** Absent stays absent; nothing is inferred from a slug, a URL, or general
  knowledge.

### What stays excluded — do NOT widen these

`REQUIREMENTS.md` Out of Scope, unchanged and not amended by this phase: user-agent obfuscation,
viewport emulation, any anti-bot-detection technique, authenticated/paywalled scraping, driving a
browser, capturing pages. **A JSON endpoint the site publishes anonymously is none of those** — it
is the same anonymous `web_fetch` against a different path the site itself serves. If an
implementation reaches for a scraping library, a headless browser, or a user-agent string, it has
left this phase's scope.

Also unchanged: LinkedIn profile fields still come from the licensed provider waterfall on the
backend, never from fetching or picturing the page.

---

## 4. Definition of done

1. On "fetched, nothing usable", the adapter tries the WordPress REST representation and then the
   sitemap route, same-host, capped, with the candidate URLs shown to the operator first.
2. `https://gctc.com.au/board-of-directors/` yields the **9 directors** end to end through the
   operator-facing path — this is the acceptance case, and it must be walked, not just unit-tested.
3. A tool ERROR (`url_not_allowed` etc.) still short-circuits to the existing named refusal. The
   ladder is for the fetched-but-empty branch only; escalating past a refusal is how a fence
   becomes a suggestion.
4. The "likely a client-rendered page" phrasing is gone unless evidenced; the final give-up message
   names what was actually tried, in order.
5. Provenance on every row names the URL it truly came from.
6. A test pins the cap and the same-host rule — an off-host or over-cap candidate is refused.
7. Suites green against §1's baselines; plugin version bumped in the SAME commit as the CHANGELOG
   cut; pushed; **merged to master**; marketplace clone refreshed.

---

## 5. Non-negotiables (all live lessons, all still true)

1. **Pin behaviour at the layer the operator reaches** — CLI as a subprocess against an isolated
   plugin root for anything about what the operator experiences. Harness:
   `tests/test_config_gate.py::_run_cli`, and `_run_header_cli` in `tests/test_header_suggest.py`.
2. **Never fix a test by making its premise false.**
3. **Red-check every new test** — revert, confirm the specific assertion fails, restore.
4. **Commit explicit paths only.** Never `git commit -a`.
5. **Never touch `~/.claude/plugins/`** in tests or scripts.
6. **Autouse `no_network` guard** — no test may perform a real fetch. The ladder must be testable
   through an injected transport/seam, the way `stub_transport` already works for dispatch.
7. **Release checklist** (bottom of `operator-claude-plugin/CHANGELOG.md`): bump
   `.claude-plugin/plugin.json` in the SAME commit as the CHANGELOG cut → push → **push to master**
   → refresh the marketplace clone. `0.9.0` shipped with the bump correct but sitting on a feature
   branch, and the Update button stayed grey until master got it. Master is the branch the
   marketplace reads.

---

## 6. Test commands (exact forms — alternatives are broken here)

```bash
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q   # 1022 passed, 5 skipped
.venv/bin/python -m pytest -q                                  # 1903 passed, 6 skipped
node --test tests/n8n/*.test.mjs                                # 553 pass (FILE glob only)
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json             # must be 0
```

System python lacks the deps. The node directory form is broken on node 24.

---

## 7. Sequencing note

`web_fetch` is a **model-invoked server tool**, not something `extraction.py` calls. So the ladder is
primarily a **skill-instruction change** (`extraction.md`), with any deterministic parts — candidate
URL construction, the same-host check, the cap — as a small testable module the instructions name.
Do not try to make a python script perform the fetch; it cannot, and a script that shells out to
one would be the scraping path this milestone excludes.

---

## 8. Other open work (do not absorb)

| Todo | Note |
|---|---|
| `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path` | **major** — now more urgent: three version bumps shipped in two days, each leaving the cron path stale |
| `2026-08-04-enrichment-throughput-ceiling` | major — levers costed, awaiting a decision |
| `2026-08-03-sweep-lookback-has-no-time-window` | major |
| UAT | 2.5 (screenshots) still needs the operator's images; 1.1 needs a re-walk on 0.6.2's changed behaviour |
