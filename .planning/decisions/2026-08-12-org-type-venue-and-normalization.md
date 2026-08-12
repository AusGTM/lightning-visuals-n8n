# Decision record — `venue` org type + org-type normalization

**Decided:** 2026-08-12
**Decided by:** operator, in session, during Phase 47's pre-arm review
**Status:** LOCKED
**Implements in:** Phase 48 · **Scores in:** Phase 49's full-population re-score
**Does not change:** Phase 47's write window, which proceeds unchanged

Raised because Phase 47's live research returned free-text `lv_org_type` for 16 of 17 pinned
companies ("Sporting club / Racecourse operator", "Thoroughbred racecourse operator /
Recreational facilities management", …). The enum gate correctly refused to guess-map them, which
surfaced two distinct problems: there is no enum member for a *venue*, and nothing structurally
prevents the researcher emitting prose in the first place.

---

## D-V1 — Add `venue` to the `lv_org_type` taxonomy, weight **5**, no hard veto

**Rationale.** A racecourse or stadium operator is a **channel, not a customer** — the route to
the clubs and leagues that are the actual buyers. That is a real category the current taxonomy
cannot express: today such a record lands `other` (0) or `unknown` (0), which is both wrong and
invisible.

**Why 5 and not 10.** The weight was chosen against the tier boundary it actually moves, not by
feel. For a content-producing ANZ venue:

| `venue` weight | `venue + produces_content (20) + ANZ (10)` | tier | motion |
| --- | --- | --- | --- |
| **5 — chosen** | 35 | **C** | nurture, or work via league/governing body |
| 10 — rejected | 40 | B | work direct |

Tier C's own definition is *"nurture, or work via league/governing body"* — that **is** the
channel framing. 10 would route venues to direct outreach, contradicting the reason the class
exists. 5 encodes the intent; 10 defeats it.

**Not a hard veto.** Racecourses and stadiums do produce and stream content. `venue` sits in the
scoring band like any other org type; only `non_anz`, `no_content` and `hardware_vendor` veto.

**Placement in the taxonomy** (post-Phase-46 weights):

```
governing_body_league  40
content_producer       20
broadcaster            20
individual_club_team   15
venue                   5   <- new
gambling_operator       0
hardware_vendor         0   (+ hard veto)
other                   0
unknown                 0
regulator             -20
```

**Recommended motion:** `work_via_league` (existing enum member — no new motion value needed).

**Note on the original framing.** The proposal was "below `individual_club_team`, above
`hardware_vendor`". The second half is not a real constraint: `hardware_vendor` is 0 *and* a hard
veto, so anything ≥ 0 clears it. The binding constraint is the Tier C/B boundary above.

---

## D-V2 — Entity collision: `individual_club_team` wins

A racecourse is frequently operated by the club itself — Thoroughbred Park is Canberra Racing
Club's course. **When `venue` and `individual_club_team` describe the same legal entity, classify
as `individual_club_team` (15).**

Rationale: the club is the buying entity; the venue is one of its assets. Without this rule the
10-point gap would be decided by whichever name the researcher happened to encounter first — a
coin-flip dressed as a classification.

`venue` is therefore reserved for operators that are **a separate legal entity from any club or
league using the facility** (independent stadium/precinct operators, government venue authorities,
commercial venue-management companies).

Research must state which of the two it found and why, since the two are visually similar from a
website read.

---

## D-V3 — Sequencing: decide now, implement in Phase 48, score in Phase 49

**Phase 47's write window is unaffected and proceeds as planned.** The three venue-shaped records
(Thoroughbred Park `10152138518`, Wyong `10215097384`, Pinjarra Park `17696004613`) take
`unknown` org type in that window. This does **not** block VETO-01 — the false non-ANZ veto clears
on *region*, not org type.

**Why not fold it into Phase 47.** This is a rubric change. Phase 46 was an entire phase —
simulation engine, decision record, sign-off — built to settle the rubric *once* so records are
touched *once*. Folding a weight change into 47's write window would be the fourth scope widening
and would land in precisely the territory Phase 46 was created to fence off.

**Why deferring costs nothing.** Phase 49 re-scores the **entire** scored population (RESCORE-01 /
RESCORE-02), because with no `lv_icp_scoring_version` property, records under a superseded rubric
cannot be segmented. A `venue` weight therefore lands in that re-score whether it is added now or
in Phase 48. Adding it early buys no write savings and costs scope discipline.

**No portal work required.** Adding an enum *value* does not touch the standing
no-new-**properties** constraint, and `lv_org_type` is not an enumeration in HubSpot
(`docs/WEB-RESEARCH-SPEC.md:208` — the portal accepts any string), so no property migration is
needed. The corollary is that the portal will not validate it either, which is what D-V4 exists to
compensate for.

---

## D-V4 — Three-layer normalization: `lv_org_type` must always be scoreable

**The problem this closes.** `lv_org_type` is a free-text property in HubSpot. The real consumer is
`config/icp_scoring.yaml`'s `base_score.org_type` map, which keys on exact enum strings — so
`"Sporting club / Racecourse operator"` resolves via `.get(org_type, 0)` to **0 points, silently**.
That is the same silent-blank failure class as the blank region that caused the false vetoes this
milestone is remediating. The enum discipline is correct; the reason stated in
`scripts/remediate_veto_companies.py:142` ("writing free text to an ENUMERATION property 400s the
batch") is **not** — the property is not an enumeration and the write would be accepted.

Belt and braces, all three layers required:

### Layer 1 — Constrain at generation (structural; the actual fix)

`src/web_research.py` currently asks for JSON in a system prompt and regex-extracts it
(`_extract_json`). Nothing prevents prose. **Replace with a forced tool call whose JSON Schema
types `lv_org_type` as an `enum`** over the taxonomy above (plus `venue`). The model then cannot
emit free text. `src/classifier_haiku.py` already uses structured output — same pattern, and this
is the layer that eliminates the class rather than cleaning up after it.

Also enum-constrain `lv_country_region_normalized` — the same run returned `"Australia - NSW"`,
`"NSW, Australia"`, `"Australia - Queensland"` as free text.

### Layer 2 — Deterministic alias table (safety net)

Add `normalize_org_type()` to `src/normalizer.py`, beside its existing siblings
(`normalize_country_region`, `normalize_revenue_band`, …) — today `lv_org_type` falls through to
`normalize_text`, i.e. passthrough, and the only gate lives in a Phase 47 script rather than in
shared code.

Rules:
- An **explicit, reviewed alias dict** — not keyword heuristics or fuzzy matching.
  e.g. `racing club` / `turf club` / `jockey club` / `race club` → `individual_club_team`;
  `racecourse operator` / `racecourse` / `raceway` / `stadium operator` → `venue`, subject to D-V2.
- Case- and punctuation-insensitive on the key, exact on the mapping.
- **Anything unmapped returns `unknown`. Never guess.** Prefer-unknown-over-guessing is already the
  web-research contract (`docs/WEB-RESEARCH-SPEC.md`); this makes it structural.
- Versioned and unit-tested, with each alias traceable to a human review.

### Layer 3 — Second-pass classifier (last resort)

For values layer 2 cannot map: one cheap Haiku call taking the free text plus the allowed enum and
returning exactly one member, **required to return `unknown` when unsure**. ~$0.0001/record. Runs
only on layer-2 misses, never as the primary path.

### Invariant

**No value reaches `lv_org_type` — in HubSpot or in the scoring engine — that is not a member of
the taxonomy.** Assert it in a test that reads the taxonomy from `config/icp_scoring.yaml` rather
than a hardcoded list, so adding a member cannot silently desynchronise the two.

---

## D-V5 — The three layers apply to **every** property that must be deterministic to be scoreable

D-V4 is not an `lv_org_type` fix. It is the general rule, and `lv_org_type` was simply where it
surfaced first. **Any property the scoring engine or a downstream gate reads by exact value must
be generated under an enum/typed schema (layer 1), normalized through a deterministic reviewed
map (layer 2), and backstopped by a classifier that answers `unknown` when unsure (layer 3).**

Free text is permitted only where nothing keys on the value — evidence summaries, reasons,
provenance blobs.

### Immediately in scope

`lv_country_region_normalized` — confirmed broken in the same Phase 47 run, which returned
`"Australia"`, `"Australia - NSW"`, `"NSW, Australia"`, `"Australia - Queensland"`,
`"Australia - Northern Territory"`, `"Australia - Western Australia"`, `"New Zealand"`, `"Italy"`.
The scoring engine keys on `AU` / `NZ` / `ANZ`, everything else collapsing to `non_anz` — which is
a **hard veto**. Free-text region is therefore not merely unscoreable, it is actively dangerous:
`"Australia - NSW"` reaching the engine unnormalized vetoes an Australian company. This is the
precise defect Phase 47 exists to remediate, still live one field over.

Allowed set: `AU` · `NZ` · `ANZ` · `Other` · `Unknown`.

### Sweep — enumerate the rest before implementing

Phase 48 must **enumerate every property read by `src/icp_scoring.py`, `config/icp_scoring.yaml`,
the n8n `Decide Company Action` node, and the HubSpot calculated property**, then classify each as
free-text-safe or must-be-deterministic, and apply all three layers to the latter. Do not
hand-pick from the list below — derive it from the code, and treat this as the starting point:

| Property | Kind | Allowed values |
| --- | --- | --- |
| `lv_org_type` | enum | taxonomy above, incl. `venue` |
| `lv_country_region_normalized` | enum | `AU` `NZ` `ANZ` `Other` `Unknown` |
| `lv_revenue_band` | enum | `<1M` `1-5M` `5-50M` `50-500M` `500-750M` `750M-1B` `1B-1.2B` `1.2B+` `unknown` |
| `lv_employee_band` | enum | `1-9` `10-50` `51-200` `201-500` `501-1000` `1001+` `unknown` |
| `lv_content_type` | enum set | `live_broadcast` `streaming` `near_live` `highlights` `none` `unknown` |
| `lv_produces_content` | tri-state | `true` `false` `unknown` |
| `lv_is_hardware_vendor` | tri-state | `true` `false` `unknown` |
| `lv_is_gambling_operator` | tri-state | `true` `false` `unknown` |
| `lv_sponsorship_reliant` | tri-state | `true` `false` `unknown` |
| contact `seniority`, `persona_group` | enum | per `config/field_policy.yaml` |

### Booleans are tri-state, never two-state

The boolean fields above are the same problem wearing a different type. `normalize_bool` already
returns `None` for unrecognized input, and D-14 forbids writing `false` on absent evidence —
because `lv_produces_content: false` and `lv_is_hardware_vendor: true` are **hard vetoes**. Layer 1
must therefore offer `unknown` as an explicit schema member rather than forcing a binary choice; a
model given only `true`/`false` will pick one. Phase 47 saw exactly this: research returned
`lv_is_gambling_operator: true` for 8 of 17 country racing clubs.

### Invariant

Every deterministic property's allowed set is defined in **one** place, read by the layer-1 schema,
the layer-2 normalizer, the layer-3 classifier, and the tests alike. A test must fail if any two
drift apart. Duplicating an allowed-set literal is how the enum and the scoring map silently
desynchronise.

---

## Implementation notes for Phase 48 planning

Files this touches:
- `config/icp_scoring.yaml` — add `venue: 5` under `base_score.org_type`; add to
  `recommended_motion` mapping as needed.
- `src/icp_scoring.py` — no logic change expected (weights are config-driven), but confirm.
- `src/normalizer.py` — new `normalize_org_type()` + alias table; wire into `normalize_field()`.
- `src/web_research.py` — layer 1 tool-call schema; enum for org type **and** region.
- `scripts/remediate_veto_companies.py` — its local `VALID_ORG_TYPES` / `_classify_org_type`
  should defer to the shared normalizer rather than keeping a second copy, and its inaccurate
  "ENUMERATION property 400s" comment should be corrected.
- `docs/WEB-RESEARCH-SPEC.md` — document `venue`, D-V2's tie-break, and the three layers.
- Tests: taxonomy/config sync assertion, alias-table cases, unmapped → `unknown`, and a case
  asserting a club-operated racecourse resolves to `individual_club_team` per D-V2.

Verification available before committing weights: `scripts/simulate_rubric_weights.py` (built in
Phase 46) scores live records read-only under a candidate config. Run the three venue-shaped
records through it to confirm the Tier C landing predicted above.
