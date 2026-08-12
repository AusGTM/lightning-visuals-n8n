# Phase 48: Enrichment Coverage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `48-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-08-12
**Phase:** 48-enrichment-coverage
**Areas discussed:** Enrichment path per cohort, `venue` enum option, Un-enrichable marker,
Credit-swallow guard scope, The Rumble's mapping, Window count, Re-derivation after writes

---

## Evidence gathered before any question was asked

Two live reads and one file read reshaped every question below, so they are recorded here as the
discussion's factual basis:

1. **Live HubSpot search (2026-08-12):** scored population **66**, blank `lv_org_type` **5** — not
   COVER-01's stale "18". The five are Racing NSW, Editix, Jam TV, Waikato, The Rumble.
2. **`grep 15008671672 47-RESEARCH-RESULTS.json` → 0 matches.** Racing NSW was never in the 17
   pinned records, so no captured evidence exists for it. The other four all have entries.
3. **Reading those four entries** showed 3 are cleanly mappable free-text and 1 (Editix) is
   `matched: false`, confidence 5, all-null. **The paid step collapsed from 5 records to 1.**
4. **Live property read:** `lv_org_type` is `enumeration`/`select` with exactly 9 options, none of
   which is `venue`. `lv_enrichment_status` already has `skipped`/`failed`;
   `lv_enrichment_review_reason` exists.
5. **`src/icp_scoring.py:82`** maps blank region to `"unknown"`, not `non_anz` — so writing to
   Editix (blank region) cannot fire a spurious geography veto.

---

## Enrichment path per cohort

| Option | Description | Selected |
|--------|-------------|----------|
| Free classify 4 + research Racing NSW | Offline enum-mapping over `47-RESEARCH-RESULTS.json` for the 4 with captured evidence; one fresh enum-constrained research call for Racing NSW. Total paid: 1 record | ✓ |
| Free classify 4, defer Racing NSW | Zero-cost pass only; COVER-01 closes for 4 of 5, last deferred to Phase 49 | |
| Re-research all 5, enum-constrained | Phase 47 option (a): fix `RESEARCH_SYSTEM` to emit the 9 values, re-run all 5. Discards already-paid evidence | |
| Full n8n provider waterfall | What the ROADMAP literally says. Providers cost credits and do not return `lv_org_type` at all | |

**User's choice:** Free classify 4 + research Racing NSW.
**Notes:** The ROADMAP's "full provider waterfall per record" was written before Phase 47's D-08
established the standalone Python research path and before the 4 records' evidence was paid for.
The cost estimate is still written ex-ante per COVER-02 — it will simply read ~1 research call.

---

## `venue` enum option

| Option | Description | Selected |
|--------|-------------|----------|
| Defer — no record needs it | Record that the population was examined and none of the 5 maps to `venue`; amend the LOCKED decision with a dated block rather than silently dropping it | ✓ |
| Add anyway, honour the decision | Add the 10th option via `sync_hubspot_properties.py`, arming the portal schema write, so it exists for future populations | |
| Decide after the free pass runs | Run the zero-cost classification first, add `venue` only if a record resists all 9 | |

**User's choice:** Defer.
**Notes:** The LOCKED decision `.planning/decisions/2026-08-12-org-type-venue-and-normalization.md`
says `venue` implements in Phase 48, and its "no portal work is required" clause is already
corrected as false. Waikato (racecourse / event centre) is the nearest miss and maps better to
`individual_club_team`. The decision file gets a second dated amendment recording that the
population was examined and the option was not spent.

---

## Un-enrichable marker

| Option | Description | Selected |
|--------|-------------|----------|
| `lv_org_type=unknown` + `lv_enrichment_review_reason` | `unknown` is already one of the 9 live options. Blank = never attempted; `unknown` = attempted and failed. Zero portal work | ✓ |
| `lv_enrichment_status=skipped` + reason | Both exist live. Keeps `lv_org_type` honestly blank — but then every future "blank org type" sweep re-picks Editix forever | |
| Both — status and org_type | Belt and braces; more writes, two places to keep consistent | |

**User's choice:** `lv_org_type=unknown` + `lv_enrichment_review_reason`.
**Notes:** Editix is the live case and the reason the marker exists — `matched: false`,
confidence 5, all fields null, with the researcher explaining that `edetrix.com.au` matched
nothing and the near-hits were an XML editor, an AI book-editing tool, and a media software
vendor. Marked `costly` for reversibility in CONTEXT.md: the blank-vs-`unknown` semantics become
the query contract every future coverage sweep keys on.

