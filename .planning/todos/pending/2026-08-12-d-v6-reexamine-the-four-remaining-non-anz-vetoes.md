# D-V6: re-examine the four remaining non-ANZ vetoes (Phase 47.5, workstream B)

**Raised:** 2026-08-12, immediately after Phase 47's armed window closed.
**Owner phase:** **47.5, workstream B** (operator-directed 2026-08-12 — moved from Phase 49,
because the write leg is blocked on 47.5's recompute fix and doing it later means doing it
twice). D-V6 already makes the re-examination mandatory; this only settles *where* it runs.
**Do NOT action in Phase 47** — three of these four are on Phase 47's forbidden list.

## The complete work-list

After Phase 47, **exactly four companies portal-wide carry a non-ANZ veto**, and all four
have a populated `lv_country_region_normalized = "Other"` — so none matches VETO-03's
blank-region search (17 → 0). Verified live 2026-08-12:

| id | name | HQ | org_type | score | tier | why it is vetoed |
|---|---|---|---|---|---|---|
| `17317850381` | Jam TV | Segrate, IT | *(blank)* | 20 | D | **Correct — leave alone.** The Italian broadcaster `jamtv.it`. D-23. Not a candidate |
| `17317184159` | Ironman | Tampa, US | governing_body_league | **70** | D | HQ-based call. **Strongest flip candidate** |
| `15860277364` | GRAVITY MEDIA | Watford, UK | broadcaster | 50 | D | HQ-based call |
| `10024564084` | Entain | Douglas, IM | gambling_operator | −70 | D | HQ **plus** a second veto |

## Why this needs deciding, not just checking

D-V6 (locked 2026-08-12) redefines `lv_country_region_normalized` as ANZ **operating
presence** — a substantive local operating entity (subsidiary, office, staff, production
ops) — explicitly **not** headquarters. All four regions were set under the old HQ reading.

**Ironman is the one that matters.** It already scores **70**, which is Tier A territory, and
is suppressed entirely by a geography call made on a Tampa HQ. It is a governing body that
produces content — the core ICP shape. If Ironman Oceania (Ironman Australia, Ironman New
Zealand, the 70.3 series) meets D-V6's bright line, the veto clears and it becomes **80 /
Tier A** — arguably the most valuable single record in the portal, currently suppressed.

Gravity Media is the same shape one tier down: Gravity Media Australia (formerly Global
Television) would, if it meets the bar, take it to **60 / Tier B**.

Entain differs and is worth stating so nobody expects movement: even if its region flips on
Ladbrokes AU / Neds, `lv_produces_content = false` fires a **second** veto ("No broadcast or
streaming content"), so it stays Tier D either way.

## Required before any write

1. **Verify operating presence against sources** — the flip candidates above are asserted
   from general knowledge, not researched. D-V6's bar is a substantive local operating
   entity, *not* "sells into ANZ", *not* "has ANZ customers", *not* a reseller. Evidence
   URLs, same standard as any other ICP input.
2. **Note the recompute trap.** All four have complete inputs, so `Company Gate` will skip
   them and `Decide Company Action` will never rewrite their veto — see Phase 47.5. Changing
   the region alone will NOT clear the flag. Either 47.5 lands first, or this repeats Phase
   47's blank-a-field workaround, which is not something to do twice by choice.
3. **One window, and it is small** — four records, three of them previously untouchable.
   Phase 47's five-window sprawl is the thing to not repeat; the run report says why it
   happened.

## Evidence

```
.planning/phases/47-veto-remediation/47-RUN-REPORT.md   § Plan 04 (actuals, window accounting)
.planning/decisions/2026-08-12-org-type-venue-and-normalization.md   D-V6
.planning/phases/47.5-veto-recompute-path/47.5-CONTEXT.md            the recompute trap
```

Live census reproducing the table above (read-only):

```bash
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from src.hubspot_client import search_records
r=search_records('companies',[{'propertyName':'lv_anti_icp_reason','operator':'CONTAINS_TOKEN','value':'Non-ANZ'}],
  ['name','lv_country_region_normalized','lv_icp_fit_score','lv_icp_tier'],limit=100)
for x in r.get('results',[]): print(x['id'], x['properties'])
"
```
