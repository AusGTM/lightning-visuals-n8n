# Phase 47 — pre-arm review of the dry-run (2026-08-12)

**Verdict: DO NOT ARM YET.** One record is a wrong-entity match at high confidence. Two others
are correct-but-worth-knowing. Nothing has been written; the window was never opened.

Reviewed `47-DRYRUN.md` and `47-RESEARCH-RESULTS.json` against the abort conditions recorded in
D-22 before arming.

## Abort conditions — all clean

| Check | Result |
| --- | --- |
| D-07 — derived field in any payload (`lv_anti_icp_flag` / `_reason` / `lv_icp_fit_score` / `lv_icp_tier`) | none |
| D-14 — `lv_produces_content: false` in any payload | none |
| D-12 — any id outside the pinned 17 | none |
| D-12 — Entain / Gravity Media / Ironman present | none |
| Distinct ids in dry-run | exactly 17 |
| `lv_is_gambling_operator: true` in payloads | 0 (the 8 false positives are gated out) |

The mechanical gates hold. The problem is upstream, in what the research *believed*.

## BLOCKER — Jam TV (`17317850381`) is a wrong-entity match

The research matched **`jamtv.it` — an Italian music-television broadcaster** — and returned:

```json
{"lv_org_type": "Media company / Web television broadcaster",
 "lv_country_region_normalized": "Italy",
 "lv_has_sports_media_fit": false,
 "confidence": 85}
```

with `match_basis: ["Domain match: jamtv.it", "Company name match: Jam TV", "Country match: Italy"]`.

Jam TV in this CRM is an **Australian sports-television production company** — which is why
`46-SIMULATION-REPORT.md` flagged it as a *false* non-ANZ veto and why D-17 called it
"broadcaster / content producer". The research locked onto a same-named Italian company.

**Why this is dangerous rather than merely wrong:** `confidence: 85` and a coherent evidence
chain make it indistinguishable from a good result by any automated check. The enum gate cannot
catch it — `Italy` is a perfectly valid region, just not this company's. Written as-is it would
either stamp a genuinely-wrong non-ANZ region (converting a false veto into a *manufactured true*
one) or leave the record unfixed, and in both cases the evidence trail would assert an Italian
music broadcaster is this account.

This is the mirror image of the defect the phase exists to clear.

**Required before arming:** re-research Jam TV pinned to its actual identity (the CRM record's own
domain, not a name search), or drop it from this window and handle it separately. Do not write the
Italian result.

## Correct, but record them

**Editix (`17317381378`) — `matched: false`, `confidence: 5`.** Searches for the CRM domain
`edetrix.com.au` returned nothing; results were unrelated (EditiX the XML editor, etc.). This is
D-14 working exactly as intended — unknown over guessing — and it satisfies COVER-01's bar that an
unresolved company be *distinguishable from one never attempted*. No action needed beyond keeping
the stated reason in the run report.

Worth noting the CRM domain itself (`edetrix.com.au` vs the name "Editix") may be a data-entry
error in the record. Out of scope here; candidate follow-up.

**Coffs Harbour Racing Club (`14752488879`) — raw research returned
`lv_produces_content: false` and `lv_is_gambling_operator: true`.** Both are wrong for a country
racing club, and both were correctly gated out of the payload (the `false` by D-14, the gambling
flag by the `d517600` fix). Payload is clean. Flagged only because the *cache* retains the wrong
values, so anything re-reading `47-RESEARCH-RESULTS.json` raw must apply the same gates.

## Coverage consequence worth an explicit decision

The research returned **free-text** `lv_org_type` for 16 of 17 (e.g. "Sporting club / Racecourse
operator", "Thoroughbred racecourse operator / Recreational facilities management",
"Not-for-Profit Racing Club") rather than CRM enum values. The enum gate added in `1a67814`
correctly refuses to guess-map these, so **only Simtech LED's `hardware_vendor` reaches a payload
with an org type.**

Consequences:

- **VETO-01 is still satisfiable** — 15 of 17 get a normalized `AU`/`NZ` region, and the veto
  clears on region. That is this phase's actual bar.
- **COVER-01 is only partly served** — 16 records end with no real `lv_org_type`, so they land as
  "attempted, unresolved with a stated reason" rather than "enriched to a real org type". Legal
  under COVER-01's wording, but it is not what D-05 envisaged when it widened scope to all
  scoring inputs.

Options: accept (the veto clears, org type stays for Phase 48), or add a deterministic
free-text → enum mapping with an explicit review of each mapping. **Not a decision to take
silently mid-window** — recorded here rather than resolved.

## State

Nothing armed. No `ALLOW_*` ever set. Zero HubSpot writes. `47-DRYRUN.md`, `47-RUN-REPORT.md`,
`47-RESEARCH-RESULTS.json`, `47-BEFORE.json` all committed. Plan 04 not started.