---

## Credit-swallow guard scope

| Option | Description | Selected |
|--------|-------------|----------|
| Driver-side pre-flight + shape assert | Check Anthropic credit before arming; assert each research payload is `ProviderResult`-shaped. Entirely in the Python driver — no rebuild, no deploy, no bounce | |
| Fix the lane properly | Gate node after `Claude Web Research` routing error-shaped payloads to a failure branch, in `build_cloud_workflows.py`. Root-cause fix, protects every future run — needs rebuild + deploy + bounce, operator-only | ✓ |
| Both — guard now, lane fix as a task | Ship the driver guard for this run and land the lane fix in the same phase | |

**User's choice:** Fix the lane properly.
**Notes:** Accepts an operator deploy+bounce as a Phase 48 obligation. The Phase 47.5 deploy
waiver expired with that phase, so the deploy is operator-only. This is the root-cause fix rather
than a per-run workaround — the shared function, not the calling path.

---

## The Rumble `20943964946` — which of the 9 options?

| Option | Description | Selected |
|--------|-------------|----------|
| `content_producer` (+20) | Produces and broadcasts skateboarding content, 740k avg viewership, sponsorship-reliant. The same evidence names **Skate Australia** as the sport's body and The Rumble as a partner | ✓ |
| `governing_body_league` (+40) | Operates a Pro Tour AND an Amateur Series — a league structure it owns and runs. "Sports league operator" is the researcher's own phrase | |
| Let the judge decide at execution | Feed the evidence to a Sonnet call constrained to the 9 options, record its verdict and reason | |

**User's choice:** `content_producer`.
**Notes:** Tier-changing (+20 vs +40). The deciding evidence is that The Rumble partners with the
governing body rather than being it.

---

## Window count

| Option | Description | Selected |
|--------|-------------|----------|
| 1 deploy + 1 armed write window | One operator deploy+bounce for the gate node; one armed window covering all 5 records at cap 5 | ✓ |
| 1 deploy + 2 armed windows | Separate the 4 free-classified records from Racing NSW, isolating the only paid record | |
| Decide at plan time | Let `gsd-plan-phase` derive the count from the task breakdown | |

**User's choice:** 1 deploy + 1 armed write window, cap 5.
**Notes:** Continues Phase 47.5's discipline — declare the count before opening anything and use
exactly that many. Phase 47 needed five cycles against a must_have of one and had to disclose it.

---

## Re-derivation after the writes

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — recompute POST per record, report before/after | Writing `lv_org_type` completes each record, so `Company Gate` skips it forever after; the recompute lane is the only way to settle the derived chain. Free: 0 credits, 0 Anthropic, 1 execution each | ✓ |
| No — COVER-01 is literally about `lv_org_type` | Scores and tiers are Phase 49's reporting scope (RESCORE-03) | |
| Recompute, but report only, no claims | Fire the recompute so the data is correct; record before/after as observation, not deliverable | |

**User's choice:** Yes — recompute POST per record, report before/after.
**Notes:** Phase 48 records the numbers; Phase 49 narrates the plain-language distribution
(RESCORE-03). D-07 (never PATCH the derived fields) still binds absolutely.

---

## Claude's Discretion

- Chunking, task ordering, and whether the offline mapping pass is a script or a plan-time table.
- Whether Racing NSW's research reuses `src/web_research.py::claude_web_research` with a corrected
  enum-constrained `RESEARCH_SYSTEM` or a narrower one-off prompt.
- Where the D-04 gate node's failure branch terminates (`Build Response` with a reason is the
  established idiom).

## Todos

**Folded:** `2026-08-12-n8n-swallows-anthropic-credit-failure.md` (0.9) — fixed at the lane per the
credit-swallow decision above.

**Reviewed, not folded:** `2026-08-04-enrichment-throughput-ceiling.md` (0.9, bites at 1000 records,
not 5 — its remedies are their own phase); `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`
(0.6, unrelated); `2026-08-04-uat-22-names-aliases-the-mapping-lacks.md` (0.6, unrelated).

## Deferred Ideas

- `venue` as a 10th enum option — revisit when a record's evidence demands it.
- Entain `10024564084`'s ANZ operating presence — never examined. Phase 49.
- A live `D` → non-`D` tier *transition* proven as a transition. Phase 49.
- Plain-language before/after tier distribution as a deliverable — Phase 49 / RESCORE-03.
